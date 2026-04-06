import asyncio
import logging

from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI

from app.api.ml import router as ml_router
from app.api.ml_v2 import router as ml_v2_router
from app.api.scanner import router as scanner_router
from app.core.config import settings
from app.engine.outcome_tracker import update_signal_outcomes

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None
_bg_task: asyncio.Task | None = None


async def _outcome_loop():
    """Background loop: update signal outcomes every 5 minutes."""
    while True:
        try:
            if _redis:
                stats = await update_signal_outcomes(_redis)
                if stats.get("updated", 0) > 0:
                    logger.info("Outcome tracker: %s", stats)
        except Exception as exc:
            logger.warning("Outcome tracker error: %s", exc)
        await asyncio.sleep(300)  # 5 min


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis, _bg_task
    try:
        _redis = aioredis.Redis(host=settings.REDIS_HOST, decode_responses=True)
        await _redis.ping()
        logger.info("Redis connected for signal tracking")
    except Exception as exc:
        logger.warning("Redis unavailable for signal tracking: %s", exc)
        _redis = None

    _bg_task = asyncio.create_task(_outcome_loop())
    app.state.redis = _redis

    yield

    if _bg_task:
        _bg_task.cancel()
    if _redis:
        await _redis.aclose()


app = FastAPI(
    title="ML Service",
    description="Signal engine, multi-asset scanner, strategy ranking, and signal tracking",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(ml_router)
app.include_router(ml_v2_router)
app.include_router(scanner_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ml-service", "redis": _redis is not None}


@app.get("/api/v1/ml/signal-stats")
async def signal_stats(symbol: str | None = None):
    """Return signal tracking statistics."""
    from app.engine.signal_tracker import compute_signal_stats
    return await compute_signal_stats(_redis, symbol)


@app.get("/api/v1/ml/weight-report")
async def weight_report():
    """Return weight optimization report."""
    from app.engine.weight_optimizer import compute_optimal_weights
    return await compute_optimal_weights(_redis)


@app.get("/api/v1/ml/calibration")
async def calibration_report():
    """Return confidence calibration report."""
    from app.engine.weight_optimizer import get_calibration_report
    return await get_calibration_report(_redis)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8006, reload=True)
