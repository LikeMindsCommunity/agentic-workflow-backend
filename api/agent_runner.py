"""Background asyncio task that owns one ClaudeSDKClient.

Pulls user messages from an inbox queue, drains the SDK's response stream into
a callback that the SessionManager turns into SSE events.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Awaitable, Callable

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)


EventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


def build_options(cwd: str | None = None) -> ClaudeAgentOptions:
    kwargs: dict[str, Any] = dict(
        cwd=cwd or os.getcwd(),
        setting_sources=["user", "project"],
        permission_mode="bypassPermissions",
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
            "mcp__*",
        ],
    )
    model = os.environ.get("CLAUDE_AGENT_MODEL")
    if model:
        kwargs["model"] = model
    return ClaudeAgentOptions(**kwargs)


def _tool_input_preview(value: Any, limit: int = 600) -> Any:
    if isinstance(value, (dict, list)):
        return value
    s = str(value)
    return s if len(s) <= limit else s[:limit] + "..."


def _tool_result_to_text(content: Any, limit: int = 1200) -> str:
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict):
                parts.append(c.get("text", str(c)))
            else:
                parts.append(str(c))
        text = "\n".join(parts)
    else:
        text = str(content)
    return text if len(text) <= limit else text[:limit] + "..."


class AgentRunner:
    """Owns one ClaudeSDKClient session for the lifetime of a Session."""

    _STOP = object()

    def __init__(self, on_event: EventCallback, cwd: str | None = None):
        self._on_event = on_event
        self._cwd = cwd
        self._inbox: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._turn_count = 0

    @property
    def turns(self) -> int:
        return self._turn_count

    def start(self, first_message: str) -> None:
        self._inbox.put_nowait(first_message)
        self._task = asyncio.create_task(self._run(), name="agent-runner")

    async def send(self, text: str) -> None:
        await self._inbox.put(text)

    async def stop(self) -> None:
        await self._inbox.put(self._STOP)
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except asyncio.TimeoutError:
                self._task.cancel()

    async def _run(self) -> None:
        try:
            async with ClaudeSDKClient(options=build_options(cwd=self._cwd)) as client:
                while True:
                    item = await self._inbox.get()
                    if item is self._STOP:
                        break
                    text: str = item  # type: ignore[assignment]
                    self._turn_count += 1
                    await self._on_event(
                        "turn_start",
                        {"turn": self._turn_count, "user_text": text},
                    )
                    await client.query(text)
                    async for msg in client.receive_response():
                        await self._dispatch(msg)
                    await self._on_event("turn_end", {"turn": self._turn_count})
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — surface to caller as event
            await self._on_event("error", {"message": f"{type(exc).__name__}: {exc}"})
        finally:
            await self._on_event("session_closed", {})

    async def _dispatch(self, msg: Any) -> None:
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    await self._on_event("assistant_text", {"text": block.text})
                elif isinstance(block, ThinkingBlock):
                    await self._on_event("thinking", {"text": block.thinking})
                elif isinstance(block, ToolUseBlock):
                    await self._on_event(
                        "tool_use",
                        {
                            "id": block.id,
                            "name": block.name,
                            "input": _tool_input_preview(block.input),
                        },
                    )
        elif isinstance(msg, UserMessage):
            content = msg.content if isinstance(msg.content, list) else []
            for block in content:
                if isinstance(block, ToolResultBlock):
                    await self._on_event(
                        "tool_result",
                        {
                            "tool_use_id": block.tool_use_id,
                            "is_error": bool(block.is_error),
                            "output": _tool_result_to_text(block.content),
                        },
                    )
        elif isinstance(msg, SystemMessage):
            if msg.subtype == "init":
                await self._on_event("system_init", {})
        elif isinstance(msg, ResultMessage):
            await self._on_event(
                "result",
                {
                    "turns": getattr(msg, "num_turns", None),
                    "cost_usd": getattr(msg, "total_cost_usd", None),
                },
            )
