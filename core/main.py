import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database.mongodb import close_db, init_db
from app.routes.user_routes import router as user_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(title="Skill Core Service", version="1.0.0", lifespan=lifespan)

app.include_router(user_router)


@app.get("/")
async def health() -> dict:
    return {"success": True, "service": "core"}
