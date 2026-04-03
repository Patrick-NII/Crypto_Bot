from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.services.telegram import format_alert, send_message

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
