"""
Draft agent — reads all inputs and writes the initial KB draft.
"""
import os
import re

from claude_agent_sdk import query, ClaudeAgentOptions, ThinkingConfigAdaptive

import config
from agents.prompts import ANALYZER_SYSTEM_PROMPT, MODE_INSTRUCTIONS
from utils.kb_utils import get_safe_name, make_kb_path
from utils.logging import log_message


async def run_draft_agent(prompt: str, mode: str) -> tuple[str, str]:
    """
    Read all inputs and write the initial KB draft.
    Returns (saved_path, inferred_safe_name).
    """
    mode_instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS.get("prompt_only", ""))
    system_prompt = ANALYZER_SYSTEM_PROMPT + f"\n\n## Mode-specific approach\n\n{mode_instruction}"

    temp_output = os.path.join(config.OUTPUT_DIR, "kb_draft_temp.md")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    agent_prompt = f"Input mode: **{mode}**\nOutput path: `{temp_output}`"

    async for message in query(
        prompt=agent_prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Glob", "Write", "WebFetch", "WebSearch"],
            cwd=config.BASE_DIR,
            system_prompt=system_prompt,
            permission_mode="bypassPermissions",
            include_partial_messages=True,
            thinking=ThinkingConfigAdaptive(type="adaptive"),
            env=config.SDK_ENV,
        ),
    ):
        log_message(message)

    if os.path.exists(temp_output):
        with open(temp_output, "r") as f:
            first_lines = f.read(500)
            match = re.search(r'<!--\s*PLATFORM:\s*(.+?)\s*-->', first_lines)
            platform_name = match.group(1) if match else "Unknown Platform"
    else:
        platform_name = "Unknown Platform"

    safe_name = get_safe_name(platform_name)
    final_path = make_kb_path(safe_name, "draft")
    if os.path.exists(temp_output):
        os.rename(temp_output, final_path)

    print(f"\n  Inferred Platform: {platform_name}")
    print(f"  Draft saved: {final_path}")
    return final_path, safe_name
