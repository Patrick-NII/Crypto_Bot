"""Okamoey Market Data Service - FastAPI application entry point.

Provides REST and WebSocket APIs for real-time cryptocurrency market data.
Port: 8003
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.markets import router as markets_router
from app.api.prices import router as prices_router
from app.core.config import settings
from app.core.redis_client import close_redis
from app.services.price_fetcher import close_exchange
from app.services.price_updater import is_running, start_updater, stop_updater
from app.services.websocket_manager import manager

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start and stop background tasks."""
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)

    # Start the background price updater
    start_updater()
    logger.info("Background price updater started")

    yield

    # Shutdown
    logger.info("Shutting down %s", settings.APP_NAME)
    await stop_updater()
    await close_exchange()
    await close_redis()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Real-time cryptocurrency market data for the Okamoey trading platform",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(prices_router)
app.include_router(markets_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "price_updater_running": is_running(),
        "websocket_clients": manager.active_count,
    }


@app.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    """WebSocket endpoint for live price streaming.

    Clients receive automatic price updates every PRICE_UPDATE_INTERVAL_SECONDS.

    Supported client messages:
    - {"type": "ping"}                            Heartbeat
    - {"type": "subscribe", "data": {"symbols": ["BTC","ETH"]}}  Subscribe hint
    """
    await manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            await manager.handle_client_message(websocket, raw)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        logger.exception("WebSocket error")
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8003, reload=True)
