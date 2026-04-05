"""
Scraper agent — discovers and scrapes relevant documentation.
"""
import json
import os

from claude_agent_sdk import query, ClaudeAgentOptions, ThinkingConfigAdaptive

import config
from agents.prompts import SCRAPER_SYSTEM_PROMPT
from utils.logging import log_message


async def run_scraper_agent(prompt: str) -> dict:
    """
    Discover and scrape all relevant documentation based on the user's prompt.
    Saves individual markdown files + _manifest.json to inputs/docs/scraped/.
    Returns the parsed manifest dict, or {} on failure.
    """
    os.makedirs(config.SCRAPED_DOCS_DIR, exist_ok=True)

    agent_prompt = f"""Here is what the user wants to build:

---
{prompt.strip()}
---

Your job: find and scrape all documentation that would be relevant for this task.
Save every page to: `{config.SCRAPED_DOCS_DIR}`
Follow your system prompt instructions exactly — sitemap first, then DOM discovery, then fetch each page.
"""

    async for message in query(
        prompt=agent_prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["WebFetch", "WebSearch", "Read", "Write", "Glob"] + config.PLAYWRIGHT_TOOLS,
            mcp_servers=config.PLAYWRIGHT_MCP_SERVER,
            cwd=config.BASE_DIR,
            system_prompt=SCRAPER_SYSTEM_PROMPT,
            permission_mode="bypassPermissions",
            include_partial_messages=True,
            thinking=ThinkingConfigAdaptive(type="adaptive"),
            env=config.SDK_ENV,
        ),
    ):
        log_message(message)

    manifest_path = os.path.join(config.SCRAPED_DOCS_DIR, "_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}
