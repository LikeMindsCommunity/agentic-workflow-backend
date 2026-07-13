"""Skill registry: index the Agent Skills the server can run.

Agent Skills live at `.claude/skills/<name>/SKILL.md` (multi-file, e.g. kb-builder)
and are invoked by asking the model to use the skill with inputs=/output= args.

The dispatch tool validates a requested skill against this index; `list_skills`
returns the catalog. Adding a skill is dropping a folder here — no code change.
"""

from __future__ import annotations

from .config import SKILLS_DIR


def frontmatter_field(text: str, field: str) -> str:
    """Pull a top-level `<field>:` value out of a YAML frontmatter block, if present.

    Handles a plain single-line value (`field: text`, quotes stripped) and a YAML
    block scalar (`field: >-` / `|` followed by an indented block — the form
    skill-generators emit for long descriptions), flattening the block to one line.
    Returns "" if the field is absent or there is no frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), len(lines))
    prefix = field + ":"
    for i in range(1, end):
        line = lines[i]
        if line[:1].isspace() or not line.startswith(prefix):
            continue  # only a top-level (unindented) frontmatter key
        value = line[len(prefix):].strip()
        if value[:1] in ("|", ">"):  # block scalar: flatten the indented body
            body = []
            for nxt in lines[i + 1:end]:
                if nxt.strip() and not nxt[:1].isspace():
                    break  # a dedented line ends the block
                body.append(nxt.strip())
            return " ".join(p for p in body if p)
        return value.strip("\"'").strip()
    return ""


def _frontmatter_description(text: str) -> str:
    """Pull `description:` out of a YAML frontmatter block, if present."""
    return frontmatter_field(text, "description")


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
