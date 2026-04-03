"""In-memory conversation store backed by Redis for TTL-based expiry."""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
        )
    return _redis


def _key(user_id: str, agent_type: str) -> str:
    return f"ai:conv:{user_id}:{agent_type}"


async def get_history(user_id: str, agent_type: str) -> list[dict[str, Any]]:
    """Retrieve conversation history for a user+agent pair."""
    r = await _get_redis()
    raw = await r.get(_key(user_id, agent_type))
    if not raw:
        return []
    try:
        msgs = json.loads(raw)
        return msgs[-settings.MAX_CONVERSATION_HISTORY :]
    except (json.JSONDecodeError, TypeError):
        return []


async def append_message(user_id: str, agent_type: str, role: str, content: str) -> None:
    """Append a message to the conversation history."""
    r = await _get_redis()
    key = _key(user_id, agent_type)
    history = await get_history(user_id, agent_type)
    history.append({"role": role, "content": content})
    # Trim to max size
    history = history[-settings.MAX_CONVERSATION_HISTORY :]
    ttl = settings.CONVERSATION_TTL_HOURS * 3600
    await r.setex(key, ttl, json.dumps(history))


async def clear_history(user_id: str, agent_type: str) -> None:
    """Clear conversation history."""
    r = await _get_redis()
    await r.delete(_key(user_id, agent_type))
