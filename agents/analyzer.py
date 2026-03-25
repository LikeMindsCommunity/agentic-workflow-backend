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


def _build_user_prompt(artifacts: list[dict], docs: list[dict],
                       scope: str, mode: str) -> str:
    parts = []

    if scope:
        parts.append("=== SCOPE / REQUIREMENTS ===\n")
        parts.append(scope)
        parts.append("")

    if artifacts:
        parts.append("\n=== SAMPLE ARTIFACTS ===\n")
        for i, artifact in enumerate(artifacts, 1):
            parts.append(f"--- Artifact {i}: {artifact['filename']} ({artifact['file_type']}) ---")
            content = artifact["raw_content"]
            # if len(content) > 15000:
            #     content = content[:15000] + "\n... [TRUNCATED] ..."
            parts.append(content)
            parts.append("")

    if docs:
        parts.append("\n=== DOCUMENTATION ===\n")
        for i, doc in enumerate(docs, 1):
            source = doc.get("source_url", doc["filename"])
            parts.append(f"--- Document {i}: {source} ---")
            content = doc["content"]
            # if len(content) > 15000:
            #     content = content[:15000] + "\n... [TRUNCATED] ..."
            parts.append(content)
            parts.append("")

    if not artifacts and not docs:
        parts.append("\nNo artifacts or documentation provided. Build from scope alone.\n")

    parts.append("\nWrite the complete knowledge base document now.")
    return "\n".join(parts)


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
    Run the Analyzer agent. Returns the knowledge base as a markdown string.
    """
    text = stream_with_retry(
        client,
        show_progress=True,
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=_build_system_prompt(mode),
        messages=[{
            "role": "user",
            "content": _build_user_prompt(artifacts, docs, scope, mode)
        }]
    )
    return _strip_markdown_fences(text)


def run_enrichment(existing_kb: str, new_docs: list[dict] = None,
                   text_answers: str = "", scope: str = "",
                   mode: str = "full") -> str:
    """
    Rewrite the knowledge base incorporating new documentation and/or
    text answers from the client.

    Args:
        existing_kb: Current KB markdown content
        new_docs: List of new doc dicts (from URLs or files added mid-loop)
        text_answers: Free-text explanations the client typed
        scope: Original scope string
        mode: Input mode
    """
    system_prompt = _build_system_prompt(mode)

    # Build the enrichment prompt with separate sections for docs and answers
    prompt_parts = [
        "Here is the current knowledge base document:\n",
        "---BEGIN KNOWLEDGE BASE---",
        existing_kb,
        "---END KNOWLEDGE BASE---\n"
    ]

    if scope:
        prompt_parts.append(f"SCOPE: {scope}\n")

    has_new_docs = new_docs and len(new_docs) > 0
    has_answers = len(text_answers.strip()) > 0

    if has_new_docs:
        prompt_parts.append("The client has provided NEW DOCUMENTATION:\n")
        for i, doc in enumerate(new_docs, 1):
            source = doc.get("source_url", doc["filename"])
            prompt_parts.append(f"--- New Document {i}: {source} ---")
            content = doc["content"]
            # if len(content) > 15000:
            #     content = content[:15000] + "\n... [TRUNCATED] ..."
            prompt_parts.append(content)
            prompt_parts.append("")

    if has_answers:
        prompt_parts.append("The client has also provided these explanations:\n")
        prompt_parts.append("---BEGIN ANSWERS---")
        prompt_parts.append(text_answers)
        prompt_parts.append("---END ANSWERS---\n")

    prompt_parts.append("""Rewrite the knowledge base incorporating ALL the new information:
- Extract everything relevant from the new documentation and integrate it into the appropriate sections
- Incorporate the client's text explanations into the relevant sections
- Remove "Needs Verification" callouts where new info confirms details
- Add new subsections if the new material covers areas not previously documented
- Preserve everything that was not affected by the new information
- Update the "Known Gaps" section: remove resolved gaps, keep unresolved ones
- Write with authority where new docs confirm something; no hedging

Return the COMPLETE updated markdown document. Start directly with the heading.""")

    user_prompt = "\n".join(prompt_parts)

    text = stream_with_retry(
        client,
        show_progress=True,
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    return _strip_markdown_fences(text)
