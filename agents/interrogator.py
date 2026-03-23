"""
Interrogator Agent

Takes the knowledge base produced by the Analyzer and:
1. Identifies all low-confidence areas and explicit gaps
2. Generates targeted, specific questions for the client
3. Prioritizes questions by severity (blocking > important > nice-to-have)
4. Batches questions to avoid overwhelming the client
"""
import json
from anthropic import Anthropic
import config

client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

INTERROGATOR_SYSTEM_PROMPT = """You are an expert technical interviewer working for LikeMinds. Your job is to review a knowledge base that was built by analyzing a client's platform artifacts and documentation, identify gaps in understanding, and generate precise questions that will fill those gaps.

You will receive a knowledge base JSON that includes confidence scores and identified gaps.

Your task is to generate a prioritized list of questions that, when answered, will raise the overall confidence of the knowledge base.

QUESTION QUALITY RULES:
- Questions must be SPECIFIC and ACTIONABLE. Not "tell me more about workflows" but "the field 'routingStrategy' accepts numeric values. We found value 3 in your sample. What are ALL valid values and what does each one mean?"
- Questions should reference the exact field path or object they're about
- Each question should explain WHY we need this info (what breaks without it)
- Group related questions together when possible
- Order by priority: blocking gaps first (we cannot generate artifacts without this), then important (affects correctness), then nice-to-have (edge cases)

OUTPUT FORMAT - respond with ONLY valid JSON, no markdown fences:
{
  "summary": "Brief summary of the knowledge base state and key gaps",
  "overall_confidence": 0.0-1.0,
  "ready_for_generation": true/false,
  "questions": [
    {
      "id": "q1",
      "priority": "blocking|important|nice_to_have",
      "category": "schema|validation|dependency|values|behavior",
      "field_reference": "dot.path.to.field or object name",
      "question": "The precise question to ask the client",
      "context": "Why we need this - what we currently know and what's missing",
      "example_from_artifact": "Quote the specific value or structure from the artifact that prompted this question"
    }
  ]
}"""


def generate_questions(
    kb_data: dict,
    max_questions: int = None,
    has_docs: bool = True,
) -> dict:
    """
    Analyze the knowledge base and generate prioritized questions.

    Args:
        kb_data: The current knowledge base dict.
        max_questions: Max number of questions to generate this round.
        has_docs: Whether any documentation was provided. When False,
                  the interrogator switches to a comprehensive "build from
                  scratch" mode and asks foundational questions in addition
                  to gap-filling ones.

    Returns a dict with summary, confidence assessment, and questions.
    """
    if max_questions is None:
        max_questions = config.QUESTIONS_PER_BATCH

    if has_docs:
        focus_instructions = f"""Focus on:
1. Fields with confidence below {config.CONFIDENCE_THRESHOLD}
2. Explicit gaps listed in the "gaps" section
3. Any validation rules or dependencies that seem incomplete
4. Enum fields where we might be missing valid values
5. Cross-field dependencies that are not yet captured"""
    else:
        focus_instructions = f"""IMPORTANT: No documentation was provided for this platform. The knowledge base was built from artifacts alone and is incomplete. You must generate comprehensive, foundational questions that will allow us to fully understand this platform from scratch.

Focus on ALL of the following (not just gaps):
1. Platform fundamentals - what is this artifact? what system/product does it configure?
2. Every field with confidence below {config.CONFIDENCE_THRESHOLD} - what does it mean, what are ALL valid values?
3. Every enum or numeric value seen in the artifacts - what do all possible values mean?
4. Required vs optional fields - what happens if optional fields are omitted?
5. Business rules and validation - what combinations are invalid? what constraints exist?
6. Deployment/creation flow - what order must objects be created in? what IDs must be pre-existing?
7. Any field whose purpose is not immediately obvious from its name alone
8. Edge cases - what are the limits (min/max lengths, value ranges, list size limits)?

Treat this as a full discovery interview, not just gap-filling."""

    prompt = f"""Review this knowledge base and generate up to {max_questions} prioritized questions.

Knowledge Base:
{json.dumps(kb_data, indent=2)}

{focus_instructions}

Generate your questions as JSON."""

    response = client.messages.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=INTERROGATOR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = response.content[0].text.strip()

    if response_text.startswith("```"):
        lines = response_text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = "\n".join(lines)

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Interrogator returned invalid JSON: {e}\nRaw response:\n{response_text[:500]}")

    return result


def format_questions_for_display(questions_data: dict) -> str:
    """Format the questions nicely for CLI display."""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"KNOWLEDGE BASE ASSESSMENT")
    lines.append(f"{'='*60}")
    lines.append(f"\n{questions_data.get('summary', 'No summary available.')}")
    lines.append(f"\nOverall Confidence: {questions_data.get('overall_confidence', 'N/A')}")
    lines.append(f"Ready for Generation: {'Yes' if questions_data.get('ready_for_generation') else 'No'}")

    questions = questions_data.get("questions", [])
    if not questions:
        lines.append("\nNo questions needed - knowledge base appears complete!")
        return "\n".join(lines)

    # Group by priority
    blocking = [q for q in questions if q.get("priority") == "blocking"]
    important = [q for q in questions if q.get("priority") == "important"]
    nice = [q for q in questions if q.get("priority") == "nice_to_have"]

    def format_group(title, group):
        if not group:
            return
        lines.append(f"\n--- {title} ---")
        for q in group:
            lines.append(f"\n  [{q['id']}] {q['question']}")
            lines.append(f"       Category: {q.get('category', 'general')}")
            lines.append(f"       Field: {q.get('field_reference', 'N/A')}")
            lines.append(f"       Why: {q.get('context', '')}")
            if q.get("example_from_artifact"):
                example = q["example_from_artifact"]
                if len(example) > 100:
                    example = example[:100] + "..."
                lines.append(f"       From artifact: {example}")

    format_group("BLOCKING (cannot generate artifacts without this)", blocking)
    format_group("IMPORTANT (affects correctness)", important)
    format_group("NICE TO HAVE (edge cases and completeness)", nice)

    return "\n".join(lines)
