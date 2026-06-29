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

from .config import PROJECT_ROOT, SESSIONS_DIR
from .harness import HARNESS
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
    # Job state, polled by the client across short calls:
    status: str = "running"   # running | need_input | onboarded | error
    progress: str = ""        # human-readable "what it's doing now", shown on poll
    questions: list = field(default_factory=list)
    result: dict | None = None        # {kb_id, summary} once onboarded
    error: str | None = None
    busy: bool = False                 # a turn is currently executing
    task: object = None                # the asyncio.Task running the current turn
    connected: bool = False
    round_index: int = 0


def _build_options(sandbox: Path) -> ClaudeAgentOptions:
    """Options for the server-side Claude running one skill session.

    cwd is the PROJECT ROOT so the SDK can load `.claude/commands/*.md`; the skill
    is told (via the harness + its argument) to confine working files to the
    sandbox. The harness is appended to the default Claude Code system prompt.
    """
    import os

    kwargs = dict(
        cwd=str(PROJECT_ROOT),
        setting_sources=["project"],
        permission_mode="bypassPermissions",
        system_prompt={"type": "preset", "preset": "claude_code", "append": HARNESS},
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

    client = ClaudeSDKClient(options=_build_options(sandbox))
    sess = Session(id=sid, skill=skill, client=client, sandbox=sandbox,
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
        shutil.rmtree(sess.sandbox, ignore_errors=True)
