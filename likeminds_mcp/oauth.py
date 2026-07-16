"""OAuth 2.1 authorization server, backed by Mongo + the Gupshup OTP login.

The MCP Python SDK ships the OAuth machinery (the /authorize, /token, /register, /revoke
handlers, the two .well-known metadata docs, PKCE verification, and the bearer-validation
middleware). We only implement the storage/identity half: this `OAuthAuthorizationServerProvider`.

Design:
  • Tokens/codes/clients are OPAQUE random strings stored in Mongo (no JWT signing keys to
    manage; revocation is a delete). Each token row carries the `user_id` (the Mongo user
    id) which is the tenant the access token maps to.
  • The user authenticates with the SAME email-OTP page. `authorize()` parks the pending
    request and redirects the browser to /login?lg=<id>; after the OTP verifies,
    `complete_authorization()` mints the auth code and redirects back to the client.
  • The subclassed token models carry `user_id` so it survives the SDK's load→exchange and
    load_access_token→tool round-trips (the base models have no user field).

Everything here requires Mongo; it's only wired in when config.MCP_OAUTH_ENABLED.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from . import config, db

# ─── token models that carry the tenant (user_id) ───────────────────────────

class LMAuthorizationCode(AuthorizationCode):
    user_id: str


class LMRefreshToken(RefreshToken):
    user_id: str
    resource: str | None = None


class LMAccessToken(AccessToken):
    user_id: str


# short-lived cache so per-request bearer validation doesn't hit Mongo every call
_access_cache: dict[str, tuple[Optional[LMAccessToken], float]] = {}


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _strip_id(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "_id"}


def _add_query(url: str, params: dict) -> str:
    """Append query params to a (possibly query-bearing) redirect URI, RFC-correctly."""
    parts = urlparse(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    for k, v in params.items():
        if v is not None:
            q[k] = v
    return urlunparse(parts._replace(query=urlencode(q)))


# ─── sync Mongo ops (run inside asyncio.to_thread) ──────────────────────────

def _clients():
    return db.collection(config.OAUTH_CLIENTS_COLLECTION)


def _requests():
    return db.collection(config.OAUTH_REQUESTS_COLLECTION)


def _codes():
    return db.collection(config.OAUTH_CODES_COLLECTION)


def _tokens():
    return db.collection(config.OAUTH_TOKENS_COLLECTION)


def _get_client_sync(cid: str) -> Optional[dict]:
    return _clients().find_one({"client_id": cid})


def _put_client_sync(doc: dict) -> None:
    _clients().update_one({"client_id": doc["client_id"]}, {"$set": doc}, upsert=True)


def _put_request_sync(doc: dict) -> None:
    _requests().insert_one(doc)


def _pop_request_sync(login_id: str) -> Optional[dict]:
    col = _requests()
    doc = col.find_one({"login_id": login_id})
    if doc:
        col.delete_one({"login_id": login_id})
    return doc


def _put_code_sync(doc: dict) -> None:
    _codes().insert_one(doc)


def _get_code_sync(code: str) -> Optional[dict]:
    return _codes().find_one({"code": code})


def _del_code_sync(code: str) -> None:
    _codes().delete_one({"code": code})


def _put_token_sync(doc: dict) -> None:
    _tokens().insert_one(doc)


def _get_token_by_access_sync(t: str) -> Optional[dict]:
    return _tokens().find_one({"access_token": t})


def _get_token_by_refresh_sync(t: str) -> Optional[dict]:
    return _tokens().find_one({"refresh_token": t})


def _del_token_any_sync(t: str) -> None:
    _tokens().delete_one({"$or": [{"access_token": t}, {"refresh_token": t}]})


# ─── the provider ───────────────────────────────────────────────────────────

class MongoOAuthProvider(
    OAuthAuthorizationServerProvider[LMAuthorizationCode, LMRefreshToken, LMAccessToken]
):
    # --- client registration (DCR) ---
    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        doc = await asyncio.to_thread(_get_client_sync, client_id)
        return OAuthClientInformationFull(**_strip_id(doc)) if doc else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        await asyncio.to_thread(
            _put_client_sync, client_info.model_dump(mode="json", exclude_none=True)
        )

    # --- authorization: park the request, send the browser to the OTP page ---
    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        login_id = secrets.token_urlsafe(24)
        await asyncio.to_thread(_put_request_sync, {
            "login_id": login_id,
            "client_id": client.client_id,
            "redirect_uri": str(params.redirect_uri),
            "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
            "code_challenge": params.code_challenge,
            "scopes": params.scopes or [config.OAUTH_SCOPE],
            "state": params.state,
            "resource": params.resource,
            "expires_at": time.time() + config.OAUTH_CODE_TTL,
        })
        base = config.PUBLIC_BASE_URL or ""
        return f"{base}/login?lg={login_id}"

    # --- authorization code ---
    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> Optional[LMAuthorizationCode]:
        doc = await asyncio.to_thread(_get_code_sync, authorization_code)
        if not doc or doc["client_id"] != client.client_id or doc["expires_at"] < time.time():
            return None
        return LMAuthorizationCode(
            code=doc["code"], scopes=doc["scopes"], expires_at=doc["expires_at"],
            client_id=doc["client_id"], code_challenge=doc["code_challenge"],
            redirect_uri=doc["redirect_uri"],
            redirect_uri_provided_explicitly=doc["redirect_uri_provided_explicitly"],
            resource=doc.get("resource"), user_id=doc["user_id"],
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: LMAuthorizationCode
    ) -> OAuthToken:
        await asyncio.to_thread(_del_code_sync, authorization_code.code)  # one-time use
        return await self._issue(
            client.client_id, authorization_code.user_id,
            list(authorization_code.scopes), authorization_code.resource,
        )

    # --- refresh token ---
    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> Optional[LMRefreshToken]:
        doc = await asyncio.to_thread(_get_token_by_refresh_sync, refresh_token)
        if not doc or doc["client_id"] != client.client_id or doc["refresh_expires_at"] < time.time():
            return None
        return LMRefreshToken(
            token=refresh_token, client_id=doc["client_id"], scopes=doc["scopes"],
            expires_at=int(doc["refresh_expires_at"]), user_id=doc["user_id"],
            resource=doc.get("resource"),
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: LMRefreshToken, scopes: list[str]
    ) -> OAuthToken:
        # rotate: invalidate the old pair, issue a fresh one (OAuth 2.1 for public clients)
        await asyncio.to_thread(_del_token_any_sync, refresh_token.token)
        _access_cache.clear()  # cheap + rare; old access token for this pair is now void
        want = scopes or list(refresh_token.scopes)
        return await self._issue(client.client_id, refresh_token.user_id, want, refresh_token.resource)

    # --- access token validation (every /mcp request) ---
    async def load_access_token(self, token: str) -> Optional[LMAccessToken]:
        now = time.time()
        hit = _access_cache.get(token)
        if hit is not None and hit[1] > now:
            return hit[0]
        doc = await asyncio.to_thread(_get_token_by_access_sync, token)
        at: Optional[LMAccessToken] = None
        if doc and doc["access_expires_at"] > now:
            at = LMAccessToken(
                token=token, client_id=doc["client_id"], scopes=doc["scopes"],
                expires_at=int(doc["access_expires_at"]), resource=doc.get("resource"),
                user_id=doc["user_id"],
            )
        # cache the result, but never past the token's own expiry (and only briefly for misses)
        ttl = min(config.TENANT_CACHE_TTL, doc["access_expires_at"] - now) if at else 30
        _access_cache[token] = (at, now + max(1, ttl))
        return at

    async def revoke_token(self, token) -> None:
        await asyncio.to_thread(_del_token_any_sync, token.token)
        _access_cache.pop(token.token, None)

    # --- helper: mint + store a token pair ---
    async def _issue(self, client_id: str, user_id: str, scopes: list[str], resource: Optional[str]) -> OAuthToken:
        access, refresh = _new_token(), _new_token()
        now = time.time()
        await asyncio.to_thread(_put_token_sync, {
            "access_token": access, "refresh_token": refresh,
            "client_id": client_id, "user_id": user_id, "scopes": scopes, "resource": resource,
            "access_expires_at": now + config.OAUTH_ACCESS_TTL,
            "refresh_expires_at": now + config.OAUTH_REFRESH_TTL,
            "created_at": now,
        })
        _access_cache.pop(access, None)
        return OAuthToken(
            access_token=access, token_type="Bearer",
            expires_in=config.OAUTH_ACCESS_TTL, scope=" ".join(scopes), refresh_token=refresh,
        )


provider = MongoOAuthProvider()


# ─── used by the login page to finish the browser flow ──────────────────────

async def complete_authorization(login_id: str, user_id: str) -> Optional[str]:
    """After the OTP verifies in an OAuth login, mint the authorization code bound to the
    verified user and return the redirect URL back to the MCP client (redirect_uri?code&state).
    Returns None if the pending request is unknown or expired."""
    req = await asyncio.to_thread(_pop_request_sync, login_id)
    if not req or req["expires_at"] < time.time():
        return None
    code = _new_token()
    await asyncio.to_thread(_put_code_sync, {
        "code": code, "client_id": req["client_id"], "user_id": user_id,
        "redirect_uri": req["redirect_uri"],
        "redirect_uri_provided_explicitly": req["redirect_uri_provided_explicitly"],
        "code_challenge": req["code_challenge"], "scopes": req["scopes"],
        "resource": req.get("resource"),
        "expires_at": time.time() + config.OAUTH_CODE_TTL,
    })
    return _add_query(req["redirect_uri"], {"code": code, "state": req.get("state")})
