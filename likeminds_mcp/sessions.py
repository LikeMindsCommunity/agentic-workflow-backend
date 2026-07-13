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

import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .config import MAX_SESSIONS, PROJECT_ROOT, SESSIONS_DIR

# session_id -> Session. Single process keeps this authoritative. Terminal records
# are kept so a client's final poll can read the result, but _gc() caps the total by
# evicting the oldest FINISHED ones so the store can't grow without bound.
_SESSIONS: dict[str, "Session"] = {}


@dataclass
class Session:
    id: str
    skill: str                # the skill this session is running
    result_id: str            # stable deliverable id: "<skill>_<session-uuid>"
    sandbox: Path             # <project>/.sessions/<id>
    inputs_dir: Path          # <sandbox>/inputs
    output_dir: Path          # <sandbox>/output/<result_id>  (deliverable harvested from here)
    # Job state, polled by the client across short calls:
    status: str = "running"   # running | need_input | done | error
    progress: str = ""        # human-readable "what it's doing now", shown on poll
    nudges: int = 0           # how many no-signal turns we've nudged past
    questions: list = field(default_factory=list)
    r2_keys: list = field(default_factory=list)  # accumulated R2 input keys to delete on done/error
    result: dict | None = None        # {result_id, summary} once done
    error: str | None = None
    finished: bool = False            # the driving task has returned
    # async coordination — all on the server's single event loop (no threads):
    task: object = None               # asyncio.Task driving this session
    reply_event: object = None        # asyncio.Event — set when a reply is ready
    pending_reply: str = ""           # the reply handed to the driver


def new_session(skill: str) -> Session:
    sid = str(uuid.uuid4())          # valid UUID: required by `claude --session-id`
    result_id = f"{skill}_{sid}"     # stable deliverable id, derived from session UUID
    sandbox = SESSIONS_DIR / sid
    inputs_dir = sandbox / "inputs"
    output_dir = sandbox / "output" / result_id
    inputs_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    (sandbox / "work").mkdir(parents=True, exist_ok=True)
    sess = Session(id=sid, skill=skill, result_id=result_id, sandbox=sandbox,
                   inputs_dir=inputs_dir, output_dir=output_dir)
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
    so the client's terminal poll can still read status + result."""
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
