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
import hashlib
import hmac
import os
import shutil
import time
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse

from . import config, engine, registry, sessions

load_dotenv()


def _configure_auth() -> None:
    """Route the spawned Claude at your Claude subscription (Max/Pro) via the OAuth
    token, instead of the provider creds in `.env`.

    - Map CLAUDE_TOKEN -> CLAUDE_CODE_OAUTH_TOKEN (the var the CLI reads for a
      long-lived subscription token from `claude setup-token`).
    - Strip Foundry/API creds so they cannot outrank the OAuth token.
    Set LIKEMINDS_MCP_AUTH=api to keep the .env API/Foundry creds instead."""
    if os.environ.get("LIKEMINDS_MCP_AUTH", "subscription").strip().lower() == "api":
        return
    token = os.environ.get("CLAUDE_TOKEN") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if token:
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = token
    for var in (
        "CLAUDE_CODE_USE_FOUNDRY",
        "ANTHROPIC_FOUNDRY_API_KEY",
        "ANTHROPIC_FOUNDRY_BASE_URL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
    ):
        os.environ.pop(var, None)


_configure_auth()

mcp = FastMCP("likeminds", host=config.HOST, port=config.PORT)

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
DONE_TEXT = (
    "The deliverable is ready. Give the user the `download_url` so they can download "
    "it, and tell them their `workspace_id` — reusing it (with the same `client`) in "
    "a new chat continues building on this same KB. If you cannot open the URL, call "
    "`fetch_result` with the `result_id` to get the file inline."
)


# ----------------------------------------------------------------------------- #
# Safe-path helpers
# ----------------------------------------------------------------------------- #

class _UploadError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _safe_relpath(name: str) -> Path | None:
    """Turn a caller-supplied (possibly nested) filename into a safe relative path.
    Rejects absolute paths and any '..' traversal; sanitizes each component. Returns
    None if nothing usable remains."""
    raw = (name or "").replace("\\", "/").strip()
    parts: list[str] = []
    for seg in raw.split("/"):
        seg = seg.strip()
        if not seg or seg == ".":
            continue
        if seg == ".." or seg.startswith("/"):
            return None
        cleaned = sessions._ID_OK.sub("-", seg).lstrip(".")
        if not cleaned:
            return None
        parts.append(cleaned)
    return Path(*parts) if parts else None


def _dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.is_dir() else 0


# ----------------------------------------------------------------------------- #
# Upload tickets (HMAC, stateless): issued over the authenticated MCP channel,
# spent against the plain-HTTP /upload endpoint.
# ----------------------------------------------------------------------------- #

def _mint_upload_ticket(client: str, workspace_id: str) -> str:
    expiry = int(time.time()) + config.UPLOAD_TICKET_TTL
    payload = f"{client}:{workspace_id}:{expiry}"
    sig = hmac.new(config.UPLOAD_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()


def _verify_upload_ticket(token: str) -> tuple[str, str] | None:
    """Return (client, workspace_id) for a valid, unexpired ticket, else None. Ids
    are sanitized to [A-Za-z0-9._-] so ':' is a safe field delimiter."""
    try:
        raw = base64.urlsafe_b64decode((token or "").encode()).decode()
        client, workspace_id, expiry, sig = raw.split(":")
    except Exception:  # noqa: BLE001
        return None
    payload = f"{client}:{workspace_id}:{expiry}"
    expected = hmac.new(config.UPLOAD_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected) or int(expiry) < int(time.time()):
        return None
    return client, workspace_id


# ----------------------------------------------------------------------------- #
# Artifact ingestion (stream to disk) + bundle expansion + deliverable packaging
# ----------------------------------------------------------------------------- #

async def _save_upload_stream(upload, dest_dir: Path) -> dict:
    """Stream one multipart UploadFile to disk under dest_dir, enforcing per-file and
    per-workspace size caps as bytes land (never buffering the whole file). Returns
    {upload_ref, name, bytes}."""
    rel = _safe_relpath(getattr(upload, "filename", "") or "upload.bin")
    if rel is None:
        raise _UploadError(400, "invalid filename")
    dest = dest_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    ws_used = _dir_size(dest_dir)
    written = 0
    try:
        with dest.open("wb") as f:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > config.MAX_FILE_BYTES:
                    raise _UploadError(413, f"file exceeds {config.MAX_FILE_BYTES // (1024*1024)} MB")
                if ws_used + written > config.MAX_WORKSPACE_BYTES:
                    raise _UploadError(413, "workspace storage quota exceeded")
                f.write(chunk)
    except _UploadError:
        dest.unlink(missing_ok=True)
        raise
    return {"upload_ref": str(rel), "name": rel.name, "bytes": written}


def _expand_zip(zip_path: Path, dest: Path) -> list[str]:
    """Expand a zip into dest with zip-slip + zip-bomb guards. Returns the relative
    paths written."""
    written: list[str] = []
    total = 0
    dest_resolved = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > config.MAX_ZIP_ENTRIES:
            raise _UploadError(413, "zip has too many entries")
        for info in infos:
            rel = _safe_relpath(info.filename)
            if rel is None:
                continue  # skip zip-slip / hostile entry
            out = dest / rel
            resolved = out.resolve()
            if resolved != dest_resolved and not str(resolved).startswith(str(dest_resolved) + os.sep):
                continue  # defense in depth against traversal
            total += info.file_size
            if total > config.MAX_ZIP_UNCOMPRESSED_BYTES:
                raise _UploadError(413, "zip uncompressed size exceeds limit")
            out.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            written.append(str(rel))
    return written


def _stage_artifacts(sess: sessions.Session, refs: list | None) -> list[str]:
    """Copy the referenced workspace artifacts into the run's inputs dir. A `.zip`
    ref is expanded (structure preserved); anything else is copied. Refs are paths
    relative to the workspace `artifacts/` dir, resolved safely inside it."""
    staged: list[str] = []
    for ref in refs or []:
        rel = _safe_relpath(str(ref))
        if rel is None:
            continue
        src = sess.artifacts_dir / rel
        if not src.is_file():
            continue
        if src.suffix.lower() == ".zip":
            try:
                staged += _expand_zip(src, sess.inputs_dir)
            except _UploadError:
                continue
        else:
            dst = sess.inputs_dir / rel.name
            shutil.copy2(src, dst)
            staged.append(rel.name)
    return staged


def _package_result(sess: sessions.Session) -> tuple[str, str, list[str]]:
    """Zip the workspace's deliverable(s) into DIST_DIR/<result_id>.zip for download:
    the KB/output at the archive root, plus any generated skills under `skills/`.
    Returns (result_id, download_url, file_names)."""
    result_id = f"{sess.skill}_{uuid.uuid4().hex[:8]}"
    config.DIST_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = config.DIST_DIR / f"{result_id}.zip"
    names: list[str] = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for base, prefix in ((sess.output_dir, ""), (sess.skills_dir, "skills/")):
            if not base.is_dir():
                continue
            for p in sorted(base.rglob("*")):
                if p.is_file():
                    rel = prefix + str(p.relative_to(base))
                    zf.write(p, rel)
                    names.append(rel)
    return result_id, f"{config.PUBLIC_URL}/download/{result_id}.zip", names


def _rewrite_skill_name(skill_md: Path, new_name: str) -> None:
    """Rewrite the `name:` field in an agent skill's SKILL.md frontmatter so Claude
    Code matches the skill by our transient name."""
    try:
        lines = skill_md.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if not lines or lines[0].strip() != "---":
        return
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            break
        if lines[i].lstrip().startswith("name:"):
            lines[i] = f"name: {new_name}"
            break
    skill_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _install_generated_skill(sess: sessions.Session, entry: dict) -> None:
    """Materialize a workspace-generated skill into the project's .claude/ under a
    transient, run-unique name so `claude -p` can invoke it. Recorded on the session
    and removed on purge. The transient name is unique per run, so it never collides
    with a global skill or another tenant's generated skill."""
    tid = "_ws_" + sess.id.replace("-", "")[:16]
    src = Path(entry["path"])
    if entry["kind"] == "command":
        config.COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
        dest = config.COMMANDS_DIR / f"{tid}.md"
        shutil.copy2(src, dest)
        sess.installed_skill_path, sess.installed_skill_is_dir = dest, False
    else:  # agent skill folder: <skills_root>/<name>/SKILL.md + support files
        config.SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        dest_dir = config.SKILLS_DIR / tid
        shutil.rmtree(dest_dir, ignore_errors=True)
        shutil.copytree(src.parent, dest_dir)
        _rewrite_skill_name(dest_dir / "SKILL.md", tid)
        sess.installed_skill_path, sess.installed_skill_is_dir = dest_dir, True
    sess.invoke_name, sess.skill_kind = tid, entry["kind"]


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

            # emit: package the (persistent) deliverable into a downloadable zip,
            # then purge only the ephemeral sandbox — the KB itself lives on under
            # the workspace so a later chat with the same workspace_id extends it.
            result_id, download_url, names = _package_result(sess)
            sessions.purge(sess)
            sess.result = {
                "result_id": result_id,
                "download_url": download_url,
                "client": sess.client,
                "workspace_id": sess.workspace_id,
                "summary": {"files": names},
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
    base = {"session_id": sess.id, "client": sess.client, "workspace_id": sess.workspace_id}
    if sess.status == "need_input":
        return {**base, "status": "need_input",
                "questions": sess.questions, "next_step": RELAY_TEXT}
    if sess.status == "done":
        return {"status": "done", **base, **(sess.result or {}), "next_step": DONE_TEXT}
    if sess.status == "error":
        return {**base, "status": "error", "message": sess.error or "unknown error"}
    n_out = 0
    if sess.output_dir.is_dir():
        n_out = sum(1 for p in sess.output_dir.rglob("*") if p.is_file())
    return {
        **base,
        "status": "running",
        "progress": sess.progress or "starting…",
        "files_written": n_out,
        "next_step": POLL_TEXT,
    }


# ----------------------------------------------------------------------------- #
# Inputs plumbing
# ----------------------------------------------------------------------------- #

def _copy_input_paths(inputs_dir: Path, paths: list | None) -> list[str]:
    """Copy LOCAL files into the session inputs dir. Only meaningful when the caller
    shares a filesystem with the server (dev / same box); gated by
    config.ALLOW_INPUT_PATHS. A remote caller's paths don't exist here — they use the
    upload flow instead (get_upload_ticket + /upload, or upload_file)."""
    copied: list[str] = []
    for p in paths or []:
        src = Path(str(p)).expanduser()
        if src.is_file():
            shutil.copy2(src, inputs_dir / Path(src.name).name)
            copied.append(src.name)
    return copied


# ----------------------------------------------------------------------------- #
# Tools
# ----------------------------------------------------------------------------- #

@mcp.tool()
async def run_skill(
    skill: Optional[str] = None,
    client: Optional[str] = None,
    workspace_id: Optional[str] = None,
    artifacts: Optional[list] = None,
    input_paths: Optional[list] = None,
    upload_refs: Optional[list] = None,
    urls: Optional[list] = None,
    context: Optional[str] = None,
    session_id: Optional[str] = None,
    response: Optional[str] = None,
    files: Optional[list] = None,
) -> dict:
    """Run any LikeMinds skill (background job + poll).

    First call: provide `skill` (any name from `list_skills`, e.g. 'kb-builder',
    'config-agent', 'generate-document') plus `client` and `workspace_id` — a durable
    per-client project key. Reuse the SAME client + workspace_id in a later chat to
    keep building the same deliverable: the skill sees the existing output (e.g. the
    KB) and EXTENDS it instead of starting over. Omit `workspace_id` to have one
    created and returned — store it and reuse it. `context` says WHAT to do (a prompt
    / SOW / instructions).

    Supplying artifacts (they live under the workspace and persist):
    - PREFERRED for shell clients (e.g. Claude Code): call `get_upload_ticket`, zip
      your artifacts folder, `curl` it to the returned upload_url, then pass the
      returned refs here in `upload_refs` with the SAME client + workspace_id. A
      `.zip` ref is expanded automatically (folder structure preserved).
    - `upload_file` — push a file by value (base64/chunked) when you cannot curl,
      then pass its ref in `upload_refs`.
    - `artifacts` / `files` — small inline text content ([{name, content}]).
    - `input_paths` — LOCAL paths; only work when the server shares your filesystem
      (dev / same box). On a remote server use the upload flow above instead.

    You get back `status: "running"` with a `session_id`. Then POLL: call again with
    ONLY that `session_id`. When status is `need_input`, show the `questions` to the
    user verbatim, wait for their reply, then call again with `session_id` +
    `response` (do NOT answer them yourself) and resume polling. Stop when status is
    `done` (a `download_url` is returned — give it to the user) or `error`.
    """
    # -------- continuation / poll on an existing run --------
    if session_id:
        sess = sessions.get_session(session_id)
        if sess is None:
            return {"status": "expired",
                    "message": "Session expired or invalid. Restart the skill."}
        if sess.status in ("done", "error"):
            return _snapshot(sess)
        # An ANSWER is a continuation carrying non-empty reply text OR files. A bare
        # session_id (or an empty response) is just a poll — it must NOT finish the
        # run. Only deliver a reply while the skill is actually waiting for one.
        allow_paths = bool(input_paths and config.ALLOW_INPUT_PATHS)
        has_answer = bool(
            (response and response.strip()) or files or artifacts or upload_refs or allow_paths
        )
        if has_answer and sess.status == "need_input":
            added = (
                engine._write_artifacts(sess.inputs_dir, artifacts)
                + engine._write_artifacts(sess.inputs_dir, files)
                + _stage_artifacts(sess, upload_refs)
            )
            if allow_paths:
                added += _copy_input_paths(sess.inputs_dir, input_paths)
            _deliver_reply(sess, engine.build_reply_message(response, added))
        await _wait_for_change(sess)
        return _snapshot(sess)

    # -------- first call: resolve identity + skill, claim the workspace, seed, start --------
    client = sessions.sanitize_id(client, fallback="default")
    workspace_id = sessions.sanitize_id(workspace_id, fallback=uuid.uuid4().hex[:12])
    skills_root = sessions.skills_dir(client, workspace_id)

    # Resolve against GLOBAL skills AND this workspace's own generated skills.
    entry = registry.resolve_skill(skill or "", skills_root)
    if entry is None:
        available = ", ".join(s["name"] for s in registry.list_skills(skills_root))
        return {"status": "error", "message": f"Unknown skill '{skill}'. Available: {available}"}

    key = sessions.workspace_key(client, workspace_id)
    sess = sessions.new_session(skill, client, workspace_id)
    if not sessions.try_claim_workspace(key, sess.id):
        # Another run is already writing this workspace's deliverable in place;
        # a second concurrent run would corrupt it. Clean up and report busy.
        sessions._SESSIONS.pop(sess.id, None)
        shutil.rmtree(sess.sandbox, ignore_errors=True)
        return {"status": "busy", "client": client, "workspace_id": workspace_id,
                "message": "This workspace already has a run in progress. Wait for it "
                           "to finish (or poll its session_id), then retry."}

    # A workspace-generated skill lives under the workspace, not .claude/ — materialize
    # it into .claude/ under a transient name for this run so `claude -p` can invoke it.
    if entry.get("scope") == "workspace":
        try:
            _install_generated_skill(sess, entry)
        except Exception as e:  # noqa: BLE001
            sessions.purge(sess)
            sessions._SESSIONS.pop(sess.id, None)
            return {"status": "error", "message": f"Could not load generated skill: {e}"}
    else:
        sess.invoke_name, sess.skill_kind = entry["name"], entry["kind"]

    engine._write_artifacts(sess.inputs_dir, artifacts)
    engine._write_artifacts(sess.inputs_dir, files)
    _stage_artifacts(sess, upload_refs)
    if input_paths and config.ALLOW_INPUT_PATHS:
        _copy_input_paths(sess.inputs_dir, input_paths)

    first_message = engine.build_first_message(skill, sess, urls, context)
    sess.task = asyncio.create_task(_drive(sess, first_message))
    await _wait_for_change(sess)
    return _snapshot(sess)


@mcp.tool()
async def get_upload_ticket(client: Optional[str] = None,
                            workspace_id: Optional[str] = None) -> dict:
    """Get a short-lived ticket to upload artifacts to a workspace over plain HTTP.

    Use this when you (a shell-capable client, e.g. Claude Code) have local files to
    send to a skill. Steps:
      1) Call this with the `client` + `workspace_id` you will run the skill under
         (reuse the same workspace_id across chats to keep building the same KB).
      2) Zip your artifacts folder and POST it to the returned `upload_url`:
             zip -r bundle.zip ./my-artifacts
             curl -H "Authorization: Bearer <upload_token>" \\
                  -F "file=@bundle.zip" <upload_url>
         Each file in the response has an `upload_ref`.
      3) Call `run_skill` with the SAME client + workspace_id and those refs in
         `upload_refs` (a `.zip` ref is expanded automatically).
    Returns {upload_url, upload_token, client, workspace_id, expires_in}."""
    client = sessions.sanitize_id(client, fallback="default")
    workspace_id = sessions.sanitize_id(workspace_id, fallback=uuid.uuid4().hex[:12])
    sessions.artifacts_dir(client, workspace_id).mkdir(parents=True, exist_ok=True)
    return {
        "upload_url": f"{config.PUBLIC_URL}/upload",
        "upload_token": _mint_upload_ticket(client, workspace_id),
        "client": client,
        "workspace_id": workspace_id,
        "expires_in": config.UPLOAD_TICKET_TTL,
    }


@mcp.tool()
async def upload_file(
    name: str,
    content: str,
    encoding: str = "utf-8",
    client: Optional[str] = None,
    workspace_id: Optional[str] = None,
    part: Optional[int] = None,
    total_parts: Optional[int] = None,
) -> dict:
    """Upload an artifact into a workspace by value — a fallback for clients that
    cannot POST to the /upload endpoint (e.g. no shell). Prefer get_upload_ticket +
    curl when you can. Streams to disk under the workspace's artifacts/ dir.

    Provide `content` as text, or base64 with encoding='base64' for binary. For a
    large file, send it in ordered chunks: call repeatedly with part=1..N and
    total_parts=N (same name); each chunk is appended. Reuse the SAME client +
    workspace_id you will run the skill under. Returns an `upload_ref` to pass to
    run_skill's `upload_refs`."""
    client = sessions.sanitize_id(client, fallback="default")
    workspace_id = sessions.sanitize_id(workspace_id, fallback=uuid.uuid4().hex[:12])
    rel = _safe_relpath(name)
    if rel is None:
        return {"error": "invalid filename"}
    try:
        data = base64.b64decode(content) if encoding == "base64" else content.encode("utf-8")
    except Exception as e:  # noqa: BLE001
        return {"error": f"could not decode content ({encoding}): {e}"}

    arts = sessions.artifacts_dir(client, workspace_id)
    dest = arts / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    append = bool(part and part > 1)
    existing = dest.stat().st_size if (append and dest.is_file()) else 0
    if existing + len(data) > config.MAX_FILE_BYTES:
        return {"error": f"file exceeds {config.MAX_FILE_BYTES // (1024*1024)} MB"}
    if _dir_size(arts) + len(data) > config.MAX_WORKSPACE_BYTES:
        return {"error": "workspace storage quota exceeded"}
    with dest.open("ab" if append else "wb") as f:
        f.write(data)
    complete = (part is None) or (total_parts is None) or (part >= total_parts)
    return {"upload_ref": str(rel), "name": rel.name, "client": client,
            "workspace_id": workspace_id, "bytes": dest.stat().st_size, "complete": complete}


@mcp.tool()
async def fetch_result(result_id: str) -> dict:
    """Fetch a finished deliverable as a base64 zip — a fallback for clients that
    cannot download from the `download_url`. Prefer the URL when you can open it."""
    name = Path(result_id).name
    if not name.endswith(".zip"):
        name += ".zip"
    path = config.DIST_DIR / name
    if not path.is_file():
        return {"error": "result not found or expired"}
    data = path.read_bytes()
    return {"name": name, "bytes": len(data), "encoding": "base64",
            "content_base64": base64.b64encode(data).decode()}


@mcp.tool()
async def list_skills(client: Optional[str] = None, workspace_id: Optional[str] = None) -> dict:
    """Return available skill names + one-line descriptions. Pass `client` +
    `workspace_id` to ALSO include the skills that workspace has generated (private to
    it — other tenants never see them)."""
    skills_root = None
    if client and workspace_id:
        skills_root = sessions.skills_dir(
            sessions.sanitize_id(client, fallback="default"),
            sessions.sanitize_id(workspace_id, fallback="ws"),
        )
    return {"skills": registry.list_skills(skills_root)}


# ----------------------------------------------------------------------------- #
# Plain-HTTP routes (mounted on the same app the reverse proxy fronts)
# ----------------------------------------------------------------------------- #

@mcp.custom_route("/upload", methods=["POST"])
async def http_upload(request: Request):
    """Multipart artifact upload. Auth by an upload ticket from get_upload_ticket
    (Bearer header). Streams each `file` part to the workspace artifacts dir."""
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth[:7].lower() == "bearer " else request.headers.get("x-upload-token", "")
    verified = _verify_upload_ticket(token)
    if not verified:
        return JSONResponse({"error": "invalid or expired upload ticket"}, status_code=401)
    client, workspace_id = verified
    dest_dir = sessions.artifacts_dir(client, workspace_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        form = await request.form()
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"could not parse multipart form: {e}"}, status_code=400)
    results = []
    try:
        for field in form.getlist("file"):
            if hasattr(field, "read") and hasattr(field, "filename"):
                results.append(await _save_upload_stream(field, dest_dir))
    except _UploadError as e:
        return JSONResponse({"error": e.message}, status_code=e.status)
    if not results:
        return JSONResponse({"error": "no 'file' part in multipart form"}, status_code=400)
    return JSONResponse({"client": client, "workspace_id": workspace_id, "uploads": results})


@mcp.custom_route("/download/{result_id}", methods=["GET"])
async def http_download(request: Request):
    """Serve a packaged deliverable zip. Usually short-circuited by the reverse proxy
    (alias to outputs/_dist/); this app route makes it work without a proxy too."""
    name = Path(request.path_params["result_id"]).name
    if not name.endswith(".zip"):
        name += ".zip"
    path = config.DIST_DIR / name
    if not path.is_file():
        return JSONResponse({"error": "not found or expired"}, status_code=404)
    return FileResponse(path, media_type="application/zip", filename=name)


@mcp.custom_route("/health", methods=["GET"])
async def http_health(request: Request):
    return JSONResponse({"status": "ok"})
