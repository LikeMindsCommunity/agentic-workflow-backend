from datetime import datetime, timezone

from fastapi import Response

from app.constants.token_constants import ACCESS_TOKEN_COOKIE_NAME, REFRESH_TOKEN_COOKIE_NAME


def set_auth_cookies(
    response: Response,
    access_token: str,
    access_exp: int,
    refresh_token: str,
    refresh_exp: int,
) -> None:
    now = int(datetime.now(timezone.utc).timestamp())

    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        max_age=max(0, access_exp - now),
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        max_age=max(0, refresh_exp - now),
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    for name in (ACCESS_TOKEN_COOKIE_NAME, REFRESH_TOKEN_COOKIE_NAME):
        response.delete_cookie(key=name, path="/", httponly=True, secure=True, samesite="strict")
