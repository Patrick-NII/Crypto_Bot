"""AI Agent Service — main FastAPI application."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.chat import router as chat_router
from app.api.agents import router as agents_router
from app.api.auto_trading import router as auto_trading_router
from app.memory.redis_client import close_redis
from app.services.auto_trader import restore_sessions, shutdown as shutdown_auto_trader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AI Agent Service starting — models: fast=%s medium=%s complex=%s",
                settings.MODEL_FAST, settings.MODEL_MEDIUM, settings.MODEL_COMPLEX)
    await restore_sessions()
    yield
    await shutdown_auto_trader()
    await close_redis()
    logger.info("AI Agent Service shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(agents_router)
app.include_router(auto_trading_router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
