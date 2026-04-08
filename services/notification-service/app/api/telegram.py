"""Telegram notifications API.

Endpoints:
    GET  /telegram/preferences        : current chat_id + per-event toggles
    PUT  /telegram/preferences        : update master + events toggles
    POST /telegram/link               : save the user's chat_id
    POST /telegram/test               : send a test message
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.telegram import send_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"])


async def _resolve_user(authorization: Optional[str]) -> Dict[str, Any]:
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


async def _save_user_chat_id(authorization: str, chat_id: str) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.put(
            f"{settings.AUTH_SERVICE_URL}/api/v1/auth/me",
            headers={
                "Authorization": authorization,
                "Content-Type": "application/json",
            },
            json={"telegram_chat_id": chat_id},
        )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Could not save chat_id: HTTP {resp.status_code}",
            )


async def _save_user_preferences(
    authorization: str,
    telegram_prefs: Dict[str, Any],
) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.put(
            f"{settings.AUTH_SERVICE_URL}/api/v1/auth/me",
            headers={
                "Authorization": authorization,
                "Content-Type": "application/json",
            },
            json={"preferences": {"telegram": telegram_prefs}},
        )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Could not save Telegram preferences: HTTP {resp.status_code}",
            )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LinkRequest(BaseModel):
    chat_id: str = Field(..., min_length=1, max_length=64)


class UpdatePreferencesRequest(BaseModel):
    master_enabled: bool = False
    events: Dict[str, bool] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/preferences")
async def get_preferences(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user = await _resolve_user(authorization)
    prefs = (user.get("preferences") or {}).get("telegram") or {}
    bot_username = settings.TELEGRAM_BOT_USERNAME or None
    return {
        "chat_id": user.get("telegram_chat_id"),
        "linked": bool(user.get("telegram_chat_id")),
        "bot_username": bot_username,
        "telegram": {
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


@router.post("/link")
async def link_chat(
    payload: LinkRequest,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Link the user's Telegram chat_id.

    The user obtains their chat_id by sending /start to the bot, which
    replies with their numeric chat id (or via @userinfobot in any chat).
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization requise")

    chat_id = payload.chat_id.strip()
    if not chat_id.lstrip("-").isdigit():
        raise HTTPException(
            status_code=400,
            detail="chat_id doit etre un identifiant numerique Telegram",
        )

    await _save_user_chat_id(authorization, chat_id)
    return {"ok": True, "chat_id": chat_id}


@router.post("/test")
async def send_test(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await _resolve_user(authorization)
    chat_id = user.get("telegram_chat_id")
    if not chat_id:
        raise HTTPException(status_code=400, detail="Aucun chat Telegram lie")
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=503, detail="Telegram bot non configure")

    result = await send_message(
        chat_id=str(chat_id),
        text=(
            "<b>GlueTrade</b>\n"
            "Test de notification reussi. Les alertes sont actives sur ce chat."
        ),
        parse_mode="HTML",
    )
    return {"ok": bool(result.get("ok")), **result}
