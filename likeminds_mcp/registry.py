"""Skill registry: index the Agent Skills the server can run.

Agent Skills live at `.claude/skills/<name>/SKILL.md` (multi-file, e.g. kb-builder)
and are invoked by asking the model to use the skill with inputs=/output= args.

The dispatch tool validates a requested skill against this index; `list_skills`
returns the catalog. Adding a skill is dropping a folder here — no code change.
"""

from __future__ import annotations

from .config import SKILLS_DIR


def _frontmatter_description(text: str) -> str:
    """Pull `description:` out of a YAML frontmatter block, if present."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            break
        if lines[i].lstrip().startswith("description:"):
            return lines[i].split(":", 1)[1].strip()
    return ""


def _first_meaningful_line(text: str) -> str:
    """First prose line, skipping headings and any YAML frontmatter block."""
    lines = text.splitlines()
    i = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                i = j + 1
                break
    for raw in lines[i:]:
        line = raw.strip()
        if not line or line.startswith("#") or line == "---":
            continue
        return line.strip("*_> ").strip()
    return ""


def _index() -> dict[str, dict]:
    """name -> {name, description} for every Agent Skill under SKILLS_DIR."""
    out: dict[str, dict] = {}
    if SKILLS_DIR.is_dir():
        for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
            name = skill_md.parent.name
            text = skill_md.read_text(encoding="utf-8")
            desc = _frontmatter_description(text) or _first_meaningful_line(text)
            out[name] = {"name": name, "description": desc[:200]}
    return out


def list_skills() -> list[dict[str, str]]:
    """Return [{name, description}] for every skill."""
    return [{"name": e["name"], "description": e["description"]} for e in _index().values()]


def resolve_skill(name: str) -> dict | None:
    """Return {name, description} for a skill, or None if unknown."""
    return _index().get(name) if name else None


def skill_exists(name: str) -> bool:
    return resolve_skill(name) is not None
