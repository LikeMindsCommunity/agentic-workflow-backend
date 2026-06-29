"""Skill registry: index the command files in `.claude/commands/`.

A skill is just a command markdown file. The dispatch tool validates a requested
skill name against this index; `list_skills` returns the catalog for discovery.
Adding a skill is dropping a `.md` file here — no code or tool registration.
"""

from __future__ import annotations

from .config import COMMANDS_DIR


def _first_meaningful_line(text: str) -> str:
    """Best-effort one-line description: first prose line, skipping headings and
    any YAML frontmatter block."""
    lines = text.splitlines()
    i = 0
    # Skip a leading `--- ... ---` frontmatter block if present.
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                i = j + 1
                break
    for raw in lines[i:]:
        line = raw.strip()
        if not line or line.startswith("#") or line == "---":
            continue
        # Strip common markdown emphasis so the blurb reads cleanly.
        return line.strip("*_> ").strip()
    return ""


def list_skills() -> list[dict[str, str]]:
    """Return [{name, description}] for every command file."""
    if not COMMANDS_DIR.is_dir():
        return []
    skills = []
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        desc = _first_meaningful_line(path.read_text(encoding="utf-8"))
        skills.append({"name": path.stem, "description": desc[:200]})
    return skills


def skill_exists(name: str) -> bool:
    if not name:
        return False
    return (COMMANDS_DIR / f"{name}.md").is_file()
