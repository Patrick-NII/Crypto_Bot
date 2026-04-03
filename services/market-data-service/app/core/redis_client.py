"""Redis async client for caching and pub/sub."""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get or create the async Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None
        logger.info("Redis connection closed")


async def cache_set(key: str, value: Any, ttl: int | None = None) -> bool:
    """Set a value in Redis cache with optional TTL.

    Args:
        key: Cache key.
        value: Value to cache (will be JSON-serialized).
        ttl: Time-to-live in seconds. Defaults to PRICE_CACHE_TTL_SECONDS.
    """
    try:
        r = await get_redis()
        serialized = json.dumps(value, default=str)
        if ttl is None:
            ttl = settings.PRICE_CACHE_TTL_SECONDS
        await r.set(key, serialized, ex=ttl)
        return True
    except Exception:
        logger.exception("Redis cache_set failed for key=%s", key)
        return False


async def cache_get(key: str) -> Any | None:
    """Get a value from Redis cache.

    Returns:
        Deserialized value or None if not found / error.
    """
    try:
        r = await get_redis()
        raw = await r.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.exception("Redis cache_get failed for key=%s", key)
        return None


async def cache_delete(key: str) -> bool:
    """Delete a key from Redis cache."""
    try:
        r = await get_redis()
        await r.delete(key)
        return True
    except Exception:
        logger.exception("Redis cache_delete failed for key=%s", key)
        return False


async def publish_message(channel: str, message: Any) -> bool:
    """Publish a message to a Redis pub/sub channel.

    Args:
        channel: Channel name.
        message: Message payload (will be JSON-serialized).
    """
    try:
        r = await get_redis()
        serialized = json.dumps(message, default=str)
        await r.publish(channel, serialized)
        return True
    except Exception:
        logger.exception("Redis publish failed on channel=%s", channel)
        return False


async def get_pubsub() -> aioredis.client.PubSub:
    """Get a new pub/sub subscriber instance."""
    r = await get_redis()
    return r.pubsub()
