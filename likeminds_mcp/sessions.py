"""In-process session records for the resume-per-turn engine.

A session is now a LIGHTWEIGHT record: an id (a real UUID, reused as Claude Code's
own session id for `--session-id` / `--resume`), a sandbox on disk, and the job
state polled by the client. There is NO live SDK client, worker thread, or event
loop parked between turns — Claude Code's on-disk session store carries the
conversation, and each turn is a fresh `claude -p` subprocess. That makes the store
cheap to hold, survivable across a server restart, and free of the cross-loop and
leak hazards of the previous parked-client design.
"""

from __future__ import annotations

import re
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .config import MAX_SESSIONS, PROJECT_ROOT, SESSIONS_DIR, WORKSPACES_ROOT

# session_id -> Session. Single process keeps this authoritative. Terminal records
# are kept so a client's final poll can read the result, but _gc() caps the total by
# evicting the oldest FINISHED ones so the store can't grow without bound.
_SESSIONS: dict[str, "Session"] = {}

# One active run per workspace: workspace_key -> session_id currently running.
# A workspace's KB dir is written in place (extend, never clobber), so two
# concurrent runs on the same workspace would corrupt it. Claim on start, release
# on any terminal path. Plain sync dict ops — safe on the single event loop.
_WORKSPACE_BUSY: dict[str, str] = {}


# --------------------------------------------------------------------------- #
# Tenant identity + persistent workspace paths
# --------------------------------------------------------------------------- #

_ID_OK = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_id(value: str | None, *, fallback: str) -> str:
    """Make a caller-supplied client / workspace id safe to embed in a path.
    Strips separators and any char outside [A-Za-z0-9._-], collapses leading dots
    (so no '..' traversal and no hidden-dir names), and falls back if empty."""
    raw = (value or "").strip()
    cleaned = _ID_OK.sub("-", raw).lstrip(".")
    return cleaned or fallback


def workspace_key(client: str, workspace_id: str) -> str:
    return f"{client}/{workspace_id}"


def workspace_root(client: str, workspace_id: str) -> Path:
    return WORKSPACES_ROOT / client / workspace_id


def kb_dir(client: str, workspace_id: str) -> Path:
    return workspace_root(client, workspace_id) / "kb"


def artifacts_dir(client: str, workspace_id: str) -> Path:
    return workspace_root(client, workspace_id) / "artifacts"


def skills_dir(client: str, workspace_id: str) -> Path:
    """Persistent per-workspace store for skills this workspace GENERATED (e.g. a
    find-bugs-<client> command produced by generate-find-bugs-skill). Indexed by the
    registry only for THIS client+workspace, so a generated skill is private to the
    workspace that made it — never visible or runnable for other tenants."""
    return workspace_root(client, workspace_id) / "skills"


def try_claim_workspace(key: str, session_id: str) -> bool:
    """Reserve a workspace for one live run. False if another live session holds it."""
    holder = _WORKSPACE_BUSY.get(key)
    if holder and holder != session_id and holder in _SESSIONS and not _SESSIONS[holder].finished:
        return False
    _WORKSPACE_BUSY[key] = session_id
    return True


def release_workspace(key: str, session_id: str) -> None:
    """Release a workspace claim, but only if this session still holds it."""
    if _WORKSPACE_BUSY.get(key) == session_id:
        _WORKSPACE_BUSY.pop(key, None)


@dataclass
class Session:
    id: str
    skill: str                # the skill/command this session is running
    client: str               # tenant label (sanitized)
    workspace_id: str         # durable per-client project id (sanitized)
    workspace_key: str        # f"{client}/{workspace_id}" — the concurrency lock key
    sandbox: Path             # <project>/.sessions/<id>  (ephemeral; purged per run)
    inputs_dir: Path          # <sandbox>/inputs
    output_dir: Path          # PERSISTENT: WORKSPACES_ROOT/<client>/<ws>/kb (survives purge)
    artifacts_dir: Path       # PERSISTENT: WORKSPACES_ROOT/<client>/<ws>/artifacts
    skills_dir: Path          # PERSISTENT: WORKSPACES_ROOT/<client>/<ws>/skills (generated skills)
    # How to invoke the skill this turn (differs for a workspace-generated skill,
    # which is materialized into .claude/ under a transient name just for the run):
    invoke_name: str = ""             # the /command or skill name to actually invoke
    skill_kind: str = "command"       # "command" | "skill"
    installed_skill_path: object = None   # Path we JIT-installed into .claude/ (removed on purge)
    installed_skill_is_dir: bool = False  # True if the install was an agent-skill folder
    # Job state, polled by the client across short calls:
    status: str = "running"   # running | need_input | done | error
    progress: str = ""        # human-readable "what it's doing now", shown on poll
    nudges: int = 0           # how many no-signal turns we've nudged past
    questions: list = field(default_factory=list)
    result: dict | None = None        # {result_id, summary} once done
    error: str | None = None
    finished: bool = False            # the driving task has returned
    # async coordination — all on the server's single event loop (no threads):
    task: object = None               # asyncio.Task driving this session
    reply_event: object = None        # asyncio.Event — set when a reply is ready
    pending_reply: str = ""           # the reply handed to the driver


def new_session(skill: str, client: str, workspace_id: str) -> Session:
    sid = str(uuid.uuid4())          # valid UUID: required by `claude --session-id`
    sandbox = SESSIONS_DIR / sid     # ephemeral: inputs + scratch, purged after the run
    inputs_dir = sandbox / "inputs"
    # The deliverable dir is PERSISTENT and lives OUTSIDE the sandbox, keyed by the
    # workspace. A prior run's KB is already here on a repeat run, so the skill's own
    # existing-KB check (recognize.md: "check output= override") flips it to an
    # update run — this is what carries context across separate chats. purge() only
    # deletes the sandbox, so the KB and artifacts survive.
    output_dir = kb_dir(client, workspace_id)
    arts_dir = artifacts_dir(client, workspace_id)
    skl_dir = skills_dir(client, workspace_id)
    inputs_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    arts_dir.mkdir(parents=True, exist_ok=True)
    skl_dir.mkdir(parents=True, exist_ok=True)
    (sandbox / "work").mkdir(parents=True, exist_ok=True)
    sess = Session(
        id=sid, skill=skill, client=client, workspace_id=workspace_id,
        workspace_key=workspace_key(client, workspace_id),
        sandbox=sandbox, inputs_dir=inputs_dir,
        output_dir=output_dir, artifacts_dir=arts_dir, skills_dir=skl_dir,
        invoke_name=skill, skill_kind="command",
    )
    _SESSIONS[sid] = sess
    _gc()
    return sess


def _gc() -> None:
    """Evict oldest FINISHED session records once the store exceeds MAX_SESSIONS.
    Live (unfinished) sessions are never evicted. Dict insertion order = age."""
    if len(_SESSIONS) <= MAX_SESSIONS:
        return
    for sid, s in list(_SESSIONS.items()):
        if len(_SESSIONS) <= MAX_SESSIONS:
            break
        if s.finished:
            del _SESSIONS[sid]


def get_session(session_id: str) -> Session | None:
    return _SESSIONS.get(session_id)


def purge(sess: Session) -> None:
    """Delete the on-disk sandbox (raw caller inputs) and best-effort remove Claude
    Code's transcript for this session — the retention guarantee. Safe to call on
    ANY terminal path (done OR error). The tiny Session record is kept in the store
    so the client's terminal poll can still read status + result.

    Note: the PERSISTENT workspace (kb/ + artifacts/) lives outside the sandbox and
    is deliberately NOT deleted — that is what carries the KB across chats. Only the
    ephemeral sandbox and the transcript go. The workspace concurrency claim is
    released here since this is a terminal path."""
    release_workspace(sess.workspace_key, sess.id)
    # Remove any workspace-generated skill we materialized into .claude/ for this run
    # (kept under a transient name so it never leaks to other tenants or lingers).
    if sess.installed_skill_path is not None:
        p = Path(sess.installed_skill_path)
        if sess.installed_skill_is_dir:
            shutil.rmtree(p, ignore_errors=True)
        else:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
        sess.installed_skill_path = None
    shutil.rmtree(sess.sandbox, ignore_errors=True)
    _purge_transcript(sess.id)


def _purge_transcript(session_id: str) -> None:
    """Best-effort deletion of Claude Code's on-disk transcript for this session.

    CC stores sessions at ~/.claude/projects/<slug>/<uuid>.jsonl, where <slug> is
    the project cwd with path separators replaced by '-'. Best-effort: the layout
    can vary by CC version, so any failure here is swallowed."""
    try:
        slug = str(PROJECT_ROOT).replace("/", "-")
        base = Path.home() / ".claude" / "projects" / slug
        for p in (base / f"{session_id}.jsonl", base / session_id):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
    except Exception:  # noqa: BLE001 — retention cleanup is best-effort
        pass
