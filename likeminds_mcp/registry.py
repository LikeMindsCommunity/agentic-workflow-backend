"""Skill registry: index the Agent Skills the server can run, scoped per tenant.

Agent Skills live at `.claude/skills/<folder>/SKILL.md` and are invoked by asking the
model to use the skill with inputs=/output= args. Skills come in two flavours:

  - BUILT-IN (shared): the folder name is the skill name (e.g. `kb-builder`). Visible
    to everyone.
  - CUSTOM (per-tenant): a skill a tenant generated at runtime, stored with an owner
    suffix `<clean-name>__u_<token>`. Visible ONLY to the tenant whose token matches.
    The suffix is also written into the SKILL.md `name:` frontmatter so the spawned
    CLI resolves EXACTLY that tenant's copy even though several tenants may share the
    same clean name.

On top of that a GLOBAL kill-switch (config.DISABLED_SKILLS_FILE / _ENV) hides named
skills from BOTH listing and resolution, so a disabled skill can be neither listed nor
run by anyone.

The pipeline driver validates each step's skill against this index (passing the caller's
tenant). Adding a built-in is still just dropping a folder here — no code change.
"""

from __future__ import annotations

import json

from .config import DISABLED_SKILLS_ENV, DISABLED_SKILLS_FILE, SKILLS_DIR

# Separates a custom skill's clean name from its owner token in the folder name and in
# the SKILL.md `name:`. Chosen so it can't be confused with a normal kebab-case skill
# name, and the token half (alnum only) can never contain it.
OWNER_SEP = "__u_"


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


def rewrite_frontmatter_name(text: str, new_name: str) -> str:
    """Return `text` with its top-level frontmatter `name:` set to `new_name`.

    Used when registering a custom skill so its `name:` matches its owner-suffixed
    folder — that is how the spawned CLI is made to resolve exactly one tenant's copy.
    Inserts a `name:` (or a whole frontmatter block) when none is present."""
    trailing = "\n" if text.endswith("\n") else ""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is not None:
            for i in range(1, end):
                s = lines[i]
                if not s[:1].isspace() and s.startswith("name:"):
                    lines[i] = f"name: {new_name}"
                    return "\n".join(lines) + trailing
            lines.insert(1, f"name: {new_name}")  # frontmatter, but no name key
            return "\n".join(lines) + trailing
    return f"---\nname: {new_name}\n---\n" + text  # no frontmatter at all


def split_owner(folder: str) -> tuple[str, str | None]:
    """`generate-x__u_abc123` -> ('generate-x', 'abc123'); a built-in -> (folder, None)."""
    clean, sep, owner = folder.rpartition(OWNER_SEP)
    if sep and clean and owner:
        return clean, owner
    return folder, None


def owned_folder(clean: str, tenant: str) -> str:
    """The on-disk folder / invocation name for a tenant's custom skill."""
    return f"{clean}{OWNER_SEP}{tenant}"


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


def _disabled() -> set[str]:
    """Names/folders globally disabled — from the JSON file and the env override.
    Best-effort: a missing or malformed file just yields the env set."""
    names: set[str] = {p.strip() for p in DISABLED_SKILLS_ENV.split(",") if p.strip()}
    try:
        if DISABLED_SKILLS_FILE.is_file():
            data = json.loads(DISABLED_SKILLS_FILE.read_text(encoding="utf-8"))
            for n in data.get("disabled") or []:
                if isinstance(n, str) and n.strip():
                    names.add(n.strip())
    except Exception:  # noqa: BLE001 — a bad kill-switch file must not break listing
        pass
    return names


def _index(tenant: str | None = None) -> dict[str, dict]:
    """clean-name -> {name, description, folder} for every skill VISIBLE to `tenant`.

    Visible = every built-in, plus custom skills owned by `tenant`. Globally-disabled
    skills (by clean name OR exact folder) are excluded. A tenant's own custom skill
    shadows a built-in of the same clean name (built-ins are indexed first, owned
    skills overwrite)."""
    if not SKILLS_DIR.is_dir():
        return {}
    disabled = _disabled()
    rows = []
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        folder = skill_md.parent.name
        clean, owner = split_owner(folder)
        rows.append((skill_md, folder, clean, owner))
    rows.sort(key=lambda r: r[3] is not None)  # built-ins (owner None) first, owned last

    out: dict[str, dict] = {}
    for skill_md, folder, clean, owner in rows:
        if clean in disabled or folder in disabled:
            continue
        if owner is not None and owner != tenant:  # someone else's private skill
            continue
        text = skill_md.read_text(encoding="utf-8")
        desc = _frontmatter_description(text) or _first_meaningful_line(text)
        # Never clip this. A skill's description is its contract with the calling agent:
        # required inputs, blocking gates and triggers all sit at the END of it. A clipped
        # description still reads as a complete sentence, so the agent invokes the skill
        # without the inputs it gates on, and the run dies deep in the skill (or worse,
        # improvises past the gate) instead of the agent simply asking for them up front.
        out[clean] = {"name": clean, "description": desc, "folder": folder}
    return out


def list_skills(tenant: str | None = None) -> list[dict[str, str]]:
    """Return [{name, description}] for every skill visible to `tenant`."""
    return [{"name": e["name"], "description": e["description"]} for e in _index(tenant).values()]


def resolve_skill(name: str, tenant: str | None = None) -> dict | None:
    """Return {name, description, folder} for a skill visible to `tenant`, else None.
    `folder` is the name to hand the CLI (owner-suffixed for a tenant's custom skill)."""
    return _index(tenant).get(name) if name else None


def skill_exists(name: str, tenant: str | None = None) -> bool:
    return resolve_skill(name, tenant) is not None
