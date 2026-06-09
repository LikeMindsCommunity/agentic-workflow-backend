from fastapi import Response
from fastapi.responses import JSONResponse

from app.utils.cookies import clear_auth_cookies, set_auth_cookies
from app.utils.redis_client import blacklist_tokens, is_rtm_blacklisted
from app.utils.response import error_response, success_response
from app.utils.token_utils import create_tokens, extract_rtm, extract_vtm


async def handle_refresh(refresh_token: str) -> JSONResponse:
    rtm = extract_rtm(refresh_token)
    if not rtm:
        return JSONResponse(status_code=401, content=error_response("Invalid refresh token"))

    if await is_rtm_blacklisted(rtm.refresh_uuid):
        return JSONResponse(
            status_code=401, content=error_response("Session expired. Please login again.")
        )

    new_vtm, new_rtm = create_tokens(rtm.user_id)

    result = JSONResponse(content=success_response())
    set_auth_cookies(
        result,
        new_vtm.access_token,
        new_vtm.expires_at,
        new_rtm.refresh_token,
        new_rtm.expires_at,
    )
    return result


async def handle_logout(access_token: str, refresh_token: str) -> JSONResponse:
    vtm = extract_vtm(access_token) if access_token else None
    rtm = extract_rtm(refresh_token) if refresh_token else None

    if vtm and rtm:
        await blacklist_tokens(vtm, rtm)

    result = JSONResponse(content=success_response())
    clear_auth_cookies(result)
    return result
