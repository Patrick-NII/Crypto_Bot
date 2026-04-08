"""Auto-Trading API — toggle, status, history, decisions, trade groups."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.auth import resolve_request_user_id
from app.repositories.auto_repository import auto_repository
from app.services.auto_trader import (
    emergency_stop,
    get_history,
    get_status,
    remember_auth,
    start,
    stop,
    update_config,
)

router = APIRouter(prefix="/api/v1/ai/auto-trading", tags=["auto-trading"])


class ToggleRequest(BaseModel):
    enabled: bool
    mode: Optional[Literal["paper", "live", "dry_run"]] = None
    portfolio_id: Optional[str] = None
    interval_seconds: Optional[int] = Field(None, ge=60, le=3600)
    config: Optional[dict] = None


class ConfigRequest(BaseModel):
    mode: Optional[Literal["paper", "live", "dry_run"]] = None
    interval_seconds: Optional[int] = Field(None, ge=60, le=3600)
    portfolio_id: Optional[str] = None
    breakers: Optional[dict] = None


class EmergencyStopRequest(BaseModel):
    reason: Optional[str] = "user_initiated"


@router.get("/status")
async def auto_trading_status(request: Request) -> dict:
    """Get current auto-trading status."""
    user_id = resolve_request_user_id(request)
    await remember_auth(user_id, request.headers.get("Authorization"))
    return get_status(user_id)


@router.post("/toggle")
async def toggle_auto_trading(req: ToggleRequest, request: Request) -> dict:
    """Enable or disable auto-trading.

    When enabling, accepts optional ``mode``, ``portfolio_id``,
    ``interval_seconds`` and ``config``. Missing fields fall back to
    the existing session defaults.
    """
    user_id = resolve_request_user_id(request)
    auth_header = request.headers.get("Authorization")
    await remember_auth(user_id, auth_header)
    if req.enabled:
        await start(
            user_id,
            auth_header,
            mode=req.mode,
            portfolio_id=req.portfolio_id,
            interval_seconds=req.interval_seconds,
            config=req.config,
        )
    else:
        await stop(user_id)
    return get_status(user_id)


@router.put("/config")
async def update_auto_config(req: ConfigRequest, request: Request) -> dict:
    """Update per-user auto-trader config without stopping the loop."""
    user_id = resolve_request_user_id(request)
    return await update_config(
        user_id,
        mode=req.mode,
        interval_seconds=req.interval_seconds,
        portfolio_id=req.portfolio_id,
        breakers=req.breakers,
    )


@router.post("/emergency-stop")
async def auto_trading_emergency_stop(
    req: EmergencyStopRequest,
    request: Request,
) -> dict:
    """Cancel all open orders + disable the auto-trader immediately."""
    user_id = resolve_request_user_id(request)
    await remember_auth(user_id, request.headers.get("Authorization"))
    summary = await emergency_stop(user_id, reason=req.reason or "user_initiated")
    return {"status": "stopped", **summary, **get_status(user_id)}


@router.get("/history")
async def auto_trading_history(request: Request) -> list[dict]:
    """Get auto-trading cycle history (RAM-cached, last 100)."""
    user_id = resolve_request_user_id(request)
    await remember_auth(user_id, request.headers.get("Authorization"))
    return get_history(user_id)


@router.get("/decisions")
async def auto_trading_decisions(
    request: Request,
    cycle_id: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """Return recent auto_decisions rows for the current user.

    Supports filtering by ``cycle_id`` and ``outcome``.
    """
    user_id = resolve_request_user_id(request)
    rows = await auto_repository.list_decisions(
        user_id,
        cycle_id=cycle_id,
        outcome=outcome,
        limit=limit,
        offset=offset,
    )
    return {
        "decisions": [
            {
                "id": r.id,
                "cycle_id": r.cycle_id,
                "decided_at": r.decided_at.isoformat() if r.decided_at else None,
                "symbol": r.symbol,
                "action": r.action,
                "quantity": str(r.quantity) if r.quantity is not None else None,
                "target_price": str(r.target_price) if r.target_price is not None else None,
                "confidence": float(r.confidence or 0),
                "score": float(r.score or 0),
                "regime": r.regime,
                "scenario": r.scenario,
                "reasoning": r.reasoning,
                "decision_outcome": r.decision_outcome,
                "outcome_reason": r.outcome_reason,
                "execution_order_id": r.execution_order_id,
                "trade_group_id": r.trade_group_id,
                "signals": r.signals,
                "context": r.context,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/trade-groups")
async def auto_trading_trade_groups(
    request: Request,
    status: Optional[str] = Query(None, pattern="^(open|closed|cancelled)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """Return trade groups (transaction lifecycles) for the current user."""
    user_id = resolve_request_user_id(request)
    rows = await auto_repository.list_trade_groups(
        user_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "trade_groups": [
            {
                "id": g.id,
                "short_id": g.id[:8] if g.id else None,
                "symbol": g.symbol,
                "side": g.side,
                "status": g.status,
                "entry_order_id": g.entry_order_id,
                "exit_order_id": g.exit_order_id,
                "entry_decision_id": g.entry_decision_id,
                "exit_decision_id": g.exit_decision_id,
                "entry_time": g.entry_time.isoformat() if g.entry_time else None,
                "exit_time": g.exit_time.isoformat() if g.exit_time else None,
                "holding_seconds": g.holding_seconds,
                "entry_quantity": str(g.entry_quantity or 0),
                "exit_quantity": str(g.exit_quantity or 0),
                "entry_price": str(g.entry_price) if g.entry_price is not None else None,
                "exit_price": str(g.exit_price) if g.exit_price is not None else None,
                "entry_fee": str(g.entry_fee) if g.entry_fee is not None else None,
                "exit_fee": str(g.exit_fee) if g.exit_fee is not None else None,
                "realized_pnl": str(g.realized_pnl) if g.realized_pnl is not None else None,
                "realized_pnl_pct": (
                    str(g.realized_pnl_pct) if g.realized_pnl_pct is not None else None
                ),
                "entry_reason": g.entry_reason,
                "exit_reason": g.exit_reason,
            }
            for g in rows
        ],
        "count": len(rows),
    }


@router.get("/export")
async def auto_trading_export(
    request: Request,
    format: Literal["csv", "json"] = Query("csv"),
    from_ts: Optional[datetime] = Query(None, alias="from"),
    to_ts: Optional[datetime] = Query(None, alias="to"),
) -> Any:
    """Export decisions as CSV or JSON for downstream retraining.

    The ``signals`` and ``context`` JSONB columns are flattened as JSON
    strings in the CSV — the ML pipeline is expected to parse them back.
    """
    user_id = resolve_request_user_id(request)
    rows = await auto_repository.decisions_for_export(
        user_id, from_ts=from_ts, to_ts=to_ts
    )

    if format == "json":
        return {
            "decisions": [
                {
                    "id": r.id,
                    "cycle_id": r.cycle_id,
                    "decided_at": r.decided_at.isoformat() if r.decided_at else None,
                    "symbol": r.symbol,
                    "action": r.action,
                    "confidence": float(r.confidence or 0),
                    "score": float(r.score or 0),
                    "regime": r.regime,
                    "scenario": r.scenario,
                    "decision_outcome": r.decision_outcome,
                    "trade_group_id": r.trade_group_id,
                    "signals": r.signals,
                    "context": r.context,
                }
                for r in rows
            ],
            "count": len(rows),
        }

    # CSV — flatten signals/context as JSON strings
    import json as _json

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "cycle_id",
            "decided_at",
            "symbol",
            "action",
            "confidence",
            "score",
            "regime",
            "scenario",
            "decision_outcome",
            "outcome_reason",
            "execution_order_id",
            "trade_group_id",
            "signals_json",
            "context_json",
            "reasoning",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.id,
                r.cycle_id,
                r.decided_at.isoformat() if r.decided_at else "",
                r.symbol,
                r.action,
                float(r.confidence or 0),
                float(r.score or 0),
                r.regime or "",
                r.scenario or "",
                r.decision_outcome,
                r.outcome_reason or "",
                r.execution_order_id or "",
                r.trade_group_id or "",
                _json.dumps(r.signals or {}, ensure_ascii=False),
                _json.dumps(r.context or {}, ensure_ascii=False),
                r.reasoning or "",
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=auto_decisions.csv"},
    )
