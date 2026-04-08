"""GlueTrade Portfolio Service -- FastAPI application entry-point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.portfolios import router as portfolios_router
from app.api.positions import router as positions_router
from app.core.config import settings
from app.core.database import engine, init_db
from app.workers.fill_consumer import fill_consumer

logger = logging.getLogger(__name__)


async def _ensure_unique_order_id_index() -> None:
    """Ensure the idempotency index on transactions.order_id exists."""
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "ux_transactions_order_id "
                    "ON transactions (order_id) "
                    "WHERE order_id IS NOT NULL"
                )
            )
    except Exception as exc:
        logger.warning("Could not create transactions.order_id unique index: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup / shutdown hooks."""
    await init_db()
    await _ensure_unique_order_id_index()
    await fill_consumer.start()
    yield
    await fill_consumer.stop()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(portfolios_router)
app.include_router(positions_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME}
