"""Per-skill engine profiles.

Each skill runs in a MODE that configures the engine's behavior:

- interactive_kb : full one-gap-at-a-time Q&A + ask-before-finish interlock
                   (kb-builder).
- oneshot        : produce the deliverable in one pass, no gap loop, no interlock
                   (config-agent, api-agent, code-agent, and unknown skills).
- command        : repo/report commands — same engine behavior as oneshot.
- execution      : live-executing skills (runner-agent) — NOT supported behind the
                   dispatcher yet; mapped to safe oneshot behavior so it can't
                   deadlock, but should be run through a dedicated gated path.

A skill may override its mode with an `x-engine-mode:` field in its SKILL.md
frontmatter; otherwise the name map below applies, then a kind-based default.
"""

from __future__ import annotations

# mode -> engine behavior
MODE_CONFIG: dict[str, dict] = {
    "interactive_kb": {"harness": "interactive", "interlock": True},
    "oneshot":        {"harness": "oneshot",     "interlock": False},
    "command":        {"harness": "oneshot",     "interlock": False},
    "execution":      {"harness": "oneshot",     "interlock": False},
}
DEFAULT_MODE = "oneshot"

# explicit skill-name -> mode overrides
SKILL_MODES: dict[str, str] = {
    "kb-builder": "interactive_kb",
    "config-agent": "oneshot",
    "api-agent": "oneshot",
    "code-agent": "oneshot",
    "runner-agent": "execution",
}


def mode_for(name: str, kind: str, frontmatter_mode: str | None = None) -> str:
    """Resolve a skill's mode: frontmatter override → name map → kind default."""
    if frontmatter_mode in MODE_CONFIG:
        return frontmatter_mode
    if name in SKILL_MODES:
        return SKILL_MODES[name]
    if kind == "command":
        return "command"
    return DEFAULT_MODE


def profile_for(mode: str) -> dict:
    return MODE_CONFIG.get(mode, MODE_CONFIG[DEFAULT_MODE])
