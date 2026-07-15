"""MongoDB tenant/user registry + tenant resolution.

Mirrors agentic-core-backend's user model: one row per email, created on OTP send
and flipped `is_verified=true` on OTP verify. The user's Mongo `_id` (hex) is the
STABLE token the client sends back on every request (config.USER_ID_HEADER) to name
its tenant.

pymongo is blocking, so every DB call is wrapped in `asyncio.to_thread` to keep the
server's single event loop free. A small TTL cache fronts token→verified validation
so a client's frequent polls don't hit Mongo on each call.

When Mongo is not configured (config.USE_MONGO is False) the server still runs, just
WITHOUT verification: `resolve_tenant` trusts any non-empty token opaquely as the
tenant key. That keeps local/dev multi-tenant isolation working without a database;
production sets MONGODB_URI to enforce the verified-login gate.
"""

from __future__ import annotations

import asyncio
import datetime
import re
import time
from typing import Optional

from . import config

# Lazily-initialised singletons — pymongo is only imported/connected when Mongo is
# actually configured, so the server has no hard dependency on it otherwise.
_client = None
_db = None

# token(tenant-key) -> (is_verified, expires_at). Fronts the per-request Mongo lookup.
_verify_cache: dict[str, tuple[bool, float]] = {}

_HEX24 = re.compile(r"^[0-9a-f]{24}$")


def _tenant_key(token: str | None) -> Optional[str]:
    """Normalise a raw header token into a filesystem-safe tenant key, or None.

    A real login token is a 24-char Mongo ObjectId hex; we lowercase it and, for any
    other opaque value (dev mode), strip to [0-9a-z] so it can never escape a path or
    collide with the owner delimiter. Empty → None (anonymous)."""
    if not token:
        return None
    key = "".join(ch for ch in str(token).strip().lower() if ch.isalnum())
    return key or None


# ─── connection ──────────────────────────────────────────────────────────────

def _connect():
    """Return the Mongo database handle, connecting on first use. Raises if Mongo is
    not configured — callers that reach here (login flow) require it."""
    global _client, _db
    if _db is not None:
        return _db
    if not config.USE_MONGO:
        raise RuntimeError(
            "MongoDB is not configured. Set MONGODB_URI and MONGODB_DB_NAME to enable login."
        )
    from pymongo import MongoClient  # lazy import: only when Mongo is in use

    kwargs: dict = {"serverSelectionTimeoutMS": 8000}
    if (config.CLOUD_PROVIDER or "").upper() == "AWS" and config.CA_FILE_PATH:
        kwargs["tls"] = True
        kwargs["tlsCAFile"] = config.CA_FILE_PATH
    _client = MongoClient(config.MONGODB_URI, **kwargs)
    _db = _client[config.MONGODB_DB_NAME]
    return _db


def _users():
    return _connect()[config.MONGODB_USERS_COLLECTION]


def collection(name: str):
    """A Mongo collection handle by name (used by the OAuth store). Sync — call inside
    a worker thread (asyncio.to_thread) from async code, like the helpers below."""
    return _connect()[name]


# ─── sync DB ops (run in a worker thread) ────────────────────────────────────

def _get_or_create_sync(email: str) -> str:
    users = _users()
    doc = users.find_one({"email": email})
    if doc:
        return str(doc["_id"])
    now = datetime.datetime.utcnow()
    res = users.insert_one(
        {"email": email, "is_verified": False, "is_deleted": False,
         "created_at": now, "updated_at": now}
    )
    return str(res.inserted_id)


def _mark_verified_sync(email: str) -> Optional[str]:
    users = _users()
    now = datetime.datetime.utcnow()
    users.update_one(
        {"email": email},
        {"$set": {"is_verified": True, "updated_at": now, "last_login_at": now},
         "$setOnInsert": {"is_deleted": False, "created_at": now}},
        upsert=True,
    )
    doc = users.find_one({"email": email})
    if not doc:
        return None
    token = str(doc["_id"])
    _verify_cache.pop(_tenant_key(token) or "", None)  # fresh grant takes effect now
    return token


def _is_verified_sync(token: str) -> bool:
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        oid = ObjectId(token)
    except (InvalidId, TypeError, ValueError):
        return False
    doc = _users().find_one({"_id": oid})
    return bool(doc and doc.get("is_verified") and not doc.get("is_deleted"))


# ─── async wrappers used by the server ───────────────────────────────────────

async def get_or_create_user(email: str) -> str:
    """Ensure a user row exists for `email`; return its id (created unverified)."""
    return await asyncio.to_thread(_get_or_create_sync, email)


async def mark_verified(email: str) -> Optional[str]:
    """Flip the user verified (upserting if needed); return the stable token (id)."""
    return await asyncio.to_thread(_mark_verified_sync, email)


async def resolve_tenant(token: Optional[str]) -> Optional[str]:
    """Map a request's raw token header to a normalised tenant key, or None (anonymous).

    Mongo ON  → the token must be a VERIFIED, non-deleted user id (cached for
                config.TENANT_CACHE_TTL seconds).
    Mongo OFF → any non-empty token is trusted opaquely as the tenant key (dev mode).
    """
    key = _tenant_key(token)
    if key is None:
        return None
    if not config.USE_MONGO:
        return key
    now = time.time()
    hit = _verify_cache.get(key)
    if hit is not None and hit[1] > now:
        return key if hit[0] else None
    try:
        ok = await asyncio.to_thread(_is_verified_sync, str(token).strip())
    except Exception:  # noqa: BLE001 — a DB blip must not 500 the whole call; deny for now
        return None
    _verify_cache[key] = (ok, now + config.TENANT_CACHE_TTL)
    return key if ok else None
