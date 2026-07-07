"""Skill registry: index both kinds of skill the server can run.

- Agent Skills  — `.claude/skills/<name>/SKILL.md` (multi-file, e.g. kb-builder),
  invoked by asking the model to use the skill with inputs=/output= args.
- Slash commands — `.claude/commands/<name>.md` (single file), invoked as
  `/<name> <args>`.

The dispatch tool validates a requested skill against this index; `list_skills`
returns the catalog. Adding a skill is dropping a file/folder here — no code change.
"""

from __future__ import annotations

from pathlib import Path

from .config import COMMANDS_DIR, SKILLS_DIR

# Names starting with this prefix are TRANSIENT installs — a workspace-generated
# skill materialized into .claude/ just for one run (see server._install_generated_skill).
# They are hidden from the catalog so they never leak into list_skills.
TRANSIENT_PREFIX = "_ws_"


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


def _index_dirs(commands_dir: Path, skills_dir: Path) -> dict[str, dict]:
    """name -> {name, kind, path, description} for one (commands, skills) pair.
    Agent Skills take precedence over a command of the same name. Transient
    per-run installs (TRANSIENT_PREFIX) are skipped so they never show in the catalog."""
    out: dict[str, dict] = {}
    if commands_dir.is_dir():
        for path in sorted(commands_dir.glob("*.md")):
            if path.stem.startswith(TRANSIENT_PREFIX):
                continue
            text = path.read_text(encoding="utf-8")
            out[path.stem] = {
                "name": path.stem, "kind": "command", "path": path,
                "description": _first_meaningful_line(text)[:200],
            }
    if skills_dir.is_dir():
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            name = skill_md.parent.name
            if name.startswith(TRANSIENT_PREFIX):
                continue
            text = skill_md.read_text(encoding="utf-8")
            desc = _frontmatter_description(text) or _first_meaningful_line(text)
            out[name] = {
                "name": name, "kind": "skill", "path": skill_md,
                "description": desc[:200],
            }
    return out


def _index() -> dict[str, dict]:
    """The GLOBAL catalog: skills/commands under the project's .claude/."""
    return _index_dirs(COMMANDS_DIR, SKILLS_DIR)


def _index_workspace(skills_root: Path | None) -> dict[str, dict]:
    """The per-workspace catalog: skills this workspace generated. A generated skill
    is either a bare `<name>.md` (command) or a `<name>/SKILL.md` folder (agent
    skill), both under the workspace's skills/ dir."""
    if skills_root is None:
        return {}
    return _index_dirs(skills_root, skills_root)


def list_skills(skills_root: Path | None = None) -> list[dict[str, str]]:
    """Return [{name, description}] for every global skill/command, plus any skills
    generated in the given workspace (scoped: never another tenant's)."""
    merged = {**_index_workspace(skills_root), **_index()}  # global wins on name clash
    return [{"name": e["name"], "description": e["description"]} for e in merged.values()]


def resolve_skill(name: str, skills_root: Path | None = None) -> dict | None:
    """Resolve a skill by name. GLOBAL skills win over a workspace-generated one of
    the same name (a tenant can't shadow a curated skill). The returned entry carries
    `scope`: "global" or "workspace"."""
    if not name:
        return None
    g = _index().get(name)
    if g:
        return {**g, "scope": "global"}
    w = _index_workspace(skills_root).get(name)
    if w:
        return {**w, "scope": "workspace"}
    return None


def skill_exists(name: str, skills_root: Path | None = None) -> bool:
    return resolve_skill(name, skills_root) is not None
