from fastapi import Response
from fastapi.responses import JSONResponse

from app.constants.token_constants import MAX_OTP_ATTEMPTS
from app.utils.cookies import set_auth_cookies
from app.utils.core_client import call_core
from app.utils.redis_client import (
    get_otp_attempts,
    increment_otp_attempts,
    reset_otp_attempts,
)
from app.utils.response import error_response, success_response
from app.utils.token_utils import create_tokens

_TOO_MANY_MSG = "Too many OTP attempts. Please try again after 30 minutes."


async def handle_request_otp(email: str) -> JSONResponse:
    if await get_otp_attempts(email) >= MAX_OTP_ATTEMPTS:
        return JSONResponse(status_code=429, content=error_response(_TOO_MANY_MSG))

    data, status = await call_core("post", "/user/otp", json={"email": email})

    if not data.get("success"):
        return JSONResponse(
            status_code=status,
            content=error_response(data.get("error_message", "Failed to send OTP")),
        )

    return JSONResponse(content=success_response())


async def handle_verify_otp(email: str, otp: str, response: Response) -> JSONResponse:
    if await get_otp_attempts(email) >= MAX_OTP_ATTEMPTS:
        return JSONResponse(status_code=429, content=error_response(_TOO_MANY_MSG))

    data, status = await call_core(
        "post", "/user/otp/verify", json={"email": email, "otp": otp}
    )

    if not data.get("success"):
        await increment_otp_attempts(email)
        return JSONResponse(
            status_code=status if status != 200 else 400,
            content=error_response(data.get("error_message", "Invalid OTP")),
        )

    await reset_otp_attempts(email)

    user_id = data["data"]["user_id"]
    vtm, rtm = create_tokens(user_id)

    result = JSONResponse(content=success_response(data.get("data")))
    set_auth_cookies(result, vtm.access_token, vtm.expires_at, rtm.refresh_token, rtm.expires_at)
    return result
