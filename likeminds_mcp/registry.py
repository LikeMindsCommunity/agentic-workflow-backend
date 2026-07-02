"""Skill registry: index both kinds of skill the server can run.

- Agent Skills  — `.claude/skills/<name>/SKILL.md` (multi-file, e.g. kb-builder),
  invoked by asking the model to use the skill with inputs=/output= args.
- Slash commands — `.claude/commands/<name>.md` (single file), invoked as
  `/<name> <args>`.

The dispatch tool validates a requested skill against this index; `list_skills`
returns the catalog. Adding a skill is dropping a file/folder here — no code change.
"""

from __future__ import annotations

from . import profiles
from .config import COMMANDS_DIR, SKILLS_DIR


def _frontmatter_field(text: str, field: str) -> str:
    """Pull `<field>:` out of a YAML frontmatter block, if present."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            break
        if lines[i].lstrip().startswith(f"{field}:"):
            return lines[i].split(":", 1)[1].strip()
    return ""


def _frontmatter_description(text: str) -> str:
    return _frontmatter_field(text, "description")


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
    """name -> {name, kind, path, description}. Skills take precedence over a
    command of the same name."""
    out: dict[str, dict] = {}
    # Slash commands.
    if COMMANDS_DIR.is_dir():
        for path in sorted(COMMANDS_DIR.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            mode = profiles.mode_for(path.stem, "command", None)
            out[path.stem] = {
                "name": path.stem, "kind": "command", "path": path,
                "description": _first_meaningful_line(text)[:200],
                "mode": mode, "profile": profiles.profile_for(mode),
            }
    # Agent Skills (override commands on name clash).
    if SKILLS_DIR.is_dir():
        for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
            name = skill_md.parent.name
            text = skill_md.read_text(encoding="utf-8")
            desc = _frontmatter_description(text) or _first_meaningful_line(text)
            mode = profiles.mode_for(name, "skill", _frontmatter_field(text, "x-engine-mode"))
            out[name] = {
                "name": name, "kind": "skill", "path": skill_md,
                "description": desc[:200],
                "mode": mode, "profile": profiles.profile_for(mode),
            }
    return out


def list_skills() -> list[dict[str, str]]:
    """Return [{name, description}] for every skill/command."""
    return [{"name": e["name"], "description": e["description"]} for e in _index().values()]


def resolve_skill(name: str) -> dict | None:
    """Return {name, kind, path, description} for a skill, or None if unknown."""
    return _index().get(name) if name else None


def skill_exists(name: str) -> bool:
    return resolve_skill(name) is not None
