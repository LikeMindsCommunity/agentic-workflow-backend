from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.handlers.user_handler import handle_fetch_user, handle_send_otp, handle_verify_otp

router = APIRouter(prefix="/user", tags=["user"])


class OTPBody(BaseModel):
    email: str


class VerifyOTPBody(BaseModel):
    email: str
    otp: str


@router.post("/otp")
async def send_otp(body: OTPBody) -> JSONResponse:
    return await handle_send_otp(body.email)


@router.post("/otp/verify")
async def verify_otp(body: VerifyOTPBody) -> JSONResponse:
    return await handle_verify_otp(body.email, body.otp)


@router.get("/")
async def get_user(x_user_id: str = Header(..., alias="X-User-Id")) -> JSONResponse:
    return await handle_fetch_user(x_user_id)
