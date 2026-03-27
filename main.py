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
import sys
import time
from datetime import datetime
from pathlib import Path

import config
from utils.file_loader import load_input_config, detect_input_mode
from agents.prompts import (
    ANALYZER_SYSTEM_PROMPT,
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
        TextBlock,
        ToolUseBlock,
        ToolResultBlock,
    )
except ImportError:
    print("\n  [ERROR] claude-agent-sdk not installed.")
    print("  Run: pip install claude-agent-sdk\n")
    sys.exit(1)


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


def log_message(message) -> None:
    """Print agent activity to stdout in CLI style."""
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, ToolUseBlock):
                arg = _format_tool_args(block.name, block.input)
                print(f"  ⎿  {block.name}({arg})")
            elif isinstance(block, TextBlock):
                text = block.text.strip()
                if text:
                    print(f"     {text}")
    elif isinstance(message, UserMessage):
        if isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, ToolResultBlock) and block.is_error:
                    print(f"  [tool error] {block.content}")


# ---------------------------------------------------------------------------
# Agent: Draft
# ---------------------------------------------------------------------------

async def run_draft_agent(cfg: dict, mode: str) -> str:
    """Read all inputs and write the initial KB draft. Returns the saved path."""
    platform_name = cfg["platform_name"]
    safe_name = get_safe_name(platform_name)
    scope = cfg.get("scope", "")
    doc_urls = cfg.get("doc_urls") or []
    output_path = make_kb_path(safe_name, "draft")

    doc_urls_block = (
        "\n".join(f"  - {u}" for u in doc_urls) if doc_urls else "  (none)"
    )
    mode_instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["full"])

    prompt = f"""Build a knowledge base for the **{platform_name}** platform.

Input mode: **{mode}**

Steps:
1. Read `inputs/input_config.yaml` for scope and context.
2. Glob and read every file in `inputs/sample_artifacts/`
   (skip `.DS_Store` and any hidden files).
3. Read every `.md .txt .json .yaml .yml .xml .html` file in `inputs/docs/`.
4. Fetch each of these documentation URLs using WebFetch:
{doc_urls_block}
5. Write the complete knowledge base to: `{output_path}`

Scope / requirements:
{scope}

Mode-specific instructions:
{mode_instruction}

Write section by section. Use the Write tool to save the final complete
document to `{output_path}`.
"""

    print(f"\n  Output path: {output_path}\n")

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Glob", "Write", "WebFetch"],
            cwd=config.BASE_DIR,
            system_prompt=ANALYZER_SYSTEM_PROMPT,
            permission_mode="acceptEdits",
        ),
    ):
        log_message(message)

    print(f"\n  Draft saved: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Agent: Interrogator
# ---------------------------------------------------------------------------

async def run_interrogator_agent(kb_path: str, mode: str) -> dict:
    """Read the KB and return knowledge gap areas as a parsed dict."""
    mode_addition = MODE_ADDITIONS.get(mode, "")
    system_prompt = INTERROGATOR_SYSTEM_PROMPT + mode_addition
    max_areas = config.MAX_AREAS_PER_ROUND

    prompt = f"""Read the knowledge base file at: `{kb_path}`

Identify up to {max_areas} knowledge areas where information is missing.
Group related gaps — do NOT list individual field-level questions.

Return ONLY valid JSON (no markdown fences, no extra text):
{{
  "summary": "2-3 sentence assessment of the KB state",
  "ready_for_generation": true or false,
  "areas": [
    {{
      "id": "a1",
      "priority": "blocking",
      "title": "Short descriptive title",
      "what_we_have": "What the KB currently documents about this area",
      "what_we_need": "What is missing and why it affects artifact file generation",
      "suggested_sources": "Type of doc/URL/explanation that would fill this gap"
    }}
  ]
}}
"""

    result_text = ""
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["Read"],
            cwd=config.BASE_DIR,
            system_prompt=system_prompt,
        ),
    ):
        log_message(message)
        if isinstance(message, ResultMessage):
            result_text = message.result  # capture before generator exhausts

    # Strip markdown fences if the model wraps the JSON
    result_text = result_text.strip()
    if result_text.startswith("```"):
        lines = result_text.splitlines()
        lines = lines[1:] if lines[0].startswith("```") else lines
        lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
        result_text = "\n".join(lines)

    return json.loads(result_text)


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

    prompt = f"""Update the knowledge base at: `{kb_path}`

The user provided this response to the identified gaps:
{user_input.strip()}

Steps:
1. Read the current KB from `{kb_path}`
2. Process the user's response:
   - If it contains URLs (starting with http), fetch each one with WebFetch
   - If it says "file", glob and read any files in `inputs/docs/` not yet covered in the KB
   - Any other text is a direct explanation — use it as-is
3. Rewrite the KB incorporating all new information:
   - Integrate new content into relevant sections
   - Remove `> **Needs Verification:**` callouts where new info confirms details
   - Add new subsections if new material reveals undocumented areas
   - Update Known Gaps: remove resolved gaps, keep unresolved ones
   - Write with authority where new docs confirm — no hedging
4. Save the complete updated KB to: `{output_path}`
"""

    print(f"\n  Output path: {output_path}\n")

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Write", "WebFetch"],
            cwd=config.BASE_DIR,
            system_prompt=ANALYZER_SYSTEM_PROMPT,
            permission_mode="acceptEdits",
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
    print(f"\n  Ready for Generation: {'YES ✓' if ready else 'NO'}")

    areas = areas_data.get("areas", [])
    if not areas:
        print("\n  No gaps identified.")
        return

    priority_groups = [
        ("BLOCKING — cannot generate without this", "blocking"),
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
    print("  (blank line to submit)")
    print(f"{'~' * 60}\n")

    lines = []
    while True:
        line = input("  > ").strip()
        if line.lower() == "done":
            return "", True
        if not line:
            if lines:
                break
        else:
            lines.append(line)

    return "\n".join(lines), False


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def main():
    print_header()

    cfg = load_input_config()
    platform_name = cfg["platform_name"]
    safe_name = get_safe_name(platform_name)
    scope = cfg.get("scope", "")
    doc_urls = cfg.get("doc_urls") or []

    mode = detect_input_mode(config.ARTIFACTS_DIR, config.DOCS_DIR, doc_urls, scope)

    artifact_count = count_dir_files(config.ARTIFACTS_DIR)
    doc_count = count_dir_files(config.DOCS_DIR)

    print(f"\n  Platform : {platform_name}")
    print(f"  Mode     : {mode}")
    print(f"  Artifacts: {artifact_count}")
    print(f"  Docs     : {doc_count} local + {len(doc_urls)} URL(s)")

    if mode == "empty":
        print(
            "\n  [ERROR] No inputs found. Add artifacts to inputs/sample_artifacts/"
            " or docs to inputs/docs/"
        )
        sys.exit(1)

    # Phase detection: resume from existing KB or start a fresh draft
    existing_kb = get_latest_kb(safe_name)

    if existing_kb:
        print(f"\n  Existing KB found: {existing_kb}")
        kb_path = existing_kb
    else:
        print_step("Draft Phase")
        print("  Running Draft Agent...")
        start = time.time()
        kb_path = await run_draft_agent(cfg, mode)
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
            print("\n  Knowledge base is READY for generation.")
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
