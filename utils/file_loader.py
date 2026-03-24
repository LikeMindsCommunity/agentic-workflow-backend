"""
Input loading, mode detection, YAML config parsing,
and mid-loop doc reloading.
"""
import os
import json
import yaml
import config


def load_input_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = config.INPUT_CONFIG_PATH

    if not os.path.exists(config_path):
        return {
            "platform_name": "Unknown Platform",
            "scope": "",
            "artifacts_dir": "sample_artifacts",
            "docs_dir": "docs",
            "doc_urls": [],
            "follow_links": False,
            "max_pages": config.MAX_PAGES_PER_URL,
            "exclude_files": []
        }

    with open(config_path, "r") as f:
        data = yaml.safe_load(f) or {}

    return {
        "platform_name": data.get("platform_name", "Unknown Platform"),
        "scope": data.get("scope", "").strip(),
        "artifacts_dir": data.get("artifacts_dir", "sample_artifacts"),
        "docs_dir": data.get("docs_dir", "docs"),
        "doc_urls": data.get("doc_urls") or [],
        "follow_links": data.get("follow_links", False),
        "max_pages": data.get("max_pages", config.MAX_PAGES_PER_URL),
        "exclude_files": data.get("exclude_files") or []
    }


def load_artifacts(artifacts_dir: str = None, exclude_files: list = None) -> list[dict]:
    if artifacts_dir is None:
        artifacts_dir = config.ARTIFACTS_DIR
    elif not os.path.isabs(artifacts_dir):
        artifacts_dir = os.path.join(config.INPUT_DIR, artifacts_dir)

    exclude_files = set(exclude_files or [])
    artifacts = []
    if not os.path.exists(artifacts_dir):
        return artifacts

    for fname in sorted(os.listdir(artifacts_dir)):
        fpath = os.path.join(artifacts_dir, fname)
        if not os.path.isfile(fpath):
            continue
        # Skip hidden/system files (e.g. .DS_Store) and explicitly excluded files
        if fname.startswith(".") or fname in exclude_files:
            continue

        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            raw_content = f.read()

        artifact = {
            "filename": fname,
            "raw_content": raw_content,
            "file_type": os.path.splitext(fname)[1].lstrip("."),
            "parsed": None
        }

        if fname.endswith((".json", ".jsonl")):
            try:
                artifact["parsed"] = json.loads(raw_content)
            except json.JSONDecodeError:
                pass

        artifacts.append(artifact)

    return artifacts


def load_docs(docs_dir: str = None) -> list[dict]:
    if docs_dir is None:
        docs_dir = config.DOCS_DIR
    elif not os.path.isabs(docs_dir):
        docs_dir = os.path.join(config.INPUT_DIR, docs_dir)

    docs = []
    if not os.path.exists(docs_dir):
        return docs

    supported = {".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".csv", ".html"}

    for fname in sorted(os.listdir(docs_dir)):
        fpath = os.path.join(docs_dir, fname)
        if not os.path.isfile(fpath):
            continue

        ext = os.path.splitext(fname)[1].lower()
        if ext not in supported:
            continue

        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        docs.append({
            "filename": fname,
            "content": content,
            "file_type": ext.lstrip(".")
        })

    return docs


def reload_docs(docs_dir: str = None,
                already_loaded: list[dict] = None) -> list[dict]:
    """
    Re-read the docs directory and return only NEW files
    that were not in the already_loaded list.
    Called mid-loop when the user says they dropped new files.
    """
    all_docs = load_docs(docs_dir)

    if not already_loaded:
        return all_docs

    known_filenames = {d["filename"] for d in already_loaded}
    new_docs = [d for d in all_docs if d["filename"] not in known_filenames]

    return new_docs


def detect_input_mode(artifacts, docs, doc_urls, scope):
    has_artifacts = len(artifacts) > 0
    has_docs = len(docs) > 0 or len(doc_urls) > 0
    has_scope = len(scope.strip()) > 0

    if has_artifacts and has_docs:
        return "full"
    elif has_artifacts:
        return "artifacts_only"
    elif has_docs:
        return "urls_only"
    elif has_scope:
        return "scope_only"
    else:
        return "empty"


def summarize_inputs(artifacts, local_docs, scraped_docs, scope, mode):
    lines = [f"  Input mode: {mode.upper().replace('_', ' ')}", ""]

    if scope:
        preview = scope[:150] + "..." if len(scope) > 150 else scope
        lines.append(f"  Scope: {preview}")
        lines.append("")

    if artifacts:
        lines.append(f"  Artifacts ({len(artifacts)}):")
        for a in artifacts:
            size = len(a["raw_content"])
            parsed_status = "parsed" if a["parsed"] else "raw"
            lines.append(f"    - {a['filename']} ({a['file_type']}, {size} chars, {parsed_status})")
    else:
        lines.append("  Artifacts: None")
    lines.append("")

    all_docs = local_docs + scraped_docs
    if all_docs:
        lines.append(f"  Documentation ({len(all_docs)} sources):")
        for d in local_docs:
            lines.append(f"    - [local] {d['filename']} ({len(d['content'])} chars)")
        for d in scraped_docs:
            lines.append(f"    - [web]   {d['filename'][:60]} ({len(d['content'])} chars)")
    else:
        lines.append("  Documentation: None")

    return "\n".join(lines)
