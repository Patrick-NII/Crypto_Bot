"""Auto-Trading API — toggle, status, and history."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.auth import resolve_request_user_id
from app.services.auto_trader import (
    get_history,
    get_status,
    remember_auth,
    start,
    stop,
)

router = APIRouter(prefix="/api/v1/ai/auto-trading", tags=["auto-trading"])


class ToggleRequest(BaseModel):
    enabled: bool


@router.get("/status")
async def auto_trading_status(request: Request) -> dict:
    """Get current auto-trading status."""
    user_id = resolve_request_user_id(request)
    await remember_auth(user_id, request.headers.get("Authorization"))
    return get_status(user_id)


@router.post("/toggle")
async def toggle_auto_trading(req: ToggleRequest, request: Request) -> dict:
    """Enable or disable auto-trading."""
    user_id = resolve_request_user_id(request)
    auth_header = request.headers.get("Authorization")
    await remember_auth(user_id, auth_header)
    if req.enabled:
        await start(user_id, auth_header)
    else:
        await stop(user_id)
    return get_status(user_id)


@router.get("/history")
async def auto_trading_history(request: Request) -> list[dict]:
    """Get auto-trading decision history."""
    user_id = resolve_request_user_id(request)
    await remember_auth(user_id, request.headers.get("Authorization"))
    return get_history(user_id)
