from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.config.settings import settings
from app.models.user import User

_client: AsyncIOMotorClient | None = None


async def init_db() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.MONGO_URI)
    await init_beanie(
        database=_client[settings.MONGO_DB_NAME],
        document_models=[User],
    )


async def close_db() -> None:
    if _client:
        _client.close()
