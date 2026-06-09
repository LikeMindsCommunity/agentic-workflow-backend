from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.constants.token_constants import ACCESS_TOKEN_COOKIE_NAME, REFRESH_TOKEN_COOKIE_NAME
from app.handlers.auth_handler import handle_logout, handle_refresh
from app.handlers.otp_handler import handle_request_otp, handle_verify_otp
from app.middleware.auth_middleware import vtm_required
from app.utils.core_client import call_core
from app.utils.response import error_response

router = APIRouter(tags=["user"])


class OTPBody(BaseModel):
    email: str


class VerifyOTPBody(BaseModel):
    email: str
    otp: str


@router.post("/user/otp")
async def request_otp(body: OTPBody) -> JSONResponse:
    return await handle_request_otp(body.email)


@router.post("/user/otp/verify")
async def verify_otp(body: VerifyOTPBody, response: Response) -> JSONResponse:
    return await handle_verify_otp(body.email, body.otp, response)


@router.post("/user/refresh")
async def refresh(request: Request) -> JSONResponse:
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_token:
        return JSONResponse(status_code=401, content=error_response("Missing refresh token"))
    return await handle_refresh(refresh_token)


@router.post("/user/logout")
async def logout(request: Request) -> JSONResponse:
    access_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME, "")
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME, "")
    return await handle_logout(access_token, refresh_token)


@router.get("/user")
async def get_user(request: Request) -> JSONResponse:
    vtm, err = await vtm_required(request)
    if err:
        return err
    data, status = await call_core("get", "/user/", headers={"X-User-Id": vtm.user_id})
    return JSONResponse(status_code=status, content=data)
