"""Internal service-to-service endpoints.

These endpoints are protected by a shared INTERNAL_API_TOKEN header
(``X-Internal-Token``). They are NOT exposed publicly through the gateway —
they exist for the notification-service to enumerate users for recap dispatch
and to confirm phone verification after a successful OTP check.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/api/v1/auth/internal", tags=["internal"])


def _require_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    """Reject requests without the shared internal token."""
    if not settings.INTERNAL_API_TOKEN:
        # When no token is configured, refuse internal calls entirely.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal API token not configured",
        )
    if x_internal_token != settings.INTERNAL_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal token",
        )


@router.get("/users-for-recap")
async def list_users_for_recap(
    target_hour: int,
    recap_type: str = "daily",
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_internal_token),
) -> dict:
    """List active users whose local recap hour matches ``target_hour``.

    Filtering happens in Python (not SQL) because the timezone offset depends
    on the user's stored timezone string.
    """
    if not 0 <= target_hour <= 23:
        raise HTTPException(status_code=400, detail="target_hour must be between 0 and 23")

    pref_key = "email_daily_recap" if recap_type == "daily" else "email_weekly_recap"

    result = await db.execute(
        select(User).where(
            User.is_active == True,  # noqa: E712
            User.is_verified == True,  # noqa: E712
        )
    )
    rows = result.scalars().all()

    matching: list[dict] = []
    for user in rows:
        prefs = user.preferences if isinstance(user.preferences, dict) else {}
        notif = prefs.get("notifications") or {}
        if not notif.get("email_enabled", True):
            continue
        if not notif.get(pref_key, True):
            continue
        recap_hour = notif.get("daily_recap_hour", 8)
        try:
            recap_hour = int(recap_hour)
        except (TypeError, ValueError):
            recap_hour = 8

        # Compare local hour by converting current UTC -> user's tz
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo

            tz = ZoneInfo(user.timezone or "UTC")
            local_hour = datetime.now(tz).hour
        except Exception:
            local_hour = target_hour  # fallback

        if local_hour != recap_hour:
            continue

        matching.append(
            {
                "id": str(user.id),
                "email": user.email,
                "username": user.username,
                "timezone": user.timezone,
                "language": user.language,
                "ai_behavior_style": user.ai_behavior_style,
            }
        )

    return {"users": matching, "count": len(matching)}


class MarkPhoneVerifiedRequest(BaseModel):
    user_id: str
    phone_number: str


@router.post("/mark-phone-verified")
async def mark_phone_verified(
    payload: MarkPhoneVerifiedRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_internal_token),
) -> dict:
    """Mark a phone number as verified.

    Called by notification-service after a successful Twilio Verify check.
    The phone number in the payload must match the user's current phone to
    avoid race conditions (e.g. user changed the number mid-flow).
    """
    try:
        user_uuid = UUID(payload.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = await db.get(User, user_uuid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.phone_number != payload.phone_number:
        raise HTTPException(
            status_code=409,
            detail="Phone number mismatch — user may have changed it in the meantime",
        )

    user.phone_verified = True
    user.phone_verified_at = datetime.now(timezone.utc)
    db.add(user)
    await db.flush()

    return {"ok": True, "phone_verified": True}


@router.get("/users/{user_id}/phone-settings")
async def get_user_phone_settings(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_internal_token),
) -> dict:
    """Return a user's phone number + SMS preferences (token-gated).

    Consumed by the sms_dispatcher in notification-service to decide
    whether to send an SMS for a given event type.
    """
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = await db.get(User, user_uuid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    prefs = user.preferences if isinstance(user.preferences, dict) else {}
    sms_prefs = prefs.get("sms") or {}

    return {
        "user_id": str(user.id),
        "phone_number": user.phone_number,
        "phone_verified": bool(user.phone_verified),
        "sms": {
            "master_enabled": bool(sms_prefs.get("master_enabled", False)),
            "events": sms_prefs.get("events") or {},
        },
    }


@router.get("/users/{user_id}/notification-settings")
async def get_user_notification_settings(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_internal_token),
) -> dict:
    """Return all notification channel settings for a user (SMS + Telegram).

    Single endpoint consumed by every dispatcher (sms_dispatcher,
    telegram_dispatcher, ...) so we don't multiply HTTP roundtrips when
    multiple channels are active for the same event.
    """
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = await db.get(User, user_uuid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    prefs = user.preferences if isinstance(user.preferences, dict) else {}
    sms_prefs = prefs.get("sms") or {}
    telegram_prefs = prefs.get("telegram") or {}

    return {
        "user_id": str(user.id),
        "phone_number": user.phone_number,
        "phone_verified": bool(user.phone_verified),
        "telegram_chat_id": user.telegram_chat_id,
        "sms": {
            "master_enabled": bool(sms_prefs.get("master_enabled", False)),
            "events": sms_prefs.get("events") or {},
        },
        "telegram": {
            "master_enabled": bool(telegram_prefs.get("master_enabled", False)),
            "events": telegram_prefs.get("events") or {},
        },
    }
