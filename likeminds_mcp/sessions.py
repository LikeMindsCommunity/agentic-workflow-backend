"""In-process session store and per-session sandbox.

For the local MVP a session is a LIVE `ClaudeSDKClient` parked in a dict between
round-trips, plus its sandbox directory. The client stays connected while the
skill waits for the user's answer; a continuation call sends the reply to the
same client. This is single-process only (no horizontal scaling, lost on
restart) — the productionization path swaps this for SDK `resume` + shared
storage, per the LLD.
"""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from . import profiles, registry
from .config import PROJECT_ROOT, SESSIONS_DIR
from .harness import harness_for
from .signals import build_signals_server

# session_id -> Session. Single worker keeps this authoritative.
_SESSIONS: dict[str, "Session"] = {}


@dataclass
class Session:
    id: str
    skill: str                # the command this session is running
    client: ClaudeSDKClient
    sandbox: Path             # <project>/.sessions/<id>
    inputs_dir: Path          # <sandbox>/inputs
    output_dir: Path          # <sandbox>/output  (final deliverable harvested from here)
    mode: str = "oneshot"     # engine mode (from the skill's profile)
    interlock: bool = False   # require ask_user before emit_result?
    # Job state, polled by the client across short calls:
    status: str = "running"   # running | need_input | onboarded | error
    progress: str = ""        # human-readable "what it's doing now", shown on poll
    asked: bool = False       # has ask_user been called at least once this session?
    questions: list = field(default_factory=list)
    result: dict | None = None        # {kb_id, summary} once onboarded
    error: str | None = None
    busy: bool = False                 # a turn is currently executing
    connected: bool = False
    round_index: int = 0
    # The skill runs in its OWN thread + event loop so it never blocks the MCP
    # server's main loop. These connect the two:
    thread: object = None              # threading.Thread running the skill
    worker_loop: object = None         # the worker thread's asyncio loop
    reply_event: object = None         # asyncio.Event (on worker loop) — reply ready
    pending_reply: str = ""            # the reply message handed to the worker


def _build_options(sandbox: Path, harness_text: str) -> ClaudeAgentOptions:
    """Options for the server-side Claude running one skill session.

    cwd is the SANDBOX, so any relative/scratch file the skill writes stays inside
    the session (and is purged with it) instead of leaking into the project root.
    The project's `.claude` is symlinked into the sandbox (see new_session) so the
    SDK still loads the skills + playbook library from cwd/.claude.
    """
    import os

    kwargs = dict(
        cwd=str(sandbox),
        setting_sources=["project"],
        permission_mode="bypassPermissions",
        system_prompt={"type": "preset", "preset": "claude_code", "append": harness_text},
        mcp_servers={"signals": build_signals_server()},
        allowed_tools=[
            "Read",
            "Write",
            "Edit",
            "Bash",
            "Glob",
            "Grep",
            "WebFetch",
            "WebSearch",
            "TodoWrite",
            "Skill",
            "mcp__signals__ask_user",
            "mcp__signals__emit_result",
        ],
    )
    # Pick the model. Explicit CLAUDE_AGENT_MODEL wins. On Azure Foundry the CLI's
    # default (a newer sonnet) may not be on the deployment, so fall back to the
    # configured deployment name (e.g. claude-sonnet-4-5).
    model = os.environ.get("CLAUDE_AGENT_MODEL")
    if not model and os.environ.get("CLAUDE_CODE_USE_FOUNDRY"):
        model = os.environ.get("AZURE_AI_DEPLOYMENT") or "claude-sonnet-4-5"
    if model:
        kwargs["model"] = model
    return ClaudeAgentOptions(**kwargs)


def new_session(skill: str) -> Session:
    sid = "ses_" + uuid.uuid4().hex[:16]
    sandbox = SESSIONS_DIR / sid
    inputs_dir = sandbox / "inputs"
    output_dir = sandbox / "output"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    (sandbox / "work").mkdir(parents=True, exist_ok=True)

    # Symlink the project's .claude into the sandbox so the SDK loads skills +
    # playbooks from cwd/.claude while cwd stays the sandbox (contains scratch).
    link = sandbox / ".claude"
    if not link.exists():
        try:
            link.symlink_to(PROJECT_ROOT / ".claude", target_is_directory=True)
        except (OSError, NotImplementedError):
            pass

    # Resolve the skill's engine mode → harness variant + interlock.
    entry = registry.resolve_skill(skill) or {}
    mode = entry.get("mode", profiles.DEFAULT_MODE)
    prof = entry.get("profile") or profiles.profile_for(mode)
    harness_text = harness_for(prof["harness"])

    client = ClaudeSDKClient(options=_build_options(sandbox, harness_text))
    sess = Session(id=sid, skill=skill, mode=mode, interlock=prof["interlock"],
                   client=client, sandbox=sandbox,
                   inputs_dir=inputs_dir, output_dir=output_dir)
    _SESSIONS[sid] = sess
    return sess


def get_session(session_id: str) -> Session | None:
    return _SESSIONS.get(session_id)


async def close_session(sess: Session) -> None:
    """Disconnect the live client and delete its sandbox so the raw client inputs
    are purged (the retention guarantee). The lightweight Session record is KEPT in
    the store so the client's terminal poll can still read status + result; only the
    live client and on-disk sandbox are released. Call AFTER harvesting outputs."""
    try:
        if sess.connected:
            await sess.client.disconnect()
    finally:
        sess.connected = False
        # Remove the .claude symlink first so rmtree can never follow it into the
        # real project .claude, then delete the sandbox.
        link = sess.sandbox / ".claude"
        if link.is_symlink():
            link.unlink(missing_ok=True)
        shutil.rmtree(sess.sandbox, ignore_errors=True)
