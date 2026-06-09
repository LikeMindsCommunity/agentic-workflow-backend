import logging

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)

_GUPSHUP_URL = "https://enterprise.smsgupshup.com/apps/TwoFactorAuth/incoming.php"


def _is_success(text: str) -> bool:
    parts = text.strip().split("|")
    return len(parts) > 0 and parts[0].strip().lower() == "success"


async def send_otp(email: str) -> bool:
    if not settings.EMAIL_GHUPSHAP_KEY:
        raise ValueError("EMAIL_GHUPSHAP_KEY is not configured")

    url = f"{_GUPSHUP_URL}?email={email}&key={settings.EMAIL_GHUPSHAP_KEY}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)

    logger.info("SendOTP response [%s]: %s", email, response.text)

    if response.status_code != 200 or not _is_success(response.text):
        logger.error("SendOTP failed [%s]: %s", email, response.text)
        return False
    return True


async def verify_otp(email: str, otp: str) -> bool:
    if not settings.EMAIL_GHUPSHAP_KEY:
        raise ValueError("EMAIL_GHUPSHAP_KEY is not configured")

    url = f"{_GUPSHUP_URL}?email={email}&code={otp}&key={settings.EMAIL_GHUPSHAP_KEY}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)

    logger.info("VerifyOTP response [%s]: %s", email, response.text)

    if response.status_code != 200 or not _is_success(response.text):
        logger.error("VerifyOTP failed [%s]: %s", email, response.text)
        return False
    return True
