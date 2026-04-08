"""Redis subscriber that dispatches SMS events to Twilio.

Subscribes to ``sms:events`` and, for each message:
    1. Fetches the user's phone + SMS preferences from auth-service
       (internal token-gated endpoint).
    2. Drops the event if master_enabled is false or the specific event
       toggle is false.
    3. Enforces a per-user rate limit (max N SMS / minute via Redis INCR).
    4. Renders the template (``sms_templates``) and sends via Twilio.
    5. Persists the attempt into ``sms_notifications``.

Graceful on every failure — SMS is a best-effort side channel, the main
trading loop must never be blocked by it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.services import sms_templates, twilio_client

logger = logging.getLogger(__name__)

_CHANNEL = "sms:events"


class _RateLimiter:
    """Token-bucket-like per-user rate limiter backed by an in-memory dict.

    The SMS flow is low-volume so a simple per-user sliding window in RAM
    is sufficient. A restart clears the counters (desired — opens the
    bucket again).
    """

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


class SmsDispatcher:
    def __init__(self) -> None:
        self._throttle = _RateLimiter(settings.SMS_THROTTLE_MAX_PER_MIN)
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
        logger.info("SmsDispatcher started, listening on %s", _CHANNEL)

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
        logger.info("SmsDispatcher stopped")

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
            await pubsub.subscribe(_CHANNEL)

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
            logger.warning("SmsDispatcher loop exited: %s", exc)

    async def _handle_event(self, envelope: Dict[str, Any]) -> None:
        user_id = envelope.get("user_id") or ""
        event_type = envelope.get("event_type") or ""
        payload: Dict[str, Any] = envelope.get("payload") or {}
        if not user_id or not event_type:
            return

        # 1. Fetch user phone + SMS preferences
        user_settings = await self._fetch_user_sms_settings(user_id)
        if user_settings is None:
            return

        if not user_settings.get("phone_verified"):
            logger.debug("Skipping SMS: phone not verified for user=%s", user_id)
            return
        phone_number = user_settings.get("phone_number")
        if not phone_number:
            return

        sms_prefs = user_settings.get("sms") or {}
        if not bool(sms_prefs.get("master_enabled")):
            return
        events = sms_prefs.get("events") or {}
        if not bool(events.get(event_type, False)):
            return

        # 2. Throttle
        if not self._throttle.allow(user_id):
            logger.warning("SMS throttled for user=%s event=%s", user_id, event_type)
            return

        # 3. Render and send
        body = sms_templates.render(event_type, payload)
        if body is None:
            logger.debug("No template for event %s", event_type)
            return

        sms_id = uuid.uuid4().hex
        result = await twilio_client.send_sms(phone_number, body)

        # 4. Persist into sms_notifications (if ai-agent-service repo is reachable)
        await self._persist_sms_record(
            sms_id=sms_id,
            user_id=user_id,
            phone_number=phone_number,
            event_type=event_type,
            payload=payload,
            twilio_sid=result.sid,
            status="sent" if result.ok else "failed",
            error=result.error,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _fetch_user_sms_settings(
        self,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        if not settings.INTERNAL_API_TOKEN:
            logger.debug("No internal token — cannot fetch user SMS settings")
            return None
        try:
            resp = await self._client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/auth/internal/users/{user_id}/phone-settings",
                headers={"X-Internal-Token": settings.INTERNAL_API_TOKEN},
            )
            if resp.status_code == 200:
                return resp.json()
            logger.debug(
                "phone-settings HTTP %s for user=%s: %s",
                resp.status_code,
                user_id,
                resp.text[:120],
            )
            return None
        except Exception as exc:
            logger.debug("phone-settings fetch failed: %s", exc)
            return None

    async def _persist_sms_record(
        self,
        *,
        sms_id: str,
        user_id: str,
        phone_number: str,
        event_type: str,
        payload: Dict[str, Any],
        twilio_sid: Optional[str],
        status: str,
        error: Optional[str],
    ) -> None:
        """Write to sms_notifications in gluetrade_trading via HTTP call.

        V1 simplification: log into structured logger only. A later version
        will POST to an internal trading-engine endpoint or write directly
        through a SQLAlchemy connection.
        """
        logger.info(
            "SMS dispatched id=%s user=%s event=%s status=%s sid=%s error=%s",
            sms_id,
            user_id,
            event_type,
            status,
            twilio_sid,
            error,
        )


# Module-level singleton
sms_dispatcher = SmsDispatcher()
