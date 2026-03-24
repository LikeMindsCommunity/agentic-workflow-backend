"""
LikeMinds Layer 1 - Platform Knowledge Base Builder

Orchestrates two agents in a refinement loop:
  Analyzer     -> writes/rewrites the KB (markdown)
  Interrogator -> reads KB, finds knowledge area gaps
  User responds per area with: URL | file | text explanation
  Analyzer     -> rewrites KB with new docs + answers

Supports four input modes:
  full            artifacts + docs (local or URLs)
  artifacts_only  only artifacts, agent asks all questions
  urls_only       doc URLs + scope, no artifacts
  scope_only      just requirements, everything via Q&A
"""
import os
import sys
import time
from datetime import datetime

import config
from utils.file_loader import (
    load_input_config, load_artifacts, load_docs,
    detect_input_mode, summarize_inputs, reload_docs
)
from utils.web_scraper import scrape_urls, scrape_url
from agents.analyzer import run_analyzer, run_enrichment
from agents.interrogator import run_interrogator, format_areas_for_display


def print_header():
    print("\n" + "=" * 60)
    print("  LikeMinds Layer 1 - Knowledge Base Builder")
    print("=" * 60)


def print_step(num: int, desc: str):
    print(f"\n{'~'*60}")
    print(f"  Step {num}: {desc}")
    print(f"{'~'*60}")


def load_all_inputs():
    """Load config, artifacts, local docs, and scraped docs."""
    input_cfg = load_input_config()
    print(f"\n  Platform: {input_cfg['platform_name']}")

    artifacts = load_artifacts(input_cfg["artifacts_dir"], input_cfg.get("exclude_files", []))
    local_docs = load_docs(input_cfg["docs_dir"])

    scraped_docs = []
    doc_urls = input_cfg.get("doc_urls", [])
    if doc_urls:
        print(f"\n  Scraping {len(doc_urls)} documentation URL(s)...")
        scraped_docs = scrape_urls(
            doc_urls,
            follow_links=input_cfg.get("follow_links", False),
            max_pages=input_cfg.get("max_pages", config.MAX_PAGES_PER_URL)
        )
        print(f"  Scraped {len(scraped_docs)} page(s)")

    all_docs = local_docs + scraped_docs
    scope = input_cfg["scope"]
    mode = detect_input_mode(artifacts, all_docs, doc_urls, scope)

    print(f"\n{summarize_inputs(artifacts, local_docs, scraped_docs, scope, mode)}")

    return input_cfg, artifacts, all_docs, mode


def save_kb(kb_markdown: str, platform_name: str,
            round_num: int, is_final: bool = False) -> str:
    """Save knowledge base markdown to outputs/."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    safe_name = platform_name.lower().replace(" ", "_")[:30]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if is_final:
        filename = f"kb_{safe_name}_FINAL_{timestamp}.md"
    else:
        filename = f"kb_{safe_name}_r{round_num}_{timestamp}.md"

    filepath = os.path.join(config.OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(kb_markdown)

    return filepath


def collect_area_responses(areas_data: dict,
                           loaded_docs: list[dict]) -> tuple:
    """
    Present knowledge areas and collect responses.

    For each area the user can:
      - Paste a URL -> system scrapes it immediately
      - Type 'file' -> system re-reads inputs/docs/ for new files
      - Type a free-text explanation
      - Type 'skip' to skip the area
      - Type 'done' to end the round

    Returns: (new_docs: list[dict], text_answers: str, updated_loaded_docs: list[dict])
    """
    areas = areas_data.get("areas", [])
    if not areas:
        return [], "", loaded_docs

    print(format_areas_for_display(areas_data))

    print(f"\n{'~'*60}")
    print("  For each area, provide one of:")
    print("    - A URL (starts with http) -> we'll scrape it")
    print("    - 'file' -> if you've added docs to inputs/docs/")
    print("    - A text explanation")
    print("    - 'skip' to skip, 'done' to finish this round")
    print(f"{'~'*60}")

    new_docs = []
    text_parts = []

    for area in areas:
        priority = area.get("priority", "?").upper()
        print(f"\n  [{area['id']}] [{priority}] {area['title']}")
        print(f"       We need: {area.get('what_we_need', '')[:120]}")
        print(f"       Suggested: {area.get('suggested_sources', '')[:120]}")
        print()

        response = input("  Your response: ").strip()

        if response.lower() == "done":
            print("\n  Ending this round.")
            break

        if response.lower() == "skip":
            print("  Skipped.\n")
            continue

        # URL response - scrape immediately
        if response.startswith("http://") or response.startswith("https://"):
            print(f"\n  Scraping {response}...")
            try:
                scraped = scrape_url(response, follow_links=False, max_pages=5)
                if scraped:
                    new_docs.extend(scraped)
                    print(f"  Scraped {len(scraped)} page(s) for: {area['title']}")
                else:
                    print(f"  [WARNING] No content extracted from URL.")
                    fallback = input("  Provide text explanation instead (or 'skip'): ").strip()
                    if fallback.lower() != "skip" and fallback:
                        text_parts.append(f"Regarding {area['title']}:")
                        text_parts.append(f"{fallback}\n")
            except Exception as e:
                print(f"  [ERROR] Failed to scrape: {e}")
                fallback = input("  Provide text explanation instead (or 'skip'): ").strip()
                if fallback.lower() != "skip" and fallback:
                    text_parts.append(f"Regarding {area['title']}:")
                    text_parts.append(f"{fallback}\n")

        # File response - reload docs directory
        elif response.lower() == "file":
            print(f"\n  Re-reading inputs/docs/ for new files...")
            fresh_docs = reload_docs(already_loaded=loaded_docs)
            if fresh_docs:
                new_docs.extend(fresh_docs)
                loaded_docs = loaded_docs + fresh_docs
                filenames = ", ".join(d["filename"] for d in fresh_docs)
                print(f"  Found {len(fresh_docs)} new file(s): {filenames}")
            else:
                print("  No new files found in inputs/docs/.")
                print("  Make sure you've saved files there before typing 'file'.")
                fallback = input("  Provide text explanation instead (or 'skip'): ").strip()
                if fallback.lower() != "skip" and fallback:
                    text_parts.append(f"Regarding {area['title']}:")
                    text_parts.append(f"{fallback}\n")

        # Text explanation
        else:
            text_parts.append(f"Regarding {area['title']}:")
            text_parts.append(f"{response}")

            # Allow multi-line input for text explanations
            print("  (Type more lines, empty line to finish this area)")
            while True:
                extra = input("  > ").strip()
                if not extra:
                    break
                text_parts.append(extra)
            text_parts.append("")

    text_answers = "\n".join(text_parts) if text_parts else ""
    return new_docs, text_answers, loaded_docs


def main():
    print_header()

    if not config.AZURE_AI_FOUNDRY_API_KEY:
        print("\n  [ERROR] AZURE_AI_FOUNDRY_API_KEY not set.")
        print("  Run: export AZURE_AI_FOUNDRY_API_KEY=your-key-here\n")
        sys.exit(1)

    # Step 1: Load inputs
    print_step(1, "Loading inputs")
    input_cfg, artifacts, all_docs, mode = load_all_inputs()
    platform_name = input_cfg["platform_name"]
    scope = input_cfg["scope"]

    if mode == "empty":
        print("\n  [ERROR] No inputs found. Provide at least one of:")
        print("    - Sample artifacts in inputs/sample_artifacts/")
        print("    - Documentation in inputs/docs/")
        print("    - Documentation URLs in inputs/input_config.yaml")
        print("    - A scope description in inputs/input_config.yaml\n")
        sys.exit(1)

    mode_messages = {
        "full": "Full analysis with artifacts and documentation.",
        "artifacts_only": "ARTIFACTS-ONLY mode. More questions to compensate for missing docs.",
        "urls_only": "DOCS-ONLY mode. No artifacts - agent will ask for structure details.",
        "scope_only": "SCOPE-ONLY mode. Very little info - expect extensive questioning."
    }
    print(f"\n  {mode_messages.get(mode, '')}")

    # Keep track of all loaded docs (for reload detection)
    loaded_docs = list(all_docs)

    # Step 2: Analyze
    print_step(2, "Analyzing inputs")
    print("\n  Running Analyzer agent...")
    print("  (This may take 30-60 seconds)\n")

    start = time.time()
    kb_markdown = run_analyzer(artifacts, all_docs, scope=scope, mode=mode)
    elapsed = time.time() - start

    kb_lines = kb_markdown.count("\n") + 1
    print(f"  Analysis complete in {elapsed:.1f}s ({kb_lines} lines)")

    saved = save_kb(kb_markdown, platform_name, round_num=0)
    print(f"  Saved draft: {saved}")

    # Step 3+: Interrogation loop
    round_num = 0
    while round_num < config.MAX_QUESTION_ROUNDS:
        round_num += 1
        print_step(2 + round_num, f"Gap Analysis Round {round_num}")

        # Identify knowledge area gaps
        print("\n  Running Interrogator agent...")
        start = time.time()
        try:
            areas_data = run_interrogator(kb_markdown, mode=mode)
        except ValueError as e:
            print(f"\n  [ERROR] Interrogator failed: {e}")
            retry = input("  Retry this round? (y/n): ").strip().lower()
            if retry == "y":
                round_num -= 1
                continue
            else:
                break

        elapsed = time.time() - start
        num_areas = len(areas_data.get("areas", []))
        print(f"  Identified {num_areas} knowledge area(s) in {elapsed:.1f}s")

        # Check if done
        if areas_data.get("ready_for_generation"):
            print(f"\n  Knowledge base is READY for generation!")
            print(f"  {areas_data.get('summary', '')}")
            break

        if not areas_data.get("areas"):
            print("\n  No gaps found. Knowledge base is complete.")
            break

        # Collect responses (URLs, files, text)
        new_docs, text_answers, loaded_docs = collect_area_responses(
            areas_data, loaded_docs
        )

        if not new_docs and not text_answers:
            print("\n  No new information provided.")
            proceed = input("  Continue to next round? (y/n): ").strip().lower()
            if proceed != "y":
                break
            continue

        # Log what we got
        if new_docs:
            print(f"\n  New documentation collected: {len(new_docs)} source(s)")
        if text_answers:
            answer_lines = text_answers.count("\n") + 1
            print(f"  Text explanations collected: {answer_lines} lines")

        # Enrich KB with new material
        print("\n  Updating knowledge base with new information...")
        start = time.time()
        kb_markdown = run_enrichment(
            existing_kb=kb_markdown,
            new_docs=new_docs,
            text_answers=text_answers,
            scope=scope,
            mode=mode
        )
        elapsed = time.time() - start

        kb_lines = kb_markdown.count("\n") + 1
        print(f"  Updated in {elapsed:.1f}s ({kb_lines} lines)")

        saved = save_kb(kb_markdown, platform_name, round_num=round_num)
        print(f"  Saved: {saved}")

        if round_num < config.MAX_QUESTION_ROUNDS:
            proceed = input("\n  Continue with more rounds? (y/n): ").strip().lower()
            if proceed != "y":
                break

    # Final save
    print_step(round_num + 3, "Saving final knowledge base")
    final_path = save_kb(kb_markdown, platform_name, round_num=round_num, is_final=True)

    # Stats
    sections = kb_markdown.count("\n## ")
    subsections = kb_markdown.count("\n### ")
    code_blocks = kb_markdown.count("```")
    verifications = kb_markdown.lower().count("needs verification")

    print(f"\n  Platform:              {platform_name}")
    print(f"  Input mode:            {mode}")
    print(f"  Rounds completed:      {round_num}")
    print(f"  Document length:       {len(kb_markdown)} chars, {kb_markdown.count(chr(10))+1} lines")
    print(f"  Sections:              {sections}")
    print(f"  Subsections:           {subsections}")
    print(f"  Code blocks:           {code_blocks // 2}")
    print(f"  Remaining gaps:        {verifications} 'Needs Verification' items")
    print(f"\n  Output: {final_path}")

    print(f"\n{'='*60}")
    print("  Layer 1 complete.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
