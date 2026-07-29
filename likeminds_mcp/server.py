"""FastMCP server: the client-facing tools `run_pipeline` and `list_pipelines`.

Execution model — background asyncio task + long-poll (avoids the client's MCP
idle timeout). A pipeline turn can run for minutes, far longer than the client's
~300s idle timeout on a single tool call. The pipeline driver starts a background
task and every call long-polls (waits up to POLL_WAIT seconds for the job state to
change) then returns a snapshot. The client keeps calling with the same
`session_id` until the status is `need_input`, `done`, or `error`.

States: running -> need_input <-> running -> ... -> done | error
  - running     : a turn is executing; keep polling.
  - need_input  : a skill asked; relay the questions, then call again with
                  session_id + response.
  - done        : finished; EVERY produced artifact written to
                  outputs/mcp/<result_id>/ — including a compiled skill and its KB,
                  which are also installed server-side.
  - error       : the run failed.

File input flow (files move by path, resolved against the SERVER's filesystem):
  - `input_paths` — absolute paths; the server copies them into the session inputs
                    dir. This is the path for binaries (PDF/DOCX/images). Resolution
                    is server-side: run on the host they are already valid, and under
                    Docker they are rebased onto the read-only host mount (see
                    config.HOST_MOUNT_SOURCE / _resolve_input_path). A path that
                    resolves to nothing is an error, never a silent skip.
  - `artifacts` / `files` — inline [{name, content}] text, written into the same dir
                    for clients that have no filesystem to point at.

Everything runs on the server's single event loop — the background driver is an
asyncio.Task, not a thread — so there are no cross-loop objects and nothing is
parked alive while a human is answering.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP

from . import config, engine, pipeline, registry, sessions

# Load .env when this module is imported directly. The `python -m likeminds_mcp`
# entrypoint also loads it before importing config, so the computed constants
# in config.py resolve from the environment regardless of how the server is started.
load_dotenv()


def _configure_auth() -> None:
    """Prepare the server's OWN fallback credential for the spawned CLI — used on any
    turn where the caller sent no BYOK header key. The effective per-request order is:

        1. the caller's header key    (applied per turn by engine._child_env)
        2. a server ANTHROPIC_API_KEY  (from .env)
        3. the Claude subscription     (CLAUDE_TOKEN -> CLAUDE_CODE_OAUTH_TOKEN)

    Steps 2 vs 3 are settled here once at startup: if a server ANTHROPIC_API_KEY is
    present it becomes the fallback and the subscription token is dropped (the API key
    would outrank it anyway); otherwise the subscription token is mapped into the var
    the CLI reads. Either way we strip Foundry/gateway creds that would outrank an API
    key, so the order above is exactly what the CLI sees."""
    for var in (
        "CLAUDE_CODE_USE_FOUNDRY",
        "ANTHROPIC_FOUNDRY_API_KEY",
        "ANTHROPIC_FOUNDRY_BASE_URL",
        "ANTHROPIC_AUTH_TOKEN",
    ):
        os.environ.pop(var, None)
    if os.environ.get("ANTHROPIC_API_KEY"):
        os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
        os.environ.pop("CLAUDE_TOKEN", None)
        return
    token = os.environ.get("CLAUDE_TOKEN") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if token:
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = token


_configure_auth()

# Stateless transport: don't issue or track an Mcp-Session-Id. A restarted server —
# or an `mcp-remote` proxy still holding a session id from a previous server run —
# then can NOT fail with "Session not found" (HTTP 404); every request is
# self-contained. Safe here because run_pipeline's pause/resume polling keys off an
# APPLICATION-level session_id (returned in the tool result, passed back as an
# argument, looked up in the in-process SESSIONS dict) — wholly independent of the
# transport session. json_response also drops the long-lived SSE stream (whose drops
# were the original point of failure) in favour of a plain JSON reply per POST.
#
# The server is UNAUTHENTICATED: it runs on the operator's own machine, bound to
# loopback by default, and every skill it can run is already on that disk. There is no
# login, no identity, and no per-caller scoping — reaching the port IS the authorization.
# Bind it to 0.0.0.0 only behind something that does the access control for you.
mcp = FastMCP(
    "likeminds",
    host=config.HOST,
    port=config.PORT,
    stateless_http=True,
    json_response=True,
)

# How long a single poll call waits for the job state to change before
# returning "running". Short, so each call returns promptly with fresh progress.
POLL_WAIT = 4

# The artifacts are the point of the run, so the done snapshot has to hand them over
# rather than describe them. The server runs on the user's own machine, so every file
# is already sitting on their disk under `output_dir` — the job is to say exactly where,
# and to put a copy wherever they actually want it. EVERY entry counts — a compiled
# skill, its assets, and each KB file are all artifacts the user is entitled to, not
# internals.
DELIVERY_TEXT = (
    "The artifacts are ready on this machine — deliver them, don't just mention them. They "
    "are in the directory given by `output_dir`, one file per entry in `summary.files`. "
    "List EVERY file, without exception, with its full path so the user can open it; when "
    "there are many, group them under short headings (deliverable / skill / knowledge base) "
    "but do not drop, sample, or summarise any of them away. If the user asked for the "
    "output somewhere specific — or you are working in their project directory — copy the "
    "files there as well and tell them the new paths. Never replace an artifact with a "
    "summary of it, and never leave the user to go hunting for where it landed."
)

PIPELINE_RELAY_TEXT = (
    "Show these question(s) to the user verbatim and wait for their reply. They may answer, or "
    "reply 'done' to stop and finish with whatever is complete. Then call run_pipeline again with "
    "ONLY this session_id and their `response` — do NOT pass pipeline_name (that would restart the "
    "pipeline instead of delivering the answer). To attach a file with the answer: pass its "
    "absolute local path in `input_paths` on the same run_pipeline call. Do NOT answer the "
    "question yourself."
)
PIPELINE_POLL_TEXT = (
    "Still working. Tell the user the current `progress`, then call run_pipeline again with ONLY "
    "this session_id (no other arguments) to keep polling. This is normal long-running progress, "
    "not an error. Repeat until status is 'need_input' or 'done'."
)


# ----------------------------------------------------------------------------- #
# Output harvesting + deliverable promotion
# ----------------------------------------------------------------------------- #

def _harvest(output_dir: Path, sandbox: Path) -> list[tuple[str, bytes]]:
    """Collect the deliverable from the sandbox as raw bytes (so binary outputs like
    PDF/DOCX/XLSX survive intact). Reads from output_dir (sess.output_dir) first;
    falls back to sandbox/work/ if output_dir is empty."""
    if output_dir.is_dir():
        files = [p for p in sorted(output_dir.rglob("*")) if p.is_file()]
        if files:
            return [(str(p.relative_to(output_dir)), p.read_bytes()) for p in files]
    work = sandbox / "work"
    if work.is_dir():
        files = [p for p in sorted(work.rglob("*")) if p.is_file()]
        if files:
            return [(str(p.relative_to(work)), p.read_bytes()) for p in files]
    return []


def _promote(result_id: str, harvested: list[tuple[str, bytes]]) -> list[str]:
    """Write the harvested (name, bytes) files to outputs/mcp/<result_id>/ — the stable,
    caller-addressable bucket. Continuing a session writes back to the SAME bucket (the
    result_id is stable across a durable session), so the deliverable accumulates under
    one id the user can save and reuse."""
    dest = config.RESULTS_DIR / result_id
    dest.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for name, content in harvested:
        out = dest / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(content)
        written.append(name)
    return written


def _register_skills(harvested: list[tuple[str, bytes]]) -> list[str]:
    """Auto-register any generated skills found in the harvested output.

    A generated skill is a directory containing a SKILL.md. Two shapes are handled:
      - nested: `<skill-name>/SKILL.md` (+ any sibling asset files under that folder) —
                the skill name is the folder name.
      - root:   a `SKILL.md` at the harvest root means the WHOLE harvest is one skill;
                the name comes from its frontmatter `name:` field.
    Each skill's FULL folder (SKILL.md plus all its assets, at any depth) is copied into
    .claude/skills/<name>/, next to the built-ins, and the folder is gitignored. The
    copied SKILL.md's `name:` frontmatter is rewritten to match its folder so the spawned
    CLI resolves it by that exact name.

    There is one user — the operator running this server — so a registered skill is
    simply installed, with no owner suffix and no visibility filter. Registration
    installs a COPY and never consumes the harvest, so what the run produced is still
    delivered in the output bucket either way."""
    roots: dict[str, str] = {}   # path-prefix under the harvest -> skill name
    for rel, content in harvested:
        if Path(rel).name != "SKILL.md":
            continue
        parent = Path(rel).parent
        if str(parent) == ".":
            name = registry.frontmatter_field(content.decode("utf-8", "replace"), "name")
            prefix = ""
        else:
            name = parent.name
            prefix = str(parent) + "/"
        name = Path((name or "").strip()).name  # sanitize: no path separators / traversal
        if name:
            roots[prefix] = name

    registered: list[str] = []
    for prefix, clean in roots.items():
        dest_root = config.SKILLS_DIR / clean
        for rel, content in harvested:
            if not rel.startswith(prefix):
                continue
            sub = rel[len(prefix):]
            out = dest_root / sub
            out.parent.mkdir(parents=True, exist_ok=True)
            if sub == "SKILL.md":  # the skill's own manifest: keep `name:` == folder name
                content = registry.rewrite_frontmatter_name(
                    content.decode("utf-8", "replace"), clean
                ).encode("utf-8")
            out.write_bytes(content)
        registered.append(clean)
        _gitignore_generated_skill(clean)
    return registered


def _gitignore_generated_skill(skill_name: str) -> None:
    """Append the generated skill directory to .gitignore if not already present."""
    gitignore = config.PROJECT_ROOT / ".gitignore"
    entry = f".claude/skills/{skill_name}/"
    try:
        existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
        if entry not in existing:
            with gitignore.open("a", encoding="utf-8") as f:
                f.write(f"\n# generated skill (auto-registered by likeminds-mcp)\n{entry}\n")
    except Exception:  # noqa: BLE001 — gitignore update is best-effort
        pass


# ----------------------------------------------------------------------------- #
# Background driver (resume-per-turn loop)
# ----------------------------------------------------------------------------- #

async def _drive(sess: sessions.Session, first_message: str) -> None:
    """Drive the whole skill lifecycle as a background task on the server's event
    loop. Turn 1 seeds the skill; every later turn resumes. Bounded by a per-turn
    timeout and a reply timeout so a hung or abandoned session can't leak a
    subprocess/task/sandbox. Updates sess.* as it goes; the tool handlers only ever
    read that state to answer polls."""
    try:
        sess.reply_event = asyncio.Event()
        message, resume = first_message, False
        while True:
            sess.status = "running"
            try:
                signal = await asyncio.wait_for(
                    engine.run_turn(sess, message, resume=resume),
                    timeout=config.TURN_TIMEOUT,
                )
            except asyncio.TimeoutError:
                # run_turn's finally kills the subprocess as it is cancelled.
                sess.status = "error"
                sess.error = f"Turn exceeded {config.TURN_TIMEOUT}s and was aborted."
                sessions.purge(sess)
                return
            resume = True  # every turn after the first resumes the same session

            if signal is None:
                # Turn ended with no signal marker — nudge and resume, up to the cap.
                if sess.nudges < engine.MAX_CONTINUES:
                    sess.nudges += 1
                    sess.progress = "Nudging to continue…"
                    message = engine.NUDGE
                    continue
                sess.status = "error"
                sess.error = "Skill ended without a signal marker after repeated nudges."
                sessions.purge(sess)
                return

            if signal["kind"] == "ask":
                sess.questions = signal["questions"]
                sess.status = "need_input"
                # Nothing runs while we wait for the human — no parked subprocess. A
                # reply timeout stops an abandoned session from leaking forever.
                try:
                    await asyncio.wait_for(sess.reply_event.wait(), timeout=config.REPLY_TIMEOUT)
                except asyncio.TimeoutError:
                    sess.status = "error"
                    sess.error = f"No reply within {config.REPLY_TIMEOUT}s; session closed."
                    sessions.purge(sess)
                    return
                sess.reply_event.clear()
                message = sess.pending_reply
                sess.progress = "Reading your answer…"
                continue

            # emit: harvest the deliverable, promote it locally, register any generated
            # skills, then purge. Promoted to outputs/mcp/<result_id>/, which survives the
            # purge so the session can be continued later under the same session_id.
            harvested = _harvest(sess.output_dir, sess.sandbox)
            names = _promote(sess.result_id, harvested)

            # Auto-register any generated skills. No skill shipped in this repo emits one
            # today — document-generator and find-bugs both read their KB at run time now —
            # so this path is currently unexercised, but it stays for caller-authored skills.
            # Registration installs a COPY under .claude/skills; it does not consume the
            # harvest. Everything the run produced — a compiled SKILL.md, its assets, a KB,
            # a document — stays in the promoted bucket too, because a registered skill the
            # user cannot inspect or keep a copy of is a black box.
            registered = _register_skills(harvested)
            sessions.purge(sess)
            sess.result = {
                "result_id": sess.result_id,
                "output_dir": str(config.RESULTS_DIR / sess.result_id),
                "summary": {"files": names},
                **({"registered_skills": registered} if registered else {}),
            }
            sess.status = "done"
            return
    except asyncio.CancelledError:
        sessions.purge(sess)  # server shutdown / cancellation — clean up, then propagate
        raise
    except Exception as e:  # noqa: BLE001 — surface as a job error, never crash the loop
        sess.status = "error"
        sess.error = f"{type(e).__name__}: {e}"
        sessions.purge(sess)  # cleanup on the error path too
    finally:
        sess.finished = True
        sess.finished_at = time.time()


def _deliver_reply(sess: sessions.Session, msg: str) -> None:
    """Hand a reply to the background driver and wake it (same loop, no threads)."""
    sess.pending_reply = msg
    sess.status = "running"
    if sess.reply_event is not None:
        sess.reply_event.set()


# ----------------------------------------------------------------------------- #
# Inputs plumbing
# ----------------------------------------------------------------------------- #

class InputPathError(RuntimeError):
    """One or more `input_paths` could not be resolved on the server's filesystem.

    Raised rather than skipping the path, because a skipped input is INVISIBLE: the step
    starts with an empty inputs dir, and the skill spends a whole turn asking the caller
    for files the caller believes it already sent. Failing at the point of staging turns
    that into an immediate, actionable error."""


def _resolve_input_path(raw: str) -> Optional[Path]:
    """Map one caller-supplied path onto something that exists on THIS filesystem.

    Two tries: the path exactly as given (a server running on the host, where the
    caller's paths are already valid), then the same path rebased onto the read-only
    host mount (a server in Docker, where they are not). Returns None when neither
    lands, which the caller turns into a loud error rather than a silent skip.

    Nothing is guessed. A path that resolves to a real file is used; anything else is
    reported with the path the caller actually gave, so the fix is obvious."""
    p = Path(raw).expanduser()
    if p.exists():
        return p

    # BOTH halves are required: an empty target would make the join below a RELATIVE
    # path, which .exists() would then resolve against the process cwd (/app) and could
    # match an unrelated file. Absent either, there is no mount to rebase onto.
    if config.HOST_MOUNT_SOURCE and config.HOST_MOUNT_TARGET:
        try:
            rel = p.relative_to(config.HOST_MOUNT_SOURCE)
        except ValueError:
            return None
        mapped = Path(config.HOST_MOUNT_TARGET) / rel
        if mapped.exists():
            return mapped
    return None


def _missing_paths_help(missing: list[str]) -> str:
    """The message a caller sees when input_paths don't resolve. It has to say what to
    DO — the same text reaches the model driving the pipeline, which can then fix the
    call itself instead of relaying a bare 'file not found' to the user."""
    listed = "\n".join(f"  - {m}" for m in missing)
    msg = (
        f"{len(missing)} input_path(s) could not be found on the server's filesystem:\n"
        f"{listed}\n\n"
    )
    if config.IN_CONTAINER and config.HOST_MOUNT_SOURCE and config.HOST_MOUNT_TARGET:
        msg += (
            f"This server runs in Docker. Host paths under {config.HOST_MOUNT_SOURCE} are "
            f"readable (mounted read-only at {config.HOST_MOUNT_TARGET}); anything outside it "
            "is invisible to the container, as is a path that simply does not exist.\n"
            "Check the path is correct, or widen LIKEMINDS_HOST_MOUNT to a directory that "
            "contains it and restart the server (see docker-compose.yml)."
        )
    elif config.IN_CONTAINER:
        msg += (
            "This server runs in Docker and resolves input_paths inside the CONTAINER, so a "
            "host path (/Users/…, /home/…, C:\\…) is not visible to it. No host directory is "
            "currently mounted: set LIKEMINDS_HOST_MOUNT to the host directory holding these "
            "files and restart the server (see docker-compose.yml)."
        )
    else:
        msg += "Check that each path is absolute, exists, and is readable by the server process."
    return msg


def _copy_input_paths(inputs_dir: Path, paths: list | None) -> list[str]:
    """Copy local files (incl. binaries) into a step's inputs dir. A directory is copied
    whole, keeping its layout, so a caller can hand over a folder of artifacts in one
    argument. Returns the names staged.

    Raises InputPathError listing every path that could not be resolved (see
    _resolve_input_path for how a host path is mapped onto container storage). Every path
    is resolved BEFORE anything is copied, so one bad entry cannot leave the inputs dir
    half-staged — on the reply path the session stays open and the caller retries the
    whole call, which would otherwise stack a partial copy on top of a partial copy."""
    resolved: list[Path] = []
    missing: list[str] = []
    for p in paths or []:
        src = _resolve_input_path(str(p))
        if src is None:
            missing.append(str(p))
        else:
            resolved.append(src)
    if missing:
        raise InputPathError(_missing_paths_help(missing))

    copied: list[str] = []
    for src in resolved:
        if src.is_file():
            shutil.copy2(src, inputs_dir / src.name)
            copied.append(src.name)
        elif src.is_dir():
            shutil.copytree(src, inputs_dir / src.name, dirs_exist_ok=True)
            copied.append(src.name + "/")
    return copied


# ----------------------------------------------------------------------------- #
# Per-request BYOK — the caller's Anthropic key, read fresh from the request header
# ----------------------------------------------------------------------------- #

def _client_api_key(ctx: Optional[Context]) -> Optional[str]:
    """The caller's Anthropic key from the request header (BYOK), or None.

    Read fresh from the live HTTP request on every call — never stored. Under the
    streamable-HTTP transport `ctx.request_context.request` is the Starlette request;
    under stdio (or if the context is unavailable) there is no request, so this
    returns None and the server falls back to its own .env creds. Read ONLY from
    config.API_KEY_HEADER (default `x-api-key`); a `Bearer ` prefix on that header's
    value is tolerated."""
    if ctx is None:
        return None
    try:
        request = ctx.request_context.request
        val = request.headers.get(config.API_KEY_HEADER) if request is not None else None
    except Exception:  # noqa: BLE001 — no request context (e.g. stdio) => no client key
        return None
    val = (val or "").strip()
    if val.lower().startswith("bearer "):
        val = val[len("bearer "):].strip()
    return val or None


# ----------------------------------------------------------------------------- #
# Pipeline orchestration — multi-step skill chains
# ----------------------------------------------------------------------------- #

def _kb_bucket_from_pipeline(pipeline_session_id: str) -> Optional[str]:
    """Given a PIPELINE session id, return the bucket id of the knowledge base that run produced
    (or used), read from that pipeline's persisted state.json. This is what lets the user hold ONE
    id — the pipeline session id — and still seed a continuation: the individual step buckets are
    recorded in state, so the KB the run built is recoverable from the pipeline id alone.

    The KB is the reusable artifact a seed-based pipeline consumes, so we resolve to it specifically
    (seeding every step bucket would drag the generated document into the KB inputs). Preference:
    the kb-builder step's output; then the KB a seeded pipeline carried in; then the last step's
    output as a last resort."""
    state = pipeline.load_state(pipeline_session_id)
    if not state:
        return None
    steps = state.get("steps") or []
    step_result_ids = state.get("step_result_ids") or {}

    def _live(rid: Optional[str]) -> Optional[str]:
        return rid if rid and (config.RESULTS_DIR / rid).is_dir() else None

    for i, name in enumerate(steps):  # the KB is produced by the kb-builder step, by convention
        if name == "kb-builder" and _live(step_result_ids.get(str(i))):
            return step_result_ids[str(i)]
    if _live(state.get("seed_result_id")):  # a seeded pipeline (e.g. document-from-kb) carried the KB in
        return state["seed_result_id"]
    if steps and _live(step_result_ids.get(str(len(steps) - 1))):
        return step_result_ids[str(len(steps) - 1)]
    return None


def _resolve_seed_buckets(seed_session_id: Optional[str]) -> list[str]:
    """Resolve a caller-supplied id to existing deliverable bucket NAME(s) under outputs/mcp/ —
    SKILL-AGNOSTIC, so the seed can be a KB today, a generated skill or any other prior deliverable
    tomorrow. Resolution order (most-specific first):
      1. a PIPELINE session id (the handle a finished run reports), bare or `pipeline_`-prefixed →
         the reusable bucket (the KB) recorded in that pipeline's state.json. Resolved FIRST, and
         it maps to the KB STEP's own subfolder (`pipeline_<pid>/<NN>_kb-builder`), NEVER to the
         `pipeline_<pid>` ROOT — the root also holds state.json and every other step's output, so
         staging it would drag the whole run (and any generated document) into the next step.
      2. an id/path that already names an existing bucket → [that] — covers a nested step path
         (`pipeline_<pid>/<NN>_<skill>`) and a standalone `<skill>_<sid>` bucket.
      3. a bare durable id `<sid>` → every standalone `<skill>_<sid>` bucket (usually exactly one).
    `pipeline_*` folders are excluded from rule 3's scan: a pipeline id is handled by rule 1, and a
    `pipeline_<pid>` state root ends with `_<pid>` so it would otherwise false-match a bare id.
    Empty list means nothing matched; more than one (only possible at rule 3) means the bare id is
    ambiguous and the caller must pass the full result_id."""
    if not seed_session_id or not seed_session_id.strip():
        return []
    sid = seed_session_id.strip()

    # 1. Pipeline session id → the KB bucket named in its state. A pipeline_<pid> folder always
    # carries a state.json, and its presence is exactly what marks sid as a pipeline id (vs a
    # plain bucket); resolve to the KB step's subfolder, never the pipeline root.
    bare = sid[len("pipeline_"):] if sid.startswith("pipeline_") else sid
    if pipeline.load_state(bare) is not None:
        kb = _kb_bucket_from_pipeline(bare)
        return [kb] if kb else []

    # 2. An id/path that is itself an existing bucket (a nested step path, or a standalone bucket).
    if (config.RESULTS_DIR / sid).is_dir():
        return [sid]

    # 3. A bare durable id → standalone <skill>_<sid> bucket(s); never a pipeline_* state root.
    if config.RESULTS_DIR.is_dir():
        direct = sorted(
            d.name for d in config.RESULTS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith("pipeline_")
            and d.name.endswith(f"_{sid}")
        )
        if direct:
            return direct

    return []


def _seed_pipeline_id(seed_session_id: Optional[str]) -> Optional[str]:
    """If `seed_session_id` names an existing PIPELINE (its state.json exists), return that
    pipeline's bare id — the signal to CONTINUE it in place (reuse its id + folder) rather than
    mint a new pipeline. Returns None for a raw bucket seed or nothing, i.e. a normal new run.
    Accepts the id bare or `pipeline_`-prefixed, mirroring _resolve_seed_buckets rule 1."""
    if not seed_session_id or not seed_session_id.strip():
        return None
    bare = seed_session_id.strip()
    bare = bare[len("pipeline_"):] if bare.startswith("pipeline_") else bare
    return bare if pipeline.load_state(bare) is not None else None


def _stage_bucket(src_dir: Path, dest_dir: Path) -> None:
    """Copy every file under an outputs/mcp bucket into a step's inputs dir, preserving
    relative paths — used to seed an existing deliverable (e.g. a KB) into a pipeline step."""
    if not src_dir.is_dir():
        return
    for src in sorted(src_dir.rglob("*")):
        if src.is_file():
            dest = dest_dir / src.relative_to(src_dir)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def _apply_step_args(context: Optional[str], args: Optional[dict]) -> Optional[str]:
    """Fold a pipeline step's declared args into the caller context as explicit key=value
    run parameters, so a skill receives them the same way pipeline args would arrive."""
    if not args:
        return context
    directive = "Run parameters: " + ", ".join(f"{k}={v}" for k, v in args.items())
    return f"{directive}\n\n{context}" if context else directive


def _kb_reference_for_step(
    psess: pipeline.PipelineSession, i: int
) -> tuple[Optional[str], bool, bool]:
    """Decide how step `i` receives the upstream KB. Returns
    (reference_kb, stage_prior, stage_seed):

      - reference_kb — the CANONICAL outputs/mcp path to hand the skill as `kb=` and read
        in place (never copied), or None to fall back to staging.
      - stage_prior  — whether to copy the PRIOR step's output bucket into this step's inputs.
      - stage_seed   — whether to copy the SEED bucket into this step's inputs.

    The KB is passed by reference (no copy) for every NON-writeback pipeline, because the KB
    it reads is always either the seed or a kb-builder step's output, and those consumers
    (document-generator, config-agent, diagnose-bug) all accept a kb=<dir> at any path. The
    WRITEBACK pipeline (apply-fixes) is the exception: it reads the KB from inputs= and mirrors
    the changed files into output= for the harness to merge back, so it MUST get the KB staged.
    A prior non-KB output (e.g. diagnose-bug's approval sheet) is always staged as before."""
    stage_prior = i > 0
    stage_seed = bool(psess.seed_result_id)
    reference_kb: Optional[str] = None
    if not psess.seed_writeback:
        if psess.seed_result_id:  # seeded generation (document-from-kb / config-from-kb)
            reference_kb = str(config.RESULTS_DIR / psess.seed_result_id)
            stage_seed = False
        elif i > 0 and psess.steps[i - 1] == "kb-builder":  # build-then-generate (document-agent…)
            prior_rid = psess.step_result_ids.get(str(i - 1), "")
            if prior_rid:
                reference_kb = str(config.RESULTS_DIR / prior_rid)
                stage_prior = False
    return reference_kb, stage_prior, stage_seed


async def _drive_pipeline(
    psess: pipeline.PipelineSession,
    input_paths: Optional[list],
    artifacts: Optional[list],
    urls: Optional[list],
    context: Optional[str],
) -> None:
    """Drive a pipeline step-by-step as a background task.

    Each step is a regular skill run (_drive task). After each step's _drive task
    finishes, the promoted output dir is threaded into the next step's inputs_dir.
    Dynamic steps ({{generated_skill}}) are resolved from the prior step's
    registered_skills. If any step goes need_input, the pipeline surfaces it to the
    client and waits for a reply before forwarding it to the skill session.
    """
    import time as _time

    try:
        psess.reply_event = asyncio.Event()

        for i in range(psess.current_step, len(psess.steps)):
            step_name = psess.steps[i]

            # Resolve dynamic step name from prior step's registered skills
            if step_name == "{{generated_skill}}":
                prior_registered = psess.step_registered_skills.get(str(i - 1), [])
                if not prior_registered:
                    raise RuntimeError(
                        f"Step {i} is {{{{generated_skill}}}} but step {i - 1} "
                        "registered no skill — cannot resolve the step name."
                    )
                step_name = prior_registered[0]
                psess.steps[i] = step_name  # resolve in place for state persistence

            psess.progress = f"Step {i + 1}/{len(psess.steps)}: {step_name}"

            entry = registry.resolve_skill(step_name)
            if entry is None:
                raise RuntimeError(
                    f"Step {i + 1} skill '{step_name}' not found. "
                    f"Available: {', '.join(s['name'] for s in registry.list_skills())}"
                )

            # Create a session for this step. WRITEBACK (the final step promotes INTO the
            # seed bucket in place) happens only for a pipeline that opted in via
            # seed_writeback — a refinement flow like output-feedback, which mutates the seed
            # and persists it under the seed's own session id. A seeded but non-writeback
            # pipeline (document-from-kb, config-from-kb) stages the seed read-only and writes
            # a fresh bucket, leaving the seed untouched.
            is_writeback = (
                bool(psess.seed_result_id) and psess.seed_writeback and i == len(psess.steps) - 1
            )
            # Every non-writeback step lands in its OWN subfolder INSIDE this pipeline's
            # folder — outputs/mcp/pipeline_<pid>/<NN>_<skill>/ — so one pipeline session's
            # entire footprint (state.json plus every step's deliverable) lives under a single
            # pipeline_<pid> root. The <NN> step-index prefix keeps the steps ordered and
            # unique even if a skill repeats, and makes a resumed step overwrite its own folder
            # in place rather than fork a new one. A writeback step is the sole exception: it
            # promotes back into the SEED's own bucket (a KB from an earlier pipeline), refining
            # it where it already lives. (result_id may contain a slash — both the sandbox
            # output dir and the outputs/mcp bucket simply nest.)
            step_result_id = (
                psess.seed_result_id if is_writeback
                else f"pipeline_{psess.id}/{psess.folder_offset + i:02d}_{entry['name']}"
            )
            sess = sessions.new_session(entry["name"], result_id=step_result_id)
            sess.api_key = psess.api_key
            psess.current_skill_sess = sess

            # Decide whether the upstream KB is REFERENCED (kb=<canonical path>, read in
            # place) or STAGED (copied into inputs). Non-writeback pipelines reference it and
            # never duplicate it; the writeback pipeline still stages it (apply-fixes needs it
            # in inputs= to mirror changed files back). A prior NON-KB output is staged either
            # way.
            reference_kb, stage_prior, stage_seed = _kb_reference_for_step(psess, i)

            # Write inputs. Step 0 gets the caller's own files (into inputs/, or into
            # inputs/generated/ in a seeded pipeline so the artifact under critique stays
            # separate). A later step gets the prior step's output copied in UNLESS that output
            # is the KB we chose to pass by reference. The seed is copied in only when it is
            # NOT being referenced (i.e. the writeback pipeline).
            if i == 0:
                if input_paths or artifacts:
                    dest = sess.inputs_dir / "generated" if psess.seed_result_id else sess.inputs_dir
                    dest.mkdir(parents=True, exist_ok=True)
                    _copy_input_paths(dest, input_paths)
                    engine._write_artifacts(dest, artifacts)
            elif stage_prior:
                prior_result_id = psess.step_result_ids.get(str(i - 1), "")
                _stage_bucket(config.RESULTS_DIR / prior_result_id, sess.inputs_dir)

            if stage_seed:
                _stage_bucket(config.RESULTS_DIR / psess.seed_result_id, sess.inputs_dir)

            # Build the first message — pass context on every step so the skill knows the end
            # goal, with this step's declared args (e.g. target=kb) folded in, and the KB by
            # reference (kb=<canonical path>) when we chose not to copy it. URLs only on step 0.
            step_urls = urls if i == 0 else None
            step_context = _apply_step_args(context, psess.step_args.get(str(i)))
            first_msg = engine.build_first_message(
                entry["folder"], sess, step_urls, step_context, kb_path=reference_kb
            )

            # Start the step driver
            sess.task = asyncio.create_task(_drive(sess, first_msg))
            pipeline.save_state(psess)

            # Monitor the step until it finishes, surfacing need_input to the client
            while not sess.finished:
                psess.progress = (
                    f"Step {i + 1}/{len(psess.steps)}: {step_name} — {sess.progress}"
                )

                if sess.status == "need_input" and psess.status != "need_input":
                    psess.questions = sess.questions
                    psess.status = "need_input"
                    # Wait for the pipeline client to answer
                    try:
                        await asyncio.wait_for(
                            psess.reply_event.wait(), timeout=config.REPLY_TIMEOUT
                        )
                    except asyncio.TimeoutError:
                        sess.task.cancel()
                        raise RuntimeError(
                            f"No reply within {config.REPLY_TIMEOUT}s; pipeline closed."
                        )
                    psess.reply_event.clear()
                    psess.status = "running"
                    # Forward the reply to the skill session so _drive resumes
                    _deliver_reply(sess, engine.build_reply_message(psess.pending_reply, []))

                await asyncio.sleep(0.5)

            if sess.status == "error":
                psess.failed_step = i
                pipeline.save_state(psess)
                raise RuntimeError(
                    f"Step {i + 1}/{len(psess.steps)} ({step_name}) failed: {sess.error}"
                )

            # Step done — record result_id and registered skills for next step
            psess.step_result_ids[str(i)] = sess.result_id
            psess.step_registered_skills[str(i)] = (sess.result or {}).get(
                "registered_skills", []
            )
            psess.current_step = i + 1
            pipeline.save_state(psess)

        # All steps done — expose last step's result as the pipeline result
        last = psess.current_skill_sess
        psess.result = (last.result or {}) if last else {}
        psess.status = "done"

    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        psess.status = "error"
        psess.error = f"{type(e).__name__}: {e}"
        pipeline.save_state(psess)
    finally:
        psess.finished = True
        psess.finished_at = _time.time()


async def _wait_for_change_pipeline(
    psess: pipeline.PipelineSession, seconds: int = POLL_WAIT
) -> None:
    """Long-poll for a pipeline session: wait until status leaves 'running'."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while psess.status == "running" and loop.time() < deadline:
        await asyncio.sleep(0.5)


def _seed_pipeline_names() -> list[str]:
    """Names of the seed-based (requires_seed) pipelines — the ones a finished run can be
    continued INTO. Read live from pipelines.json so this never drifts from the config."""
    return [p.get("name", "") for p in pipeline.load_pipelines() if p.get("requires_seed")]


def _pipeline_continue_text(psess: pipeline.PipelineSession) -> str:
    """Instruction for the model to hand the user a clean session id and the exact, correct way to
    continue. The pipeline session id is the ONLY handle the user keeps — every underlying bucket
    (the KB and each step's output) is recorded in the run's state.json and recovered from that id
    server-side, so no other id is ever exposed. Continuation is ALWAYS via run_pipeline;
    to build on a finished run, pass this same session id as `seed_session_id`
    (NOT session_id — that only resumes an unfinished run of THIS pipeline)."""
    seed_pipelines = _seed_pipeline_names()
    seed_list = ", ".join(f"'{n}'" for n in seed_pipelines) or "the seed-based pipelines"
    return (
        f"This pipeline is finished. Give the user its session id explicitly: {psess.id}. That is "
        f"the ONLY id they need to keep — the knowledge base and every step output are recoverable "
        f"from it server-side. To build on this result, call run_pipeline again with a "
        f"seed-based pipeline ({seed_list}; call list_pipelines to see what each does) and pass THIS session id as "
        f"for what each does) and pass THIS session id as `seed_session_id` — not session_id. The "
        f"server resolves it to the knowledge base behind this run. Use session_id only to resume "
        f"this pipeline while it is unfinished."
    )


def _pipeline_snapshot(psess: pipeline.PipelineSession) -> dict:
    """Serialise a PipelineSession into the response dict the client receives."""
    if psess.status == "need_input":
        return {
            "status": "need_input",
            "session_id": psess.id,
            "pipeline": psess.pipeline_name,
            "current_step": psess.current_step + 1,
            "total_steps": len(psess.steps),
            "step_name": psess.steps[psess.current_step] if psess.current_step < len(psess.steps) else "",
            "questions": psess.questions,
            "next_step": PIPELINE_RELAY_TEXT,
        }
    if psess.status == "done":
        result = psess.result or {}
        return {
            "status": "done",
            "pipeline": psess.pipeline_name,
            "steps_completed": len(psess.steps),
            **result,
            # The pipeline session id is the one handle the user keeps; it comes AFTER **result so a
            # step's own result dict can never shadow it. No step/bucket ids are exposed — they are
            # recovered from this id server-side when a continuation seeds from it.
            "session_id": psess.id,
            "how_to_continue": _pipeline_continue_text(psess),
            "next_step": (
                "Pipeline complete. " + DELIVERY_TEXT
                + " Then give the user the pipeline session_id and relay how_to_continue so they "
                "know how to refine or reuse this result — all continuation is via run_pipeline."
            ),
        }
    if psess.status == "error":
        failed = psess.failed_step
        resume_hint = (
            f" Call run_pipeline again with session_id='{psess.id}' and intent to resume "
            f"from step {failed + 1} ({psess.steps[failed] if failed >= 0 and failed < len(psess.steps) else '?'}) "
            "without re-running earlier steps."
            if failed >= 0 else ""
        )
        return {
            "status": "error",
            "session_id": psess.id,
            "pipeline": psess.pipeline_name,
            "failed_step": failed + 1 if failed >= 0 else None,
            "failed_step_name": psess.steps[failed] if 0 <= failed < len(psess.steps) else None,
            "steps_completed": failed if failed >= 0 else psess.current_step,
            "message": (psess.error or "unknown error") + resume_hint,
        }
    # running
    return {
        "status": "running",
        "session_id": psess.id,
        "pipeline": psess.pipeline_name,
        "current_step": psess.current_step + 1,
        "total_steps": len(psess.steps),
        "step_name": psess.steps[psess.current_step] if psess.current_step < len(psess.steps) else "",
        "progress": psess.progress or "starting…",
        "next_step": PIPELINE_POLL_TEXT,
    }


async def run_pipeline(
    pipeline_name: Optional[str] = None,
    context: Optional[str] = None,
    input_paths: Optional[list] = None,
    artifacts: Optional[list] = None,
    urls: Optional[list] = None,
    seed_session_id: Optional[str] = None,
    session_id: Optional[str] = None,
    response: Optional[str] = None,
    ctx: Optional[Context] = None,
) -> dict:
    client_key = _client_api_key(ctx)

    # POLL or ANSWER on an existing pipeline session
    if session_id and not pipeline_name:
        psess = pipeline.get_pipeline_session(session_id)
        if psess is None:
            # Not in memory — check disk for a resumable failed state
            state = pipeline.load_state(session_id)
            if state is None:
                return {"status": "error", "message": f"Pipeline session '{session_id}' not found or expired."}
            failed = state.get("failed_step", -1)
            failed_name = state["steps"][failed] if 0 <= failed < len(state["steps"]) else "?"
            return {
                "status": "error",
                "session_id": session_id,
                "pipeline": state.get("pipeline_name"),
                "failed_step": failed + 1 if failed >= 0 else None,
                "failed_step_name": failed_name,
                "steps_completed": failed if failed >= 0 else 0,
                "message": (
                    f"Pipeline failed at step {failed + 1} ({failed_name}). "
                    f"Call run_pipeline with session_id='{session_id}' and pipeline_name to resume from that step."
                ),
            }

        if client_key:
            psess.api_key = client_key

        if psess.status in ("done", "error"):
            return _pipeline_snapshot(psess)

        has_answer = bool((response and response.strip()) or input_paths or artifacts)
        if has_answer and psess.status == "need_input":
            skill_sess = psess.current_skill_sess
            if skill_sess is not None:
                # Stage the attachments BEFORE releasing the reply. If a path does not
                # resolve, the reply is NOT consumed — the session stays in need_input so
                # the caller can correct the paths and answer again, rather than the skill
                # resuming against files that never arrived.
                try:
                    _copy_input_paths(skill_sess.inputs_dir, input_paths)
                except InputPathError as e:
                    snapshot = _pipeline_snapshot(psess)
                    snapshot["error"] = str(e)
                    snapshot["next_step"] = (
                        "The file(s) you attached could not be read — see `error`. The question "
                        "above is still open and the session is still waiting. Fix the paths and "
                        "call run_pipeline again with the same session_id, the same response, and "
                        "corrected input_paths. Do not restart the pipeline."
                    )
                    return snapshot
                engine._write_artifacts(skill_sess.inputs_dir, artifacts)
            psess.pending_reply = response or ""
            psess.reply_event.set()

        await _wait_for_change_pipeline(psess)
        return _pipeline_snapshot(psess)

    # RESUME: session_id + pipeline_name → restart from the failed step
    if session_id and pipeline_name:
        state = pipeline.load_state(session_id)
        if state is None:
            return {"status": "error", "message": f"No saved pipeline state for session_id '{session_id}'."}
        new_inputs = {"input_paths": input_paths, "urls": urls, "context": context}
        psess = pipeline.restore_pipeline_session(session_id, state, client_key, new_inputs)
        # Drive from the MERGED inputs, not just this call's. A local path stays valid, so
        # it is persisted in state — which only helps if a resume that re-runs step 0
        # restages the original files alongside anything new the caller just added.
        merged = psess.original_inputs
        psess.task = asyncio.create_task(
            _drive_pipeline(psess, merged.get("input_paths"), artifacts,
                            merged.get("urls"), merged.get("context"))
        )
        await _wait_for_change_pipeline(psess)
        return _pipeline_snapshot(psess)

    # FIRST CALL: pipeline_name required
    if not pipeline_name:
        available = [p["name"] for p in pipeline.load_pipelines()]
        return {"status": "error", "message": (
            "run_pipeline needs `pipeline_name` to start a pipeline, or `session_id` to poll/resume. "
            f"Available pipelines: {', '.join(available) or 'none'}."
        )}

    matched = pipeline.find_pipeline(pipeline_name)
    if matched is None:
        available = [p["name"] for p in pipeline.load_pipelines()]
        return {"status": "error", "message": (
            f"Unknown pipeline '{pipeline_name}'. "
            f"Available: {', '.join(available) or 'none'}."
        )}

    seed_matches = _resolve_seed_buckets(seed_session_id)
    if seed_session_id and not seed_matches:
        return {"status": "error", "message": (
            f"No deliverable bucket found for seed_session_id='{seed_session_id}' under outputs/mcp/. "
            "Pass the session id (or result id) of the earlier run whose output you want to refine."
        )}
    if len(seed_matches) > 1:
        return {"status": "error", "message": (
            f"seed_session_id='{seed_session_id}' is ambiguous — it matches several buckets "
            f"({', '.join(seed_matches)}). Pass the full result id (one of those) instead."
        )}
    seed_result_id = seed_matches[0] if seed_matches else None
    if matched.get("requires_seed") and not seed_result_id:
        return {"status": "error", "message": (
            f"Pipeline '{pipeline_name}' needs `seed_session_id` — the session id of the earlier run "
            "whose output is being refined — so the server can stage it and write the changes back "
            "into it in place. Pass seed_session_id and try again."
        )}

    original_inputs = {
        "input_paths": input_paths or [],
        "urls": urls or [],
        "context": context,
        "seed_session_id": seed_session_id,
    }
    # Continue-in-place: when the seed is itself a PIPELINE (not a bare bucket), this run
    # APPENDS to that pipeline — reusing its id as the poll handle and dropping the new
    # deliverable into the same pipeline_<id>/ folder next to the KB it is generated from,
    # instead of minting a fresh top-level pipeline. Any other seed (a raw bucket) still
    # starts a new pipeline that merely references the seed.
    seed_pid = _seed_pipeline_id(seed_session_id)
    if seed_pid:
        base_state = pipeline.load_state(seed_pid)
        psess = pipeline.new_appended_session(
            seed_pid, base_state, matched, seed_result_id,
            client_key, original_inputs,
        )
    else:
        psess = pipeline.new_pipeline_session(
            matched, client_key, original_inputs, seed_result_id=seed_result_id
        )
    psess.task = asyncio.create_task(
        _drive_pipeline(psess, input_paths, artifacts, urls, context)
    )
    await _wait_for_change_pipeline(psess)
    return _pipeline_snapshot(psess)


# Set the docstring BEFORE mcp.tool() decorates so FastMCP registers the live description.
run_pipeline.__doc__ = pipeline.build_run_pipeline_doc()
run_pipeline = mcp.tool()(run_pipeline)


@mcp.tool()
async def list_pipelines(ctx: Optional[Context] = None) -> dict:
    """Return all available pipelines with their names, descriptions, steps, and trigger phrases.

    Always call this before run_pipeline to pick the right pipeline_name for the
    user's intent. Match the user's request against each pipeline's description and
    triggers to decide which one to run."""
    pipelines = pipeline.load_pipelines()
    return {"pipelines": pipelines}
