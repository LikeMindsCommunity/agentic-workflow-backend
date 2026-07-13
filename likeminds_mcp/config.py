"""Shared paths, constants, and runtime config for the local MCP server."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

# The package lives at <project>/likeminds_mcp, so the project root (which holds
# `.claude/`) is one level up. Resolving from __file__ keeps this correct
# regardless of the directory the server is launched from.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

COMMANDS_DIR = PROJECT_ROOT / ".claude" / "commands"   # slash-command skills
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"       # multi-file Agent Skills
SESSIONS_DIR = PROJECT_ROOT / ".sessions"   # per-session sandboxes (gitignored)
RESULTS_DIR = PROJECT_ROOT / "outputs" / "mcp"   # promoted deliverables (under gitignored outputs/)

# How the spawned Claude signals a pause (ask the user) or a finish (deliverable
# done): it writes one of these markers on its own line in its reply, and the engine
# watches the turn's streamed text for them. Deliberately NOT an MCP tool — a stdio
# MCP server is not guaranteed to finish connecting before a `claude -p` turn begins
# (the init event fires with the server still "pending"), so a signal tool can race
# and be missing on the turn. A text marker has no such race.
ASK_MARKER = "<<<LM_ASK>>>"
DONE_MARKER = "<<<LM_DONE>>>"

# Local HTTP bind for the MCP server. Clients connect at http://HOST:PORT/mcp .
# Set LIKEMINDS_MCP_HOST=0.0.0.0 in production to accept external connections.
HOST = os.environ.get("LIKEMINDS_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("LIKEMINDS_MCP_PORT", "8787"))

# The Claude Code CLI we drive as a subprocess (one process per turn). Override
# with CLAUDE_BIN; otherwise resolve from PATH.
CLAUDE_BIN = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or "claude"

# Default model for spawned turns. "opus[1m]" = the latest Opus with the 1M-token
# context window (the `[1m]` suffix is how Claude Code opts into 1M context).
# Override with CLAUDE_AGENT_MODEL (e.g. "sonnet", "opus", or a full model id).
MODEL = os.environ.get("CLAUDE_AGENT_MODEL") or "opus[1m]"

# Safety bounds (override the timeouts via env). These stop a hung or abandoned
# session from leaking a subprocess / task / sandbox indefinitely.
TURN_TIMEOUT = int(os.environ.get("LIKEMINDS_MCP_TURN_TIMEOUT", "1800000"))    # s; abort one hung turn
REPLY_TIMEOUT = int(os.environ.get("LIKEMINDS_MCP_REPLY_TIMEOUT", "3600000"))  # s; close an unanswered session
MAX_SESSIONS = 500   # evict oldest FINISHED session records beyond this

# Cloudflare R2 — output delivery for remote clients.
# When all four vars are set, harvested deliverables are uploaded to R2 and
# presigned download URLs are returned in the done snapshot alongside result_id.
# Falls back to local-only (outputs/mcp/) when any var is missing.
R2_BUCKET     = os.environ.get("R2_BUCKET")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_ENDPOINT   = os.environ.get("R2_ENDPOINT")
R2_URL_EXPIRY = int(os.environ.get("R2_URL_EXPIRY", "3600"))  # presigned URL TTL in seconds
USE_R2        = all([R2_BUCKET, R2_ACCESS_KEY, R2_SECRET_KEY, R2_ENDPOINT])
