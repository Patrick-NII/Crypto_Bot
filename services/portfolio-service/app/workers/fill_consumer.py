"""Redis-backed fill consumer.

Subscribes to ``trading:orders`` and applies every ``ORDER_FILLED`` event to
the portfolio ledger via :func:`apply_fill`. Idempotent thanks to the unique
``Transaction.order_id`` constraint.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from app.core.config import settings
from app.core.database import async_session
from app.services.ledger_writer import FillPayload, apply_fill

logger = logging.getLogger(__name__)

_CHANNEL = "trading:orders"
_FILL_EVENTS = {"ORDER_FILLED", "ORDER_PARTIALLY_FILLED"}


class FillConsumer:
    """Background task that mirrors trading-engine fills into the SQL ledger."""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._redis = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run())
        logger.info("FillConsumer started, listening on %s", _CHANNEL)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        if self._redis is not None:
            try:
                await self._redis.close()
            except Exception:
                pass
            self._redis = None
        logger.info("FillConsumer stopped")

    async def _run(self) -> None:
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
                decode_responses=True,
            )
            pubsub = self._redis.pubsub()
            await pubsub.subscribe(_CHANNEL)

            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    payload = json.loads(message.get("data") or "{}")
                except (json.JSONDecodeError, TypeError):
                    continue

                event = payload.get("event") or ""
                if event not in _FILL_EVENTS:
                    continue

                fill = FillPayload.from_redis_payload(payload)
                if fill is None:
                    continue

                await self._handle_fill(fill)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("FillConsumer loop exited unexpectedly: %s", exc)

    async def _handle_fill(self, fill: FillPayload) -> None:
        async with async_session() as db:
            try:
                await apply_fill(db, fill)
            except Exception as exc:
                logger.error(
                    "Failed to apply fill order_id=%s: %s",
                    fill.order_id,
                    exc,
                )
                try:
                    await db.rollback()
                except Exception:
                    pass


# Module-level singleton
fill_consumer = FillConsumer()
