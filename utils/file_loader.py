"""
Input config loading and mode detection.
"""
import os
import yaml
import config


def load_input_config(config_path: str = None) -> dict:
    """
    Load input_config.yaml and return a prompt.

    The prompt is passed directly to the agent, which will intelligently:
    - Infer the platform name
    - Extract any documentation URLs
    - Understand the scope and requirements
    """
    if config_path is None:
        config_path = config.INPUT_CONFIG_PATH

    if not os.path.exists(config_path):
        return {"prompt": ""}

    with open(config_path, "r") as f:
        data = yaml.safe_load(f) or {}

    # New format: single prompt field (let the agent parse it)
    if "prompt" in data:
        return {"prompt": data.get("prompt", "").strip()}

    # Legacy format: reconstruct a prompt from the old fields
    platform = data.get("platform_name", "Unknown Platform")
    scope = data.get("scope", "").strip()
    urls = data.get("doc_urls") or []

    legacy_prompt = f"Platform: {platform}\n\n{scope}"
    if urls:
        legacy_prompt += "\n\nDocumentation URLs:\n" + "\n".join(f"- {u}" for u in urls)

    return {"prompt": legacy_prompt.strip()}


def detect_input_mode(artifacts_dir: str, docs_dir: str, prompt: str) -> str:
    """
    Determine mode based on what inputs are available.
    The agent will figure out URLs from the prompt itself.

    Modes:
      artifacts_and_docs — artifacts AND local docs exist
      artifacts_only     — artifacts only, no local docs
      docs_only          — local docs only, no artifacts
      prompt_only        — only a prompt (agent will find URLs/context)
      empty              — nothing at all
    """
    has_artifacts = _has_files(artifacts_dir)
    has_local_docs = _has_files(docs_dir)
    has_prompt = bool(prompt.strip())

    if has_artifacts and has_local_docs:
        return "artifacts_and_docs"
    if has_artifacts:
        return "artifacts_only"
    if has_local_docs:
        return "docs_only"
    if has_prompt:
        return "prompt_only"
    return "empty"


def _has_files(directory: str) -> bool:
    """Return True if the directory (or any subdirectory) contains at least one non-hidden file."""
    if not os.path.isdir(directory):
        return False
    for root, dirs, files in os.walk(directory):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if not f.startswith("."):
                return True
    return False
