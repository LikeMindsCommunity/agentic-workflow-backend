import logging

from fastapi.responses import JSONResponse

from app.repositories import user_repository
from app.utils.otp_service import send_otp, verify_otp
from app.utils.response import error_response, success_response

logger = logging.getLogger(__name__)


async def handle_send_otp(email: str) -> JSONResponse:
    try:
        ok = await send_otp(email)
    except ValueError as exc:
        return JSONResponse(status_code=500, content=error_response(str(exc)))
    except Exception as exc:
        logger.error("send_otp error: %s", exc)
        return JSONResponse(status_code=500, content=error_response("Failed to send OTP"))

    if not ok:
        return JSONResponse(status_code=400, content=error_response("Failed to send OTP"))

    existing = await user_repository.find_by_email(email)
    if not existing:
        await user_repository.create(email)

    return JSONResponse(content=success_response())


async def handle_verify_otp(email: str, otp: str) -> JSONResponse:
    try:
        ok = await verify_otp(email, otp)
    except ValueError as exc:
        return JSONResponse(status_code=500, content=error_response(str(exc)))
    except Exception as exc:
        logger.error("verify_otp error: %s", exc)
        return JSONResponse(status_code=500, content=error_response("OTP verification failed"))

    if not ok:
        return JSONResponse(status_code=400, content=error_response("Invalid or expired OTP"))

    user = await user_repository.find_by_email(email)
    if not user:
        return JSONResponse(status_code=404, content=error_response("User not found"))

    if not user.is_verified:
        await user_repository.set_verified(user)

    await user_repository.set_last_login(user)

    return JSONResponse(content=success_response({"user_id": str(user.id)}))


async def handle_fetch_user(user_id: str) -> JSONResponse:
    user = await user_repository.find_by_id(user_id)
    if not user:
        return JSONResponse(status_code=404, content=error_response("User not found"))

    return JSONResponse(
        content=success_response(
            {
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "name": user.name,
                    "kind": user.kind,
                    "tenant_id": user.tenant_id,
                    "is_verified": user.is_verified,
                    "created_at": user.created_at.isoformat(),
                    "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                }
            }
        )
    )
