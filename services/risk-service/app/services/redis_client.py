"""Tiny Redis async client for the risk-service.

Used by the daily trade counter (one key per user-day, TTL 24h).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis = None


async def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis.asyncio as aioredis

        _redis = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
        )
        await _redis.ping()
        return _redis
    except Exception as exc:
        logger.warning("Risk-service Redis unavailable: %s", exc)
        _redis = None
        return None


def _today_key(user_id: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"trades:user:{user_id}:{today}"


async def get_daily_trade_count(user_id: str) -> int:
    """Return the user's executed trade count for the current UTC day."""
    if not user_id:
        return 0
    r = await _get_redis()
    if r is None:
        return 0
    try:
        value = await r.get(_today_key(user_id))
        if value is None:
            return 0
        return int(value)
    except Exception as exc:
        logger.debug("get_daily_trade_count failed: %s", exc)
        return 0


async def increment_daily_trade_count(user_id: str) -> int:
    """Increment the user's daily counter and ensure the 24h TTL is set."""
    if not user_id:
        return 0
    r = await _get_redis()
    if r is None:
        return 0
    try:
        key = _today_key(user_id)
        new_value = await r.incr(key)
        if new_value == 1:
            # First increment of the day → arm the TTL
            await r.expire(key, 86400 * 2)  # 48h to survive timezone weirdness
        return int(new_value)
    except Exception as exc:
        logger.debug("increment_daily_trade_count failed: %s", exc)
        return 0
