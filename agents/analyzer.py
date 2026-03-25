"""
Analyzer Agent

Reads artifacts, documentation, and scope, then produces a comprehensive
markdown knowledge base document. Outputs markdown directly.

Enrichment mode accepts new documentation AND text answers separately,
so the agent can extract maximum information from full doc pages.
"""
from anthropic import AnthropicFoundry
import config
from utils.stream_utils import stream_with_retry

client = AnthropicFoundry(
    base_url=config.AZURE_AI_FOUNDRY_ENDPOINT,
    api_key=config.AZURE_AI_FOUNDRY_API_KEY,
)


KB_STRUCTURE_GUIDE = """
The knowledge base document MUST follow this structure. Every section should be
thorough, with annotated examples pulled from the artifacts wherever possible.

```
# <Platform Name> - <Artifact Type> Knowledge Base

## Overview
What this platform is, what artifact we are generating, how it is used in practice.

## Core Concepts
Key terminology and entity relationships. Define every major concept
before diving into structure. Use subsections (###) per concept.

## Artifact Structure
Top-level walkthrough of the artifact format. Show the full high-level
shape with an annotated example. Explain what each major section contains.

## <Object/Section Name> (one section per major object or component)
For each distinct object type or major section in the artifact:
- What it represents and when it is used
- All fields: name, type, required/optional, valid values, defaults
- Annotated JSON/config examples showing real values from the sample artifacts
- Behavioral notes: what happens when a field is set to a specific value
- Edge cases or special rules

(Repeat for each object type. Use ### for sub-sections within each object.)

## Validation Rules and Constraints
All rules that must hold for a generated artifact to be valid.
Group by scope: per-field rules, cross-field rules, cross-object rules.
For each rule, explain what breaks if it is violated.

## Dependencies and Ordering
What must exist before what. Creation sequence.
Bidirectional references if applicable (parent/child patterns).
Show the exact fields that establish references between objects.

## Common Patterns
Recurring configurations with complete annotated examples.
Explain when and why each pattern is used.
Include copy-paste-ready templates that can be adapted.

## Integration Checklist
Step-by-step process for assembling a complete artifact.
Number each step. Note which locations in the artifact need updating.

## Troubleshooting
Common issues in the format: "Issue: <problem>" / "Check: <what to verify>"

## Known Gaps
Areas where the knowledge base is still incomplete.
What specific information is needed to fill each gap.
```

WRITING RULES:
- Cover every DISTINCT field type and object type, but do NOT repeat the same
  pattern for every instance. One annotated example per pattern is enough.
- Use annotated JSON/config blocks with inline comments explaining each element.
- When you infer something from the artifact without doc confirmation, add:
  > **Needs Verification:** <what is unclear and what we assumed>
- Show real values from the sample artifacts, not placeholder values.
- Validation rules should describe both the rule AND what breaks when violated.
- Common patterns should include complete, copy-paste-ready examples.
- Use ### subsections liberally to keep content scannable.
- Do NOT use confidence scores, numeric ratings, or structured metadata.
- Be thorough but concise. Prefer prose + one good example over exhaustive
  field-by-field repetition. The Q&A rounds will fill gaps.
- Write in clear, direct prose. This document will be read by both humans and AI.
"""


MODE_INSTRUCTIONS = {
    "full": """
You have SAMPLE ARTIFACTS (real outputs from the platform) and DOCUMENTATION.

Your approach:
- Walk through every element in the artifacts and explain it using the documentation.
- Pull real values from the artifacts into your annotated examples.
- Where the docs clearly explain something, write with authority.
- Where the docs are vague or silent on something visible in the artifact, document
  what you observe and add a "Needs Verification" callout.
- Cross-reference multiple artifacts (if provided) to identify what varies per
  deployment vs what is structurally constant.""",

    "artifacts_only": """
You have ONLY sample artifacts. No documentation was provided.

Your approach:
- Reverse-engineer the complete structure from what you can observe.
- Document every field, its apparent type, and what the value suggests about its purpose.
- Be liberal with "Needs Verification" callouts since nothing is doc-confirmed.
- Infer relationships from field names and ID references.
- When you see numeric codes or abbreviated values (e.g. routingStrategy: 3),
  document exactly what you see but flag that the meaning is unknown.
- The "Known Gaps" section should be extensive since we have no documentation.
- Focus on capturing the COMPLETE structure even if meaning is uncertain.""",

    "urls_only": """
You have DOCUMENTATION (from websites or files) and a SCOPE description, but NO sample artifacts.

Your approach:
- Extract all schema, field, and rule information from the docs.
- Use the scope to understand what artifact type we are targeting.
- Where docs include examples, use those as your annotated examples.
- The "Known Gaps" section should note that no real artifact has been validated.
- Add a "Needs Verification" callout asking for sample artifacts to validate the schema.""",

    "scope_only": """
You have ONLY a scope/requirements description. No artifacts, no documentation.

Your approach:
- Write a skeleton document based on what you can infer from the scope.
- Every section should contain a "Needs Verification" callout explaining what
  information is needed to fill it in.
- The "Known Gaps" section should be the longest section, listing everything
  we need to learn.
- Focus on establishing the right structure so the Q&A process can fill it in."""
}


def _build_system_prompt(mode: str) -> str:
    return f"""You are an expert platform analyst working for LikeMinds. Your job is to write a comprehensive knowledge base document for a client's platform. This document will be used by another AI system (and by human consultants) to generate valid artifacts for this platform in the future.

You must output a well-structured MARKDOWN document. No JSON. No preamble or closing remarks outside the document. Start directly with the markdown heading.

{KB_STRUCTURE_GUIDE}

{MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["full"])}"""


def _build_context_block(artifacts: list[dict], docs: list[dict],
                         scope: str, mode: str) -> str:
    """
    Build the input context (artifacts + docs + scope) WITHOUT a trailing
    directive. The section-specific directive is appended separately per call.
    """
    parts = []

    if scope:
        parts.append("=== SCOPE / REQUIREMENTS ===\n")
        parts.append(scope)
        parts.append("")

    if artifacts:
        parts.append("\n=== SAMPLE ARTIFACTS ===\n")
        for i, artifact in enumerate(artifacts, 1):
            parts.append(f"--- Artifact {i}: {artifact['filename']} ({artifact['file_type']}) ---")
            parts.append(artifact["raw_content"])
            parts.append("")

    if docs:
        parts.append("\n=== DOCUMENTATION ===\n")
        for i, doc in enumerate(docs, 1):
            source = doc.get("source_url", doc["filename"])
            parts.append(f"--- Document {i}: {source} ---")
            parts.append(doc["content"])
            parts.append("")

    if not artifacts and not docs:
        parts.append("\nNo artifacts or documentation provided. Build from scope alone.\n")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Section batches for chunked KB generation.
# Each batch is one API call that writes a specific slice of the document.
# This keeps individual responses small enough to avoid Azure gateway timeouts
# while still producing a complete, fully-detailed knowledge base.
# ---------------------------------------------------------------------------
SECTION_BATCHES = [
    {
        "label": "Overview · Core Concepts · Artifact Structure",
        "directive": (
            "Start the knowledge base document with the title heading, then write ONLY "
            "these three sections:\n"
            "1. # <Platform Name> - <Artifact Type> Knowledge Base  ← document title\n"
            "2. ## Overview\n"
            "3. ## Core Concepts\n"
            "4. ## Artifact Structure\n\n"
            "Stop after completing ## Artifact Structure. Do NOT write any other sections."
        ),
    },
    {
        "label": "Objects and Fields",
        "directive": (
            "Continue the knowledge base by writing ONLY the per-object detail sections.\n"
            "For every distinct object type in the artifacts write one ## section that covers:\n"
            "  - What the object represents and when it is used\n"
            "  - All fields with type, required/optional, valid values, defaults\n"
            "  - Annotated JSON examples using real values from the sample artifacts\n"
            "  - Behavioral notes and edge cases\n\n"
            "Do NOT re-write Overview, Core Concepts, Artifact Structure, or any later sections. "
            "Object sections only."
        ),
    },
    {
        "label": "Validation Rules · Dependencies · Common Patterns",
        "directive": (
            "Continue the knowledge base by writing ONLY these three sections:\n"
            "1. ## Validation Rules and Constraints\n"
            "2. ## Dependencies and Ordering\n"
            "3. ## Common Patterns\n\n"
            "Do NOT re-write any earlier sections or the closing sections."
        ),
    },
    {
        "label": "Integration Checklist · Troubleshooting · Known Gaps",
        "directive": (
            "Finish the knowledge base by writing ONLY these three sections:\n"
            "1. ## Integration Checklist\n"
            "2. ## Troubleshooting\n"
            "3. ## Known Gaps\n\n"
            "Do NOT re-write any earlier sections."
        ),
    },
]


def _strip_markdown_fences(text: str) -> str:
    """Remove wrapping markdown code fences if present."""
    text = text.strip()
    for prefix in ["```markdown", "```md", "```"]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def run_analyzer(artifacts: list[dict], docs: list[dict],
                 scope: str = "", mode: str = "full") -> str:
    """
    Generate the knowledge base in section batches to avoid Azure gateway
    timeouts on large responses.  Each batch writes a specific slice of the
    document; the slices are joined into a single markdown string at the end.
    """
    system_prompt = _build_system_prompt(mode)
    context_block = _build_context_block(artifacts, docs, scope, mode)

    section_texts = []
    for i, batch in enumerate(SECTION_BATCHES, 1):
        print(f"\n  [{i}/{len(SECTION_BATCHES)}] Generating: {batch['label']} ...")
        user_prompt = context_block + f"\n\n{batch['directive']}"

        text = stream_with_retry(
            client,
            show_progress=True,
            model=config.MODEL,
            max_tokens=config.MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        section_texts.append(_strip_markdown_fences(text))

    return "\n\n".join(section_texts)


# ---------------------------------------------------------------------------
# Enrichment batches — mirror SECTION_BATCHES exactly so the KB structure
# stays consistent.  Each call receives the full existing KB as read-only
# context but outputs ONLY the sections listed in its directive.
# This keeps output tokens per call well within the Azure gateway timeout.
# ---------------------------------------------------------------------------
ENRICHMENT_BATCHES = [
    {
        "label": "Overview · Core Concepts · Artifact Structure",
        "directive": (
            "Rewrite ONLY these three sections incorporating the new information:\n"
            "1. ## Overview\n"
            "2. ## Core Concepts\n"
            "3. ## Artifact Structure\n\n"
            "Output ONLY these three sections. Start directly with ## Overview.\n"
            "Do NOT include the document title or any other sections."
        ),
    },
    {
        "label": "Objects and Fields",
        "directive": (
            "Rewrite ONLY the per-object and per-component detail sections "
            "incorporating the new information.\n"
            "These are every ## section that is NOT one of: Overview, Core Concepts, "
            "Artifact Structure, Validation Rules and Constraints, Dependencies and "
            "Ordering, Common Patterns, Integration Checklist, Troubleshooting, Known Gaps.\n\n"
            "Output ONLY those object/component sections. "
            "Do NOT include any structural or closing sections."
        ),
    },
    {
        "label": "Validation Rules · Dependencies · Common Patterns",
        "directive": (
            "Rewrite ONLY these three sections incorporating the new information:\n"
            "1. ## Validation Rules and Constraints\n"
            "2. ## Dependencies and Ordering\n"
            "3. ## Common Patterns\n\n"
            "Output ONLY these three sections. Start directly with "
            "## Validation Rules and Constraints.\n"
            "Do NOT include any other sections."
        ),
    },
    {
        "label": "Integration Checklist · Troubleshooting · Known Gaps",
        "directive": (
            "Rewrite ONLY these three closing sections incorporating the new information:\n"
            "1. ## Integration Checklist\n"
            "2. ## Troubleshooting\n"
            "3. ## Known Gaps\n\n"
            "Output ONLY these three sections. Start directly with ## Integration Checklist.\n"
            "Do NOT include any other sections."
        ),
    },
]


def run_enrichment(existing_kb: str, new_docs: list[dict] = None,
                   text_answers: str = "", scope: str = "",
                   mode: str = "full") -> str:
    """
    Update the knowledge base section-by-section with new documentation
    and/or client answers.

    Each batch call receives the full existing KB as read-only context but
    outputs only its assigned sections, keeping generation time short enough
    to avoid Azure gateway timeouts.

    Args:
        existing_kb:  Current KB markdown content
        new_docs:     New doc dicts (from URLs or files shared mid-loop)
        text_answers: Free-text explanations typed by the client
        scope:        Original scope string
        mode:         Input mode
    """
    system_prompt = _build_system_prompt(mode)

    # Build the new-information block once — reused in every batch call
    new_info_parts = []

    if scope:
        new_info_parts.append(f"SCOPE: {scope}\n")

    if new_docs:
        new_info_parts.append("NEW DOCUMENTATION PROVIDED BY CLIENT:\n")
        for i, doc in enumerate(new_docs, 1):
            source = doc.get("source_url", doc["filename"])
            new_info_parts.append(f"--- New Document {i}: {source} ---")
            new_info_parts.append(doc["content"])
            new_info_parts.append("")

    if text_answers.strip():
        new_info_parts.append("CLIENT EXPLANATIONS:\n")
        new_info_parts.append("---BEGIN ANSWERS---")
        new_info_parts.append(text_answers.strip())
        new_info_parts.append("---END ANSWERS---\n")

    new_info_block = "\n".join(new_info_parts)

    # Extract the document title line (# heading) to preserve it
    title_line = next(
        (line for line in existing_kb.splitlines()
         if line.startswith("# ") and not line.startswith("## ")),
        ""
    )

    # Enrich each section batch independently
    section_texts = []
    for i, batch in enumerate(ENRICHMENT_BATCHES, 1):
        print(f"\n  [{i}/{len(ENRICHMENT_BATCHES)}] Enriching: {batch['label']} ...")

        user_prompt = (
            "Here is the complete current knowledge base for context:\n\n"
            "---BEGIN EXISTING KB---\n"
            f"{existing_kb}\n"
            "---END EXISTING KB---\n\n"
            f"{new_info_block}\n"
            f"{batch['directive']}\n\n"
            "Rewrite rules for the sections you are updating:\n"
            "- Integrate all relevant new information into the appropriate subsections\n"
            "- Remove \"Needs Verification\" callouts where new info confirms details\n"
            "- Add new subsections if the new material reveals undocumented areas\n"
            "- Preserve content that is not affected by the new information\n"
            "- Write with authority where new docs confirm something; no hedging"
        )

        text = stream_with_retry(
            client,
            show_progress=True,
            model=config.MODEL,
            max_tokens=config.MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        section_texts.append(_strip_markdown_fences(text))

    # Reassemble: preserved title + all enriched section outputs
    parts = []
    if title_line:
        parts.append(title_line)
        parts.append("")
    parts.extend(section_texts)

    return "\n\n".join(parts)
