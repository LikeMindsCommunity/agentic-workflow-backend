"""
Agent message logging utilities.
"""
import os

from claude_agent_sdk import (
    AssistantMessage,
    UserMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    ToolResultBlock,
)


def _format_tool_args(name: str, args: dict) -> str:
    """Return the most display-worthy argument for a tool call."""
    for key in ("path", "file_path", "url", "pattern", "command", "query"):
        if key in args:
            return str(args[key])
    if args:
        return str(next(iter(args.values())))
    return ""


def log_message(message, verbose: bool = False) -> None:
    """Print agent activity to stdout in CLI style.

    verbose=True  → also prints ThinkingBlock summaries and TextBlock previews.
    verbose=False → only tool calls, tool errors, and result stats (default).
    Set CLAUDE_VERBOSE=1 in env to enable at runtime.
    """
    verbose = verbose or os.environ.get("CLAUDE_VERBOSE", "") == "1"

    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, ThinkingBlock):
                if verbose:
                    thinking_preview = (block.thinking or "")[:300].replace("\n", " ")
                    if len(block.thinking or "") > 300:
                        thinking_preview += "…"
                    print(f"  [think] {thinking_preview}")
            elif isinstance(block, TextBlock):
                if verbose:
                    text_preview = (block.text or "")[:200].replace("\n", " ")
                    if len(block.text or "") > 200:
                        text_preview += "…"
                    print(f"  [text]  {text_preview}")
            elif isinstance(block, ToolUseBlock):
                arg = _format_tool_args(block.name, block.input)
                print(f"  ⎿  {block.name}({arg})")

    elif isinstance(message, UserMessage):
        if isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    if block.is_error:
                        print(f"  [tool error] {block.content}")
                    elif verbose:
                        result_preview = str(block.content or "")[:120].replace("\n", " ")
                        print(f"  [tool ok]   {result_preview}")

    elif isinstance(message, ResultMessage):
        usage = getattr(message, "usage", None)
        if usage:
            inp = getattr(usage, "input_tokens", "?")
            out = getattr(usage, "output_tokens", "?")
            cache_r = getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_w = getattr(usage, "cache_creation_input_tokens", 0) or 0
            print(
                f"\n  [done] tokens — in: {inp}  out: {out}"
                f"  cache_read: {cache_r}  cache_write: {cache_w}"
            )
        stop = getattr(message, "stop_reason", None)
        if stop and stop != "end_turn":
            print(f"  [stop_reason] {stop}")
