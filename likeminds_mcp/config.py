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

# How the spawned Claude signals a pause (ask the user) or a finish (deliverable
# done): it writes one of these markers on its own line in its reply, and the engine
# watches the turn's streamed text for them. Deliberately NOT an MCP tool — a stdio
# MCP server is not guaranteed to finish connecting before a `claude -p` turn begins
# (the init event fires with the server still "pending"), so a signal tool can race
# and be missing on the turn. A text marker has no such race.
ASK_MARKER = "<<<LM_ASK>>>"
DONE_MARKER = "<<<LM_DONE>>>"

# Local HTTP bind for the MCP server. Clients connect at http://HOST:PORT/mcp .
HOST = "127.0.0.1"
PORT = 8787

# The Claude Code CLI we drive as a subprocess (one process per turn). Override
# with CLAUDE_BIN; otherwise resolve from PATH.
CLAUDE_BIN = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or "claude"

# Default model for spawned turns. "opus[1m]" = the latest Opus with the 1M-token
# context window (the `[1m]` suffix is how Claude Code opts into 1M context).
# Override with CLAUDE_AGENT_MODEL (e.g. "sonnet", "opus", or a full model id).
MODEL = os.environ.get("CLAUDE_AGENT_MODEL") or "opus[1m]"

# Optional extra MCP servers loaded into every spawned turn — e.g. playwright for a
# browser skill. A JSON file shaped like {"mcpServers": {...}}. If absent, the
# spawned Claude runs with NO MCP servers (see engine._mcp_config_json). See README.
EXTRA_MCP_CONFIG = PROJECT_ROOT / "likeminds_mcp" / "extra_mcp.json"

# Safety bounds (override the timeouts via env). These stop a hung or abandoned
# session from leaking a subprocess / task / sandbox indefinitely.
TURN_TIMEOUT = int(os.environ.get("LIKEMINDS_MCP_TURN_TIMEOUT", "1800000"))    # s; abort one hung turn
REPLY_TIMEOUT = int(os.environ.get("LIKEMINDS_MCP_REPLY_TIMEOUT", "3600000"))  # s; close an unanswered session
MAX_SESSIONS = 500   # evict oldest FINISHED session records beyond this

# --------------------------------------------------------------------------- #
# Deployment: persistent per-client workspaces, artifact upload, KB download
# --------------------------------------------------------------------------- #

# Root that holds persistent per-client workspaces: WORKSPACES_ROOT/<client>/
# <workspace_id>/{kb,artifacts}. Survives session purge and server restart — it is
# what makes a KB continue across separate chats keyed by the same workspace_id.
WORKSPACES_ROOT = PROJECT_ROOT / "outputs"

# Where finished KBs are packaged (zipped) for download. Served by the reverse
# proxy at PUBLIC_URL/download/<result_id>.zip and pruned by a cron.
DIST_DIR = PROJECT_ROOT / "outputs" / "_dist"

# Public base URL the reverse proxy answers on (e.g. https://mcp.example.com).
# Used to build the upload endpoint (/upload) and download links (/download/...).
# Defaults to the local bind so the flow also works without a proxy in dev.
PUBLIC_URL = (os.environ.get("LIKEMINDS_PUBLIC_URL") or f"http://{HOST}:{PORT}").rstrip("/")

# Secret used to HMAC-sign short-lived upload tickets. A caller gets a ticket from
# the `get_upload_ticket` tool (over the authenticated MCP channel) and presents it
# to the plain-HTTP /upload endpoint; the endpoint verifies it statelessly.
UPLOAD_SECRET = os.environ.get("LIKEMINDS_UPLOAD_SECRET") or "dev-insecure-upload-secret"
UPLOAD_TICKET_TTL = int(os.environ.get("LIKEMINDS_UPLOAD_TICKET_TTL", "900"))  # seconds

# Upload size caps (bytes). Enforced as bytes stream to disk so a large upload can
# neither OOM the process nor fill the disk unbounded.
MAX_FILE_BYTES = int(os.environ.get("LIKEMINDS_MAX_FILE_MB", "50")) * 1024 * 1024
MAX_WORKSPACE_BYTES = int(os.environ.get("LIKEMINDS_MAX_WORKSPACE_MB", "500")) * 1024 * 1024

# Zip-bundle expansion guards (zip-bomb protection).
MAX_ZIP_UNCOMPRESSED_BYTES = int(os.environ.get("LIKEMINDS_MAX_ZIP_MB", "1024")) * 1024 * 1024
MAX_ZIP_ENTRIES = int(os.environ.get("LIKEMINDS_MAX_ZIP_ENTRIES", "5000"))

# `input_paths` copies from the SERVER's filesystem, so it only makes sense when the
# caller shares a disk with the server (local dev / same box). Disable it on a remote
# deployment (LIKEMINDS_ALLOW_INPUT_PATHS=0) so remote callers are steered to the
# upload flow instead of silently attaching nothing.
ALLOW_INPUT_PATHS = os.environ.get("LIKEMINDS_ALLOW_INPUT_PATHS", "1").strip().lower() not in ("0", "false", "no")
