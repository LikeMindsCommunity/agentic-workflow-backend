"""
Utility to load and categorize input files from the inputs directory.

Supports three input modes:
  1. Local files in inputs/docs/          - full doc content
  2. URL list in inputs/docs/urls.txt     - fetches docs from the web
  3. inputs/requirements.md              - scope/requirements definition
"""
import os
import json
import re
from urllib.request import urlopen, Request
from urllib.error import URLError
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# HTML → plain text helper
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    """Minimal HTML parser that strips tags and decodes entities."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_tags = {"script", "style", "nav", "footer", "header"}
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._skip_tags and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self._parts)


def _html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


# ---------------------------------------------------------------------------
# URL fetching
# ---------------------------------------------------------------------------

def fetch_url_as_doc(url: str) -> dict | None:
    """
    Fetch a URL and return a doc dict, or None on failure.
    Handles HTML pages (strips tags) and plain text/markdown.
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; LikeMinds-Layer1/1.0)"}
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "").lower()
            raw = resp.read().decode("utf-8", errors="replace")
    except URLError as e:
        print(f"  [WARNING] Could not fetch {url}: {e}")
        return None

    if "html" in content_type:
        text = _html_to_text(raw)
        # Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
    else:
        text = raw

    if not text.strip():
        print(f"  [WARNING] Fetched empty content from {url}")
        return None

    # Use last path segment as a pseudo-filename
    slug = url.rstrip("/").split("/")[-1] or "index"
    slug = re.sub(r"[^a-zA-Z0-9._-]", "_", slug)

    return {
        "filename": f"[URL] {slug}",
        "content": text,
        "file_type": "url",
        "source_url": url,
    }


def load_docs_from_url_list(urls_file: str) -> list[dict]:
    """
    Read a file containing one URL per line and fetch each as a doc.
    Lines starting with '#' or empty lines are ignored.
    """
    if not os.path.exists(urls_file):
        return []

    with open(urls_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    urls = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    urls = [u for u in urls if _is_url(u)]

    if not urls:
        return []

    print(f"  Fetching {len(urls)} URL(s) from {os.path.basename(urls_file)}...")
    docs = []
    for url in urls:
        doc = fetch_url_as_doc(url)
        if doc:
            docs.append(doc)
            print(f"    OK  {url}")

    return docs


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------

def load_artifacts(artifacts_dir: str) -> list[dict]:
    """
    Load all sample artifacts from the artifacts directory.
    Returns a list of dicts with filename, content (raw string), and parsed content if JSON.
    """
    artifacts = []
    if not os.path.exists(artifacts_dir):
        return artifacts

    for fname in sorted(os.listdir(artifacts_dir)):
        fpath = os.path.join(artifacts_dir, fname)
        if not os.path.isfile(fpath):
            continue

        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            raw_content = f.read()

        artifact = {
            "filename": fname,
            "raw_content": raw_content,
            "file_type": os.path.splitext(fname)[1].lstrip("."),
            "parsed": None,
        }

        if fname.endswith((".json", ".jsonl")):
            try:
                artifact["parsed"] = json.loads(raw_content)
            except json.JSONDecodeError:
                pass

        artifacts.append(artifact)

    return artifacts


# ---------------------------------------------------------------------------
# Docs (local files + URLs)
# ---------------------------------------------------------------------------

def load_docs(docs_dir: str) -> list[dict]:
    """
    Load documentation from the docs directory.

    Two sources are combined:
      1. Local files with a supported extension (not urls.txt)
      2. URLs listed in urls.txt (one per line)

    Returns a list of doc dicts with: filename, content, file_type,
    and optionally source_url for URL-fetched docs.
    """
    docs = []
    if not os.path.exists(docs_dir):
        return docs

    supported_extensions = {".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".csv", ".html"}

    for fname in sorted(os.listdir(docs_dir)):
        fpath = os.path.join(docs_dir, fname)
        if not os.path.isfile(fpath):
            continue

        # urls.txt is handled separately below
        if fname.lower() == "urls.txt":
            continue

        ext = os.path.splitext(fname)[1].lower()
        if ext not in supported_extensions:
            continue

        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        docs.append({
            "filename": fname,
            "content": content,
            "file_type": ext.lstrip("."),
        })

    # Fetch URL-based docs
    urls_file = os.path.join(docs_dir, "urls.txt")
    url_docs = load_docs_from_url_list(urls_file)
    docs.extend(url_docs)

    return docs


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------

def load_requirements(requirements_path: str) -> str | None:
    """
    Load the optional scope/requirements file.
    Returns the file content as a string, or None if it doesn't exist.
    """
    if not os.path.exists(requirements_path):
        return None

    with open(requirements_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read().strip()

    return content if content else None


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def summarize_inputs(
    artifacts: list[dict],
    docs: list[dict],
    requirements: str | None = None,
) -> str:
    lines = []

    if requirements:
        lines.append("Requirements / Scope: LOADED")
        # Show first 2 lines as a preview
        preview = "\n".join(requirements.splitlines()[:2])
        lines.append(f"  {preview}")
        lines.append("")

    lines.append(f"Loaded {len(artifacts)} artifact(s):")
    for a in artifacts:
        size = len(a["raw_content"])
        parsed_status = "parsed" if a["parsed"] else "raw"
        lines.append(f"  - {a['filename']} ({a['file_type']}, {size} chars, {parsed_status})")

    local_docs = [d for d in docs if d.get("file_type") != "url"]
    url_docs = [d for d in docs if d.get("file_type") == "url"]

    lines.append(f"\nLoaded {len(local_docs)} local documentation file(s):")
    for d in local_docs:
        size = len(d["content"])
        lines.append(f"  - {d['filename']} ({d['file_type']}, {size} chars)")

    if url_docs:
        lines.append(f"\nFetched {len(url_docs)} URL-based documentation source(s):")
        for d in url_docs:
            size = len(d["content"])
            lines.append(f"  - {d['source_url']} ({size} chars)")

    if not docs:
        lines.append("\n  (No documentation provided - artifacts-only mode)")

    return "\n".join(lines)
