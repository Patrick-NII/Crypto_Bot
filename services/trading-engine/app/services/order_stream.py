"""Per-user order stream — polls CCXT for open/closed orders and publishes diffs to Redis.

Each WebSocket subscriber triggers a background task for the user (at most one
per user). The task polls ``list_open_orders`` every ``_POLL_INTERVAL`` seconds,
compares against the previous snapshot, and publishes every change to the
Redis channel ``trading:user-orders:{user_id}``.

When the last subscriber disconnects, the task is torn down.

V1 compromise: the poller calls ``OrderManager.list_open_orders`` which wraps
``fetch_open_orders`` + ``fetch_closed_orders``. V2 should swap this for
CCXT Pro's websocket user data stream for lower latency and no rate usage.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Set

from app.models.order import OrderResponse

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 3.0  # seconds


class OrderStreamManager:
    """Owns the per-user background poller tasks."""

    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task] = {}
        self._subscribers: Dict[str, int] = {}  # user_id -> ref count
        self._user_auth: Dict[str, str] = {}    # user_id -> last auth header seen
        self._last_snapshot: Dict[str, Dict[str, Dict[str, Any]]] = {}
        # order_manager is injected lazily to avoid circular import
        self._order_manager: Any = None
        self._redis: Any = None

    def attach(self, order_manager: Any) -> None:
        """Wire the OrderManager and its Redis client."""
        self._order_manager = order_manager
        self._redis = getattr(order_manager, "_redis", None)

    # ------------------------------------------------------------------
    # Subscriber lifecycle
    # ------------------------------------------------------------------

    async def subscribe(self, user_id: str, auth_header: Optional[str]) -> None:
        """Register a subscriber for *user_id*. Idempotent ref-counted."""
        self._subscribers[user_id] = self._subscribers.get(user_id, 0) + 1
        if auth_header:
            self._user_auth[user_id] = auth_header

        if user_id not in self._tasks or self._tasks[user_id].done():
            task = asyncio.create_task(self._poll_loop(user_id))
            self._tasks[user_id] = task
            logger.info(
                "OrderStream: started poller for user=%s (subs=%d)",
                user_id,
                self._subscribers[user_id],
            )

    async def unsubscribe(self, user_id: str) -> None:
        """Release a subscriber reference. Stops the poller when count hits 0."""
        if user_id not in self._subscribers:
            return
        self._subscribers[user_id] -= 1
        if self._subscribers[user_id] <= 0:
            self._subscribers.pop(user_id, None)
            self._user_auth.pop(user_id, None)
            self._last_snapshot.pop(user_id, None)
            task = self._tasks.pop(user_id, None)
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            logger.info("OrderStream: stopped poller for user=%s", user_id)

    async def stop_all(self) -> None:
        """Cancel every running poller. Called on shutdown."""
        for user_id in list(self._tasks.keys()):
            task = self._tasks.pop(user_id, None)
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._subscribers.clear()
        self._user_auth.clear()
        self._last_snapshot.clear()

    # ------------------------------------------------------------------
    # Poller loop
    # ------------------------------------------------------------------

    async def _poll_loop(self, user_id: str) -> None:
        try:
            while True:
                try:
                    await self._poll_once(user_id)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("OrderStream poll error for %s: %s", user_id, exc)
                await asyncio.sleep(_POLL_INTERVAL)
        except asyncio.CancelledError:
            return

    async def _poll_once(self, user_id: str) -> None:
        if self._order_manager is None:
            return
        auth_header = self._user_auth.get(user_id)

        open_orders = await self._order_manager.list_open_orders(
            user_id=user_id,
            auth_header=auth_header,
        )

        current: Dict[str, Dict[str, Any]] = {}
        for order in open_orders:
            payload = OrderResponse.from_order(order).dict()
            current[order.id] = payload

        previous = self._last_snapshot.get(user_id, {})
        diffs: list[Dict[str, Any]] = []

        # Added or updated
        for oid, payload in current.items():
            prev = previous.get(oid)
            if prev is None:
                diffs.append({"event": "order_new", "order": payload})
            elif prev != payload:
                diffs.append({"event": "order_update", "order": payload})

        # Removed (closed, cancelled, filled)
        for oid, payload in previous.items():
            if oid not in current:
                diffs.append({"event": "order_done", "order": payload})

        self._last_snapshot[user_id] = current

        if diffs and self._redis is not None:
            channel = f"trading:user-orders:{user_id}"
            for diff in diffs:
                try:
                    await self._redis.publish(channel, json.dumps(diff, default=str))
                except Exception as exc:
                    logger.debug("Failed to publish diff: %s", exc)


# Module-level singleton
order_stream_manager = OrderStreamManager()
