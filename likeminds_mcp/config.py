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

# ─── Multi-tenant identity (login token) ─────────────────────────────────────
# A user logs in at /login (email OTP) and gets back a STABLE token — their Mongo
# user _id — which their MCP client then sends on EVERY request in this header. The
# server maps the token to a tenant, so custom skills a tenant creates are visible
# only to that tenant (list_skills / run_skill are filtered by it). This is ORTHOGONAL
# to API_KEY_HEADER: the api-key header selects who PAYS for inference; this header
# selects WHO YOU ARE. A request with no (or an unverified) token is treated as
# anonymous — it sees only the shared built-in skills and can't install private ones.
USER_ID_HEADER = os.environ.get("LIKEMINDS_MCP_USER_HEADER", "x-user-id").strip() or "x-user-id"

# MongoDB — the tenant/user registry (mirrors agentic-core-backend's user model). A
# user row is created on OTP send and flipped is_verified=true on verify; the row _id
# is the token above. When MONGODB_URI/DB are unset the server runs WITHOUT verification:
# any token header is trusted opaquely as a tenant key (fine for local dev / a trusted
# network) — set Mongo in production to enforce verified login.
MONGODB_URI = os.environ.get("MONGODB_URI")
MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME")
MONGODB_USERS_COLLECTION = os.environ.get("MONGODB_USERS_COLLECTION", "users")
USE_MONGO = bool(MONGODB_URI and MONGODB_DB_NAME)
# Cache a token→verified lookup this many seconds so a client's frequent polls don't
# hit Mongo on every call.
TENANT_CACHE_TTL = int(os.environ.get("LIKEMINDS_MCP_TENANT_CACHE_TTL", "300"))

# Gupshup TwoFactorAuth — hosted email OTP. The service generates, emails, and
# validates the code, so the server only proxies send/verify and never stores OTPs.
EMAIL_GHUPSHAP_KEY = os.environ.get("EMAIL_GHUPSHAP_KEY")
GUPSHUP_OTP_URL = os.environ.get(
    "GUPSHUP_OTP_URL", "https://enterprise.smsgupshup.com/apps/TwoFactorAuth/incoming.php"
)

# ─── Global skill kill-switch ────────────────────────────────────────────────
# A JSON file listing skills disabled for EVERYONE — hidden from BOTH list_skills and
# run_skill (so a disabled skill can be neither listed nor run, by any tenant). Shape:
# {"disabled": ["skill-name", ...]}. Read fresh per call, so toggling needs no restart.
# LIKEMINDS_MCP_DISABLED_SKILLS is an optional comma-separated env override, merged in.
DISABLED_SKILLS_FILE = Path(
    os.environ.get("LIKEMINDS_MCP_DISABLED_SKILLS_FILE", str(PROJECT_ROOT / "disabled_skills.json"))
)
DISABLED_SKILLS_ENV = os.environ.get("LIKEMINDS_MCP_DISABLED_SKILLS", "")

# ─── OAuth 2.1 authorization (native MCP login) ──────────────────────────────
# When enabled, the server becomes an OAuth 2.1 authorization server + resource server:
# /mcp requires an `Authorization: Bearer <token>` and the client (Claude Code, claude.ai,
# Desktop) runs the browser login itself — no hand-pasted token. The user still verifies
# via the same Gupshup OTP page (it becomes the /authorize login UI); the access token maps
# to the Mongo user id = the tenant. Requires USE_MONGO and PUBLIC_BASE_URL (the issuer).
# While this is OFF the server keeps the header-based identity (USER_ID_HEADER) path.
MCP_OAUTH_ENABLED = os.environ.get("MCP_OAUTH_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")
PUBLIC_BASE_URL = (os.environ.get("PUBLIC_BASE_URL") or "").strip().rstrip("/") or None

# Token/code lifetimes (seconds) and the Mongo collections backing the OAuth store.
OAUTH_ACCESS_TTL = int(os.environ.get("MCP_OAUTH_ACCESS_TTL", "3600"))            # 1h access token
OAUTH_REFRESH_TTL = int(os.environ.get("MCP_OAUTH_REFRESH_TTL", str(60 * 60 * 24 * 30)))  # 30d refresh
OAUTH_CODE_TTL = int(os.environ.get("MCP_OAUTH_CODE_TTL", "600"))                # 10m auth code / pending login
OAUTH_SCOPE = os.environ.get("MCP_OAUTH_SCOPE", "mcp").strip() or "mcp"
OAUTH_CLIENTS_COLLECTION = os.environ.get("MCP_OAUTH_CLIENTS_COLLECTION", "oauth_clients")
OAUTH_TOKENS_COLLECTION = os.environ.get("MCP_OAUTH_TOKENS_COLLECTION", "oauth_tokens")
OAUTH_CODES_COLLECTION = os.environ.get("MCP_OAUTH_CODES_COLLECTION", "oauth_codes")
OAUTH_REQUESTS_COLLECTION = os.environ.get("MCP_OAUTH_REQUESTS_COLLECTION", "oauth_requests")

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
