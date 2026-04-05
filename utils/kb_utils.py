"""
KB file path helpers.
"""
import os
from datetime import datetime
from pathlib import Path

import config


def get_safe_name(platform_name: str) -> str:
    return platform_name.lower().replace(" ", "_")[:30]


def get_latest_kb(safe_name: str) -> str | None:
    """Return path to the most recently modified KB file, or None."""
    out_dir = Path(config.OUTPUT_DIR)
    if not out_dir.exists():
        return None
    files = sorted(out_dir.glob(f"kb_{safe_name}_*.md"), key=os.path.getmtime, reverse=True)
    return str(files[0]) if files else None


def make_kb_path(safe_name: str, label: str) -> str:
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(config.OUTPUT_DIR, f"kb_{safe_name}_{label}_{ts}.md")


def count_dir_files(directory: str) -> int:
    """Count non-hidden files in a directory (non-recursive)."""
    if not os.path.isdir(directory):
        return 0
    return sum(
        1 for f in os.listdir(directory)
        if not f.startswith(".") and os.path.isfile(os.path.join(directory, f))
    )
