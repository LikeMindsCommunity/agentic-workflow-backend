"""Shared paths, constants, and runtime config for the local MCP server."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

# The package lives at <project>/likeminds_mcp, so the project root (which holds
# `.claude/`) is one level up. Resolving from __file__ keeps this correct
# regardless of the directory the server is launched from.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"       # multi-file Agent Skills
SESSIONS_DIR = PROJECT_ROOT / ".sessions"   # per-session sandboxes (gitignored)
RESULTS_DIR = PROJECT_ROOT / "outputs" / "mcp"   # promoted deliverables (under gitignored outputs/)

# ─── Host-path resolution ────────────────────────────────────────────────────
# `input_paths` is resolved against the SERVER's filesystem. Under Docker that is the
# CONTAINER's filesystem, where a caller's host path (/Users/…, C:\…) simply does not
# exist — so a caller pasting a perfectly valid local path gets an empty inputs dir.
#
# HOST_MOUNT_SOURCE is the host directory bind-mounted read-only at HOST_MOUNT_TARGET
# (default /host). A path under it is rewritten onto the mount, so ANY host path the
# caller can name works with no copying and no translation. docker-compose.yml defaults
# it to the host's $HOME, which is broad on purpose: everything under it is readable by a
# CLI running with --permission-mode bypassPermissions, including ~/.ssh and other
# projects' secrets. Set LIKEMINDS_HOST_MOUNT to something narrower to shrink that
# surface — at the cost of paths outside it no longer resolving.
#
# Empty HOST_MOUNT_SOURCE disables the rewrite entirely; a server run directly on the
# host never needs it, because there the caller's paths resolve natively.
# Whatever still fails to resolve is reported as an error, never skipped.
# IN_CONTAINER and HOST_MOUNT_TARGET are declared in the Dockerfile (both are properties
# of the image, fixed at build time); HOST_MOUNT_SOURCE comes from docker-compose.yml,
# which alone knows the host-side path. Nothing is defaulted here — outside the image all
# three are empty, which is correct for a server run directly on the host, where the
# caller's paths need no rewriting. .strip() because a stray space in a hand-edited .env
# would otherwise make every rebase silently miss.
IN_CONTAINER = os.environ.get("LIKEMINDS_IN_CONTAINER", "").strip() == "1"
HOST_MOUNT_SOURCE = os.environ.get("LIKEMINDS_HOST_MOUNT", "").strip()
HOST_MOUNT_TARGET = os.environ.get("LIKEMINDS_HOST_MOUNT_AT", "").strip()

# The host-visible ABSOLUTE path of `outputs/`. It exists so the server can tell the
# spawned skill a path the CALLER can actually open — a pause that says "look at this
# screenshot" is useless if the path only resolves inside the server. Two cases:
#   * Server on the host: PROJECT_ROOT is already the real host path, so outputs/ under
#     it is directly openable — no env needed.
#   * Server in Docker: PROJECT_ROOT is /app, and only docker-compose.yml knows the host
#     side of the `./outputs:/app/outputs` bind mount, so it injects LIKEMINDS_HOST_OUTPUTS.
# A relative path can NOT stand in here: the caller's viewer resolves it against the
# caller's own cwd, not the server's, which is exactly why a cited `outputs/…` path fails
# to preview. Hard-coding an absolute path is wrong too — it breaks every other checkout
# (a second deployment dir, Docker's /app) — so it is derived, with the env override.
_host_outputs = os.environ.get("LIKEMINDS_HOST_OUTPUTS", "").strip()
HOST_OUTPUTS_ROOT = Path(_host_outputs) if _host_outputs else (PROJECT_ROOT / "outputs")

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
# NOTE for BYOK (below): a raw Anthropic API key only reaches 1M-context Opus if the
# account has that access — otherwise set CLAUDE_AGENT_MODEL to a model it can serve.
MODEL = os.environ.get("CLAUDE_AGENT_MODEL") or "opus[1m]"

# ─── Per-request BYOK (bring-your-own-key) ───────────────────────────────────
# The caller may send its own Anthropic key in a request header; the server reads it
# fresh per request and injects it into the spawned CLI, so that turn's inference
# bills to the caller's account. The key is never persisted (no disk, no logs) — it
# lives only in the child process environment for the duration of the turn. This is
# the "header shortcut" that works on Claude Code, which attaches configured headers
# on every request. API_KEY_HEADER is the header to read the key from (default
# x-api-key; an `Authorization: Bearer <key>` value is also accepted).
#
# The header key is the FIRST choice of credential per request; with no header key the
# spawned CLI falls back to the server's own creds (see server._configure_auth), in
# order: a server ANTHROPIC_API_KEY from .env, else the Claude subscription token.
API_KEY_HEADER = os.environ.get("LIKEMINDS_MCP_KEY_HEADER", "x-api-key").strip() or "x-api-key"

# ─── Global skill kill-switch ────────────────────────────────────────────────
# A JSON file listing skills disabled for EVERYONE — hidden from both the registry
# listing and the pipeline driver, so a disabled skill can be neither listed nor run.
# Shape: {"disabled": ["skill-name", ...]}. Read fresh per call, so toggling needs no
# restart. LIKEMINDS_MCP_DISABLED_SKILLS is an optional comma-separated env override,
# merged in.
DISABLED_SKILLS_FILE = Path(
    os.environ.get("LIKEMINDS_MCP_DISABLED_SKILLS_FILE", str(PROJECT_ROOT / "disabled_skills.json"))
)
DISABLED_SKILLS_ENV = os.environ.get("LIKEMINDS_MCP_DISABLED_SKILLS", "")

# Safety bounds (override the timeouts via env). These stop a hung or abandoned
# session from leaking a subprocess / task / sandbox indefinitely.
TURN_TIMEOUT = int(os.environ.get("LIKEMINDS_MCP_TURN_TIMEOUT", "1800"))    # s; abort one hung turn (default 30 min)
REPLY_TIMEOUT = int(os.environ.get("LIKEMINDS_MCP_REPLY_TIMEOUT", "3600"))  # s; close an unanswered session (default 1 h)
MAX_SESSIONS = 500   # evict oldest FINISHED session records beyond this
