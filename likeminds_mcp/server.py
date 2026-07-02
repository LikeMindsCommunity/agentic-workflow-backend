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
import base64
import shutil
import threading
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from . import engine_sdk, registry, sessions
from .config import HOST, OUTPUTS_DIR, PORT

load_dotenv()

mcp = FastMCP("likeminds", host=HOST, port=PORT)

# How long a single run_skill call waits for the job state to change before
# returning "running". Kept SHORT so each call needs only a sliver of main-thread
# time (the worker thread contends for the GIL) and returns promptly with fresh
# progress. Frequent polls are fine now that each one shows live progress.
POLL_WAIT = 4

# Hard interlock: if the skill tries to finish before ever asking the user, we
# refuse and push it back to the gap step. Allowed a few times before giving up so
# a genuinely gap-free skill can't deadlock.
MAX_EMIT_BLOCKS = 3
EMIT_BLOCKED_MSG = (
    "STOP — you called emit_result but you have NOT presented the gaps to the user "
    "yet (ask_user was never called). The skill REQUIRES presenting all blocking "
    "and important gaps and assumptions to the user via ask_user, and waiting for "
    "their reply, BEFORE finishing. First make sure every planned KB section is "
    "written as a complete file in output/, then call ask_user now with the full "
    "gap block. Do not call emit_result again until the user has answered or said "
    "'done'."
)

RELAY_TEXT = (
    "Show this ONE gap to the user verbatim and wait for their reply. They may "
    "answer it, reply 'skip' to skip it, or 'done' to stop and finish the KB. Then "
    "call run_skill again with this session_id and their `response`. To attach a "
    "file with the answer: if you have a real local path use `input_paths`; if you "
    "do NOT (e.g. the regular chat, an uploaded attachment), first call the "
    "`upload_file` tool with the file's content, then pass the returned id in "
    "`upload_refs` on the SAME run_skill call. Do NOT answer the gap yourself — "
    "after you relay the reply, the skill asks the next gap."
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
    """Write the harvested KB into the project's `outputs/` dir, PRESERVING the
    skill's own structure (e.g. `{client}/kb/…`) so the final KB lands at
    `outputs/{client}/kb/`. Falls back to inlined manifest content only if nothing
    was found on disk."""
    files = harvested
    if not files and manifest:
        files = [
            (f["name"], str(f.get("content", "")))
            for f in manifest
            if isinstance(f, dict) and f.get("name")
        ]
    written = []
    for name, content in files:
        out = OUTPUTS_DIR / name  # `name` is relative, e.g. exotel-anfx-ivr/kb/00-overview.md
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        written.append(name)
    # kb_id = the top-level client folder under outputs/ (kb-builder's {client}).
    kb_id = written[0].split("/")[0] if written else f"kb_{skill}_{uuid.uuid4().hex[:8]}"
    return kb_id, written


# ----------------------------------------------------------------------------- #
# Background turn runner
# ----------------------------------------------------------------------------- #

async def _drive_session(sess: sessions.Session, first_message: str) -> None:
    """The whole skill lifecycle, run ON THE WORKER THREAD's own event loop so it
    never blocks the MCP server's main loop. Updates sess.* state as it goes; the
    main loop only ever reads that state to answer polls."""
    try:
        sess.reply_event = asyncio.Event()
        sess.worker_loop = asyncio.get_running_loop()
        await sess.client.connect()
        sess.connected = True
        await sess.client.query(first_message)
        emit_blocks = 0
        while True:
            sess.status = "running"
            signal = await engine_sdk.run_until_signal(sess)
            if signal is None:
                sess.status = "error"
                sess.error = "Skill ended without calling ask_user or emit_result."
                return
            if signal["kind"] == "emit":
                # HARD INTERLOCK (interactive modes only): refuse to finish if the
                # skill never asked the user. One-shot skills finish freely.
                if sess.interlock and not sess.asked and emit_blocks < MAX_EMIT_BLOCKS:
                    emit_blocks += 1
                    sess.progress = "Finishing blocked — must ask gaps first…"
                    await sess.client.query(EMIT_BLOCKED_MSG)
                    continue
                harvested = _harvest(sess.sandbox)
                kb_id, names = _promote(sess.skill, harvested, signal.get("files"))
                await sessions.close_session(sess)  # harvest first, then purge
                sess.result = {"kb_id": kb_id, "summary": {"files": names}}
                sess.status = "onboarded"
                return
            # ask_user: publish the questions and wait for the main loop to hand us
            # a reply (it sets pending_reply and fires reply_event via the worker loop).
            sess.asked = True
            sess.questions = signal["questions"]
            sess.status = "need_input"
            await sess.reply_event.wait()
            sess.reply_event.clear()
            sess.progress = "Reading your answer…"
            await sess.client.query(sess.pending_reply)
    except Exception as e:  # noqa: BLE001 — surface as job error, never crash the thread
        sess.status = "error"
        sess.error = f"{type(e).__name__}: {e}"


def _worker_entry(sess: sessions.Session, first_message: str) -> None:
    """Thread target: own event loop, drives one skill session start to finish."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_drive_session(sess, first_message))
    finally:
        loop.close()


def _start_worker(sess: sessions.Session, first_message: str) -> None:
    sess.status = "running"
    sess.thread = threading.Thread(
        target=_worker_entry, args=(sess, first_message), daemon=True
    )
    sess.thread.start()


def _deliver_reply(sess: sessions.Session, msg: str) -> None:
    """Hand a reply to the worker thread and wake it (thread-safe)."""
    sess.pending_reply = msg
    sess.status = "running"
    sess.worker_loop.call_soon_threadsafe(sess.reply_event.set)


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

# In-memory uploads store: upload_ref -> {"name": str, "data": bytes}. Lets a
# client that can't hand over a local file path (e.g. the regular Claude chat) push
# a file's content in, then reference it by ref on run_skill.
UPLOADS: dict[str, dict] = {}


def _materialize_uploads(inputs_dir: Path, refs: list | None) -> list[str]:
    """Write previously-uploaded files (by upload_ref) into the session inputs."""
    added: list[str] = []
    for ref in refs or []:
        item = UPLOADS.pop(str(ref), None)
        if item:
            (inputs_dir / item["name"]).write_bytes(item["data"])
            added.append(item["name"])
    return added


def _ingest_paths_from_text(inputs_dir: Path, text: str | None) -> list[str]:
    """Backstop: if the client names a real local file path in the reply text
    (instead of routing it through input_paths / upload_file), copy that file into
    the session inputs so the skill can read it — rather than silently drop it.
    Handles filenames with spaces by trimming trailing words until a real file
    matches. Returns the names ingested."""
    if not text:
        return []
    added: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        pos = 0
        while (i := line.find("/", pos)) != -1:
            pos = i + 1
            cand = line[i:].strip().strip("`\"'.,)")
            while cand and cand not in seen:
                p = Path(cand)
                if p.is_file():
                    shutil.copy2(p, inputs_dir / p.name)
                    added.append(p.name)
                    seen.add(cand)
                    break
                if " " in cand:              # drop a trailing word, retry (spaces)
                    cand = cand.rsplit(" ", 1)[0].rstrip("`\"'.,)")
                else:
                    break
    return added


def _unresolved_input_paths(paths: list | None) -> list[str]:
    """Which of the given input_paths do NOT exist on the server's filesystem."""
    out = []
    for p in paths or []:
        sp = Path(str(p)).expanduser()
        if not (sp.is_file() or sp.is_dir()):
            out.append(str(p))
    return out


def _paths_error(unresolved: list[str]) -> str:
    return (
        "These input_paths were not found on the server: " + ", ".join(unresolved) + ". "
        "If they are CHAT ATTACHMENTS (no real local path), do NOT use input_paths — "
        "send each file's CONTENT via the upload_file tool (encoding='base64' for "
        "binary, upload large files in chunks) and pass the returned upload_refs "
        "instead. If they are meant to be real local files, re-check the absolute paths."
    )


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
        elif src.is_dir():  # e.g. an existing KB directory for api/config/code-agent
            shutil.copytree(src, inputs_dir / src.name, dirs_exist_ok=True)
            copied.append(src.name + "/")
    return copied


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
) -> dict:
    """Run a LikeMinds skill (background job + poll).

    First call: provide `skill` (e.g. 'kb-builder') and inputs. Choose the file
    channel by what you actually have:
    - ATTACHED files (regular chat — no real path): you MUST send their CONTENT via
      the `upload_file` tool, then pass the returned ids in `upload_refs`. For a
      binary file (.anfx zip, image) use encoding='base64'; for a large file upload
      it in chunks (see upload_file). Do NOT put an attachment's filename in
      `input_paths` — it has no real path and will be silently dropped.
    - REAL local paths (Claude Code, or paths you can see on this machine): pass the
      absolute paths in `input_paths`.
    - Small inline text: `artifacts` / `files` ([{name, content}]).
    You get back `status: "running"` with a `session_id`.

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
        # If the answer relied ONLY on input_paths and none resolve, hold the gap
        # open and tell the client to use upload_file instead of dropping the file.
        unresolved = _unresolved_input_paths(input_paths)
        if (input_paths and len(unresolved) == len(input_paths)
                and not (files or artifacts or upload_refs)
                and (response is None or not response.strip())):
            return {"status": "need_input", "session_id": sess.id,
                    "questions": sess.questions, "warning": _paths_error(unresolved),
                    "next_step": RELAY_TEXT}
        has_answer = (
            response is not None or files or input_paths or artifacts or upload_refs
        )
        if has_answer and sess.status == "need_input":
            added = (
                engine_sdk._write_artifacts(sess.inputs_dir, artifacts)
                + engine_sdk._write_artifacts(sess.inputs_dir, files)
                + _copy_input_paths(sess.inputs_dir, input_paths)
                + _materialize_uploads(sess.inputs_dir, upload_refs)
                + _ingest_paths_from_text(sess.inputs_dir, response)
            )
            _deliver_reply(sess, engine_sdk.build_reply_message(response, added))
        await _wait_for_change(sess)
        return _snapshot(sess)

    # First call — spin up the worker thread and return promptly.
    if not registry.skill_exists(skill or ""):
        available = ", ".join(s["name"] for s in registry.list_skills())
        return {"status": "error", "message": f"Unknown skill '{skill}'. Available: {available}"}
    entry = registry.resolve_skill(skill)
    if entry and entry["mode"] == "execution":
        return {"status": "error",
                "message": f"'{skill}' performs live execution and is not available via "
                           "run_skill yet — it needs a dedicated, gated runner path."}
    # Don't start the skill with silently-empty inputs: if input_paths were given
    # but none resolve on the server (the classic chat-attachment mistake), fail
    # loudly with guidance so the client re-sends the files via upload_file.
    unresolved = _unresolved_input_paths(input_paths)
    if input_paths and len(unresolved) == len(input_paths):
        return {"status": "error", "message": _paths_error(unresolved)}
    sess = sessions.new_session(skill)
    engine_sdk._write_artifacts(sess.inputs_dir, artifacts)
    _copy_input_paths(sess.inputs_dir, input_paths)
    _materialize_uploads(sess.inputs_dir, upload_refs)
    # Backstop: pull in any real local paths the client named in `context` (e.g. a
    # chat that typed the paths in the request instead of using input_paths).
    _ingest_paths_from_text(sess.inputs_dir, context)
    first_message = engine_sdk.build_first_message(skill, sess, urls, context)
    _start_worker(sess, first_message)
    await _wait_for_change(sess)
    return _snapshot(sess)


@mcp.tool()
async def upload_file(
    name: str, content: str, encoding: str = "utf-8", upload_ref: Optional[str] = None
) -> dict:
    """Upload a file's content so a skill can use it — for clients with NO local
    filesystem path (e.g. the regular Claude chat, where a file is ATTACHED rather
    than referenced by path).

    Use this for attachments. For a binary file (e.g. a .anfx zip, an image), set
    `encoding='base64'`. Do NOT use run_skill's `input_paths` for an attachment —
    an attachment has no real path, so it will be silently dropped.

    LARGE FILES — upload in CHUNKS: call this once (leave `upload_ref` empty) to get
    a ref, then call again for each further chunk passing that SAME `upload_ref` to
    APPEND. Keep chunks well under ~200 KB of `content` each. When done, pass the ref
    to run_skill's `upload_refs`. This is how you deliver a large attachment the
    chat can't inline in a single call — do not give up on size, just chunk it.

    Returns `{upload_ref, name, bytes}` (bytes = total accumulated so far)."""
    clean = Path(name).name or "upload.bin"
    try:
        data = base64.b64decode(content) if encoding == "base64" else content.encode("utf-8")
    except Exception as e:  # noqa: BLE001
        return {"error": f"could not decode content ({encoding}): {e}"}
    if upload_ref and upload_ref in UPLOADS:
        UPLOADS[upload_ref]["data"] += data          # append this chunk
        ref = upload_ref
    else:
        ref = "up_" + uuid.uuid4().hex[:12]
        UPLOADS[ref] = {"name": clean, "data": data}
    return {"upload_ref": ref, "name": UPLOADS[ref]["name"], "bytes": len(UPLOADS[ref]["data"])}


@mcp.tool()
async def list_skills() -> dict:
    """List available skills with one-line descriptions. Use this to pick the right
    skill for the user's intent, then call run_skill with that name. Rough guide:
    build/update a knowledge base -> kb-builder; generate a config/nodeflow ->
    config-agent; produce an LLD / execution doc -> api-agent; write/integrate code
    -> code-agent."""
    return {"skills": registry.list_skills()}
