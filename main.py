"""
LikeMinds Layer 1 - Knowledge Base Builder

Uses the Claude Agentic SDK to orchestrate the KB build loop.
Claude agents handle all file I/O, web fetching, and generation.
Python orchestrates the loop and handles user interaction.

Flow:
  1. Read input_config.yaml + detect mode
  2. Draft agent  → reads inputs, writes KB file
  3. Interrogator → reads KB, returns gap JSON
  4. User Q&A     → collect URLs / files / text
  5. Enrichment   → reads KB + new info, writes updated KB
  6. Repeat 3-5 until ready or user types 'done'
"""
import anyio
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import config
from utils.file_loader import load_input_config, detect_input_mode
from agents.prompts import (
    ANALYZER_SYSTEM_PROMPT,
    ENRICHMENT_SYSTEM_PROMPT,
    INTERROGATOR_SYSTEM_PROMPT,
    MODE_INSTRUCTIONS,
    MODE_ADDITIONS,
)

try:
    from claude_agent_sdk import (
        query,
        ClaudeAgentOptions,
        AssistantMessage,
        UserMessage,
        ResultMessage,
        StreamEvent,
        TextBlock,
        ThinkingBlock,
        ToolUseBlock,
        ToolResultBlock,
        ThinkingConfigAdaptive,
    )
except ImportError:
    print("\n  [ERROR] claude-agent-sdk not installed.")
    print("  Run: pip install claude-agent-sdk\n")
    sys.exit(1)

# ---------------------------------------------------------------------------
# MCP: Playwright stealth browser — bypasses bot detection (Cloudflare, etc.)
# Uses rebrowser-playwright under the hood for fingerprint evasion.
# Requires Xvfb on Linux (runs headed for better stealth).
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
# Helpers
# ---------------------------------------------------------------------------

def get_safe_name(platform_name: str) -> str:
    return platform_name.lower().replace(" ", "_")[:30]


def get_latest_kb(safe_name: str) -> str | None:
    """Return path to the most recently modified KB file, or None."""
    out_dir = Path(config.OUTPUT_DIR)
    if not out_dir.exists():
        return None
    files = sorted(out_dir.glob(f"kb_{safe_name}_*.md"), key=os.path.getmtime, reverse=True)
    return str(files[0]) if files else None


def make_kb_path(safe_name: str, label: str) -> str:
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(config.OUTPUT_DIR, f"kb_{safe_name}_{label}_{ts}.md")


def count_dir_files(directory: str) -> int:
    """Count non-hidden files in a directory (non-recursive)."""
    if not os.path.isdir(directory):
        return 0
    return sum(
        1 for f in os.listdir(directory)
        if not f.startswith(".") and os.path.isfile(os.path.join(directory, f))
    )


def print_header():
    print("\n" + "=" * 60)
    print("  LikeMinds Layer 1 - Knowledge Base Builder")
    print("=" * 60)


def print_step(label: str):
    print(f"\n{'~' * 60}")
    print(f"  {label}")
    print(f"{'~' * 60}")


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
                    # Trim long thinking to first 300 chars so it doesn't swamp the terminal
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
            inp  = getattr(usage, "input_tokens", "?")
            out  = getattr(usage, "output_tokens", "?")
            cache_r = getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_w = getattr(usage, "cache_creation_input_tokens", 0) or 0
            print(
                f"\n  [done] tokens — in: {inp}  out: {out}"
                f"  cache_read: {cache_r}  cache_write: {cache_w}"
            )
        stop = getattr(message, "stop_reason", None)
        if stop and stop != "end_turn":
            print(f"  [stop_reason] {stop}")


# ---------------------------------------------------------------------------
# Agent: Draft
# ---------------------------------------------------------------------------

async def run_draft_agent(prompt: str, mode: str) -> tuple[str, str]:
    """
    Read all inputs and write the initial KB draft.
    Returns (saved_path, inferred_platform_name).
    """
    mode_instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS.get("prompt_only", ""))

    # Temporary output path - will rename after agent infers platform name
    temp_output = os.path.join(config.OUTPUT_DIR, "kb_draft_temp.md")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    agent_prompt = f"""Build a comprehensive knowledge base for a client's platform/domain based on their stated use case.

---

## Step 1 — Read config and understand the task

1. Read `inputs/input_config.yaml`. It contains a single `prompt` field with the user's natural language description.

2. From the prompt, intelligently infer:
   - **Platform/domain name** (e.g., "Exotel", "Twilio", "MoEngage", "Salesforce") — look for mentions like "for the X platform", "X workflows", etc.
   - **Use case** — what they want to achieve or automate with this KB
   - **Documentation URLs** — any http/https URLs mentioned in the prompt (you'll fetch these)

---

## Step 2 — Load inputs

### Sample/Reference Files
- Glob all files in `inputs/sample_artifacts/`
- Skip `.DS_Store` and hidden files
- Read each file. Note whether `.json` files are valid JSON or raw text.

### Documentation
- Read all `.md .txt .json .yaml .yml .xml .html` files from `inputs/docs/`
- Extract any URLs from the user's prompt. For each URL:
  1. Try `WebFetch` first (fast, no browser needed)
  2. If it returns a 403/404 error or empty content, use the stealth browser:
     a. Call `mcp__playwright__playwright_custom_user_agent` first
     b. Call `mcp__playwright__playwright_navigate` — if it times out (30s), call it again immediately; the second attempt succeeds because the Cloudflare cookie is already set from the first attempt
     c. Call `mcp__playwright__playwright_get_visible_text` to extract the page text
     d. **Validate the page loaded correctly**: if the visible text contains "Page not found", "404", "This page doesn't exist", or is fewer than 200 characters — the page is dead, skip it and do not use its content
- When discovering links to follow: navigate through **category/section pages** (URLs containing `/sections/` or `/categories/`) rather than jumping directly to article IDs. Section pages list all current valid articles. Avoid hardcoding or guessing article IDs — only follow URLs you explicitly found in visible page text.
- When following links: extract href attribute values from the visible text and call `mcp__playwright__playwright_navigate` directly on each URL — do NOT use `mcp__playwright__playwright_click` for navigation as element selectors are unreliable on Cloudflare-protected pages
- After every `mcp__playwright__playwright_navigate` call, check the first 300 characters of `mcp__playwright__playwright_get_visible_text` output. If it contains "Page not found", "404", or similar — skip this URL entirely and move to the next one

Input mode: **{mode}**

---

## Step 3 — Write the KB

Write the complete knowledge base document following the KB Structure in your system prompt.

**IMPORTANT:** Start your KB with this HTML comment containing the platform name you inferred:
```
<!-- PLATFORM: Your Inferred Platform Name -->
```

Stream your output directly — write each section as you go.

{mode_instruction}

Save the completed document to: `{temp_output}`

Use the Write tool to save the final complete document. Do NOT ask for confirmation — just write it.
"""

    async for message in query(
        prompt=agent_prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Glob", "Write", "WebFetch", "WebSearch"] + PLAYWRIGHT_TOOLS,
            mcp_servers=PLAYWRIGHT_MCP_SERVER,
            cwd=config.BASE_DIR,
            system_prompt=ANALYZER_SYSTEM_PROMPT,
            permission_mode="bypassPermissions",
            include_partial_messages=True,
            thinking=ThinkingConfigAdaptive(type="adaptive"),
        ),
    ):
        log_message(message)

    # Extract platform name from the KB file the agent wrote
    if os.path.exists(temp_output):
        with open(temp_output, "r") as f:
            first_lines = f.read(500)
            match = re.search(r'<!--\s*PLATFORM:\s*(.+?)\s*-->', first_lines)
            platform_name = match.group(1) if match else "Unknown Platform"
    else:
        platform_name = "Unknown Platform"

    # Rename to proper path with platform name
    safe_name = get_safe_name(platform_name)
    final_path = make_kb_path(safe_name, "draft")
    if os.path.exists(temp_output):
        os.rename(temp_output, final_path)

    print(f"\n  Inferred Platform: {platform_name}")
    print(f"  Draft saved: {final_path}")
    return final_path, safe_name


# ---------------------------------------------------------------------------
# Agent: Interrogator
# ---------------------------------------------------------------------------

async def run_interrogator_agent(kb_path: str, mode: str) -> dict:
    """Read the KB and return knowledge gap areas as a parsed dict."""
    mode_addition = MODE_ADDITIONS.get(mode, "")
    system_prompt = INTERROGATOR_SYSTEM_PROMPT + mode_addition
    max_areas = config.MAX_AREAS_PER_ROUND

    prompt = f"""Read the knowledge base file at: `{kb_path}`

Identify where information is missing **from the perspective of successfully executing the use case described in the KB's Overview section**.

Group related unknowns into **{max_areas} knowledge areas maximum**. Do NOT list individual field-level questions — group related gaps so the client can respond with a single doc, URL, or explanation.

If there are no blocking gaps and no more than 2 minor important gaps that are already acknowledged in Known Gaps → set ready_for_generation to true.

Return ONLY valid JSON (no markdown fences, no extra text):
{{
  "summary": "2-3 sentence assessment of the KB state",
  "ready_for_generation": true or false,
  "areas": [
    {{
      "id": "a1",
      "priority": "blocking | important | nice_to_have",
      "title": "Short descriptive title",
      "what_we_have": "What the KB currently documents about this area",
      "what_we_need": "What is missing and why it affects the use case — be specific about what is unknown",
      "suggested_sources": "Type of doc/URL/explanation that would fill this gap"
    }}
  ]
}}
"""

    result_text = ""
    last_text_block = ""  # fallback: SDK sometimes returns empty ResultMessage.result
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep"],
            cwd=config.BASE_DIR,
            system_prompt=system_prompt,
            include_partial_messages=True,
            thinking=ThinkingConfigAdaptive(type="adaptive"),
        ),
    ):
        log_message(message)
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text:
                    last_text_block = block.text  # keep the last substantive text
        elif isinstance(message, ResultMessage):
            result_text = message.result or ""

    # Fall back to the last TextBlock if ResultMessage.result came back empty
    if not result_text.strip() and last_text_block.strip():
        result_text = last_text_block

    # Strip markdown fences if the model wraps the JSON
    result_text = result_text.strip()
    if result_text.startswith("```"):
        lines = result_text.splitlines()
        lines = lines[1:] if lines[0].startswith("```") else lines
        lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
        result_text = "\n".join(lines)

    # If there's prose before the JSON object, skip to the opening brace
    brace_start = result_text.find("{")
    if brace_start > 0:
        result_text = result_text[brace_start:]

    # raw_decode parses exactly one JSON value and ignores any trailing prose
    parsed, _ = json.JSONDecoder().raw_decode(result_text)
    return parsed


# ---------------------------------------------------------------------------
# Agent: Enrichment
# ---------------------------------------------------------------------------

async def run_enrichment_agent(
    kb_path: str,
    user_input: str,
    safe_name: str,
    round_num: int,
) -> str:
    """Update the KB with new information. Returns the path of the updated file."""
    output_path = make_kb_path(safe_name, f"r{round_num}")

    prompt = f"""Update the knowledge base with new information collected from the user.

---

## Current KB

Read the current KB from: `{kb_path}`

---

## User's response to identified gaps

{user_input.strip()}

---

## How to process the response

Parse the user's response naturally:
- **URL** (starts with `http`) → fetch each one. Try `WebFetch` first; if it returns a 403/empty response, use the stealth browser: call `mcp__playwright__playwright_custom_user_agent` first, then `mcp__playwright__playwright_navigate` (if it times out, call navigate again immediately — the second attempt works because the Cloudflare cookie is already set), then `mcp__playwright__playwright_get_visible_text`. After navigating, validate the page loaded: if visible text contains "Page not found", "404", or fewer than 200 characters — skip it. Never use `mcp__playwright__playwright_click` for navigation — extract href values from visible text and navigate directly.
- **`file`** → glob and read `inputs/docs/`. Load any files not yet covered in the KB. If nothing new, note that.
- **Text explanation** → use it as-is to fill the relevant gaps.

---

## How to update the KB

1. Read the current KB from `{kb_path}`
2. Process all new information from the user's response
3. Rewrite the KB incorporating everything new:
   - Integrate new doc content into the relevant sections
   - Remove `> **Needs Verification:**` callouts where new info confirms the detail
   - Add new subsections if new material reveals undocumented areas
   - Update **Known Gaps**: remove resolved gaps, keep unresolved ones
   - Write with authority where new docs confirm — no hedging
   - Keep the `<!-- PLATFORM: ... -->` comment at the top
4. Save the complete updated KB to: `{output_path}`

Do NOT ask for confirmation — just read, update, and write.
"""

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Glob", "Write", "WebFetch", "WebSearch"] + PLAYWRIGHT_TOOLS,
            mcp_servers=PLAYWRIGHT_MCP_SERVER,
            cwd=config.BASE_DIR,
            system_prompt=ENRICHMENT_SYSTEM_PROMPT,
            permission_mode="bypassPermissions",
            include_partial_messages=True,
            thinking=ThinkingConfigAdaptive(type="adaptive"),
        ),
    ):
        log_message(message)

    print(f"\n  Enrichment saved: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# CLI: display gaps and collect user responses
# ---------------------------------------------------------------------------

def display_areas(areas_data: dict):
    print(f"\n{'=' * 60}")
    print("  KNOWLEDGE BASE ASSESSMENT")
    print(f"{'=' * 60}")
    print(f"\n  {areas_data.get('summary', '')}")
    ready = areas_data.get("ready_for_generation", False)
    print(f"\n  Ready for Use: {'YES ✓' if ready else 'NO'}")

    areas = areas_data.get("areas", [])
    if not areas:
        print("\n  No gaps identified.")
        return

    priority_groups = [
        ("BLOCKING — use case cannot proceed without this", "blocking"),
        ("IMPORTANT — affects correctness", "important"),
        ("NICE TO HAVE — completeness", "nice_to_have"),
    ]
    for group_label, priority in priority_groups:
        group = [a for a in areas if a.get("priority") == priority]
        if not group:
            continue
        print(f"\n  --- {group_label} ---")
        for a in group:
            print(f"\n    [{a['id']}] {a['title']}")
            print(f"         We have: {a.get('what_we_have', '')}")
            print(f"         We need: {a.get('what_we_need', '')}")
            print(f"         Source:  {a.get('suggested_sources', '')}")


def collect_user_input() -> tuple[str, bool]:
    """
    Collect free-form user input after gaps are displayed.
    Returns (user_input, user_done).
    user_done=True when the user typed 'done' — caller should skip enrichment.

    The raw input is passed directly to the enrichment agent, which handles
    URL fetching, file reading, and text incorporation itself.
    """
    print(f"\n{'~' * 60}")
    print("  Paste a URL, type 'file' if you dropped docs into inputs/docs/,")
    print("  explain in plain text, or type 'done' to finish.")
    print("  (Enter once to submit. For multi-line input, end with a blank line.)")
    print(f"{'~' * 60}\n")

    lines = []
    while True:
        try:
            line = input("  > ").strip()
        except EOFError:
            break
        if line.lower() == "done":
            return "", True
        if not line:
            if lines:
                break
            # First input is blank — prompt again, don't hang
            continue
        lines.append(line)
        # Peek: if next char would be a newline (single-line input), auto-submit
        # by breaking after the first non-empty line unless user continues typing
        break

    # If user continued past first line, collect remaining lines until blank
    while lines:
        try:
            line = input("  > ").strip()
        except EOFError:
            break
        if not line:
            break
        if line.lower() == "done":
            return "", True
        lines.append(line)

    return "\n".join(lines), False


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def main():
    print_header()

    cfg = load_input_config()
    prompt = cfg.get("prompt", "")

    if not prompt:
        print("\n  [ERROR] No prompt found in input_config.yaml")
        sys.exit(1)

    mode = detect_input_mode(config.ARTIFACTS_DIR, config.DOCS_DIR, prompt)

    artifact_count = count_dir_files(config.ARTIFACTS_DIR)
    doc_count = count_dir_files(config.DOCS_DIR)

    print(f"\n  Mode     : {mode}")
    print(f"  Artifacts: {artifact_count}")
    print(f"  Docs     : {doc_count} local")
    print(f"\n  User Prompt Preview:")
    print(f"  {prompt[:150]}{'...' if len(prompt) > 150 else ''}\n")

    if mode == "empty":
        print(
            "\n  [ERROR] No inputs found. Provide a prompt in input_config.yaml"
            " and/or add files to inputs/sample_artifacts/ or inputs/docs/"
        )
        sys.exit(1)

    # Phase detection: start a fresh draft (platform name inferred by agent)
    print_step("Draft Phase")
    print("  Running Draft Agent...")
    start = time.time()
    kb_path, safe_name = await run_draft_agent(prompt, mode)
    print(f"  Draft completed in {time.time() - start:.1f}s")

    # Refinement loop — runs until ready_for_generation, no areas, or user types 'done'
    round_num = 0
    while True:
        round_num += 1
        print_step(f"Gap Analysis — Round {round_num}")

        print("  Running Interrogator Agent...")
        start = time.time()
        try:
            areas_data = await run_interrogator_agent(kb_path, mode)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"\n  [ERROR] Interrogator returned invalid output: {e}")
            retry = input("  Retry this round? (y/n): ").strip().lower()
            if retry == "y":
                round_num -= 1
                continue
            break

        print(f"  Interrogator completed in {time.time() - start:.1f}s")
        display_areas(areas_data)

        if areas_data.get("ready_for_generation"):
            print("\n  Knowledge base is READY for use.")
            break

        if not areas_data.get("areas"):
            print("\n  No gaps found.")
            break

        # Collect loop — re-present until something is provided or user types 'done'
        while True:
            user_input, user_done = collect_user_input()

            if user_done:
                break

            if user_input.strip():
                break

            # Nothing provided — prompt and collect again (same round, no re-interrogation)
            print("\n  Nothing provided. Type 'done' to finish, or share info for one of the areas above.")

        if user_done:
            break

        print_step(f"Enrichment — Round {round_num}")
        print("  Running Enrichment Agent...")
        start = time.time()
        kb_path = await run_enrichment_agent(
            kb_path, user_input, safe_name, round_num
        )
        print(f"  Enrichment completed in {time.time() - start:.1f}s")
        # immediately loop back to interrogator — no confirmation prompt

    # Final save
    final_path = make_kb_path(safe_name, "FINAL")
    content = Path(kb_path).read_text(encoding="utf-8")
    Path(final_path).write_text(content, encoding="utf-8")

    # Extract platform name from final KB
    match = re.search(r'<!--\s*PLATFORM:\s*(.+?)\s*-->', content[:500])
    platform_name = match.group(1) if match else safe_name

    verifications = content.lower().count("needs verification")

    print(f"\n{'=' * 60}")
    print(f"  Platform       : {platform_name}")
    print(f"  Mode           : {mode}")
    print(f"  Rounds         : {round_num}")
    print(f"  Output         : {final_path}")
    print(f"  Remaining gaps : {verifications} 'Needs Verification' items")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    anyio.run(main)
