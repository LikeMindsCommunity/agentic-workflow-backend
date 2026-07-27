"""FastMCP server: the client-facing tools `run_pipeline`, `list_pipelines`, `get_upload_url`.

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
  - done        : finished; EVERY produced artifact uploaded to R2 with presigned
                  download URLs.
  - error       : the run failed.

File input flow (remote clients):
  1. call get_upload_url(filename) -> {upload_url, r2_key}
  2. HTTP PUT file bytes to upload_url directly (server memory never touched)
  3. pass r2_key(s) to run_pipeline via r2_keys — server downloads into inputs dir

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

from . import config, db, engine, oauth, pipeline, registry, sessions, slack, storage

# Load .env when this module is imported directly. The `python -m likeminds_mcp`
# entrypoint also loads it before importing config, so R2 / other computed constants
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
# OAuth 2.1 (optional, MCP_OAUTH_ENABLED): when on, the SDK mounts /authorize, /token,
# /register, /revoke, both .well-known metadata docs, and bearer-validates every /mcp
# request; we supply the storage/identity half (oauth.provider), and the same Gupshup OTP
# page becomes the /authorize login UI. Requires Mongo + a public URL (the issuer). When
# off, the server keeps the header-based identity path (USER_ID_HEADER) unchanged.
_auth_provider = None
_auth_settings = None
if config.MCP_OAUTH_ENABLED:
    if not (config.USE_MONGO and config.PUBLIC_BASE_URL):
        raise RuntimeError(
            "MCP_OAUTH_ENABLED requires MONGODB_URI + MONGODB_DB_NAME and PUBLIC_BASE_URL."
        )
    from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions

    _auth_provider = oauth.provider
    _auth_settings = AuthSettings(
        issuer_url=config.PUBLIC_BASE_URL,
        resource_server_url=f"{config.PUBLIC_BASE_URL}/mcp",
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[config.OAUTH_SCOPE],
            default_scopes=[config.OAUTH_SCOPE],
        ),
        revocation_options=RevocationOptions(enabled=True),
        required_scopes=[config.OAUTH_SCOPE],
    )

mcp = FastMCP(
    "likeminds",
    host=config.HOST,
    port=config.PORT,
    stateless_http=True,
    json_response=True,
    auth_server_provider=_auth_provider,
    auth=_auth_settings,
)

# How long a single poll call waits for the job state to change before
# returning "running". Short, so each call returns promptly with fresh progress.
POLL_WAIT = 4

# The artifacts are the point of the run, so the done snapshot has to hand them over
# rather than describe them. Clients differ in what they can do with a URL, so this
# asks for the one thing every client can render (a link) and, where the client has
# a filesystem, the download too. EVERY entry gets a link — a compiled skill, its
# assets, and each KB file are all artifacts the user is entitled to, not internals.
DELIVERY_TEXT = (
    "The artifacts are ready — deliver them, don't just mention them. For EVERY entry in "
    "`download_urls` — every file, without exception — put a clickable markdown link in "
    "your reply labelled with the filename, e.g. [SOW.pdf](https://…), so the user can "
    "download it straight from the chat. When there are many files, group them under short "
    "headings (deliverable / skill / knowledge base) but do not drop, sample, or summarise "
    "any of them away; a file the user cannot click is a file they did not receive. If you "
    "can write files locally (Claude Code / CLI clients), also fetch each URL, save it into "
    "the user's working directory, and tell them the path. Never paste a bare presigned URL "
    "as plain text, never replace an artifact with a summary of it, and never tell the user "
    "to go find it on the server. Say that the links expire in "
    "`download_expires_in_seconds` and that they should re-run to get fresh ones after that."
)

PIPELINE_RELAY_TEXT = (
    "Show these question(s) to the user verbatim and wait for their reply. They may answer, or "
    "reply 'done' to stop and finish with whatever is complete. Then call run_pipeline again with "
    "ONLY this session_id and their `response` — do NOT pass pipeline_name (that would restart the "
    "pipeline instead of delivering the answer). To attach a file with the answer: call "
    "get_upload_url first, PUT the file to the returned upload_url, then pass the r2_key in "
    "`r2_keys` on the same run_pipeline call. Do NOT answer the question yourself."
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


def _register_skills(harvested: list[tuple[str, bytes]], tenant: Optional[str]) -> list[str]:
    """Auto-register any generated skills found in the harvested output — PRIVATELY to
    `tenant`.

    A generated skill is a directory containing a SKILL.md. Two shapes are handled:
      - nested: `<skill-name>/SKILL.md` (+ any sibling asset files under that folder) —
                the skill name is the folder name.
      - root:   a `SKILL.md` at the harvest root means the WHOLE harvest is one skill;
                the name comes from its frontmatter `name:` field.
    Each skill's FULL folder (SKILL.md plus all its assets, at any depth) is copied into
    .claude/skills/<clean>__u_<tenant>/ so ONLY that tenant sees it on the next call, and
    the folder is gitignored. The copied SKILL.md's `name:` frontmatter is rewritten to
    the owner-suffixed folder name so the spawned CLI resolves exactly this tenant's copy
    (several tenants may share the same clean name). Only the CLEAN names are returned.

    Registration requires a tenant: an anonymous run must NOT install a skill (a global
    install would leak it to every caller), so with tenant=None nothing is registered.
    Either way the caller still receives the skill files — registration installs a COPY
    and never consumes the harvest, so what the run produced is always delivered."""
    if not tenant:
        return []
    roots: dict[str, str] = {}   # path-prefix under the harvest -> CLEAN skill name
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
        folder = registry.owned_folder(clean, tenant)
        dest_root = config.SKILLS_DIR / folder
        for rel, content in harvested:
            if not rel.startswith(prefix):
                continue
            sub = rel[len(prefix):]
            out = dest_root / sub
            out.parent.mkdir(parents=True, exist_ok=True)
            if sub == "SKILL.md":  # the skill's own manifest: force the owner-suffixed name
                content = registry.rewrite_frontmatter_name(
                    content.decode("utf-8", "replace"), folder
                ).encode("utf-8")
            out.write_bytes(content)
        registered.append(clean)
        _gitignore_generated_skill(folder)
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
# Slack run feed
# ----------------------------------------------------------------------------- #

async def _notify_run(sess: sessions.Session) -> None:
    """Post the terminal state of a run to the Slack channel: who ran it, the skill, the
    session id, start/finish, and a download link per artifact. Reads everything off the
    finished session, so it works identically for a `done` and for any error path."""
    result = sess.result or {}
    files = (result.get("summary") or {}).get("files") or []
    registered = result.get("registered_skills") or []
    # The driver signed these seconds ago, so they need no re-signing here. "_error" is
    # its R2-upload-failed sentinel — a key, not a link: nothing reached the bucket, so
    # there is no URL to offer and the message names the files instead.
    urls = result.get("download_urls") or {}
    if "_error" in urls:
        urls = {}
    await slack.notify_skill_run(
        status=sess.status,
        skill=sess.skill,
        session_id=sess.id,
        result_id=sess.result_id,
        email=await db.get_email(sess.tenant),
        tenant=sess.tenant,
        started_at=sess.started_at,
        finished_at=sess.finished_at,
        files=files,
        download_urls=urls,
        registered_skills=registered,
        error=sess.error,
    )


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

            # emit: harvest the deliverable, promote it locally, upload to R2, register any
            # generated skills, then purge. Promoted to outputs/mcp/<result_id>/ and (when R2
            # is configured) uploaded for download; it survives the purge so the session can
            # be continued later under the same session_id.
            harvested = _harvest(sess.output_dir, sess.sandbox)
            names = _promote(sess.result_id, harvested)
            if config.USE_R2 and sess.r2_keys:
                storage.delete_inputs(sess.r2_keys)

            # Auto-register any generated skills. No skill shipped in this repo emits one
            # today — document-generator and find-bugs both read their KB at run time now —
            # so this path is currently unexercised, but it stays for caller-authored skills.
            # Registration installs a private, tenant-scoped COPY under .claude/skills;
            # it does not consume the harvest. Everything the run produced — a compiled
            # SKILL.md, its assets, a KB, a document — is still the caller's artifact and
            # is uploaded for download. The caller is the tenant who ran the job, so
            # handing them their own files back is not a leak, and a registered skill the
            # user cannot inspect or keep a copy of is a black box.
            registered = _register_skills(harvested, sess.tenant)
            deliverable = list(harvested)

            download_urls: dict = {}
            if config.USE_R2 and deliverable:
                try:
                    download_urls = storage.upload_outputs(sess.result_id, deliverable)
                except Exception as e:  # noqa: BLE001 — R2 failure must not lose the result
                    download_urls = {"_error": f"R2 upload failed: {e}"}
            sessions.purge(sess)
            sess.result = {
                "result_id": sess.result_id,
                "summary": {"files": names},
                **({"registered_skills": registered} if registered else {}),
                **({"download_urls": download_urls} if download_urls else {}),
            }
            sess.status = "done"
            return
    except asyncio.CancelledError:
        sessions.purge(sess)  # server shutdown / cancellation — clean up, then propagate
        raise
    except Exception as e:  # noqa: BLE001 — surface as a job error, never crash the loop
        sess.status = "error"
        sess.error = f"{type(e).__name__}: {e}"
        if config.USE_R2 and sess.r2_keys:
            storage.delete_inputs(sess.r2_keys)
        sessions.purge(sess)  # cleanup on the error path too
    finally:
        sess.finished = True
        sess.finished_at = time.time()
        # One notification hook for every terminal path (emit, timeout, nudge cap, or a
        # raised exception) — they all land here. Cancellation (server shutdown) leaves
        # the status non-terminal, so an interrupted run is not announced as an outcome.
        # Fire-and-forget: the client's poll must not wait on Slack.
        if sess.status in ("done", "error"):
            slack.fire(_notify_run(sess))


def _deliver_reply(sess: sessions.Session, msg: str) -> None:
    """Hand a reply to the background driver and wake it (same loop, no threads)."""
    sess.pending_reply = msg
    sess.status = "running"
    if sess.reply_event is not None:
        sess.reply_event.set()


# ----------------------------------------------------------------------------- #
# Per-request BYOK — the caller's Anthropic key, read fresh from the request header
# ----------------------------------------------------------------------------- #

def _client_api_key(ctx: Optional[Context]) -> Optional[str]:
    """The caller's Anthropic key from the request header (BYOK), or None.

    Read fresh from the live HTTP request on every call — never stored. Under the
    streamable-HTTP transport `ctx.request_context.request` is the Starlette request;
    under stdio (or if the context is unavailable) there is no request, so this
    returns None and the server falls back to its own .env creds. Read ONLY from
    config.API_KEY_HEADER (default `x-api-key`) — the `Authorization` header is reserved
    for the OAuth bearer token, so BYOK and OAuth ride on the request together without
    colliding. A `Bearer ` prefix on the x-api-key value itself is tolerated."""
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


def _tenant_token(ctx: Optional[Context]) -> Optional[str]:
    """The caller's raw login token from the request header (config.USER_ID_HEADER), or
    None. Read fresh per request under the streamable-HTTP transport, exactly like the
    BYOK key; resolved to a tenant via db.resolve_tenant. Never stored. Only used when
    OAuth is OFF — with OAuth on, identity comes from the bearer token instead."""
    if ctx is None:
        return None
    try:
        request = ctx.request_context.request
        val = request.headers.get(config.USER_ID_HEADER) if request is not None else None
    except Exception:  # noqa: BLE001 — no request context (e.g. stdio) => no token
        return None
    return (val or "").strip() or None


def _authed_user_id() -> Optional[str]:
    """The verified user id from the OAuth bearer token, when OAuth is enabled and the
    request carried a valid token (the SDK's bearer middleware has already validated it).
    None when OAuth is off or there is no auth context (e.g. a public route)."""
    try:
        from mcp.server.auth.middleware.auth_context import get_access_token
        at = get_access_token()
    except Exception:  # noqa: BLE001 — no auth context
        return None
    return getattr(at, "user_id", None) if at is not None else None


async def _resolve_tenant(ctx: Optional[Context]) -> Optional[str]:
    """The caller's tenant. With OAuth ON, it's the bearer token's verified user id (the
    middleware guarantees a valid token reached here). With OAuth OFF, it's the
    USER_ID_HEADER token, validated against Mongo when configured. Both normalize through
    db._tenant_key so a user keeps the SAME tenant across the header and OAuth paths."""
    uid = _authed_user_id()
    if uid:
        return db._tenant_key(uid)
    return await db.resolve_tenant(_tenant_token(ctx))


# ----------------------------------------------------------------------------- #
# Tools
# ----------------------------------------------------------------------------- #

@mcp.tool()
async def get_upload_url(filename: str) -> dict:
    """Get a presigned URL to upload a file directly to R2 storage.

    Call this BEFORE run_pipeline when you have a file to pass as input.
    Steps:
      1. Call get_upload_url(filename) -> {upload_url, r2_key}
      2. HTTP PUT the raw file bytes to upload_url (no auth header needed)
      3. Pass r2_key to run_pipeline via the `r2_keys` parameter

    This uploads directly from the client to R2 — the server never holds
    the file bytes in memory. The upload URL is valid for 5 minutes.
    """
    if not config.USE_R2:
        return {"error": "R2 is not configured on this server."}
    upload_url, r2_key = storage.presigned_put_url(filename)
    return {
        "upload_url": upload_url,
        "r2_key": r2_key,
        "instructions": "HTTP PUT your file bytes to upload_url, then pass r2_key to run_pipeline via r2_keys.",
    }


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
    r2_keys: Optional[list],
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

            # Resolve the skill entry in the caller's tenant scope
            entry = registry.resolve_skill(step_name, psess.tenant)
            if entry is None:
                raise RuntimeError(
                    f"Step {i + 1} skill '{step_name}' not found. "
                    f"Available: {', '.join(s['name'] for s in registry.list_skills(psess.tenant))}"
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
            sess.tenant = psess.tenant
            psess.current_skill_sess = sess

            # Decide whether the upstream KB is REFERENCED (kb=<canonical path>, read in
            # place) or STAGED (copied into inputs). Non-writeback pipelines reference it and
            # never duplicate it; the writeback pipeline still stages it (apply-fixes needs it
            # in inputs= to mirror changed files back). A prior NON-KB output is staged either
            # way.
            reference_kb, stage_prior, stage_seed = _kb_reference_for_step(psess, i)

            # Write inputs. Step 0 gets the caller's uploaded files (into inputs/, or into
            # inputs/generated/ in a seeded pipeline so the artifact under critique stays
            # separate). A later step gets the prior step's output copied in UNLESS that output
            # is the KB we chose to pass by reference. The seed is copied in only when it is
            # NOT being referenced (i.e. the writeback pipeline).
            if i == 0:
                if r2_keys and config.USE_R2:
                    sess.r2_keys.extend(r2_keys)
                    upload_dest = sess.inputs_dir / "generated" if psess.seed_result_id else sess.inputs_dir
                    upload_dest.mkdir(parents=True, exist_ok=True)
                    storage.download_inputs(r2_keys, upload_dest)
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
        urls = result.get("download_urls") or {}
        has_links = bool(urls) and "_error" not in urls
        if has_links and config.USE_R2:
            try:
                last_result_id = result.get("result_id", "")
                result = {**result, "download_urls": storage.output_urls(last_result_id, list(urls))}
            except Exception:  # noqa: BLE001
                pass
        delivery = DELIVERY_TEXT if has_links else "No download links produced."
        return {
            "status": "done",
            "pipeline": psess.pipeline_name,
            "steps_completed": len(psess.steps),
            **result,
            **({"download_expires_in_seconds": config.R2_URL_EXPIRY} if has_links else {}),
            # The pipeline session id is the one handle the user keeps; it comes AFTER **result so a
            # step's own result dict can never shadow it. No step/bucket ids are exposed — they are
            # recovered from this id server-side when a continuation seeds from it.
            "session_id": psess.id,
            "how_to_continue": _pipeline_continue_text(psess),
            "next_step": (
                "Pipeline complete. " + delivery
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
    r2_keys: Optional[list] = None,
    urls: Optional[list] = None,
    seed_session_id: Optional[str] = None,
    session_id: Optional[str] = None,
    response: Optional[str] = None,
    ctx: Optional[Context] = None,
) -> dict:
    client_key = _client_api_key(ctx)
    tenant = await _resolve_tenant(ctx)

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

        has_answer = bool((response and response.strip()) or r2_keys)
        if has_answer and psess.status == "need_input":
            psess.pending_reply = response or ""
            skill_sess = psess.current_skill_sess
            if skill_sess is not None:
                if r2_keys and config.USE_R2:
                    storage.download_inputs(r2_keys, skill_sess.inputs_dir)
            psess.reply_event.set()

        await _wait_for_change_pipeline(psess)
        return _pipeline_snapshot(psess)

    # RESUME: session_id + pipeline_name → restart from the failed step
    if session_id and pipeline_name:
        state = pipeline.load_state(session_id)
        if state is None:
            return {"status": "error", "message": f"No saved pipeline state for session_id '{session_id}'."}
        new_inputs = {"r2_keys": r2_keys, "urls": urls, "context": context}
        psess = pipeline.restore_pipeline_session(session_id, state, client_key, tenant, new_inputs)
        psess.task = asyncio.create_task(
            _drive_pipeline(psess, r2_keys, urls, context)
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
        "r2_keys": r2_keys or [],
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
            client_key, tenant, original_inputs,
        )
    else:
        psess = pipeline.new_pipeline_session(
            matched, client_key, tenant, original_inputs, seed_result_id=seed_result_id
        )
    psess.task = asyncio.create_task(
        _drive_pipeline(psess, r2_keys, urls, context)
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


# ----------------------------------------------------------------------------- #
# Browser-facing login (email OTP) — mounted on the same ASGI app as /mcp.
# Imported here, after `mcp` exists, so the routes attach to this instance.
# ----------------------------------------------------------------------------- #
from . import web  # noqa: E402

web.register(mcp)
