"""FastMCP server: the two client-facing tools, `run_skill` and `list_skills`.

Execution model — background job + long-poll (avoids the client's MCP idle
timeout). A skill turn can run for minutes, far longer than the client's ~300s
idle timeout on a single tool call. So `run_skill` never blocks for a whole turn:
it kicks the turn off as a background task and returns quickly. Each call
"long-polls" — it waits up to POLL_WAIT seconds for the job state to change, then
returns a snapshot. The client keeps calling with the same `session_id` until the
status is `need_input` or `onboarded`.

States: running -> need_input <-> running -> ... -> onboarded | error
  - running     : a turn is executing; keep polling.
  - need_input  : the skill asked questions; relay them, then call again with
                  session_id + response.
  - onboarded   : done; KB harvested to kb/<kb_id>/.
  - error       : the turn failed.
"""

from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from . import engine_sdk, registry, sessions
from .config import HOST, KB_DIR, PORT

load_dotenv()

mcp = FastMCP("likeminds", host=HOST, port=PORT)

# How long a single run_skill call waits for the job state to change before
# returning "running". Kept high (but under the client's ~300s idle timeout) so the
# client polls only a few times for a long run instead of dozens — far fewer
# repeated calls, which otherwise look like a stuck loop to the user.
POLL_WAIT = 150

RELAY_TEXT = (
    "Show these questions to the user verbatim, wait for their reply and any "
    "attachments, then call run_skill again with this session_id and the user's "
    "`response`. If the user points to local files to answer the gaps, pass their "
    "absolute paths in `input_paths` (best for binary/large files) or their text "
    "in `files` ([{name, content}]) on that SAME call so the skill can read them. "
    "Do NOT answer the questions yourself."
)
POLL_TEXT = (
    "Still working. Tell the user the current `progress` and `files_written` so "
    "they can see what's happening, then call run_skill again with ONLY this "
    "session_id (no other arguments) to keep polling. This is normal long-running "
    "progress, not an error. Repeat until status is 'need_input' or 'onboarded'."
)


# ----------------------------------------------------------------------------- #
# Output harvesting + KB promotion
# ----------------------------------------------------------------------------- #

def _harvest(sandbox: Path) -> list[tuple[str, str]]:
    """Collect the deliverable from the sandbox. Prefer `output/`; fall back to
    `work/`. Returns [(relative_name, content)]."""
    for sub in ("output", "work"):
        base = sandbox / sub
        if not base.is_dir():
            continue
        files = [p for p in sorted(base.rglob("*")) if p.is_file()]
        if files:
            return [
                (str(p.relative_to(base)), p.read_text(encoding="utf-8", errors="replace"))
                for p in files
            ]
    return []


def _promote(skill: str, harvested: list[tuple[str, str]], manifest: list | None) -> tuple[str, list[str]]:
    """Write the harvested files to kb/<kb_id>/. Falls back to any inlined content
    in the emit manifest only if nothing was found on disk."""
    files = harvested
    if not files and manifest:
        files = [
            (f["name"], str(f.get("content", "")))
            for f in manifest
            if isinstance(f, dict) and f.get("name")
        ]
    kb_id = f"kb_{skill}_{uuid.uuid4().hex[:8]}"
    dest = KB_DIR / kb_id
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in files:
        out = dest / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        written.append(name)
    return kb_id, written


# ----------------------------------------------------------------------------- #
# Background turn runner
# ----------------------------------------------------------------------------- #

async def _run_turn(sess: sessions.Session) -> None:
    """Run one skill turn to its next signal and update the session job state.
    Runs as a detached task; never raises out."""
    try:
        signal = await engine_sdk.run_until_signal(sess)
        if signal is None:
            sess.status = "error"
            sess.error = "Skill ended without calling ask_user or emit_result."
        elif signal["kind"] == "ask":
            sess.questions = signal["questions"]
            sess.status = "need_input"
        else:  # emit
            harvested = _harvest(sess.sandbox)
            print(f"[harvest] sandbox={sess.sandbox} "
                  f"output_exists={(sess.sandbox/'output').is_dir()} "
                  f"files={[(n, len(c)) for n, c in harvested]}", flush=True)
            kb_id, names = _promote(sess.skill, harvested, signal.get("files"))
            await sessions.close_session(sess)  # harvest first, then purge sandbox
            sess.result = {"kb_id": kb_id, "summary": {"files": names}}
            sess.status = "onboarded"
    except Exception as e:  # noqa: BLE001 - surface as job error, don't crash server
        sess.status = "error"
        sess.error = f"{type(e).__name__}: {e}"
    finally:
        sess.busy = False


def _start_turn(sess: sessions.Session) -> None:
    sess.status = "running"
    sess.busy = True
    sess.task = asyncio.create_task(_run_turn(sess))


async def _wait_for_change(sess: sessions.Session, seconds: int = POLL_WAIT) -> None:
    """Long-poll: wait until the job leaves 'running' or the window elapses."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + seconds
    while sess.status == "running" and loop.time() < deadline:
        await asyncio.sleep(1)


def _snapshot(sess: sessions.Session) -> dict:
    if sess.status == "need_input":
        return {"status": "need_input", "session_id": sess.id,
                "questions": sess.questions, "next_step": RELAY_TEXT}
    if sess.status == "onboarded":
        return {"status": "onboarded", **(sess.result or {})}
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


# ----------------------------------------------------------------------------- #
# Tools
# ----------------------------------------------------------------------------- #

def _copy_input_paths(inputs_dir: Path, paths: list | None) -> list[str]:
    """Copy local files (incl. binaries like .anfx) into the session inputs dir.
    For large/binary inputs that can't ride inline as text artifacts. Returns the
    names of files copied."""
    copied = []
    for p in paths or []:
        src = Path(str(p)).expanduser()
        if src.is_file():
            shutil.copy2(src, inputs_dir / src.name)
            copied.append(src.name)
    return copied


@mcp.tool()
async def run_skill(
    skill: Optional[str] = None,
    artifacts: Optional[list] = None,
    input_paths: Optional[list] = None,
    urls: Optional[list] = None,
    context: Optional[str] = None,
    session_id: Optional[str] = None,
    response: Optional[str] = None,
    files: Optional[list] = None,
) -> dict:
    """Run a LikeMinds skill (background job + poll).

    First call: provide `skill` (e.g. 'platform-kb') and inputs. Inputs may be
    inline text `artifacts` ([{name, content}]) and/or `input_paths` (absolute
    paths to local files — used for large or binary inputs like .anfx archives,
    which the server copies into the session). You get back `status: "running"`
    with a `session_id`.

    Then POLL: call again with ONLY that `session_id` (no other args). Keep
    polling while status is `running`. When status is `need_input`, present the
    `questions` to the user verbatim, wait for their reply, then call again with
    `session_id` + `response` (do NOT answer the questions yourself) and resume
    polling. Stop when status is `onboarded` (KB stored server-side) or `error`.
    """
    if session_id:
        sess = sessions.get_session(session_id)
        if sess is None:
            return {"status": "expired",
                    "message": "Session expired or invalid. Restart the skill."}
        if sess.status in ("onboarded", "error"):
            return _snapshot(sess)
        # An ANSWER is any continuation that carries reply text OR reference files
        # (inline artifacts/files, or local input_paths). Otherwise it's a poll.
        has_answer = (
            response is not None or files or input_paths or artifacts
        )
        if has_answer and sess.status == "need_input" and not sess.busy:
            added = (
                engine_sdk._write_artifacts(sess.inputs_dir, artifacts)
                + engine_sdk._write_artifacts(sess.inputs_dir, files)
                + _copy_input_paths(sess.inputs_dir, input_paths)
            )
            msg = engine_sdk.build_reply_message(response, added)
            await sess.client.query(msg)
            _start_turn(sess)
        await _wait_for_change(sess)
        return _snapshot(sess)

    # First call.
    if not registry.skill_exists(skill or ""):
        available = ", ".join(s["name"] for s in registry.list_skills())
        return {"status": "error", "message": f"Unknown skill '{skill}'. Available: {available}"}
    sess = sessions.new_session(skill)
    engine_sdk._write_artifacts(sess.inputs_dir, artifacts)
    _copy_input_paths(sess.inputs_dir, input_paths)
    await sess.client.connect()
    sess.connected = True
    msg = engine_sdk.build_first_message(skill, sess, urls, context)
    await sess.client.query(msg)
    _start_turn(sess)
    await _wait_for_change(sess)
    return _snapshot(sess)


@mcp.tool()
async def list_skills() -> dict:
    """Return the available skill names and one-line descriptions."""
    return {"skills": registry.list_skills()}
