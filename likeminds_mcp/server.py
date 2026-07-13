"""FastMCP server: the client-facing tools `run_skill`, `upload_file`, `list_skills`.

Execution model — background asyncio task + long-poll (avoids the client's MCP
idle timeout). A skill turn can run for minutes, far longer than the client's
~300s idle timeout on a single tool call. So `run_skill` never blocks for a whole
turn: the first call starts a background task that drives the resume-per-turn loop,
and every call long-polls (waits up to POLL_WAIT seconds for the job state to
change) then returns a snapshot. The client keeps calling with the same
`session_id` until the status is `need_input`, `done`, or `error`.

States: running -> need_input <-> running -> ... -> done | error
  - running     : a turn is executing; keep polling.
  - need_input  : the skill asked; relay the questions, then call again with
                  session_id + response.
  - done        : finished; deliverable harvested to outputs/mcp/<result_id>/.
  - error       : the run failed.

Everything runs on the server's single event loop — the background driver is an
asyncio.Task, not a thread — so there are no cross-loop objects and nothing is
parked alive while a human is answering.
"""

from __future__ import annotations

import asyncio
import base64
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP

from . import config, engine, registry, sessions

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
# self-contained. Safe here because run_skill's pause/resume polling keys off an
# APPLICATION-level session_id (returned in the tool result, passed back as an
# argument, looked up in the in-process SESSIONS dict) — wholly independent of the
# transport session. json_response also drops the long-lived SSE stream (whose drops
# were the original point of failure) in favour of a plain JSON reply per POST.
mcp = FastMCP(
    "likeminds",
    host=config.HOST,
    port=config.PORT,
    stateless_http=True,
    json_response=True,
)

# How long a single run_skill call waits for the job state to change before
# returning "running". Short, so each call returns promptly with fresh progress.
POLL_WAIT = 4

RELAY_TEXT = (
    "Show these question(s) to the user verbatim and wait for their reply. They may "
    "answer, or reply 'done' to stop and finish with whatever is complete. Then call "
    "run_skill again with this session_id and their `response`. To attach a file "
    "with the answer: if you have a real local path use `input_paths`; otherwise "
    "call the `upload_file` tool first and pass the returned id in `upload_refs` on "
    "the SAME run_skill call. Do NOT answer the question yourself."
)
POLL_TEXT = (
    "Still working. Tell the user the current `progress` and `files_written`, then "
    "call run_skill again with ONLY this session_id (no other arguments) to keep "
    "polling. This is normal long-running progress, not an error. Repeat until "
    "status is 'need_input' or 'done'."
)


# ----------------------------------------------------------------------------- #
# Output harvesting + deliverable promotion
# ----------------------------------------------------------------------------- #

def _harvest(sandbox: Path) -> list[tuple[str, bytes]]:
    """Collect the deliverable from the sandbox as raw bytes (so binary outputs like
    PDF/DOCX/XLSX survive intact). Prefer `output/`; fall back to `work/`."""
    for sub in ("output", "work"):
        base = sandbox / sub
        if not base.is_dir():
            continue
        files = [p for p in sorted(base.rglob("*")) if p.is_file()]
        if files:
            return [(str(p.relative_to(base)), p.read_bytes()) for p in files]
    return []


def _promote(session_id: str, harvested: list[tuple[str, bytes]]) -> list[str]:
    """Write the harvested (name, bytes) files to outputs/mcp/<session_id>/ — the
    stable, caller-addressable bucket. Continuing a session writes back to the SAME
    bucket, so the deliverable accumulates under one id the user can save and reuse."""
    dest = config.RESULTS_DIR / session_id
    dest.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for name, content in harvested:
        out = dest / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(content)
        written.append(name)
    return written


def _install_skills(harvested: list[tuple[str, bytes]]) -> list[str]:
    """Register any skill-shaped deliverable into the project's live skills dir.

    A skill-creation skill (document-generator, generate-find-bugs-skill,
    skill-creator, …) produces a NEW Agent Skill — a `SKILL.md` plus its assets. But
    the harness makes every skill write its deliverable into the sandbox output dir, so
    a freshly built skill would otherwise land only in outputs/mcp/<id>/ and never be
    discoverable by registry._index(). This step deterministically copies each skill
    folder found in the harvest into SKILLS_DIR/<name>/, so list_skills / run_skill pick
    it up on the very next call — independent of where (or whether) the spawned model
    tried to install it. The deliverable is still promoted to outputs/mcp/<id>/ as well.

    A skill's root is the directory holding its SKILL.md; that directory's name is the
    skill name (matching how registry keys skills by folder). If a SKILL.md sits at the
    harvest root, the whole harvest is one skill and the name comes from its frontmatter
    `name:`. Returns the names of the skills installed."""
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
        name = Path(name.strip()).name  # sanitize: no path separators / traversal
        if name:
            roots[prefix] = name

    installed: list[str] = []
    for prefix, name in roots.items():
        dest_root = config.SKILLS_DIR / name
        for rel, content in harvested:
            if not rel.startswith(prefix):
                continue
            out = dest_root / rel[len(prefix):]
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(content)
        installed.append(name)
    return installed


def _seed_prior_outputs(output_dir: Path, prior: Path) -> list[str]:
    """Copy a prior session's promoted deliverable into this run's output dir so the
    skill can read and extend it in place — harvest then captures the full updated set
    (edited + untouched files), so writing back never loses prior work. Returns the
    relative filenames seeded."""
    seeded: list[str] = []
    for p in sorted(prior.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(prior)
        dest = output_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
        seeded.append(str(rel))
    return seeded


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

            # emit: harvest the deliverable, purge the sandbox, report done. It is
            # promoted to outputs/mcp/<sess.id>/ (the stable, caller-facing id), so it
            # survives the purge and can be continued later under the same session_id.
            harvested = _harvest(sess.sandbox)
            names = _promote(sess.id, harvested)
            registered = _install_skills(harvested)
            sessions.purge(sess)
            summary = {"files": names}
            if registered:
                summary["skills_registered"] = registered
            sess.result = {"result_id": sess.id, "summary": summary}
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


def _deliver_reply(sess: sessions.Session, msg: str) -> None:
    """Hand a reply to the background driver and wake it (same loop, no threads)."""
    sess.pending_reply = msg
    sess.status = "running"
    if sess.reply_event is not None:
        sess.reply_event.set()


async def _wait_for_change(sess: sessions.Session, seconds: int = POLL_WAIT) -> None:
    """Long-poll: wait until the job leaves 'running' or the window elapses."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while sess.status == "running" and loop.time() < deadline:
        await asyncio.sleep(0.5)


def _snapshot(sess: sessions.Session) -> dict:
    if sess.status == "need_input":
        return {"status": "need_input", "session_id": sess.id,
                "questions": sess.questions, "next_step": RELAY_TEXT}
    if sess.status == "done":
        result = sess.result or {}
        registered = (result.get("summary") or {}).get("skills_registered")
        save_note = (
            f"Tell the user their session_id is {sess.id} and that they can save it and "
            "pass it back later (with a skill + context) on a run_skill call to continue "
            "building on these output artifacts."
        )
        if registered:
            next_step = (
                "Done. Registered new skill(s) into this server's .claude/skills so they "
                "resolve on the next list_skills/run_skill call: "
                + ", ".join(registered) + ". " + save_note
            )
        else:
            next_step = "Done. " + save_note
        return {"status": "done", "session_id": sess.id, **result, "next_step": next_step}
    if sess.status == "error":
        return {"status": "error", "session_id": sess.id,
                "message": sess.error or "unknown error"}
    n_out = 0
    if sess.output_dir.is_dir():
        n_out = sum(1 for p in sess.output_dir.rglob("*") if p.is_file())
    return {
        "status": "running",
        "session_id": sess.id,
        "progress": sess.progress or "starting…",
        "files_written": n_out,
        "next_step": POLL_TEXT,
    }


async def _start_continuation(
    skill: str,
    session_id: str,
    client_key: Optional[str],
    artifacts: Optional[list],
    files: Optional[list],
    input_paths: Optional[list],
    upload_refs: Optional[list],
    urls: Optional[list],
    context: Optional[str],
) -> dict:
    """Start a NEW run that continues a previously saved session: seed that session's
    promoted output artifacts (outputs/mcp/<session_id>/) into a fresh sandbox and let
    the skill build on them, writing the updated deliverable back under the SAME id.
    Carries the caller's per-request BYOK header key (client_key) into the new run."""
    sid = Path(str(session_id)).name  # sanitize — never escape RESULTS_DIR
    prior = config.RESULTS_DIR / sid
    if not prior.is_dir() or not any(prior.iterdir()):
        return {"status": "error",
                "message": (f"No saved outputs for session_id '{sid}'. Omit session_id "
                            "to start a new session.")}
    if not registry.skill_exists(skill or ""):
        available = ", ".join(s["name"] for s in registry.list_skills())
        return {"status": "error", "message": f"Unknown skill '{skill}'. Available: {available}"}
    live = sessions.get_session(sid)
    if live is not None and not live.finished:
        return {"status": "error",
                "message": (f"Session '{sid}' is still active — finish or answer it "
                            "(call with session_id + response, no skill) before continuing.")}
    sess = sessions.new_session(skill, durable_id=sid)
    sess.api_key = client_key  # BYOK: carry the caller's key into the continued run
    # Stage any NEW inputs the caller attached alongside the continuation request.
    engine._write_artifacts(sess.inputs_dir, artifacts)
    engine._write_artifacts(sess.inputs_dir, files)
    _copy_input_paths(sess.inputs_dir, input_paths)
    _materialize_uploads(sess.inputs_dir, upload_refs)
    # Seed the prior deliverable into the output dir so the skill continues in place.
    seeded = _seed_prior_outputs(sess.output_dir, prior)
    first_message = engine.build_first_message(
        skill, sess, urls, context, continued=True, seeded=seeded
    )
    sess.task = asyncio.create_task(_drive(sess, first_message))
    await _wait_for_change(sess)
    return _snapshot(sess)


# ----------------------------------------------------------------------------- #
# Inputs plumbing
# ----------------------------------------------------------------------------- #

# In-memory uploads store: upload_ref -> {"name": str, "data": bytes}. Lets a client
# that can't pass a local file path (e.g. the regular Claude chat) push a file's
# content in, then reference it by ref on run_skill.
UPLOADS: dict[str, dict] = {}


def _materialize_uploads(inputs_dir: Path, refs: list | None) -> list[str]:
    added: list[str] = []
    for ref in refs or []:
        item = UPLOADS.pop(str(ref), None)
        if item:
            (inputs_dir / item["name"]).write_bytes(item["data"])
            added.append(item["name"])
    return added


def _copy_input_paths(inputs_dir: Path, paths: list | None) -> list[str]:
    """Copy local files (incl. binaries) into the session inputs dir."""
    copied: list[str] = []
    for p in paths or []:
        src = Path(str(p)).expanduser()
        if src.is_file():
            shutil.copy2(src, inputs_dir / src.name)
            copied.append(src.name)
    return copied


# ----------------------------------------------------------------------------- #
# Per-request BYOK — the caller's Anthropic key, read fresh from the request header
# ----------------------------------------------------------------------------- #

def _client_api_key(ctx: Optional[Context]) -> Optional[str]:
    """The caller's Anthropic key from the request header (BYOK), or None.

    Read fresh from the live HTTP request on every call — never stored. Under the
    streamable-HTTP transport `ctx.request_context.request` is the Starlette request;
    under stdio (or if the context is unavailable) there is no request, so this
    returns None and the server falls back to its own .env creds. Accepts either a
    bare key (`x-api-key: <key>`) or an `Authorization: Bearer <key>` value."""
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
# Tools
# ----------------------------------------------------------------------------- #

@mcp.tool()
async def run_skill(
    skill: Optional[str] = None,
    artifacts: Optional[list] = None,
    input_paths: Optional[list] = None,
    upload_refs: Optional[list] = None,
    urls: Optional[list] = None,
    context: Optional[str] = None,
    session_id: Optional[str] = None,
    response: Optional[str] = None,
    files: Optional[list] = None,
    ctx: Optional[Context] = None,
) -> dict:
    """Run any LikeMinds skill (background job + poll).

    First call: provide `skill` (any name from `list_skills`, e.g. 'kb-builder',
    'config-agent', 'setup-document-generator') and its inputs. `context` says WHAT to do
    (a prompt / SOW / instructions). Ways to supply files:
    - `input_paths` — absolute paths to local files (best for binary/large files;
      only when you have a real local path, e.g. Claude Code).
    - `upload_refs` — ids from the `upload_file` tool (when you have NO local path,
      e.g. the regular Claude chat: call upload_file first, pass the ref).
    - `artifacts` / `files` — inline text content ([{name, content}]).
    You get back `status: "running"` with a `session_id`.

    Then POLL: call again with ONLY that `session_id` (no other args). Keep polling
    while status is `running`. When status is `need_input`, show the `questions` to
    the user verbatim, wait for their reply, then call again with `session_id` +
    `response` (do NOT answer them yourself) and resume polling. Stop when status is
    `done` (deliverable at outputs/mcp/<session_id>/) or `error`.

    CONTINUE a past session: pass a previously returned `session_id` TOGETHER WITH a
    `skill` (and `context`). The server seeds that session's saved output artifacts
    into a new run so the skill continues from them, writing the updated deliverable
    back under the SAME session_id. The done result reports the `session_id`, so
    surface it to the user to save and continue later.
    """
    # The caller's own Anthropic key (BYOK), read fresh from THIS request's header.
    client_key = _client_api_key(ctx)

    # Continuation: a skill AND a prior session_id together start a NEW run seeded from
    # that session's saved outputs. (A bare poll never carries a skill, so this is
    # unambiguous.)
    if skill and session_id:
        return await _start_continuation(
            skill, session_id, client_key, artifacts, files, input_paths, upload_refs, urls, context
        )

    if session_id:
        sess = sessions.get_session(session_id)
        if sess is None:
            return {"status": "expired",
                    "message": "Session expired or invalid. Restart the skill."}
        # Re-read the key per request so a rotated key takes effect on the next turn;
        # a bare poll with no header leaves the previously captured key in place.
        if client_key:
            sess.api_key = client_key
        if sess.status in ("done", "error"):
            return _snapshot(sess)
        # An ANSWER is a continuation carrying non-empty reply text OR files. A bare
        # session_id (or an empty response) is just a poll — it must NOT finish the
        # run. Only deliver a reply while the skill is actually waiting for one.
        has_answer = bool(
            (response and response.strip()) or files or input_paths or artifacts or upload_refs
        )
        if has_answer and sess.status == "need_input":
            added = (
                engine._write_artifacts(sess.inputs_dir, artifacts)
                + engine._write_artifacts(sess.inputs_dir, files)
                + _copy_input_paths(sess.inputs_dir, input_paths)
                + _materialize_uploads(sess.inputs_dir, upload_refs)
            )
            _deliver_reply(sess, engine.build_reply_message(response, added))
        await _wait_for_change(sess)
        return _snapshot(sess)

    # First call — validate, seed inputs, start the background driver, return promptly.
    if not registry.skill_exists(skill or ""):
        available = ", ".join(s["name"] for s in registry.list_skills())
        return {"status": "error", "message": f"Unknown skill '{skill}'. Available: {available}"}
    sess = sessions.new_session(skill)
    sess.api_key = client_key  # BYOK: injected into the spawned CLI env each turn
    engine._write_artifacts(sess.inputs_dir, artifacts)
    _copy_input_paths(sess.inputs_dir, input_paths)
    _materialize_uploads(sess.inputs_dir, upload_refs)
    first_message = engine.build_first_message(skill, sess, urls, context)
    sess.task = asyncio.create_task(_drive(sess, first_message))
    await _wait_for_change(sess)
    return _snapshot(sess)


@mcp.tool()
async def upload_file(name: str, content: str, encoding: str = "utf-8") -> dict:
    """Upload a file's content so a skill can use it — for clients with NO local
    filesystem path to pass (e.g. the regular Claude chat).

    Provide the file's full content as `content` (plain text, or base64 with
    encoding='base64' for binary). Returns an `upload_ref`; pass that ref to
    run_skill's `upload_refs` — on the first call as an input, or on a continuation
    to answer with a file. Prefer run_skill's `input_paths` when you have a real
    local file path (e.g. Claude Code)."""
    clean = Path(name).name or "upload.bin"
    try:
        data = base64.b64decode(content) if encoding == "base64" else content.encode("utf-8")
    except Exception as e:  # noqa: BLE001
        return {"error": f"could not decode content ({encoding}): {e}"}
    ref = "up_" + uuid.uuid4().hex[:12]
    UPLOADS[ref] = {"name": clean, "data": data}
    while len(UPLOADS) > config.MAX_UPLOADS:   # evict oldest un-consumed uploads
        UPLOADS.pop(next(iter(UPLOADS)))
    return {"upload_ref": ref, "name": clean, "bytes": len(data)}


@mcp.tool()
async def list_skills() -> dict:
    """Return the available skill names and one-line descriptions."""
    return {"skills": registry.list_skills()}
