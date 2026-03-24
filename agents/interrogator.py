"""
Interrogator Agent

Reads the knowledge base markdown document and identifies gaps by
reasoning about whether a system could generate valid artifacts using
only this document as reference. Generates targeted questions.
"""
import json
from anthropic import AnthropicFoundry
import config

client = AnthropicFoundry(
    base_url=config.AZURE_AI_FOUNDRY_ENDPOINT,
    api_key=config.AZURE_AI_FOUNDRY_API_KEY,
)


BASE_SYSTEM_PROMPT = """You are reviewing a knowledge base document written for a client's platform. Your job is to determine whether this document is complete enough for an AI system to generate valid artifacts using ONLY this document as reference.

HOW TO FIND GAPS:
Read the document and ask yourself: "If I were given a requirement and this document, could I generate a valid artifact? Where would I get stuck?" Specifically look for:
- Fields mentioned but never explained (what does this value mean?)
- Values shown without context (what are ALL valid values, not just the ones in the sample?)
- Rules that seem incomplete (the doc says X is required, but when exactly?)
- Missing behavioral descriptions (what happens on error, timeout, invalid input?)
- Dependencies that are implied but not documented (does object A need to exist before B?)
- "Needs Verification" callouts that indicate the Analyzer was guessing
- Sections that are too thin compared to the complexity of what they describe

QUESTION QUALITY:
- Be SPECIFIC. Reference exact field names, values, and sections from the KB.
  BAD: "Tell me more about node configuration"
  GOOD: "The PlayNode has a 'timeout' attribute set to '60000' in the example. Is this in milliseconds? What is the valid range? What happens when timeout is reached?"
- Explain WHY you need this (what cannot be generated correctly without it)
- Each question should directly fill a gap that blocks or degrades artifact generation

PRIORITY LEVELS:
- blocking: Generation is impossible or will produce invalid artifacts without this
- important: Generation is possible but artifacts may be incorrect in some scenarios
- nice_to_have: Edge cases, optimizations, or completeness improvements

OUTPUT FORMAT - respond with ONLY valid JSON, no markdown fences:
{
  "summary": "2-3 sentence assessment of the KB's current state",
  "ready_for_generation": true or false,
  "questions": [
    {
      "id": "q1",
      "priority": "blocking",
      "section_reference": "which section of the KB this relates to",
      "question": "the precise question",
      "context": "why we need this and what the KB currently says or is missing"
    }
  ]
}

READY FOR GENERATION CRITERIA:
Return true ONLY when there are no blocking gaps AND no more than 1-2 minor
important gaps that are explicitly acknowledged in the KB's Known Gaps section.
When in doubt, return false."""


MODE_ADDITIONS = {
    "artifacts_only": """

SPECIAL CONTEXT: This KB was built from artifacts alone with no documentation.
Most content is inferred. Be thorough - your questions are the primary way we
build real understanding. Ask more questions than usual (up to the max).

Focus especially on:
- Meaning of every numeric code, enum value, and abbreviation
- Complete list of valid values for every field (not just what appeared in samples)
- All validation rules (the KB likely has very few since they were inferred)
- Platform-specific behaviors that cannot be guessed from structure alone""",

    "urls_only": """

SPECIAL CONTEXT: This KB was built from documentation only, with no sample artifacts.
The schema may be theoretically correct but unvalidated against real output.

Focus especially on:
- Requesting sample artifacts to validate the documented structure
- Real-world usage patterns and defaults
- Which documented features are commonly used vs rarely touched
- Edge cases the documentation might not cover""",

    "scope_only": """

SPECIAL CONTEXT: This KB was built from a scope description only. Almost
everything is a placeholder. Your questions need to establish fundamentals.

Focus on:
- What platform is this? What are its APIs?
- Can you provide sample output files?
- Is there documentation available (URLs or files)?
- What are the core objects/entities in the system?""",

    "full": ""
}


def run_interrogator(kb_markdown: str, mode: str = "full",
                     max_questions: int = None) -> dict:
    """
    Read the KB and generate prioritized questions.
    Returns dict with summary, ready_for_generation, and questions.
    """
    if max_questions is None:
        max_questions = {
            "artifacts_only": config.QUESTIONS_PER_BATCH + 3,
            "scope_only": config.QUESTIONS_PER_BATCH + 5,
            "urls_only": config.QUESTIONS_PER_BATCH + 2,
            "full": config.QUESTIONS_PER_BATCH
        }.get(mode, config.QUESTIONS_PER_BATCH)

    system_prompt = BASE_SYSTEM_PROMPT + MODE_ADDITIONS.get(mode, "")

    user_prompt = f"""Review this knowledge base and generate up to {max_questions} prioritized questions to fill the gaps.

---BEGIN KNOWLEDGE BASE---
{kb_markdown}
---END KNOWLEDGE BASE---

Generate your questions as JSON."""

    response = client.messages.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )

    response_text = response.content[0].text.strip()

    # Clean markdown fences
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = "\n".join(lines)

    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Interrogator returned invalid JSON: {e}\n"
            f"Raw response:\n{response_text[:500]}"
        )


def format_questions_for_display(questions_data: dict) -> str:
    """Format questions for CLI display."""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"  KNOWLEDGE BASE ASSESSMENT")
    lines.append(f"{'='*60}")
    lines.append(f"\n  {questions_data.get('summary', 'No summary available.')}")
    lines.append(f"\n  Ready for Generation: {'Yes' if questions_data.get('ready_for_generation') else 'No'}")

    questions = questions_data.get("questions", [])
    if not questions:
        lines.append("\n  No questions needed - knowledge base appears complete!")
        return "\n".join(lines)

    blocking = [q for q in questions if q.get("priority") == "blocking"]
    important = [q for q in questions if q.get("priority") == "important"]
    nice = [q for q in questions if q.get("priority") == "nice_to_have"]

    def show_group(title, group):
        if not group:
            return
        lines.append(f"\n  --- {title} ---")
        for q in group:
            lines.append(f"\n    [{q['id']}] {q['question']}")
            if q.get("section_reference"):
                lines.append(f"         Section: {q['section_reference']}")
            lines.append(f"         Why: {q.get('context', '')}")

    show_group("BLOCKING (cannot generate without this)", blocking)
    show_group("IMPORTANT (affects correctness)", important)
    show_group("NICE TO HAVE (completeness)", nice)

    return "\n".join(lines)
