"""Twilio SDK wrapper.

The Twilio Python SDK is blocking — every call goes through
``asyncio.to_thread`` so we don't block the FastAPI event loop. The client
is lazy-initialised on first use; if credentials are missing, calls return
a ``{"ok": False, "error": "not_configured"}`` result instead of raising.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TwilioResult:
    ok: bool
    sid: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None
    code: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "sid": self.sid,
            "status": self.status,
            "error": self.error,
            "code": self.code,
        }


_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        return None
    try:
        from twilio.rest import Client

        _client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        logger.info("Twilio client initialised (verify=%s)", bool(settings.TWILIO_VERIFY_SERVICE_SID))
        return _client
    except Exception as exc:
        logger.warning("Twilio client init failed: %s", exc)
        return None


def _send_sms_sync(to: str, body: str) -> Dict[str, Any]:
    client = _get_client()
    if client is None:
        return {"ok": False, "error": "not_configured"}
    kwargs: Dict[str, Any] = {"to": to, "body": body}
    if settings.TWILIO_MESSAGING_SERVICE_SID:
        kwargs["messaging_service_sid"] = settings.TWILIO_MESSAGING_SERVICE_SID
    elif settings.TWILIO_PHONE_NUMBER:
        kwargs["from_"] = settings.TWILIO_PHONE_NUMBER
    else:
        return {"ok": False, "error": "no_sender_configured"}

    try:
        message = client.messages.create(**kwargs)
        return {
            "ok": True,
            "sid": message.sid,
            "status": getattr(message, "status", None),
        }
    except Exception as exc:
        # TwilioRestException has .code, .status, .msg attributes
        code = getattr(exc, "code", None)
        status = getattr(exc, "status", None)
        msg = getattr(exc, "msg", None) or str(exc)
        return {"ok": False, "error": msg, "code": code, "status": status}


async def send_sms(to: str, body: str) -> TwilioResult:
    """Async wrapper around blocking SDK."""
    result = await asyncio.to_thread(_send_sms_sync, to, body)
    return TwilioResult(
        ok=bool(result.get("ok")),
        sid=result.get("sid"),
        status=result.get("status"),
        error=result.get("error"),
        code=result.get("code"),
    )


# ---------------------------------------------------------------------------
# Verify V2 (OTP)
# ---------------------------------------------------------------------------


def _start_verification_sync(phone: str) -> Dict[str, Any]:
    client = _get_client()
    if client is None or not settings.TWILIO_VERIFY_SERVICE_SID:
        return {"ok": False, "error": "verify_not_configured"}
    try:
        verification = (
            client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID)
            .verifications.create(to=phone, channel="sms")
        )
        return {
            "ok": True,
            "sid": verification.sid,
            "status": verification.status,
            "channel": "sms",
        }
    except Exception as exc:
        code = getattr(exc, "code", None)
        msg = getattr(exc, "msg", None) or str(exc)
        return {"ok": False, "error": msg, "code": code}


def _check_verification_sync(phone: str, code: str) -> Dict[str, Any]:
    client = _get_client()
    if client is None or not settings.TWILIO_VERIFY_SERVICE_SID:
        return {"ok": False, "verified": False, "error": "verify_not_configured"}
    try:
        check = (
            client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID)
            .verification_checks.create(to=phone, code=code)
        )
        return {
            "ok": True,
            "verified": check.status == "approved",
            "status": check.status,
        }
    except Exception as exc:
        twilio_code = getattr(exc, "code", None)
        msg = getattr(exc, "msg", None) or str(exc)
        return {"ok": False, "verified": False, "error": msg, "code": twilio_code}


async def start_verification(phone: str) -> Dict[str, Any]:
    return await asyncio.to_thread(_start_verification_sync, phone)


async def check_verification(phone: str, code: str) -> Dict[str, Any]:
    return await asyncio.to_thread(_check_verification_sync, phone, code)


def is_configured() -> bool:
    return bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN)
