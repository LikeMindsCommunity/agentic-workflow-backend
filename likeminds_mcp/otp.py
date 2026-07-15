"""Gupshup TwoFactorAuth — hosted email OTP (send + verify).

Two GET calls to the same endpoint; the service generates, emails, and validates the
one-time code, so this server never generates or stores an OTP itself. The response
is pipe-delimited text that begins with `success` on success, e.g. `success | ...`
(anything else is a failure). Mirrors the flow in agentic-core-backend.
"""

from __future__ import annotations

import httpx

from . import config


class OTPError(RuntimeError):
    """A send/verify call could not be completed (misconfig or upstream failure)."""


def _is_success(body: str) -> bool:
    """Gupshup returns `success | ...` on success; the first pipe field is the status."""
    if not body:
        return False
    return body.split("|", 1)[0].strip().lower() == "success"


async def send_otp(email: str) -> None:
    """Ask Gupshup to email an OTP to `email`. Raises OTPError on failure."""
    if not config.EMAIL_GHUPSHAP_KEY:
        raise OTPError("OTP service is not configured (EMAIL_GHUPSHAP_KEY unset).")
    params = {"email": email, "key": config.EMAIL_GHUPSHAP_KEY}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(config.GUPSHUP_OTP_URL, params=params)
    except httpx.HTTPError as e:
        raise OTPError(f"Could not reach the OTP service: {e}") from e
    if not (resp.status_code == 200 and _is_success(resp.text)):
        raise OTPError("Failed to send the verification code. Please try again.")


async def verify_otp(email: str, otp: str) -> bool:
    """Verify `otp` for `email` with Gupshup. Returns True iff the code is correct.
    Raises OTPError only when the service is unreachable/misconfigured (not on a wrong
    code — that just returns False)."""
    if not config.EMAIL_GHUPSHAP_KEY:
        raise OTPError("OTP service is not configured (EMAIL_GHUPSHAP_KEY unset).")
    params = {"email": email, "code": otp, "key": config.EMAIL_GHUPSHAP_KEY}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(config.GUPSHUP_OTP_URL, params=params)
    except httpx.HTTPError as e:
        raise OTPError(f"Could not reach the OTP service: {e}") from e
    return resp.status_code == 200 and _is_success(resp.text)
