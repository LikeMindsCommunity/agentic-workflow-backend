"""
Input config loading and mode detection.
"""
import os
import yaml
import config


def load_input_config(config_path: str = None) -> dict:
    """Load input_config.yaml and return the three core fields."""
    if config_path is None:
        config_path = config.INPUT_CONFIG_PATH

    if not os.path.exists(config_path):
        return {"platform_name": "Unknown Platform", "scope": "", "doc_urls": []}

    with open(config_path, "r") as f:
        data = yaml.safe_load(f) or {}

    return {
        "platform_name": data.get("platform_name", "Unknown Platform"),
        "scope": data.get("scope", "").strip(),
        "doc_urls": data.get("doc_urls") or [],
    }


def detect_input_mode(
    artifacts_dir: str, docs_dir: str, doc_urls: list, scope: str
) -> str:
    """
    Determine mode based on what inputs are available.

    Modes:
      full           — artifacts AND (local docs or URLs)
      artifacts_only — artifacts only, no docs
      urls_only      — docs/URLs only, no artifacts
      scope_only     — only a scope description
      empty          — nothing at all
    """
    has_artifacts = _has_files(artifacts_dir)
    has_docs = bool(doc_urls) or _has_files(docs_dir)
    has_scope = bool(scope.strip())

    if has_artifacts and has_docs:
        return "full"
    if has_artifacts:
        return "artifacts_only"
    if has_docs:
        return "urls_only"
    if has_scope:
        return "scope_only"
    return "empty"


def _has_files(directory: str) -> bool:
    """Return True if the directory exists and contains at least one non-hidden file."""
    if not os.path.isdir(directory):
        return False
    return any(
        f for f in os.listdir(directory)
        if not f.startswith(".") and os.path.isfile(os.path.join(directory, f))
    )
