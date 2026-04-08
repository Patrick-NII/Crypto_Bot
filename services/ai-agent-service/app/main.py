"""AI Agent Service — main FastAPI application."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.chat import router as chat_router
from app.api.agents import router as agents_router
from app.api.auto_trading import router as auto_trading_router
from app.memory.redis_client import close_redis
from app.services.auto_trader import restore_sessions, shutdown as shutdown_auto_trader
from app.services.outcome_backfill import backfill_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


_backfill_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _backfill_task
    logger.info("AI Agent Service starting — models: fast=%s medium=%s complex=%s",
                settings.MODEL_FAST, settings.MODEL_MEDIUM, settings.MODEL_COMPLEX)
    await restore_sessions()
    _backfill_task = asyncio.create_task(backfill_loop())
    logger.info("Outcome backfill loop started (every 15 min)")
    yield
    await shutdown_auto_trader()
    if _backfill_task is not None:
        _backfill_task.cancel()
        try:
            await _backfill_task
        except asyncio.CancelledError:
            pass
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
