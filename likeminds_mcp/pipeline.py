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


def new_pipeline_session(
    pipeline: dict,
    api_key: str | None,
    tenant: str | None,
    original_inputs: dict,
) -> "PipelineSession":
    """Create and register a new PipelineSession."""
    import time
    sid = str(uuid.uuid4())
    psess = PipelineSession(
        id=sid,
        pipeline_name=pipeline["name"],
        steps=list(pipeline["steps"]),
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
    """Persist pipeline progress to disk. Called after each step and on failure."""
    path = _state_path(psess.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "pipeline_name": psess.pipeline_name,
        "steps": psess.steps,
        "current_step": psess.current_step,
        "failed_step": psess.failed_step,
        "step_result_ids": psess.step_result_ids,
        "step_registered_skills": psess.step_registered_skills,
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
passed to every step. The server runs each skill in sequence and threads outputs
automatically between steps.

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

On `done`: `download_urls` maps each result filename to a presigned download URL.
Render each as a clickable link for the user.\
"""


def _format_pipeline_entry(p: dict) -> str:
    name = p.get("name", "")
    description = p.get("description", "")
    steps = " -> ".join(p.get("steps", []))
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
