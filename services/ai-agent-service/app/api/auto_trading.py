"""Auto-Trading API — toggle, status, and history."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.auto_trader import start, stop, get_status, get_history

router = APIRouter(prefix="/api/v1/ai/auto-trading", tags=["auto-trading"])


class ToggleRequest(BaseModel):
    enabled: bool


@router.get("/status")
async def auto_trading_status() -> dict:
    """Get current auto-trading status."""
    return get_status()


@router.post("/toggle")
async def toggle_auto_trading(req: ToggleRequest) -> dict:
    """Enable or disable auto-trading."""
    if req.enabled:
        start()
    else:
        stop()
    return get_status()


@router.get("/history")
async def auto_trading_history() -> list[dict]:
    """Get auto-trading decision history."""
    return get_history()
