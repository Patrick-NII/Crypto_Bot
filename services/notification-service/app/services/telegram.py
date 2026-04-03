import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


async def send_message(
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
) -> dict[str, Any]:
    """Send a message via Telegram Bot API using httpx."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping message send")
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}

    url = f"{TELEGRAM_API_BASE.format(token=settings.TELEGRAM_BOT_TOKEN)}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        result = response.json()

    if not result.get("ok"):
        logger.error("Telegram API error: %s", result)

    return result


def format_alert(alert_type: str, data: dict[str, Any]) -> str:
    """Format an alert into an HTML message for Telegram."""
    templates = {
        "trade_executed": (
            "<b>Trade Executed</b>\n"
            "Symbol: <code>{symbol}</code>\n"
            "Side: {side}\n"
            "Quantity: {quantity}\n"
            "Price: ${price}"
        ),
        "price_alert": (
            "<b>Price Alert</b>\n"
            "Symbol: <code>{symbol}</code>\n"
            "Current Price: ${current_price}\n"
            "Target: ${target_price}\n"
            "Direction: {direction}"
        ),
        "risk_warning": (
            "<b>Risk Warning</b>\n"
            "Type: {warning_type}\n"
            "Message: {message}\n"
            "Severity: {severity}"
        ),
        "system": (
            "<b>System Notification</b>\n"
            "Service: {service}\n"
            "Message: {message}"
        ),
    }

    template = templates.get(alert_type, "<b>{type}</b>\n{message}")
    try:
        return template.format(**data, type=alert_type)
    except KeyError as e:
        logger.warning("Missing key %s in alert data for type %s", e, alert_type)
        return f"<b>{alert_type}</b>\n<pre>{data}</pre>"
