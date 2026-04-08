import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.services.recap_generator import generate_daily_recap
from app.services.telegram import format_alert, send_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class SendNotificationRequest(BaseModel):
    chat_id: Optional[str] = None
    message: str


class SendAlertRequest(BaseModel):
    chat_id: Optional[str] = None
    alert_type: str = "system"
    data: dict = {}


class NotificationResponse(BaseModel):
    sent: bool
    detail: str


@router.post("/send", response_model=NotificationResponse)
async def send_notification(request: SendNotificationRequest):
    """Send a test notification to Telegram."""
    chat_id = request.chat_id or settings.TELEGRAM_CHAT_ID
    if not chat_id:
        return NotificationResponse(sent=False, detail="No chat_id provided or configured")

    result = await send_message(chat_id=chat_id, text=request.message)
    if result.get("ok"):
        return NotificationResponse(sent=True, detail="Message sent successfully")
    return NotificationResponse(sent=False, detail=result.get("error", "Unknown error"))


@router.post("/send-alert", response_model=NotificationResponse)
async def send_alert(request: SendAlertRequest):
    """Send a formatted alert to Telegram."""
    chat_id = request.chat_id or settings.TELEGRAM_CHAT_ID
    if not chat_id:
        return NotificationResponse(sent=False, detail="No chat_id provided or configured")

    formatted = format_alert(request.alert_type, request.data)
    result = await send_message(chat_id=chat_id, text=formatted)
    if result.get("ok"):
        return NotificationResponse(sent=True, detail="Alert sent successfully")
    return NotificationResponse(sent=False, detail=result.get("error", "Unknown error"))


@router.post("/recap/test")
async def trigger_test_recap(authorization: Optional[str] = Header(default=None)):
    """Manually trigger a daily recap email for the authenticated user.

    The frontend forwards the user's JWT in the Authorization header — we use
    it both to identify the user (via auth-service) and to fetch their
    portfolio/trades on their behalf.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # Resolve user via auth-service /me
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/auth/me",
                headers={"Authorization": authorization},
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid auth token")
            user_profile = resp.json()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to resolve user: %s", exc)
        raise HTTPException(status_code=503, detail="Auth service unavailable")

    user_email = user_profile.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User has no email")

    user_dict = {
        "id": user_profile.get("id"),
        "email": user_email,
        "username": user_profile.get("username"),
        "ai_behavior_style": user_profile.get("ai_behavior_style", "balanced"),
        "timezone": user_profile.get("timezone", "Europe/Paris"),
    }

    # Build recap data
    try:
        recap_data = await generate_daily_recap(user_dict, auth_header=authorization)
    except Exception as exc:
        logger.error("Recap generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Recap generation failed: {exc}")

    # Send via mailing-service
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{settings.MAILING_SERVICE_URL}/api/v1/mail/send",
                json={
                    "to": user_email,
                    "template": "daily_recap",
                    "data": recap_data,
                },
            )
            if resp.status_code >= 400:
                logger.warning("Mail send returned %s: %s", resp.status_code, resp.text[:200])
                raise HTTPException(
                    status_code=502,
                    detail=f"Mailing service returned {resp.status_code}",
                )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Mail dispatch failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return {"sent": True, "to": user_email, "template": "daily_recap"}
