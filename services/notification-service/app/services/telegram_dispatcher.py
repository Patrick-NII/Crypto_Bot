"""Telegram dispatcher — Redis subscriber that pushes events to Telegram.

Mirrors ``sms_dispatcher`` but consumes the user's Telegram preferences
instead. Both dispatchers subscribe to the same ``notification:events``
channel so the auto-trader publishes a single message that fans out to
every active channel.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.services import telegram_templates
from app.services.telegram import send_message

logger = logging.getLogger(__name__)

# Listen on both channel names for backward compatibility:
# - "notification:events" : the new generic channel
# - "sms:events"          : the legacy name still used by ai-agent-service
_CHANNELS = ("notification:events", "sms:events")


class _RateLimiter:
    """Per-user sliding window rate limiter (RAM-only)."""

    def __init__(self, max_per_window: int, window_seconds: int = 60) -> None:
        self.max = max_per_window
        self.window = window_seconds
        self._buckets: Dict[str, list[float]] = {}

    def allow(self, user_key: str) -> bool:
        now = time.monotonic()
        bucket = self._buckets.setdefault(user_key, [])
        cutoff = now - self.window
        bucket[:] = [ts for ts in bucket if ts > cutoff]
        if len(bucket) >= self.max:
            return False
        bucket.append(now)
        return True


class TelegramDispatcher:
    def __init__(self) -> None:
        self._throttle = _RateLimiter(getattr(settings, "TELEGRAM_THROTTLE_MAX_PER_MIN", 10))
        self._task: Optional[asyncio.Task] = None
        self._redis = None
        self._client = httpx.AsyncClient(timeout=10.0)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run())
        logger.info("TelegramDispatcher started, listening on %s", _CHANNELS)

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
        await self._client.aclose()
        logger.info("TelegramDispatcher stopped")

    # ------------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                f"redis://{settings.REDIS_HOST}:6379",
                decode_responses=True,
            )
            pubsub = self._redis.pubsub()
            for channel in _CHANNELS:
                await pubsub.subscribe(channel)

            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    payload = json.loads(message.get("data") or "{}")
                except Exception:
                    continue
                await self._handle_event(payload)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("TelegramDispatcher loop exited: %s", exc)

    async def _handle_event(self, envelope: Dict[str, Any]) -> None:
        user_id = envelope.get("user_id") or ""
        event_type = envelope.get("event_type") or ""
        payload: Dict[str, Any] = envelope.get("payload") or {}
        if not user_id or not event_type:
            return

        # 1. Fetch user notification settings
        user_settings = await self._fetch_user_notification_settings(user_id)
        if user_settings is None:
            return

        chat_id = user_settings.get("telegram_chat_id")
        if not chat_id:
            logger.debug("Skipping Telegram: no chat_id for user=%s", user_id)
            return

        telegram_prefs = user_settings.get("telegram") or {}
        if not bool(telegram_prefs.get("master_enabled")):
            return
        events = telegram_prefs.get("events") or {}
        if not bool(events.get(event_type, False)):
            return

        # 2. Throttle
        if not self._throttle.allow(user_id):
            logger.warning("Telegram throttled for user=%s event=%s", user_id, event_type)
            return

        # 3. Render and send
        body = telegram_templates.render(event_type, payload)
        if body is None:
            logger.debug("No telegram template for event %s", event_type)
            return

        sms_id = uuid.uuid4().hex
        result = await send_message(chat_id=str(chat_id), text=body, parse_mode="HTML")

        ok = bool(result.get("ok"))
        logger.info(
            "Telegram dispatched id=%s user=%s event=%s ok=%s",
            sms_id,
            user_id,
            event_type,
            ok,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _fetch_user_notification_settings(
        self,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        if not settings.INTERNAL_API_TOKEN:
            logger.debug("No internal token — cannot fetch user notification settings")
            return None
        try:
            resp = await self._client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/auth/internal/users/{user_id}/notification-settings",
                headers={"X-Internal-Token": settings.INTERNAL_API_TOKEN},
            )
            if resp.status_code == 200:
                return resp.json()
            logger.debug(
                "notification-settings HTTP %s for user=%s",
                resp.status_code,
                user_id,
            )
            return None
        except Exception as exc:
            logger.debug("notification-settings fetch failed: %s", exc)
            return None


# Module-level singleton
telegram_dispatcher = TelegramDispatcher()
