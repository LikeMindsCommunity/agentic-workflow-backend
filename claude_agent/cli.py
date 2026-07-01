"""CLI: run a Claude Code skill via the Claude Agent SDK.

Usage:
    python -m claude_agent <skill-name> [arguments...]

Example:
    python -m claude_agent platform-kb inputs/sample_artifacts inputs/docs

The SDK auto-loads slash commands from `.claude/commands/` (and skills from
`.claude/skills/`) when `setting_sources=["project"]` is set, so we trigger the
skill by issuing `/<skill-name> <args>` as the first user message.

Streams tool calls, tool outputs, thinking, and assistant text live.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

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

DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"
RESET = "\033[0m"


def _truncate(s: str, n: int = 400) -> str:
    s = str(s).replace("\n", " ")
    return s if len(s) <= n else s[:n] + "..."


def _load_input_config_prompt(path: str = "inputs/input_config.yaml") -> str:
    p = Path(path)
    if not p.exists():
        return ""
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return ""
    prompt = data.get("prompt") if isinstance(data, dict) else None
    return prompt.strip() if isinstance(prompt, str) else ""


def _build_options() -> ClaudeAgentOptions:
    kwargs = dict(
        cwd=os.getcwd(),
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


def _render_message(msg) -> None:
    """Print a single SDK message in a streaming-friendly format."""
    if isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):
                sys.stdout.write(block.text)
                sys.stdout.flush()
            elif isinstance(block, ThinkingBlock):
                print(f"\n{MAGENTA}[thinking]{RESET} {DIM}{_truncate(block.thinking, 400)}{RESET}")
            elif isinstance(block, ToolUseBlock):
                print()
                print(f"{CYAN}→ {block.name}{RESET} {DIM}{_truncate(block.input)}{RESET}")
        print()

    elif isinstance(msg, UserMessage):
        for block in msg.content if isinstance(msg.content, list) else []:
            if isinstance(block, ToolResultBlock):
                content = block.content
                if isinstance(content, list):
                    parts = []
                    for c in content:
                        if isinstance(c, dict):
                            parts.append(c.get("text", str(c)))
                        else:
                            parts.append(str(c))
                    content = "\n".join(parts)
                tag = "error" if block.is_error else "output"
                print(f"{YELLOW}← {tag}{RESET} {DIM}{_truncate(content, 600)}{RESET}")

    elif isinstance(msg, SystemMessage):
        if msg.subtype == "init":
            print(f"{DIM}[claude-agent] session ready{RESET}")

    elif isinstance(msg, ResultMessage):
        cost = getattr(msg, "total_cost_usd", None)
        turns = getattr(msg, "num_turns", None)
        bits = []
        if turns is not None:
            bits.append(f"{turns} turns")
        if cost is not None:
            bits.append(f"${cost:.4f}")
        if bits:
            print(f"{DIM}[claude-agent] turn complete: {', '.join(bits)}{RESET}")


async def run_loop(skill_name: str, user_arguments: str) -> None:
    options = _build_options()

    print(f"{GREEN}[claude-agent] running skill: /{skill_name}{RESET}")
    if user_arguments:
        print(f"{GREEN}[claude-agent] arguments: {user_arguments}{RESET}")
    print(f"{DIM}[claude-agent] type 'done' or Ctrl-D to exit{RESET}\n")

    config_prompt = _load_input_config_prompt()
    first_msg = f"/{skill_name} {user_arguments}".strip()
    if config_prompt:
        first_msg += (
            "\n\nThe following prompt was loaded from inputs/input_config.yaml — "
            "treat it as authoritative user guidance for this run:\n\n"
            + config_prompt
        )
        print(
            f"{DIM}[claude-agent] loaded prompt from inputs/input_config.yaml "
            f"({len(config_prompt)} chars){RESET}\n"
        )

    async with ClaudeSDKClient(options=options) as client:
        pending = first_msg
        while True:
            await client.query(pending)
            async for msg in client.receive_response():
                _render_message(msg)

            try:
                text = input(f"\n{GREEN}>{RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not text:
                continue
            if text.lower() in ("done", "exit"):
                return
            pending = text


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(prog="claude-agent")
    parser.add_argument(
        "skill",
        help="skill / slash command name (matches .claude/commands/<name>.md)",
    )
    parser.add_argument(
        "arguments",
        nargs=argparse.REMAINDER,
        help="passed as $ARGUMENTS to the slash command",
    )
    args = parser.parse_args()

    user_arguments = " ".join(args.arguments) if args.arguments else ""
    try:
        asyncio.run(run_loop(args.skill, user_arguments))
    except KeyboardInterrupt:
        print()
        sys.exit(130)


if __name__ == "__main__":
    main()
