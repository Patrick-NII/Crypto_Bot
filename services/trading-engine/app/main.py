"""Trading Engine - FastAPI application entry point.

Handles order execution, strategy management, and trade lifecycle.
Port: 8004
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.orders import router as orders_router
from app.core.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Order execution and trading strategy engine for the Okamoey trading platform",
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


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "trading-engine",
        "trading_mode": settings.TRADING_MODE,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8004, reload=True)
