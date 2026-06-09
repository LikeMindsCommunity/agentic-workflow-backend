from typing import Any

import httpx

from app.config.settings import settings


async def call_core(method: str, path: str, **kwargs: Any) -> tuple[dict, int]:
    url = f"{settings.CORE_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await getattr(client, method)(url, **kwargs)
    try:
        return response.json(), response.status_code
    except Exception:
        return {"success": False, "error_message": "Invalid response from core"}, response.status_code
