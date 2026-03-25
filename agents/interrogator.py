"""
Interrogator Agent

Reads the knowledge base markdown and identifies KNOWLEDGE AREAS where
information is missing, rather than asking individual field-level questions.

Each area groups related gaps so the client can respond with a single
doc dump, URL, or explanation that resolves many gaps at once.
"""
import json
from anthropic import AnthropicFoundry
import config
from utils.stream_utils import stream_with_retry

client = AnthropicFoundry(
    base_url=config.AZURE_AI_FOUNDRY_ENDPOINT,
    api_key=config.AZURE_AI_FOUNDRY_API_KEY,
)


BASE_SYSTEM_PROMPT = """You are reviewing a knowledge base document written for a client's platform. Your job is to determine whether this document is complete enough for an AI system to generate valid artifact FILES using ONLY this document as reference.

CRITICAL SCOPE BOUNDARY — only flag gaps that directly affect writing the artifact file:
- YES: field names, their types, required vs optional, valid values, defaults
- YES: expression/condition syntax used in the file (operators, functions, variable references)
- YES: valid event names and transition trigger values written into the file
- YES: object structure — what nests inside what, ID reference patterns
- NO: runtime platform behaviour (what happens at call time, agent routing logic)
- NO: platform operations (audio upload process, CDN management, retention policies)
- NO: performance limits, rate limits, cost implications
- NO: external system integration (CRM webhooks, OAuth flows, database credentials)

A gap only belongs here if NOT knowing it would cause you to write an incorrect or invalid value in the artifact file. If the gap is about what happens AFTER the file is deployed and executed, ignore it.

IMPORTANT: You are NOT generating a list of individual questions. Instead, you are identifying KNOWLEDGE AREAS where information is missing. Each area groups multiple related gaps so the client can respond efficiently with a single documentation dump, URL, or explanation.

HOW TO IDENTIFY KNOWLEDGE AREAS:
Read the document and find clusters of related unknowns that affect what you would write in the file. For example:
- Multiple unknown field values on TransferNode = one area: "TransferNode Attribute Schema"
- Unclear variable reference syntax = one area: "Variable Reference Format in Expressions"
- Unknown valid event name strings = one area: "Transition Event Names and Trigger Values"

DO NOT split closely related gaps into separate areas. Group them.
Aim for 3-5 areas maximum per review, not 15-20.

FOR EACH AREA, provide:
- what_we_have: What the KB already documents about this area (be specific)
- what_we_need: What is missing and why it prevents writing a correct value in the artifact
- suggested_sources: What kind of documentation would fill this gap

PRIORITY LEVELS:
- blocking: Would cause you to write an invalid or missing required field in the artifact
- important: Artifact can be written but a specific field value may be wrong in some scenarios
- nice_to_have: Edge cases or optional fields that rarely appear

OUTPUT FORMAT - respond with ONLY valid JSON, no markdown fences:
{
  "summary": "2-3 sentence assessment of the KB's current state",
  "ready_for_generation": true or false,
  "areas": [
    {
      "id": "a1",
      "priority": "blocking",
      "title": "Short descriptive title for this knowledge area",
      "what_we_have": "What the KB currently documents about this area",
      "what_we_need": "Coherent description of what is missing and why it matters for artifact generation",
      "suggested_sources": "What kind of doc/URL/explanation would fill this gap"
    }
  ]
}

READY FOR GENERATION CRITERIA:
Return true ONLY when there are no blocking areas AND important areas are either
resolved or explicitly acknowledged in the KB's Known Gaps section.
When in doubt, return false."""


MODE_ADDITIONS = {
    "artifacts_only": """

SPECIAL CONTEXT: This KB was built from artifacts alone with no documentation.
Most content is inferred. The client likely has docs or URLs they can share.

Frame your areas around gaps that affect what you write in the artifact file:
- Unknown valid values for enum/numeric fields (e.g., what does routingStrategy: 3 mean?)
- Attribute schemas where required vs optional is unclear
- Expression or condition syntax where you'd have to guess the format
- Event name strings that were inferred and may be wrong

Do NOT raise areas about: platform operations, deployment process, audio management,
external system integrations, performance limits, or runtime behaviour.

The goal is to get the client to share the schema/API reference docs so you can
confirm what to write in the file — not to understand the full platform.""",

    "urls_only": """

SPECIAL CONTEXT: This KB was built from documentation only, no sample artifacts.

Frame your areas around:
- Getting sample artifacts to validate the schema
- Real-world usage patterns not covered in docs
- Default configurations and common setups""",

    "scope_only": """

SPECIAL CONTEXT: This KB was built from a scope description only.

Frame your areas around foundational needs:
- Platform documentation (suggest they share URLs or files)
- Sample output artifacts
- API access or developer portal links""",

    "full": ""
}


def run_interrogator(kb_markdown: str, mode: str = "full",
                     max_areas: int = None) -> dict:
    """
    Read the KB and identify knowledge areas with gaps.
    Returns dict with summary, ready_for_generation, and areas.
    """
    if max_areas is None:
        max_areas = config.MAX_AREAS_PER_ROUND

    system_prompt = BASE_SYSTEM_PROMPT + MODE_ADDITIONS.get(mode, "")

    user_prompt = f"""Review this knowledge base and identify up to {max_areas} knowledge areas where information is missing.

Group related gaps together. Do NOT list individual field-level questions.
Think about what documentation or explanation the client could provide that
would resolve multiple gaps at once.

---BEGIN KNOWLEDGE BASE---
{kb_markdown}
---END KNOWLEDGE BASE---

Generate your assessment as JSON."""

    print("  Interrogating KB", end="", flush=True)
    response_text = stream_with_retry(
        client,
        show_progress=False,
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    ).strip()
    print(" done\n", flush=True)

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


def format_areas_for_display(areas_data: dict) -> str:
    """Format knowledge areas for CLI display."""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"  KNOWLEDGE BASE ASSESSMENT")
    lines.append(f"{'='*60}")
    lines.append(f"\n  {areas_data.get('summary', 'No summary available.')}")
    lines.append(f"\n  Ready for Generation: {'Yes' if areas_data.get('ready_for_generation') else 'No'}")

    areas = areas_data.get("areas", [])
    if not areas:
        lines.append("\n  No gaps found. Knowledge base appears complete!")
        return "\n".join(lines)

    blocking = [a for a in areas if a.get("priority") == "blocking"]
    important = [a for a in areas if a.get("priority") == "important"]
    nice = [a for a in areas if a.get("priority") == "nice_to_have"]

    def show_group(title, group):
        if not group:
            return
        lines.append(f"\n  --- {title} ---")
        for a in group:
            lines.append(f"\n    [{a['id']}] {a['title']}")
            lines.append(f"         We have: {a.get('what_we_have', 'N/A')}")
            lines.append(f"         We need: {a.get('what_we_need', 'N/A')}")
            lines.append(f"         Suggested: {a.get('suggested_sources', 'N/A')}")

    show_group("BLOCKING (cannot generate without this)", blocking)
    show_group("IMPORTANT (affects correctness)", important)
    show_group("NICE TO HAVE (completeness)", nice)

    return "\n".join(lines)
