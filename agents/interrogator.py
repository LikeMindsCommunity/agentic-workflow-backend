"""
Interrogator agent — reads the KB and returns knowledge gap areas.
"""
import json

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ThinkingConfigAdaptive,
)

import config
from agents.prompts import INTERROGATOR_SYSTEM_PROMPT, MODE_ADDITIONS
from utils.logging import log_message


async def run_interrogator_agent(kb_path: str, mode: str) -> dict:
    """Read the KB and return knowledge gap areas as a parsed dict."""
    mode_addition = MODE_ADDITIONS.get(mode, "")
    system_prompt = INTERROGATOR_SYSTEM_PROMPT(config.MAX_AREAS_PER_ROUND) + mode_addition

    result_text = ""
    last_text_block = ""
    async for message in query(
        prompt=f"Read the knowledge base at: `{kb_path}`",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Write", "WebFetch", "WebSearch"] + config.PLAYWRIGHT_TOOLS,
            mcp_servers=config.PLAYWRIGHT_MCP_SERVER,
            cwd=config.BASE_DIR,
            system_prompt=system_prompt,
            include_partial_messages=True,
            thinking=ThinkingConfigAdaptive(type="adaptive"),
            env=config.SDK_ENV,
        ),
    ):
        log_message(message)
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text:
                    last_text_block = block.text
        elif isinstance(message, ResultMessage):
            result_text = message.result or ""

    if not result_text.strip() and last_text_block.strip():
        result_text = last_text_block

    result_text = result_text.strip()
    if result_text.startswith("```"):
        lines = result_text.splitlines()
        lines = lines[1:] if lines[0].startswith("```") else lines
        lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
        result_text = "\n".join(lines)

    brace_start = result_text.find("{")
    if brace_start > 0:
        result_text = result_text[brace_start:]

    parsed, _ = json.JSONDecoder().raw_decode(result_text)
    return parsed
