from fastapi import Request
from fastapi.responses import JSONResponse

from app.constants.token_constants import ACCESS_TOKEN_COOKIE_NAME, REFRESH_TOKEN_COOKIE_NAME
from app.utils.redis_client import is_rtm_blacklisted, is_vtm_blacklisted
from app.utils.response import error_response
from app.utils.token_utils import RefreshTokenMeta, VerifyTokenMeta, extract_rtm, extract_vtm


async def vtm_required(request: Request) -> tuple[VerifyTokenMeta | None, JSONResponse | None]:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        return None, JSONResponse(status_code=401, content=error_response("Missing access token"))

    vtm = extract_vtm(token)
    if not vtm:
        return None, JSONResponse(status_code=401, content=error_response("Invalid access token"))

    if await is_vtm_blacklisted(vtm.access_uuid):
        return None, JSONResponse(
            status_code=401, content=error_response("Session expired. Please login again.")
        )

    return vtm, None


async def rtm_required(request: Request) -> tuple[RefreshTokenMeta | None, JSONResponse | None]:
    token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    if not token:
        return None, JSONResponse(status_code=401, content=error_response("Missing refresh token"))

    rtm = extract_rtm(token)
    if not rtm:
        return None, JSONResponse(status_code=401, content=error_response("Invalid refresh token"))

    if await is_rtm_blacklisted(rtm.refresh_uuid):
        return None, JSONResponse(
            status_code=401, content=error_response("Session expired. Please login again.")
        )

    return rtm, None
