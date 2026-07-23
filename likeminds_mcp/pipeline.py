"""Pipeline orchestration: routes user intent to a skill chain and tracks pipeline state.

A pipeline is a named sequence of skills that run one after another, with each step's
output directory threaded into the next step's inputs. The pipeline state is persisted to
disk so a failed pipeline can be resumed from the failed step without re-running earlier ones.

State lifecycle:
  new_pipeline_session() -> PipelineSession (status=running)
  _drive_pipeline (server.py) drives step-by-step, updating status
  save_state() persists after each step completion and on failure
  load_state() / restore_pipeline_session() used on resume
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import config

PIPELINES_FILE = config.PROJECT_ROOT / ".claude" / "pipelines.json"

# pipeline_session_id -> PipelineSession
_PIPELINE_SESSIONS: dict[str, "PipelineSession"] = {}


@dataclass
class PipelineSession:
    id: str                          # pipeline session id (the client's poll handle)
    pipeline_name: str               # e.g. "document-agent"
    steps: list[str]                 # resolved step names; {{generated_skill}} replaced in-place
    current_step: int                # index of the step currently running (or next to run)
    failed_step: int                 # index of the step that failed, or -1
    step_result_ids: dict[str, str]  # str(step_index) → result_id of the completed step
    step_registered_skills: dict[str, list[str]]  # str(step_index) → registered skill names
    original_inputs: dict[str, Any]  # {r2_keys, urls, context} from first call
    api_key: str | None
    tenant: str | None
    step_args: dict[str, dict] = field(default_factory=dict)  # str(step_index) → per-step args, e.g. {"target": "kb"}
    seed_result_id: str | None = None  # existing outputs/mcp bucket staged (read-only) into every step
    seed_writeback: bool = False     # True → the final step writes back INTO seed_result_id in place (refine, e.g. output-feedback); False → the seed is staged read-only and the final step writes a FRESH bucket (generate-from-seed, e.g. document-from-kb / config-from-kb)
    # Continue-in-place: when a run is SEEDED BY A PIPELINE id, it reuses that pipeline's id
    # and folder instead of minting a new one. Its steps keep their own 0-based indices (so
    # threading / writeback / KB-reference are unchanged), but their output folders are shifted
    # by folder_offset so they land AFTER the reused pipeline's existing steps, and save_state
    # persists the CUMULATIVE pipeline (base_state + this run) so pipeline_<id>/state.json is the
    # one growing record. folder_offset == 0 (the default) is an ordinary first-of-its-kind run.
    folder_offset: int = 0
    base_state: dict | None = None
    status: str = "running"          # running | need_input | done | error
    progress: str = ""
    questions: list = field(default_factory=list)
    pending_reply: str = ""
    reply_event: object = None       # asyncio.Event — set when client sends a response
    current_skill_sess: object = None  # the active sessions.Session for the current step
    result: dict | None = None       # final pipeline result (from the last step)
    error: str | None = None
    finished: bool = False
    task: object = None              # asyncio.Task driving the pipeline
    started_at: float = 0.0
    finished_at: float = 0.0


def load_pipelines() -> list[dict]:
    """Load pipeline definitions from .claude/pipelines.json. Returns [] if missing."""
    if not PIPELINES_FILE.is_file():
        return []
    try:
        return json.loads(PIPELINES_FILE.read_text(encoding="utf-8")).get("pipelines", [])
    except Exception:  # noqa: BLE001
        return []


def find_pipeline(name: str) -> Optional[dict]:
    """Look up a pipeline by exact name. Returns the pipeline dict or None."""
    return next((p for p in load_pipelines() if p.get("name") == name), None)


def _step_name(step) -> str:
    """A pipeline step is either a bare skill name (`"kb-builder"`) or an object
    (`{"skill": "diagnose-bug", "args": {"target": "kb"}}`). Return the skill name."""
    return step["skill"] if isinstance(step, dict) else step


def _parse_steps(raw_steps: list) -> tuple[list[str], dict[str, dict]]:
    """Split a pipeline's `steps` into resolved skill names and a per-index args map.

    Keeping `steps` a plain list[str] means the existing {{generated_skill}} resolution and
    in-place step mutation keep working unchanged; any per-step args ride alongside, keyed
    by str(index). A bare-string step contributes no args."""
    names: list[str] = []
    args: dict[str, dict] = {}
    for i, s in enumerate(raw_steps):
        names.append(_step_name(s))
        if isinstance(s, dict) and s.get("args"):
            args[str(i)] = dict(s["args"])
    return names, args


def new_pipeline_session(
    pipeline: dict,
    api_key: str | None,
    tenant: str | None,
    original_inputs: dict,
    seed_result_id: str | None = None,
) -> "PipelineSession":
    """Create and register a new PipelineSession.

    `seed_result_id` (optional) names an existing deliverable bucket under outputs/mcp/
    that the driver stages (read-only) into every step's inputs. Whether the final step
    then writes its output BACK into that same bucket in place is decided by the pipeline's
    own `seed_writeback` flag: refinement pipelines (e.g. output-feedback) set it and mutate
    the seed in place, while generate-from-seed pipelines (e.g. document-from-kb,
    config-from-kb) leave it unset so the seed stays untouched and the deliverable lands in
    a fresh bucket of its own."""
    import time
    sid = str(uuid.uuid4())
    steps, step_args = _parse_steps(pipeline["steps"])
    psess = PipelineSession(
        id=sid,
        pipeline_name=pipeline["name"],
        steps=steps,
        step_args=step_args,
        seed_result_id=seed_result_id,
        seed_writeback=bool(pipeline.get("seed_writeback")),
        current_step=0,
        failed_step=-1,
        step_result_ids={},
        step_registered_skills={},
        original_inputs=original_inputs,
        api_key=api_key,
        tenant=tenant,
        reply_event=asyncio.Event(),
        started_at=time.time(),
    )
    _PIPELINE_SESSIONS[sid] = psess
    return psess


def new_appended_session(
    pipeline_id: str,
    base_state: dict,
    new_pipeline: dict,
    kb_bucket: str | None,
    api_key: str | None,
    tenant: str | None,
    original_inputs: dict,
) -> "PipelineSession":
    """Create a run that CONTINUES an existing pipeline `pipeline_id` in place, rather than
    minting a new top-level pipeline. Used when a seeded run is pointed at a PIPELINE id: the
    caller keeps that one id as their poll handle, and the new deliverable lands inside the
    same `pipeline_<id>/` folder next to the KB it was generated from.

    The new pipeline's steps run as their OWN 0-based sequence (threading, writeback and
    KB-reference logic are all unchanged), but `folder_offset` shifts their output folders to
    start after the reused pipeline's existing steps, so `<NN>_<skill>` indices never collide.
    `kb_bucket` is the reused pipeline's KB, referenced (or, for a writeback pipeline, written
    back) by the appended steps. `base_state` is the reused pipeline's persisted state, kept so
    save_state can persist the cumulative pipeline. This registration REPLACES the finished
    original session under the same id so a poll on `pipeline_id` follows the new run."""
    import time
    steps, step_args = _parse_steps(new_pipeline["steps"])
    psess = PipelineSession(
        id=pipeline_id,
        pipeline_name=new_pipeline["name"],
        steps=steps,
        step_args=step_args,
        seed_result_id=kb_bucket,
        seed_writeback=bool(new_pipeline.get("seed_writeback")),
        folder_offset=len(base_state.get("steps") or []),
        base_state=base_state,
        current_step=0,
        failed_step=-1,
        step_result_ids={},
        step_registered_skills={},
        original_inputs=original_inputs,
        api_key=api_key,
        tenant=tenant,
        reply_event=asyncio.Event(),
        started_at=time.time(),
    )
    _PIPELINE_SESSIONS[pipeline_id] = psess
    return psess


def restore_pipeline_session(
    session_id: str,
    state: dict,
    api_key: str | None,
    tenant: str | None,
    new_inputs: dict,
) -> "PipelineSession":
    """Restore a PipelineSession from persisted state for resume.

    `new_inputs` is whatever the caller passed on the resume call — used to refresh
    files or context if the caller wants to supply additional input on retry.
    Merges with original_inputs stored in state so nothing is lost.
    """
    import time
    stored_inputs = state.get("original_inputs", {})
    merged_inputs = {**stored_inputs}
    # Caller may supply new r2_keys / urls on resume (e.g. a corrected file)
    if new_inputs.get("r2_keys"):
        merged_inputs["r2_keys"] = (merged_inputs.get("r2_keys") or []) + new_inputs["r2_keys"]
    if new_inputs.get("urls"):
        merged_inputs["urls"] = (merged_inputs.get("urls") or []) + new_inputs["urls"]
    if new_inputs.get("context"):
        merged_inputs["context"] = new_inputs["context"]

    psess = PipelineSession(
        id=session_id,
        pipeline_name=state["pipeline_name"],
        steps=state["steps"],
        step_args=state.get("step_args", {}),
        seed_result_id=state.get("seed_result_id"),
        seed_writeback=state.get("seed_writeback", False),
        current_step=state.get("failed_step", 0),  # resume from the failed step
        failed_step=-1,
        step_result_ids=state.get("step_result_ids", {}),
        step_registered_skills=state.get("step_registered_skills", {}),
        original_inputs=merged_inputs,
        api_key=api_key,
        tenant=tenant,
        reply_event=asyncio.Event(),
        started_at=time.time(),
    )
    _PIPELINE_SESSIONS[session_id] = psess
    return psess


def get_pipeline_session(session_id: str) -> Optional["PipelineSession"]:
    return _PIPELINE_SESSIONS.get(session_id)


# --------------------------------------------------------------------------- #
# Disk persistence — resume across process restarts
# --------------------------------------------------------------------------- #

def _state_path(session_id: str) -> Path:
    return config.RESULTS_DIR / f"pipeline_{session_id}" / "state.json"


def save_state(psess: "PipelineSession") -> None:
    """Persist pipeline progress to disk. Called after each step and on failure.

    For a continue-in-place run (folder_offset > 0) the CUMULATIVE pipeline is written —
    the reused pipeline's steps plus this run's, with this run's own 0-based indices mapped
    to their offset positions — so pipeline_<id>/state.json stays the single growing record
    (and _kb_bucket_from_pipeline still finds the KB at index 0)."""
    path = _state_path(psess.id)
    path.parent.mkdir(parents=True, exist_ok=True)

    steps = psess.steps
    step_args = psess.step_args
    step_result_ids = psess.step_result_ids
    step_registered_skills = psess.step_registered_skills
    current_step = psess.current_step
    failed_step = psess.failed_step

    if psess.folder_offset and psess.base_state is not None:
        off = psess.folder_offset
        base = psess.base_state

        def _merge(base_map: dict, own_map: dict) -> dict:
            merged = dict(base_map or {})
            for k, v in (own_map or {}).items():
                merged[str(off + int(k))] = v
            return merged

        steps = list(base.get("steps") or []) + list(psess.steps)
        step_args = _merge(base.get("step_args") or {}, psess.step_args)
        step_result_ids = _merge(base.get("step_result_ids") or {}, psess.step_result_ids)
        step_registered_skills = _merge(
            base.get("step_registered_skills") or {}, psess.step_registered_skills
        )
        current_step = off + psess.current_step
        failed_step = off + psess.failed_step if psess.failed_step >= 0 else -1

    state = {
        "pipeline_name": psess.pipeline_name,
        "steps": steps,
        "step_args": step_args,
        "seed_result_id": psess.seed_result_id,
        "seed_writeback": psess.seed_writeback,
        "current_step": current_step,
        "failed_step": failed_step,
        "step_result_ids": step_result_ids,
        "step_registered_skills": step_registered_skills,
        "original_inputs": {
            k: v for k, v in psess.original_inputs.items()
            if k != "r2_keys"  # don't persist R2 keys — they expire
        },
    }
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_state(session_id: str) -> Optional[dict]:
    """Load persisted pipeline state from disk. Returns None if not found."""
    path = _state_path(session_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# Dynamic docstring builder
# --------------------------------------------------------------------------- #

_PIPELINE_DOC_BODY = """\
Run a multi-step skill pipeline by picking a pipeline name from the list below.

First call: pass `pipeline_name` (e.g. "config-generator") and your files via
`r2_keys` (from get_upload_url) or `urls`. `context` is free-form instructions
passed to every step. For a seed-based pipeline — one that REFINES or BUILDS ON an
earlier run's output rather than starting from uploads (e.g. "output-feedback",
"document-from-kb") — also pass `seed_session_id`: the PIPELINE SESSION ID that the
earlier run reported on completion. That one id is enough — the server recovers the
underlying deliverable bucket (the KB, or any other prior output) from that run's
saved state, stages it into the pipeline, and (for a write-back pipeline) writes the
result back into it in place. The server runs each skill in sequence and threads
outputs automatically between steps.

{pipeline_block}

You get back `status: "running"` with a `session_id`, the current step name, and
step number out of total.

Then POLL: call again with ONLY `session_id` (no other args) until status is
`done` or `error`. On `need_input`, relay the questions to the user verbatim,
wait for their reply, then call again with `session_id` + `response` and resume
polling. Do NOT answer the questions yourself.

On `error`: the response includes `failed_step` and `failed_step_name`. Call
again with the same `session_id` + `pipeline_name` to resume from the failed
step — completed steps are NOT re-run, so only the failed step and anything
after it is retried.

On `done`: `download_urls` maps each result filename to a presigned download URL —
render each as a clickable link for the user. Also give the user the `session_id`
(the pipeline session id) explicitly and relay `how_to_continue`: it is the only id
they need to keep, and the way to refine or reuse this result is another run_pipeline
call that passes this same id as `seed_session_id`. Do not surface any internal bucket
or step ids — they are recovered from the pipeline session id server-side.\
"""


def _format_pipeline_entry(p: dict) -> str:
    name = p.get("name", "")
    description = p.get("description", "")
    steps = " -> ".join(_step_name(s) for s in p.get("steps", []))
    triggers = ", ".join(f'"{t}"' for t in p.get("triggers", []))
    return (
        f"[{name}]\n"
        f"  What it does: {description}\n"
        f"  Steps: {steps}\n"
        f"  Triggers (use any of these phrases in intent): {triggers}"
    )


def build_run_pipeline_doc() -> str:
    """Build the run_pipeline docstring dynamically from pipelines.json.

    Called once at server startup so FastMCP registers the up-to-date description.
    Adding a new pipeline to .claude/pipelines.json + restarting the server is all
    that is needed — no code change required.
    """
    pipelines = load_pipelines()
    if not pipelines:
        pipeline_block = "No pipelines configured. Add entries to .claude/pipelines.json."
    else:
        entries = "\n\n".join(_format_pipeline_entry(p) for p in pipelines)
        pipeline_block = f"Available pipelines:\n\n{entries}"

    return _PIPELINE_DOC_BODY.format(pipeline_block=pipeline_block)
