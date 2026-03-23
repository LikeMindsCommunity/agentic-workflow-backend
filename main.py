"""
LikeMinds Layer 1 - Platform Knowledge Base Builder

Main orchestrator that runs the full workflow:
1. Load input artifacts, documentation (local files or URLs), and optional requirements
2. Run Analyzer agent to produce draft knowledge base
3. Run Interrogator agent to identify gaps and generate questions
4. Interactive Q&A loop with the user
5. Re-analyze with new context after each answer round
6. Output final knowledge base as a structured Markdown file

Input modes supported:
  - Artifacts + local docs    → inputs/sample_artifacts/ + inputs/docs/*.md
  - Artifacts + URL docs      → inputs/sample_artifacts/ + inputs/docs/urls.txt
  - Artifacts only            → inputs/sample_artifacts/ (agent asks all questions)
  - Any of the above + scope  → inputs/requirements.md defines the focus
"""
import os
import sys
import json
import time
from datetime import datetime

import config
from utils.file_loader import load_artifacts, load_docs, load_requirements, summarize_inputs
from agents.analyzer import run_analyzer, run_enrichment
from agents.interrogator import generate_questions, format_questions_for_display
from models.knowledge_base import KnowledgeBase
from utils.kb_formatter import to_markdown


def print_header():
    print("\n" + "=" * 60)
    print("  LikeMinds Layer 1 - Knowledge Base Builder")
    print("=" * 60)


def print_step(step_num: int, description: str):
    print(f"\n{'─' * 60}")
    print(f"  Step {step_num}: {description}")
    print(f"{'─' * 60}")


def validate_inputs():
    """
    Load and validate all inputs.
    Returns (artifacts, docs, requirements, has_docs).
    """
    artifacts = load_artifacts(config.ARTIFACTS_DIR)
    docs = load_docs(config.DOCS_DIR)
    requirements = load_requirements(config.REQUIREMENTS_FILE)

    if not artifacts:
        print(f"\n[ERROR] No artifacts found in {config.ARTIFACTS_DIR}")
        print("Please add at least one sample artifact (JSON, config file, etc.)")
        print("These are examples of the output your system should generate.\n")
        sys.exit(1)

    has_docs = bool(docs)

    print(f"\n{summarize_inputs(artifacts, docs, requirements)}")

    if not has_docs:
        print("\n[INFO] No documentation provided - running in artifacts-only mode.")
        print("The Interrogator will ask comprehensive foundational questions to build")
        print("the knowledge base from scratch.\n")
    elif requirements:
        print("\n[INFO] Requirements file loaded - analysis will be scoped accordingly.\n")

    return artifacts, docs, requirements, has_docs


def run_analysis_phase(
    artifacts: list[dict],
    docs: list[dict],
    requirements: str | None,
) -> dict:
    """Run the Analyzer agent and return raw knowledge base dict."""
    print("\n  Running Analyzer agent...")
    print("  (This may take 30-60 seconds depending on artifact complexity)\n")

    start = time.time()
    kb_data = run_analyzer(artifacts, docs, requirements=requirements)
    elapsed = time.time() - start

    num_objects = len(kb_data.get("objects", []))
    num_fields = sum(len(obj.get("fields", [])) for obj in kb_data.get("objects", []))
    num_rules = len(kb_data.get("validation_rules", []))
    num_gaps = len(kb_data.get("gaps", []))

    print(f"  Analysis complete in {elapsed:.1f}s")
    print(f"  Found: {num_objects} objects, {num_fields} fields, {num_rules} validation rules, {num_gaps} gaps")

    return kb_data


def run_interrogation_phase(kb_data: dict, has_docs: bool) -> dict:
    """Run the Interrogator agent and return questions."""
    print("\n  Running Interrogator agent...")

    start = time.time()
    questions_data = generate_questions(kb_data, has_docs=has_docs)
    elapsed = time.time() - start

    num_questions = len(questions_data.get("questions", []))
    print(f"  Generated {num_questions} questions in {elapsed:.1f}s")

    return questions_data


def interactive_qa(questions_data: dict) -> str:
    """
    Present questions to the user and collect answers.
    Returns a formatted string of all Q&A pairs.
    """
    questions = questions_data.get("questions", [])
    if not questions:
        return ""

    print(format_questions_for_display(questions_data))

    print(f"\n{'─' * 60}")
    print("  Answer the questions below. Type 'skip' to skip a question.")
    print("  Type 'done' to finish this round (remaining questions carry over).")
    print(f"{'─' * 60}\n")

    qa_pairs = []
    for q in questions:
        print(f"  [{q['id']}] [{q.get('priority', '?')}] {q['question']}")
        if q.get('field_reference'):
            print(f"       (Re: {q['field_reference']})")
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
                "question_id": q["id"],
                "question": q["question"],
                "field_reference": q.get("field_reference", ""),
                "answer": answer
            })
            print()

    if not qa_pairs:
        return ""

    context_parts = ["Client provided the following answers:\n"]
    for pair in qa_pairs:
        context_parts.append(f"Q ({pair['field_reference']}): {pair['question']}")
        context_parts.append(f"A: {pair['answer']}\n")

    return "\n".join(context_parts)


def save_snapshot(kb_data: dict, round_num: int = 0):
    """Save an intermediate JSON snapshot of the knowledge base."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"kb_snapshot_r{round_num}_{timestamp}.json"
    filepath = os.path.join(config.OUTPUT_DIR, filename)
    with open(filepath, "w") as f:
        json.dump(kb_data, f, indent=2)
    print(f"\n  Snapshot saved: {filepath}")
    return filepath


def save_final_output(kb_data: dict) -> str:
    """
    Save the final knowledge base as a Markdown file.
    Also saves a companion JSON for programmatic use.
    """
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Markdown — the primary human-readable output
    md_filename = f"knowledge_base_FINAL_{timestamp}.md"
    md_filepath = os.path.join(config.OUTPUT_DIR, md_filename)
    with open(md_filepath, "w", encoding="utf-8") as f:
        f.write(to_markdown(kb_data))

    # JSON companion — for Layer 2 programmatic consumption
    json_filename = f"knowledge_base_FINAL_{timestamp}.json"
    json_filepath = os.path.join(config.OUTPUT_DIR, json_filename)
    with open(json_filepath, "w") as f:
        json.dump(kb_data, f, indent=2)

    return md_filepath, json_filepath


def main():
    print_header()

    if not config.ANTHROPIC_API_KEY:
        print("\n[ERROR] ANTHROPIC_API_KEY environment variable not set.")
        print("Run: export ANTHROPIC_API_KEY=your-key-here\n")
        sys.exit(1)

    # Step 1: Load inputs
    print_step(1, "Loading inputs")
    artifacts, docs, requirements, has_docs = validate_inputs()

    # Step 2: Initial analysis
    print_step(2, "Analyzing artifacts and documentation")
    kb_data = run_analysis_phase(artifacts, docs, requirements)
    save_snapshot(kb_data, round_num=0)

    # Step 3+: Interrogation loop
    round_num = 0
    while round_num < config.MAX_QUESTION_ROUNDS:
        round_num += 1
        print_step(2 + round_num, f"Interrogation Round {round_num}")

        questions_data = run_interrogation_phase(kb_data, has_docs=has_docs)

        if questions_data.get("ready_for_generation"):
            confidence = questions_data.get("overall_confidence", "N/A")
            print(f"\n  Knowledge base is ready for generation!")
            print(f"  Overall confidence: {confidence}")
            break

        if not questions_data.get("questions"):
            print("\n  No more questions to ask. Knowledge base is complete.")
            break

        additional_context = interactive_qa(questions_data)

        if not additional_context:
            print("\n  No answers provided.")
            proceed = input("  Continue to next round? (y/n): ").strip().lower()
            if proceed != "y":
                break
            continue

        print("\n  Updating knowledge base with your answers...")
        start = time.time()
        kb_data = run_enrichment(kb_data, additional_context)
        elapsed = time.time() - start
        print(f"  Knowledge base updated in {elapsed:.1f}s")

        save_snapshot(kb_data, round_num=round_num)

        if round_num < config.MAX_QUESTION_ROUNDS:
            proceed = input("\n  Continue with more questions? (y/n): ").strip().lower()
            if proceed != "y":
                break

    # Final save
    print_step(round_num + 3, "Saving final knowledge base")
    md_path, json_path = save_final_output(kb_data)

    # Summary
    kb = KnowledgeBase.from_dict(kb_data)
    confidence = kb.overall_confidence()
    low_items = kb.get_low_confidence_items()

    print(f"\n  Final knowledge base (Markdown): {md_path}")
    print(f"  Final knowledge base (JSON):     {json_path}")
    print(f"  Overall confidence: {confidence:.2f}")
    print(f"  Objects: {len(kb.objects)}")
    print(f"  Total fields: {sum(len(o.fields) for o in kb.objects)}")
    print(f"  Validation rules: {len(kb.validation_rules)}")
    print(f"  Dependencies: {len(kb.dependencies)}")
    print(f"  Remaining gaps: {len(kb.gaps)}")

    if low_items:
        print(f"\n  Items still below confidence threshold ({config.CONFIDENCE_THRESHOLD}):")
        for item in low_items[:5]:
            if item["type"] == "field":
                print(f"    - {item['object']}.{item['field']} (confidence: {item['confidence']})")
            else:
                print(f"    - {item['name']} (confidence: {item['confidence']})")
        if len(low_items) > 5:
            print(f"    ... and {len(low_items) - 5} more")

    print(f"\n{'='*60}")
    print("  Layer 1 complete. Knowledge base is ready for Layer 2.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
