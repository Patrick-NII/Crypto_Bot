"""Trading Engine - FastAPI application entry point.

Handles order execution, strategy management, and trade lifecycle.
Port: 8004
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.orders import router as orders_router
from app.api.strategies_api import router as strategies_router
from app.core.config import settings
from app.services.order_manager import OrderManager

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Global order manager -- initialised during lifespan
order_manager: Optional[OrderManager] = None

# Background task handle
_pending_check_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

_PENDING_CHECK_INTERVAL = 30  # seconds


async def _check_pending_loop() -> None:
    """Background loop that checks pending paper orders every 30 seconds."""
    while True:
        try:
            if order_manager is not None:
                changed = await order_manager.check_pending_orders()
                if changed:
                    logger.info(
                        "Pending order check filled %d order(s)", len(changed)
                    )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("Pending order check error: %s", exc)
        await asyncio.sleep(_PENDING_CHECK_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown of shared resources."""
    global order_manager, _pending_check_task

    # Startup
    logger.info("Starting Trading Engine (mode=%s)", settings.TRADING_MODE)
    order_manager = OrderManager()
    await order_manager.init_redis()

    # Start background pending-order checker for paper mode
    if settings.TRADING_MODE == "paper":
        _pending_check_task = asyncio.create_task(_check_pending_loop())
        logger.info(
            "Started pending order checker (interval=%ds)", _PENDING_CHECK_INTERVAL
        )

    yield

    # Shutdown
    if _pending_check_task is not None:
        _pending_check_task.cancel()
        try:
            await _pending_check_task
        except asyncio.CancelledError:
            pass
    if order_manager is not None:
        await order_manager.close()
    logger.info("Trading Engine shut down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Order execution and trading strategy engine for the GlueTrade trading platform",
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
app.include_router(orders_router)
app.include_router(strategies_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "trading-engine",
        "version": settings.APP_VERSION,
        "trading_mode": settings.TRADING_MODE,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8004, reload=True)
