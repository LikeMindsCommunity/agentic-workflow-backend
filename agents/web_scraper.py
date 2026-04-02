"""
Web Scraper Agent — Crawls documentation sites and saves content as markdown files.

Can be used:
  1. As a pre-step in the KB pipeline (main.py)
  2. Standalone via CLI: python -m agents.web_scraper "https://docs.example.com"
  3. Via Claude Code: /web-scrape
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import anyio

# Allow running as standalone module
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from agents.prompts import WEB_SCRAPER_SYSTEM_PROMPT

try:
    from claude_agent_sdk import (
        query,
        ClaudeAgentOptions,
        AssistantMessage,
        ResultMessage,
        TextBlock,
        ThinkingBlock,
        ToolUseBlock,
        ThinkingConfigAdaptive,
    )
except ImportError:
    print("\n  [ERROR] claude-agent-sdk not installed.")
    print("  Run: pip install claude-agent-sdk\n")
    sys.exit(1)


# ---------------------------------------------------------------------------
# MCP: same stealth playwright config as main.py
# ---------------------------------------------------------------------------
PLAYWRIGHT_MCP_SERVER = {
    "playwright": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@pvinis/playwright-stealth-mcp-server"],
    }
}

PLAYWRIGHT_TOOLS = [
    "mcp__playwright__playwright_custom_user_agent",
    "mcp__playwright__playwright_navigate",
    "mcp__playwright__playwright_get_visible_text",
    "mcp__playwright__playwright_get_visible_html",
    "mcp__playwright__playwright_click",
    "mcp__playwright__playwright_scroll",
    "mcp__playwright__playwright_screenshot",
    "mcp__playwright__playwright_close",
]

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_MAX_PAGES = 30
DEFAULT_OUTPUT_DIR = os.path.join(config.INPUT_DIR, "docs", "scraped")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_1) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/73.0.3683.75 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Logging (same pattern as main.py)
# ---------------------------------------------------------------------------
def _format_tool_args(name: str, args: dict) -> str:
    for key in ("path", "file_path", "url", "pattern", "command", "query"):
        if key in args:
            return str(args[key])
    if args:
        return str(next(iter(args.values())))
    return ""


def log_message(message, verbose: bool = False) -> None:
    verbose = verbose or os.environ.get("CLAUDE_VERBOSE", "") == "1"

    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, ThinkingBlock):
                if verbose:
                    preview = (block.thinking or "")[:300].replace("\n", " ")
                    if len(block.thinking or "") > 300:
                        preview += "…"
                    print(f"  [think] {preview}")
            elif isinstance(block, TextBlock):
                if verbose:
                    preview = (block.text or "")[:200].replace("\n", " ")
                    if len(block.text or "") > 200:
                        preview += "…"
                    print(f"  [text]  {preview}")
            elif isinstance(block, ToolUseBlock):
                arg = _format_tool_args(block.name, block.input)
                print(f"  ⎿  {block.name}({arg})")

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


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
async def run_web_scraper_agent(
    urls: list[str],
    output_dir: str = DEFAULT_OUTPUT_DIR,
    max_pages: int = DEFAULT_MAX_PAGES,
    user_agent: str = DEFAULT_USER_AGENT,
    context_hint: str = "",
) -> dict:
    """
    Scrape documentation from the given URLs and save as markdown files.

    Args:
        urls: Seed URLs to start crawling from.
        output_dir: Where to save scraped markdown files.
        max_pages: Maximum number of pages to scrape.
        user_agent: Browser user agent string.
        context_hint: Optional context about what kind of docs to prioritize
                      (e.g., "MoEngage SDK integration for push notifications").

    Returns:
        Parsed manifest dict, or empty dict if manifest couldn't be read.
    """
    os.makedirs(output_dir, exist_ok=True)

    url_list = "\n".join(f"- {url}" for url in urls)
    context_block = f"\n\n**Context:** {context_hint}\nPrioritize pages most relevant to this context." if context_hint else ""

    prompt = f"""Scrape documentation from these seed URLs and save all useful content as markdown files.

## Seed URLs

{url_list}

## Configuration

- **Output directory:** `{output_dir}`
- **Max pages:** {max_pages}
- **User agent:** `{user_agent}`
{context_block}

## Instructions

1. Set the browser user agent to the one specified above.
2. Start with each seed URL. Try `WebFetch` first — if it fails (403, empty), use the stealth browser.
3. From each page, extract internal documentation links and follow them (up to {max_pages} pages total).
4. For each page with substantive content, save a markdown file to `{output_dir}/<slug>.md`.
5. After scraping all reachable pages (or hitting the {max_pages} limit), write `{output_dir}/_manifest.json`.
6. Close the browser when done.

Prioritize API references, SDK docs, schema docs, and developer guides over marketing content.
"""

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=[
                "Read", "Glob", "Write", "WebFetch", "WebSearch",
            ] + PLAYWRIGHT_TOOLS,
            mcp_servers=PLAYWRIGHT_MCP_SERVER,
            cwd=config.BASE_DIR,
            system_prompt=WEB_SCRAPER_SYSTEM_PROMPT,
            permission_mode="bypassPermissions",
            include_partial_messages=True,
            thinking=ThinkingConfigAdaptive(type="adaptive"),
        ),
    ):
        log_message(message)

    # Read manifest if it was created
    manifest_path = os.path.join(output_dir, "_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            return json.load(f)

    return {}


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------
async def _cli_main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Scrape documentation from URLs and save as markdown files."
    )
    parser.add_argument(
        "urls",
        nargs="+",
        help="One or more seed URLs to scrape.",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--max-pages", "-m",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help=f"Maximum pages to scrape (default: {DEFAULT_MAX_PAGES})",
    )
    parser.add_argument(
        "--context", "-c",
        default="",
        help="Context hint for prioritizing content (e.g., 'push notification SDK integration')",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  Web Scraper Agent")
    print("=" * 60)
    print(f"\n  URLs:       {', '.join(args.urls)}")
    print(f"  Output:     {args.output_dir}")
    print(f"  Max pages:  {args.max_pages}")
    if args.context:
        print(f"  Context:    {args.context}")
    print()

    start = time.time()
    manifest = await run_web_scraper_agent(
        urls=args.urls,
        output_dir=args.output_dir,
        max_pages=args.max_pages,
        context_hint=args.context,
    )
    elapsed = time.time() - start

    print(f"\n{'=' * 60}")
    if manifest:
        print(f"  Pages scraped: {manifest.get('pages_scraped', '?')}")
        print(f"  Pages failed:  {manifest.get('pages_failed', '?')}")
        print(f"  Files saved:   {len(manifest.get('files', []))}")
    else:
        print("  Warning: No manifest file was created.")
    print(f"  Time:          {elapsed:.1f}s")
    print(f"  Output:        {args.output_dir}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    anyio.run(_cli_main)
