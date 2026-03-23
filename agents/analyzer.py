"""
Analyzer Agent

Takes sample artifacts and documentation, produces a structured knowledge base
with confidence scores. This agent:
1. Decomposes the artifact structure (schema, fields, types, nesting)
2. Maps each element against provided documentation
3. Assigns confidence scores based on how well each element is understood
"""
import json
from anthropic import Anthropic
import config

client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

ANALYZER_SYSTEM_PROMPT = """You are an expert platform analyst working for LikeMinds. Your job is to reverse-engineer artifacts (JSON files, config files, etc.) that clients provide, and build a structured knowledge base that would allow an AI system to generate similar artifacts in the future.

You will receive:
1. One or more SAMPLE ARTIFACTS - these are real outputs from the client's platform
2. DOCUMENTATION - any docs the client has provided about their platform

Your task is to analyze these inputs and produce a structured knowledge base in JSON format.

IMPORTANT RULES:
- Be exhaustive. Every field, every nested object, every array element in the artifact must be accounted for.
- For each field, determine: data type, whether it's required, what valid values look like, and any constraints.
- If you find something in the artifact that is NOT explained by the docs, mark it with low confidence (0.3-0.5) and note what's unclear.
- If the docs explain something well, mark it with high confidence (0.8-1.0).
- If the docs partially explain it, mark it medium confidence (0.5-0.8).
- Look for PATTERNS across multiple artifacts if provided. What varies vs what stays constant?
- Identify dependencies: what objects reference other objects? What order must things be created in?
- Identify validation rules: what combinations are invalid? What constraints exist?

OUTPUT FORMAT - respond with ONLY valid JSON, no markdown fences, no preamble:
{
  "platform_name": "string",
  "artifact_type": "string - what kind of artifact this is",
  "artifact_description": "string - one paragraph describing what this artifact represents",
  "objects": [
    {
      "name": "string - object/entity name",
      "description": "string",
      "confidence": 0.0-1.0,
      "relationships": ["references to other object names"],
      "fields": [
        {
          "field_path": "dot.notation.path - e.g. workflow.nodes[].type",
          "data_type": "string|number|boolean|array|object|enum",
          "required": true/false,
          "description": "what this field represents",
          "valid_values": ["for enums, list all known values"],
          "default_value": "if known, null otherwise",
          "depends_on": "field_path of dependency, null if none",
          "constraints": ["list of rules/constraints as strings"],
          "confidence": 0.0-1.0,
          "source": "artifact_analysis|documentation|inferred"
        }
      ]
    }
  ],
  "dependencies": [
    {
      "source_object": "string",
      "target_object": "string",
      "relationship": "must_exist_before|references|contains",
      "description": "string"
    }
  ],
  "validation_rules": [
    {
      "rule_id": "string",
      "description": "string",
      "scope": ["which objects/fields"],
      "severity": "error|warning",
      "confidence": 0.0-1.0
    }
  ],
  "common_patterns": [
    {
      "pattern_name": "string",
      "description": "string",
      "example_summary": "string"
    }
  ],
  "gaps": [
    {
      "area": "string - which part of the artifact",
      "description": "string - what's unclear",
      "severity": "blocking|important|nice_to_have"
    }
  ]
}"""


def build_analysis_prompt(
    artifacts: list[dict],
    docs: list[dict],
    requirements: str | None = None,
) -> str:
    """Construct the user prompt with all artifacts, docs, and optional requirements."""
    parts = []

    # Requirements / scope section (if provided)
    if requirements:
        parts.append("=== REQUIREMENTS / SCOPE ===\n")
        parts.append("The client has defined the following scope and requirements for this knowledge base:")
        parts.append(requirements)
        parts.append("\nUse these requirements to focus your analysis and prioritize which fields and behaviors matter most.")
        parts.append("")

    parts.append("=== SAMPLE ARTIFACTS ===\n")
    for i, artifact in enumerate(artifacts, 1):
        parts.append(f"--- Artifact {i}: {artifact['filename']} (type: {artifact['file_type']}) ---")
        content = artifact["raw_content"]
        if len(content) > 15000:
            content = content[:15000] + "\n... [TRUNCATED - artifact continues] ..."
        parts.append(content)
        parts.append("")

    parts.append("\n=== DOCUMENTATION ===\n")
    if docs:
        for i, doc in enumerate(docs, 1):
            source_label = doc.get("source_url", doc["filename"])
            parts.append(f"--- Document {i}: {source_label} (type: {doc['file_type']}) ---")
            content = doc["content"]
            if len(content) > 15000:
                content = content[:15000] + "\n... [TRUNCATED - document continues] ..."
            parts.append(content)
            parts.append("")
    else:
        parts.append(
            "No documentation was provided. Analyze the artifacts based on their structure alone. "
            "Mark all fields with lower confidence (0.3-0.5) since there is no documentation to validate against. "
            "The Interrogator will ask the client comprehensive questions to fill all gaps."
        )

    parts.append("\nAnalyze the above and produce the structured knowledge base JSON.")

    return "\n".join(parts)


def run_analyzer(
    artifacts: list[dict],
    docs: list[dict],
    requirements: str | None = None,
) -> dict:
    """
    Run the analyzer agent on the provided artifacts and docs.
    Returns the parsed knowledge base dict.
    """
    prompt = build_analysis_prompt(artifacts, docs, requirements=requirements)

    response = client.messages.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=ANALYZER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = response.content[0].text.strip()

    # Clean potential markdown fences
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        # Remove first and last lines if they are fences
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = "\n".join(lines)

    try:
        kb_data = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Analyzer returned invalid JSON: {e}\nRaw response:\n{response_text[:500]}")

    return kb_data


def run_enrichment(kb_data: dict, additional_context: str) -> dict:
    """
    Re-run analysis with additional context (e.g. client answers to questions).
    Updates confidence scores and fills gaps.
    """
    prompt = f"""You previously analyzed a platform and produced this knowledge base:

{json.dumps(kb_data, indent=2)}

The client has now provided additional context:

{additional_context}

Update the knowledge base with this new information:
1. Update field descriptions and valid_values where the new info is relevant
2. Increase confidence scores for fields that are now better understood
3. Remove gaps that have been resolved
4. Add any new validation rules or constraints revealed by the new info
5. If the new info reveals NEW gaps or questions, add those

Return the complete updated knowledge base in the same JSON format. Return ONLY valid JSON."""

    response = client.messages.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=ANALYZER_SYSTEM_PROMPT,
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
        updated_data = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Enrichment returned invalid JSON: {e}\nRaw response:\n{response_text[:500]}")

    return updated_data
