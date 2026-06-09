import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config.settings import settings
from app.constants.token_constants import (
    BETA_ACCESS_TOKEN_EXPIRY_MINUTES,
    CLAIM_ACCESS_UUID,
    CLAIM_DATA,
    CLAIM_EXP,
    CLAIM_REFRESH_UUID,
    CLAIM_USER_ID,
    PROD_ACCESS_TOKEN_EXPIRY_MINUTES,
    REFRESH_TOKEN_EXPIRY_DAYS,
)
from app.utils.crypto import decrypt, encrypt

ALGORITHM = "HS256"


def _is_beta() -> bool:
    return settings.SERVER_ENVIRONMENT != "prod"


def _access_expiry_minutes() -> int:
    return BETA_ACCESS_TOKEN_EXPIRY_MINUTES if _is_beta() else PROD_ACCESS_TOKEN_EXPIRY_MINUTES


@dataclass
class VerifyTokenMeta:
    access_uuid: str
    user_id: str
    access_token: str
    expires_at: int


@dataclass
class RefreshTokenMeta:
    refresh_uuid: str
    user_id: str
    refresh_token: str
    expires_at: int


def create_tokens(user_id: str) -> tuple[VerifyTokenMeta, RefreshTokenMeta]:
    now = datetime.now(timezone.utc)

    access_uuid = str(uuid.uuid4())
    access_exp = int((now + timedelta(minutes=_access_expiry_minutes())).timestamp())

    refresh_uuid = str(uuid.uuid4())
    refresh_exp = int((now + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS)).timestamp())

    # Encrypt access token payload before embedding in JWT
    access_payload = {CLAIM_ACCESS_UUID: access_uuid, CLAIM_USER_ID: user_id}
    encrypted_access = encrypt(json.dumps(access_payload).encode())
    access_token = jwt.encode(
        {CLAIM_DATA: encrypted_access, CLAIM_EXP: access_exp},
        settings.ACCESS_SECRET,
        algorithm=ALGORITHM,
    )

    # Encrypt refresh token payload before embedding in JWT
    refresh_payload = {CLAIM_REFRESH_UUID: refresh_uuid, CLAIM_USER_ID: user_id}
    encrypted_refresh = encrypt(json.dumps(refresh_payload).encode())
    refresh_token = jwt.encode(
        {CLAIM_DATA: encrypted_refresh, CLAIM_EXP: refresh_exp},
        settings.ACCESS_SECRET,
        algorithm=ALGORITHM,
    )

    return (
        VerifyTokenMeta(
            access_uuid=access_uuid,
            user_id=user_id,
            access_token=access_token,
            expires_at=access_exp,
        ),
        RefreshTokenMeta(
            refresh_uuid=refresh_uuid,
            user_id=user_id,
            refresh_token=refresh_token,
            expires_at=refresh_exp,
        ),
    )


def extract_vtm(token: str) -> VerifyTokenMeta | None:
    try:
        claims = jwt.decode(token, settings.ACCESS_SECRET, algorithms=[ALGORITHM])
        exp = int(claims.get(CLAIM_EXP, 0))
        if exp < int(datetime.now(timezone.utc).timestamp()):
            return None
        inner = json.loads(decrypt(claims[CLAIM_DATA]))
        return VerifyTokenMeta(
            access_uuid=inner[CLAIM_ACCESS_UUID],
            user_id=inner[CLAIM_USER_ID],
            access_token=token,
            expires_at=exp,
        )
    except Exception:
        return None


def extract_rtm(token: str) -> RefreshTokenMeta | None:
    try:
        claims = jwt.decode(token, settings.ACCESS_SECRET, algorithms=[ALGORITHM])
        exp = int(claims.get(CLAIM_EXP, 0))
        if exp < int(datetime.now(timezone.utc).timestamp()):
            return None
        inner = json.loads(decrypt(claims[CLAIM_DATA]))
        return RefreshTokenMeta(
            refresh_uuid=inner[CLAIM_REFRESH_UUID],
            user_id=inner[CLAIM_USER_ID],
            refresh_token=token,
            expires_at=exp,
        )
    except Exception:
        return None
