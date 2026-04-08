"""APScheduler-based hourly job that triggers daily recap emails.

Each hour the scheduler queries auth-service for users whose local
``daily_recap_hour`` matches the current hour in their timezone, then for each
match generates a recap and POSTs it to the mailing-service.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.services.recap_generator import generate_daily_recap

logger = logging.getLogger(__name__)


class RecapScheduler:
    """Wrap APScheduler to dispatch daily/weekly recap emails."""

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler(timezone="UTC")
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        # Run a few minutes past every hour to give the systems time to be ready
        self._scheduler.add_job(
            self._dispatch_daily_recaps,
            CronTrigger(minute=7),
            id="daily_recap_dispatch",
            replace_existing=True,
        )
        # Weekly recap fires on Sunday at 18:07 UTC
        self._scheduler.add_job(
            self._dispatch_weekly_recaps,
            CronTrigger(day_of_week="sun", hour=18, minute=7),
            id="weekly_recap_dispatch",
            replace_existing=True,
        )
        self._scheduler.start()
        self._started = True
        logger.info("RecapScheduler started (daily=hourly, weekly=Sun 18:07 UTC)")

    def stop(self) -> None:
        if not self._started:
            return
        self._scheduler.shutdown(wait=False)
        self._started = False
        logger.info("RecapScheduler stopped")

    async def _fetch_users_for_recap(
        self,
        client: httpx.AsyncClient,
        target_hour: int,
        recap_type: str,
    ) -> list[dict[str, Any]]:
        if not settings.INTERNAL_API_TOKEN:
            logger.debug("INTERNAL_API_TOKEN not set, skipping recap dispatch")
            return []
        try:
            resp = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/auth/internal/users-for-recap",
                params={"target_hour": target_hour, "recap_type": recap_type},
                headers={"X-Internal-Token": settings.INTERNAL_API_TOKEN},
                timeout=10.0,
            )
            if resp.status_code == 200:
                return resp.json().get("users", [])
            logger.warning(
                "Internal users-for-recap returned %s: %s",
                resp.status_code,
                resp.text[:200],
            )
        except Exception as exc:
            logger.warning("Failed to fetch users for recap: %s", exc)
        return []

    async def _send_recap(
        self,
        client: httpx.AsyncClient,
        user: dict[str, Any],
        template: str,
    ) -> None:
        try:
            recap_data = await generate_daily_recap(user, auth_header=None)
            resp = await client.post(
                f"{settings.MAILING_SERVICE_URL}/api/v1/mail/send",
                json={
                    "to": user["email"],
                    "template": template,
                    "data": recap_data,
                },
                timeout=15.0,
            )
            if resp.status_code >= 400:
                logger.warning(
                    "Mail send failed for %s: HTTP %s",
                    user["email"],
                    resp.status_code,
                )
            else:
                logger.info("Recap email sent to %s", user["email"])
        except Exception as exc:
            logger.error("Recap send failed for %s: %s", user.get("email"), exc)

    async def _dispatch_daily_recaps(self) -> None:
        target_hour = datetime.now(timezone.utc).hour
        async with httpx.AsyncClient() as client:
            users = await self._fetch_users_for_recap(client, target_hour, "daily")
            if not users:
                return
            logger.info("Dispatching daily recap to %d users", len(users))
            for user in users:
                await self._send_recap(client, user, "daily_recap")
                await asyncio.sleep(0.2)  # gentle pacing

    async def _dispatch_weekly_recaps(self) -> None:
        target_hour = datetime.now(timezone.utc).hour
        async with httpx.AsyncClient() as client:
            users = await self._fetch_users_for_recap(client, target_hour, "weekly")
            if not users:
                return
            logger.info("Dispatching weekly recap to %d users", len(users))
            for user in users:
                await self._send_recap(client, user, "daily_recap")  # reuse template
                await asyncio.sleep(0.2)


_scheduler: RecapScheduler | None = None


def get_scheduler() -> RecapScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = RecapScheduler()
    return _scheduler
