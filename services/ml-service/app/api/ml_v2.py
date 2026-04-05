"""ML Service API V2 — advanced multi-dimensional signals.

Separate router to avoid breaking V1.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.signal_engine import generate_advanced_signal
from app.services.data_fetcher import fetch_closes_and_volumes, fetch_candles

router = APIRouter(prefix="/api/v2/ml", tags=["ml-v2"])


class TradePlanResponse(BaseModel):
    side: str
    entry_zone: str
    invalidation_zone: str
    target_zone: str
    risk_reward: str
    validity: str
    style: str


class ContradictionItem(BaseModel):
    description: str
    severity: str


class TimeframeBiasResponse(BaseModel):
    micro: str
    higher: str
    alignment: str


class SubScoreItem(BaseModel):
    category: str
    score: int
    label: str


class SignalV2Response(BaseModel):
    symbol: str
    # 5 core dimensions
    direction_score: int
    confidence_score: int
    risk_score: int
    setup_quality_score: int
    actionability: str
    # Context
    action: str
    direction_label: str
    market_regime: str
    signal_context: str
    timeframe_bias: TimeframeBiasResponse
    # Details
    sub_scores: list[SubScoreItem]
    reasons: list[str]
    contradictions: list[ContradictionItem]
    trade_plan: TradePlanResponse | None = None
    # Meta
    timestamp: str
    price: float | None = None
    source: str = "signal-engine-v2"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sub_label(cat: str, score: int) -> str:
    from app.services.signal_engine import _sub_label as sl
    return sl(cat, score)


@router.get("/signals/{symbol}", response_model=SignalV2Response)
async def get_signal_v2(
    symbol: str,
    interval: str = Query("1h", description="Primary timeframe interval"),
    lookback: int = Query(120, ge=30, le=500),
    higher_tf: str = Query("4h", description="Higher timeframe for bias"),
):
    """V2 advanced signal with 5 dimensions, contradictions, trade plan."""
    sym = symbol.upper()

    # Fetch primary candles
    candles, source = await fetch_candles(sym, interval, lookback)
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    volumes = [c.volume for c in candles]

    # Fetch higher TF for multi-timeframe bias
    higher_candles, _ = await fetch_candles(sym, higher_tf, 60)
    higher_closes = [c.close for c in higher_candles] if higher_candles else None

    result = generate_advanced_signal(
        sym, closes, highs, lows, volumes, higher_closes,
    )

    return SignalV2Response(
        symbol=sym,
        direction_score=result.direction_score,
        confidence_score=result.confidence_score,
        risk_score=result.risk_score,
        setup_quality_score=result.setup_quality_score,
        actionability=result.actionability,
        action=result.action,
        direction_label=result.direction_label,
        market_regime=result.market_regime,
        signal_context=result.signal_context,
        timeframe_bias=TimeframeBiasResponse(
            micro=result.timeframe_bias.micro,
            higher=result.timeframe_bias.higher,
            alignment=result.timeframe_bias.alignment,
        ),
        sub_scores=[
            SubScoreItem(category=cat, score=score, label=_sub_label(cat, score))
            for cat, score in result.sub_scores.items()
        ],
        reasons=result.reasons,
        contradictions=[
            ContradictionItem(description=c.description, severity=c.severity)
            for c in result.contradictions
        ],
        trade_plan=TradePlanResponse(
            side=result.trade_plan.side,
            entry_zone=result.trade_plan.entry_zone,
            invalidation_zone=result.trade_plan.invalidation_zone,
            target_zone=result.trade_plan.target_zone,
            risk_reward=result.trade_plan.risk_reward,
            validity=result.trade_plan.validity,
            style=result.trade_plan.style,
        ) if result.trade_plan else None,
        timestamp=_utc_now(),
        price=closes[-1] if closes else None,
        source=source,
    )
