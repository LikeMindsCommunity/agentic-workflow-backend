"""The engine: drive a live ClaudeSDKClient until it hits a signal tool.

run_until_signal consumes one full turn of the SDK stream and reports the first
`ask_user` / `emit_result` call it sees. Real tools (Read/Write/Bash/web/Skill)
are executed by the SDK itself; the engine only watches for the two signals.
"""

from __future__ import annotations

from pathlib import Path

from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock

from .config import ASK_USER_TOOL, EMIT_RESULT_TOOL
from .sessions import Session


def _write_artifacts(inputs_dir: Path, artifacts: list | None) -> list[str]:
    """Persist client text artifacts as files in the session inputs directory.
    Returns the names of the files written."""
    written = []
    for art in artifacts or []:
        if not isinstance(art, dict):
            continue
        name = art.get("name")
        content = art.get("content")
        if not name or content is None:
            continue
        dest = inputs_dir / Path(name).name  # flatten; no path traversal
        dest.write_text(str(content), encoding="utf-8")
        written.append(dest.name)
    return written


def build_first_message(
    skill: str, sess: Session, urls: list | None, context: str | None
) -> str:
    """The slash-command invocation that seeds the skill.

    $ARGUMENTS gets the inputs directory first (the skill reads materials there),
    then any URLs. Context is appended as guidance.
    """
    parts = [f"/{skill} {sess.inputs_dir}"]
    if urls:
        parts.append(" ".join(str(u) for u in urls))
    msg = " ".join(parts).strip()
    if context:
        msg += f"\n\nAdditional context from the client:\n{context}"
    return msg


def build_reply_message(response: str | None, added_files: list[str]) -> str:
    """The user's answer to the open questions, for a continuation call.
    `added_files` are filenames the user just provided (already in the inputs dir)."""
    msg = (response or "").strip()
    if added_files:
        msg += (
            "\n\nThe user provided the following file(s) to answer the gaps; they "
            "are now in your inputs directory: " + ", ".join(added_files) + ".\n"
            "READ each of these files in full now and use their contents to resolve "
            "the open gaps and enrich the KB. Do NOT finalize (emit_result) until "
            "you have read and incorporated them. After incorporating, re-assess "
            "gaps and either ask the user about anything still unresolved, or finish."
        )
    if not msg:
        msg = "done"
    return msg


# The Agent SDK has no `tool_choice: "any"`, so the model may end a turn with a
# plain text message (e.g. a "draft complete" summary) instead of calling a signal
# tool. When that happens we nudge it to proceed and run another turn, rather than
# treating the silent turn as a failure. This emulates the LLD's forced tool call.
MAX_CONTINUES = 12
NUDGE = (
    "Your turn ended without calling ask_user or emit_result. Do not stop here. "
    "If any blocking/important gaps or unconfirmed assumptions remain, call "
    "ask_user now with the verbatim gap block. If the deliverable in the output/ "
    "directory is complete and no blocking/important gaps remain, call emit_result "
    "now. Otherwise keep working — but you MUST end by calling ask_user or "
    "emit_result."
)


def _describe(block: ToolUseBlock) -> str | None:
    """A short, human-readable description of what a tool call is doing, for the
    live progress shown to the client on each poll. None = not worth surfacing."""
    name = block.name
    inp = block.input or {}
    base = lambda k: Path(str(inp.get(k, ""))).name
    if name in ("Write", "Edit"):
        return f"Writing {base('file_path')}"
    if name == "Read":
        return f"Reading {base('file_path')}"
    if name == "Bash":
        return f"Running: {str(inp.get('command', ''))[:60]}"
    if name == "WebSearch":
        return f"Web search: {str(inp.get('query', ''))[:60]}"
    if name == "WebFetch":
        return f"Fetching {str(inp.get('url', ''))[:60]}"
    if name in ("Glob", "Grep"):
        return "Searching files"
    if name.startswith("mcp__signals__"):
        return None  # a signal, not progress
    return None


async def _consume_turn(sess: Session) -> dict | None:
    """Consume one SDK turn; return the first signal seen, or None if the turn
    ended without calling ask_user / emit_result. Updates sess.progress as it goes."""
    signal: dict | None = None
    async for msg in sess.client.receive_response():
        if not isinstance(msg, AssistantMessage):
            continue
        for block in msg.content:
            if isinstance(block, TextBlock):
                line = block.text.strip().split("\n")[0]
                if line:
                    sess.progress = line[:160]
                continue
            if not isinstance(block, ToolUseBlock):
                continue
            desc = _describe(block)
            if desc:
                sess.progress = desc
            if signal is not None:
                continue  # keep the first signal of the turn
            if block.name == ASK_USER_TOOL:
                signal = {"kind": "ask", "questions": block.input.get("questions", [])}
            elif block.name == EMIT_RESULT_TOOL:
                signal = {"kind": "emit", "files": block.input.get("files", [])}
    return signal


async def run_until_signal(sess: Session) -> dict | None:
    """Run turns until the model calls ask_user or emit_result. If a turn ends
    without a signal, nudge the model and continue (up to MAX_CONTINUES) instead of
    failing. Returns the signal, or None only if the model never signals after
    repeated nudges.

    Returns {"kind": "ask", "questions": [...]} or {"kind": "emit", "files": [...]}.
    """
    for _ in range(MAX_CONTINUES):
        signal = await _consume_turn(sess)
        if signal is not None:
            return signal
        await sess.client.query(NUDGE)
    return None
