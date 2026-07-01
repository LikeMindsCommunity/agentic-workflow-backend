"""Shared paths and constants for the local MCP server."""

from __future__ import annotations

from pathlib import Path

# The package lives at <project>/likeminds_mcp, so the project root (which holds
# `.claude/commands/`) is one level up. Resolving from __file__ keeps this correct
# regardless of the directory the server is launched from.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

COMMANDS_DIR = PROJECT_ROOT / ".claude" / "commands"   # slash-command skills
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"       # multi-file Agent Skills
SESSIONS_DIR = PROJECT_ROOT / ".sessions"   # per-session sandboxes (gitignored)
KB_DIR = PROJECT_ROOT / "kb"                 # promoted deliverables land here

# Names of the in-process signal tools the engine intercepts.
ASK_USER_TOOL = "mcp__signals__ask_user"
EMIT_RESULT_TOOL = "mcp__signals__emit_result"

# Local HTTP bind for the MCP server. Clients connect at http://HOST:PORT/mcp .
HOST = "127.0.0.1"
PORT = 8787
