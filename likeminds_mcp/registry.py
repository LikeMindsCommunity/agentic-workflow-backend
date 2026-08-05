# Copyright 2026 LikeMinds
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Skill registry: index the Agent Skills the server can run.

Agent Skills live at `.claude/skills/<name>/SKILL.md` and are invoked by asking the
model to use the skill with inputs=/output= args. The folder name IS the skill name —
for the built-ins shipped in this repo and equally for a skill a run generated and the
server installed. There is one user (the operator running this server), so there is no
ownership, no per-caller scoping, and no private copies.

A GLOBAL kill-switch (config.DISABLED_SKILLS_FILE / _ENV) hides named skills from both
listing and resolution, so a disabled skill can be neither listed nor run.

The pipeline driver validates each step's skill against this index. Adding a skill is
still just dropping a folder here — no code change.
"""

from __future__ import annotations

import json

from .config import DISABLED_SKILLS_ENV, DISABLED_SKILLS_FILE, SKILLS_DIR


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

    Used when installing a generated skill so its `name:` matches the folder it landed
    in — that is what the spawned CLI resolves on. Inserts a `name:` (or a whole
    frontmatter block) when none is present."""
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
    """Skill names globally disabled — from the JSON file and the env override.
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


def _index() -> dict[str, dict]:
    """name -> {name, description, folder} for every runnable skill.
    Globally-disabled skills are excluded."""
    if not SKILLS_DIR.is_dir():
        return {}
    disabled = _disabled()
    out: dict[str, dict] = {}
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        name = skill_md.parent.name
        if name in disabled:
            continue
        text = skill_md.read_text(encoding="utf-8")
        desc = _frontmatter_description(text) or _first_meaningful_line(text)
        # Never clip this. A skill's description is its contract with the calling agent:
        # required inputs, blocking gates and triggers all sit at the END of it. A clipped
        # description still reads as a complete sentence, so the agent invokes the skill
        # without the inputs it gates on, and the run dies deep in the skill (or worse,
        # improvises past the gate) instead of the agent simply asking for them up front.
        out[name] = {"name": name, "description": desc, "folder": name}
    return out


def list_skills() -> list[dict[str, str]]:
    """Return [{name, description}] for every runnable skill."""
    return [{"name": e["name"], "description": e["description"]} for e in _index().values()]


def resolve_skill(name: str) -> dict | None:
    """Return {name, description, folder} for a runnable skill, else None.
    `folder` is the name to hand the CLI."""
    return _index().get(name) if name else None


