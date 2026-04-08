"""Email dispatcher: subscribe to Redis events and route to mailing-service.

Subscribes to:
  - trading:user-orders   (buy/sell confirmations)
  - trading:user-deposits (deposit/withdrawal)
  - auth:security         (login_notification)

For each event, fetches user notification preferences (if not in payload),
checks throttle (max N emails per user per minute), and POSTs to mailing-service.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx

from app.core.config import settings
from app.services.event_bridge import build_template_payload, classify_event

logger = logging.getLogger(__name__)


class _Throttle:
    """In-memory per-user-per-minute throttle (5 emails/user/60s default)."""

    def __init__(self, max_per_window: int, window_seconds: int = 60) -> None:
        self.max = max_per_window
        self.window = window_seconds
        self._buckets: dict[str, list[float]] = {}

    def allow(self, user_key: str) -> bool:
        now = time.monotonic()
        bucket = self._buckets.setdefault(user_key, [])
        # Trim old timestamps
        cutoff = now - self.window
        bucket[:] = [ts for ts in bucket if ts > cutoff]
        if len(bucket) >= self.max:
            return False
        bucket.append(now)
        return True


class EmailDispatcher:
    """Subscribe to trading and security Redis channels and dispatch emails."""

    CHANNELS = ("trading:user-orders", "trading:user-deposits", "auth:security")

    def __init__(self) -> None:
        self._throttle = _Throttle(settings.EMAIL_THROTTLE_MAX_PER_MIN)
        self._task: asyncio.Task | None = None
        self._client = httpx.AsyncClient(timeout=10.0)

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run())
        logger.info("EmailDispatcher started, listening on %s", self.CHANNELS)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._client.aclose()
        logger.info("EmailDispatcher stopped")

    async def _run(self) -> None:
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(f"redis://{settings.REDIS_HOST}:6379")
            pubsub = r.pubsub()
            await pubsub.subscribe(*self.CHANNELS)
            logger.info("EmailDispatcher subscribed to Redis channels")

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    channel = (
                        message["channel"].decode()
                        if isinstance(message["channel"], (bytes, bytearray))
                        else str(message["channel"])
                    )
                    raw = (
                        message["data"].decode()
                        if isinstance(message["data"], (bytes, bytearray))
                        else str(message["data"])
                    )
                    payload = json.loads(raw)
                    await self._handle_event(channel, payload)
                except Exception as exc:
                    logger.error("EmailDispatcher failed to handle event: %s", exc)
        except Exception as exc:
            logger.warning("EmailDispatcher loop exited: %s", exc)

    async def _handle_event(self, channel: str, payload: dict[str, Any]) -> None:
        event = classify_event(channel, payload)
        if event is None:
            return

        user_email = event.get("user_email")
        if not user_email:
            logger.debug("Event without user_email, skipping (channel=%s)", channel)
            return

        # Check user notification preference
        pref_key = event.get("preference_key")  # e.g. "email_trades"
        if pref_key:
            allowed = await self._user_pref_allows(event.get("user_id"), pref_key)
            if not allowed:
                logger.debug("User %s opted out of %s, skipping", user_email, pref_key)
                return

        # Throttle by user
        if not self._throttle.allow(user_email):
            logger.warning("Throttled email to %s (channel=%s)", user_email, channel)
            return

        template = event["template"]
        template_data = build_template_payload(template, payload)

        try:
            resp = await self._client.post(
                f"{settings.MAILING_SERVICE_URL}/api/v1/mail/send",
                json={
                    "to": user_email,
                    "template": template,
                    "data": template_data,
                },
            )
            if resp.status_code >= 400:
                logger.warning(
                    "Mailing service returned %s for %s template=%s body=%s",
                    resp.status_code,
                    user_email,
                    template,
                    resp.text[:200],
                )
            else:
                logger.info("Email queued: to=%s template=%s", user_email, template)
        except Exception as exc:
            logger.error("Failed to call mailing-service: %s", exc)

    async def _user_pref_allows(
        self,
        user_id: str | None,
        pref_key: str,
    ) -> bool:
        """Check if user has the given email preference enabled.

        For now, returns True by default (opt-out model). Once notification
        preferences are exposed via an internal endpoint, this will fetch them.
        """
        # Optimistic default: most preferences are ON by default. The producing
        # service is expected to embed user_preferences in the event payload
        # when overriding this default.
        return True


_dispatcher: EmailDispatcher | None = None


def get_dispatcher() -> EmailDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = EmailDispatcher()
    return _dispatcher
