"""
LikeMinds Layer 1 - Platform Knowledge Base Builder

Orchestrates two agents in a refinement loop:
  Analyzer  -> writes/rewrites the KB (markdown)
  Interrogator -> reads KB, finds gaps, generates questions
  User answers -> fed back into Analyzer

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
    detect_input_mode, summarize_inputs
)
from utils.web_scraper import scrape_urls
from agents.analyzer import run_analyzer, run_enrichment
from agents.interrogator import run_interrogator, format_questions_for_display


def print_header():
    print("\n" + "=" * 60)
    print("  LikeMinds Layer 1 - Knowledge Base Builder")
    print("=" * 60)


def print_step(num: int, desc: str):
    print(f"\n{'~'*60}")
    print(f"  Step {num}: {desc}")
    print(f"{'~'*60}")


def load_all_inputs():
    """Load config, artifacts, local docs, and scraped docs. Returns everything."""
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


def interactive_qa(questions_data: dict) -> str:
    """Present questions and collect answers. Returns formatted Q&A context."""
    questions = questions_data.get("questions", [])
    if not questions:
        return ""

    print(format_questions_for_display(questions_data))

    print(f"\n{'~'*60}")
    print("  Answer the questions below.")
    print("  Type 'skip' to skip, 'done' to finish this round.")
    print(f"{'~'*60}\n")

    qa_pairs = []
    for q in questions:
        priority = q.get("priority", "?").upper()
        print(f"  [{q['id']}] [{priority}] {q['question']}")
        if q.get("section_reference"):
            print(f"       (Re: {q['section_reference']})")
        print()

        answer = input("  Your answer: ").strip()

        if answer.lower() == "done":
            print("\n  Ending this Q&A round.")
            break
        elif answer.lower() == "skip":
            print("  Skipped.\n")
            continue
        else:
            qa_pairs.append({
                "id": q["id"],
                "question": q["question"],
                "section": q.get("section_reference", ""),
                "answer": answer
            })
            print()

    if not qa_pairs:
        return ""

    parts = ["Client provided the following answers:\n"]
    for pair in qa_pairs:
        ref = f" (Section: {pair['section']})" if pair["section"] else ""
        parts.append(f"Q{ref}: {pair['question']}")
        parts.append(f"A: {pair['answer']}\n")

    return "\n".join(parts)


def main():
    print_header()

    if not config.AZURE_AI_FOUNDRY_ENDPOINT:
        print("\n  [ERROR] AZURE_AI_FOUNDRY_ENDPOINT not set.")
        print("  Run: export AZURE_AI_FOUNDRY_ENDPOINT=https://<your-resource>.services.ai.azure.com/models\n")
        sys.exit(1)
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
        print_step(2 + round_num, f"Interrogation Round {round_num}")

        # Generate questions
        print("\n  Running Interrogator agent...")
        start = time.time()
        try:
            questions_data = run_interrogator(kb_markdown, mode=mode)
        except ValueError as e:
            print(f"\n  [ERROR] Interrogator failed: {e}")
            retry = input("  Retry this round? (y/n): ").strip().lower()
            if retry == "y":
                round_num -= 1
                continue
            else:
                break

        elapsed = time.time() - start
        num_q = len(questions_data.get("questions", []))
        print(f"  Generated {num_q} question(s) in {elapsed:.1f}s")

        # Check if done
        if questions_data.get("ready_for_generation"):
            print(f"\n  Knowledge base is READY for generation!")
            print(f"  {questions_data.get('summary', '')}")
            break

        if not questions_data.get("questions"):
            print("\n  No more questions. Knowledge base is complete.")
            break

        # Q&A
        qa_context = interactive_qa(questions_data)

        if not qa_context:
            print("\n  No answers provided.")
            proceed = input("  Continue to next round? (y/n): ").strip().lower()
            if proceed != "y":
                break
            continue

        # Enrich
        print("\n  Updating knowledge base with your answers...")
        start = time.time()
        kb_markdown = run_enrichment(
            kb_markdown, qa_context, scope=scope, mode=mode
        )
        elapsed = time.time() - start

        kb_lines = kb_markdown.count("\n") + 1
        print(f"  Updated in {elapsed:.1f}s ({kb_lines} lines)")

        saved = save_kb(kb_markdown, platform_name, round_num=round_num)
        print(f"  Saved: {saved}")

        if round_num < config.MAX_QUESTION_ROUNDS:
            proceed = input("\n  Continue with more questions? (y/n): ").strip().lower()
            if proceed != "y":
                break

    # Final save
    print_step(round_num + 3, "Saving final knowledge base")
    final_path = save_kb(kb_markdown, platform_name, round_num=round_num, is_final=True)

    # Count some stats from the markdown
    sections = kb_markdown.count("\n## ")
    subsections = kb_markdown.count("\n### ")
    code_blocks = kb_markdown.count("```")
    verifications = kb_markdown.lower().count("needs verification")

    print(f"\n  Platform:              {platform_name}")
    print(f"  Input mode:            {mode}")
    print(f"  Q&A rounds completed:  {round_num}")
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
