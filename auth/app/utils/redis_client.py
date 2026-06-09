from datetime import datetime, timezone

import redis.asyncio as aioredis

from app.config.settings import settings
from app.constants.token_constants import MAX_OTP_ATTEMPTS, OTP_BLOCK_TTL_SECONDS

_client: aioredis.Redis | None = None


def _parse_dsn(dsn: str) -> tuple[str, int]:
    # Strip surrounding quotes if present
    dsn = dsn.strip('"').strip("'")
    if ":" in dsn:
        host, port_str = dsn.rsplit(":", 1)
        return host, int(port_str)
    return dsn, 6379


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        host, port = _parse_dsn(settings.REDIS_DSN)
        _client = aioredis.Redis(
            host=host,
            port=port,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )
    return _client


async def blacklist_tokens(vtm, rtm) -> None:
    client = get_redis()
    now = int(datetime.now(timezone.utc).timestamp())

    access_ttl = max(0, vtm.expires_at - now)
    refresh_ttl = max(0, rtm.expires_at - now)

    if access_ttl > 0:
        await client.setex(vtm.access_uuid, access_ttl, vtm.user_id)
    if refresh_ttl > 0:
        await client.setex(rtm.refresh_uuid, refresh_ttl, rtm.user_id)


async def is_vtm_blacklisted(access_uuid: str) -> bool:
    return await get_redis().get(access_uuid) is not None


async def is_rtm_blacklisted(refresh_uuid: str) -> bool:
    return await get_redis().get(refresh_uuid) is not None


async def get_otp_attempts(email: str) -> int:
    val = await get_redis().get(f"otp_attempts:{email}")
    return int(val) if val else 0


async def increment_otp_attempts(email: str) -> int:
    client = get_redis()
    key = f"otp_attempts:{email}"
    count = await client.incr(key)
    if count == 1:
        await client.expire(key, OTP_BLOCK_TTL_SECONDS)
    return count


async def reset_otp_attempts(email: str) -> None:
    await get_redis().delete(f"otp_attempts:{email}")
