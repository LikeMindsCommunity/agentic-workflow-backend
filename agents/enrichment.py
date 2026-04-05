"""
Enrichment agent — updates the KB with new information from the user.
"""
from claude_agent_sdk import query, ClaudeAgentOptions, ThinkingConfigAdaptive

import config
from agents.prompts import ENRICHMENT_SYSTEM_PROMPT
from utils.kb_utils import make_kb_path
from utils.logging import log_message


async def run_enrichment_agent(
    kb_path: str,
    user_input: str,
    safe_name: str,
    round_num: int,
) -> str:
    """Update the KB with new information. Returns the path of the updated file."""
    output_path = make_kb_path(safe_name, f"r{round_num}")

    prompt = f"""Current KB: `{kb_path}`
Output path: `{output_path}`

User's response to the identified gaps:

{user_input.strip()}
"""

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Glob", "Write", "WebFetch", "WebSearch"] + config.PLAYWRIGHT_TOOLS,
            mcp_servers=config.PLAYWRIGHT_MCP_SERVER,
            cwd=config.BASE_DIR,
            system_prompt=ENRICHMENT_SYSTEM_PROMPT,
            permission_mode="bypassPermissions",
            include_partial_messages=True,
            thinking=ThinkingConfigAdaptive(type="adaptive"),
            env=config.SDK_ENV,
        ),
    ):
        log_message(message)

    print(f"\n  Enrichment saved: {output_path}")
    return output_path
