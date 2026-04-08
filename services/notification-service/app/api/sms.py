"""SMS API — phone verification + user preferences + test send."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services import twilio_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sms", tags=["sms"])

# Rate limiter: 3 verification starts / 10 min per user+phone
_verify_start_buckets: Dict[str, list[float]] = {}
_VERIFY_WINDOW = 600  # 10 min
_VERIFY_MAX = 3


def _verify_allow(key: str) -> bool:
    now = time.monotonic()
    bucket = _verify_start_buckets.setdefault(key, [])
    cutoff = now - _VERIFY_WINDOW
    bucket[:] = [t for t in bucket if t > cutoff]
    if len(bucket) >= _VERIFY_MAX:
        return False
    bucket.append(now)
    return True


def _validate_phone(phone: str) -> str:
    """Return E.164 or raise HTTPException(400)."""
    try:
        import phonenumbers

        parsed = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("invalid number")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Numero de telephone invalide (format E.164 requis, ex: +33612345678)",
        )


async def _resolve_user(authorization: Optional[str]) -> Dict[str, Any]:
    """Resolve the caller via auth-service /auth/me."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization requise")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/auth/me",
                headers={"Authorization": authorization},
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid token")
            return resp.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Auth service unavailable: {exc}")


async def _save_user_phone(
    authorization: str,
    phone: str,
) -> None:
    """PUT the phone_number on the authenticated user (resets verification)."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.put(
            f"{settings.AUTH_SERVICE_URL}/api/v1/auth/me",
            headers={"Authorization": authorization, "Content-Type": "application/json"},
            json={"phone_number": phone},
        )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Could not save phone: HTTP {resp.status_code}",
            )


async def _mark_phone_verified(user_id: str, phone: str) -> None:
    if not settings.INTERNAL_API_TOKEN:
        raise HTTPException(status_code=503, detail="Internal token not configured")
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            f"{settings.AUTH_SERVICE_URL}/api/v1/auth/internal/mark-phone-verified",
            headers={"X-Internal-Token": settings.INTERNAL_API_TOKEN, "Content-Type": "application/json"},
            json={"user_id": user_id, "phone_number": phone},
        )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Internal mark-phone-verified failed: {resp.text[:120]}",
            )


async def _save_user_preferences(
    authorization: str,
    sms_prefs: Dict[str, Any],
) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.put(
            f"{settings.AUTH_SERVICE_URL}/api/v1/auth/me",
            headers={"Authorization": authorization, "Content-Type": "application/json"},
            json={"preferences": {"sms": sms_prefs}},
        )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Could not save SMS preferences: HTTP {resp.status_code}",
            )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class StartVerifyRequest(BaseModel):
    phone: str = Field(..., min_length=6, max_length=32)


class CheckVerifyRequest(BaseModel):
    phone: str = Field(..., min_length=6, max_length=32)
    code: str = Field(..., min_length=3, max_length=10)


class UpdatePreferencesRequest(BaseModel):
    master_enabled: bool = False
    events: Dict[str, bool] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/preferences")
async def get_preferences(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await _resolve_user(authorization)
    prefs = (user.get("preferences") or {}).get("sms") or {}
    return {
        "phone_number": user.get("phone_number"),
        "phone_verified": bool(user.get("phone_verified")),
        "sms": {
            "master_enabled": bool(prefs.get("master_enabled", False)),
            "events": prefs.get("events") or {},
        },
    }


@router.put("/preferences")
async def update_preferences(
    payload: UpdatePreferencesRequest,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization requise")
    await _save_user_preferences(
        authorization,
        {
            "master_enabled": payload.master_enabled,
            "events": payload.events,
        },
    )
    return {"ok": True}


@router.post("/verify/start")
async def verify_start(
    payload: StartVerifyRequest,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user = await _resolve_user(authorization)
    user_id = str(user.get("id") or "")
    phone = _validate_phone(payload.phone)

    # Rate limit per (user, phone)
    if not _verify_allow(f"{user_id}:{phone}"):
        raise HTTPException(
            status_code=429,
            detail="Trop de demandes de code. Reessayez dans quelques minutes.",
        )

    # Persist the (unverified) phone on the user — it will be verified on check
    assert authorization is not None  # guaranteed by _resolve_user
    await _save_user_phone(authorization, phone)

    if not twilio_client.is_configured() or not settings.TWILIO_VERIFY_SERVICE_SID:
        # Sandbox mode — no Twilio configured, we still persist the phone
        # and return a dev-only marker. The user can call check/ with the
        # fixed code "000000" in this mode for local testing.
        logger.warning("Twilio Verify not configured — sandbox mode for phone %s", phone)
        return {"status": "sandbox", "channel": "none"}

    result = await twilio_client.start_verification(phone)
    if not result.get("ok"):
        raise HTTPException(
            status_code=502,
            detail=result.get("error") or "Impossible d'envoyer le code",
        )
    return {"status": result.get("status") or "pending", "channel": "sms"}


@router.post("/verify/check")
async def verify_check(
    payload: CheckVerifyRequest,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user = await _resolve_user(authorization)
    user_id = str(user.get("id") or "")
    phone = _validate_phone(payload.phone)

    if not twilio_client.is_configured() or not settings.TWILIO_VERIFY_SERVICE_SID:
        # Sandbox mode — accept any 6-digit code for local testing
        if payload.code == "000000":
            await _mark_phone_verified(user_id, phone)
            return {"status": "approved", "verified": True}
        raise HTTPException(status_code=400, detail="Sandbox: use code 000000")

    result = await twilio_client.check_verification(phone, payload.code)
    if not result.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error") or "Code invalide",
        )
    if not result.get("verified"):
        return {"status": result.get("status") or "pending", "verified": False}

    await _mark_phone_verified(user_id, phone)
    return {"status": "approved", "verified": True}


@router.post("/test")
async def send_test(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await _resolve_user(authorization)
    if not user.get("phone_verified"):
        raise HTTPException(status_code=400, detail="Numero non verifie")
    phone = user.get("phone_number")
    if not phone:
        raise HTTPException(status_code=400, detail="Aucun numero enregistre")
    if not twilio_client.is_configured():
        raise HTTPException(status_code=503, detail="Twilio non configure")
    result = await twilio_client.send_sms(
        phone, "[GlueTrade] Test SMS reussi. Les notifications sont actives."
    )
    return result.to_dict()
