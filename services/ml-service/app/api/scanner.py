"""Scanner API — multi-asset opportunity scanning and ranking.

New endpoints added alongside existing /api/v1/ml/* routes.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.engine.ranking_engine import scan_opportunities
from app.engine.signal_engine import compute_all_strategies
from app.engine.enhanced_scoring import compute_enhanced_scores
from app.services.data_fetcher import fetch_multi_timeframe, fetch_closes_and_volumes
from app.engine.market_context import build_market_context
from app.settings.user_settings import get_settings

router = APIRouter(prefix="/api/v1/scanner", tags=["scanner"])


class SubScoreResponse(BaseModel):
    category: str
    score: int
    label: str


class ContradictionResponse(BaseModel):
    description: str
    severity: str


class TradePlanResponse(BaseModel):
    side: str
    entry_zone: str
    invalidation_zone: str
    target_zone: str
    risk_reward: str
    validity: str
    execution_style: str


class OpportunityResponse(BaseModel):
    rank: int
    symbol: str
    # 5 core dimensions
    direction: int = 50
    direction_label: str = "Neutre"
    confidence: float = 0
    risk: int = 50
    setup_quality: int = 50
    actionability: str = "IGNORE"
    # Context
    action: str = "HOLD"
    market_regime: str = "UNKNOWN"
    signal_context: str = "mixed"
    # Details
    sub_scores: list[SubScoreResponse] = []
    key_reasons: list[str] = []
    contradictions: list[ContradictionResponse] = []
    signal_trade_plan: TradePlanResponse | None = None
    # Legacy compat
    global_score: float = 0
    score_100: int = 50
    status: str = "ignore"
    action_label: str = "Neutre"
    confidence_level: str = "moyen"
    best_strategy: dict | None = None
    market_context: dict | None = None
    trade_plan: dict | None = None
    timestamp: str = ""


class ScannerResponse(BaseModel):
    opportunities: list[OpportunityResponse]
    mode: str
    scanned: int
    actionable: int
    timestamp: str


class DetailedSignalResponse(BaseModel):
    symbol: str
    mode: str
    strategies: list[dict]
    market_context: dict
    timestamp: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(obj) -> dict:
    """Convert dataclass to dict, handling nested dataclasses."""
    if obj is None:
        return {}
    d = asdict(obj)
    # Remove None values for cleaner JSON
    return {k: v for k, v in d.items() if v is not None}


@router.get("/opportunities", response_model=ScannerResponse)
async def get_opportunities(
    symbols: str = Query("BTC,ETH,SOL,BNB,XRP", description="Comma-separated symbols"),
    mode: str = Query("scalping", description="Trading mode: scalping, intraday, swing"),
    top_n: int = Query(3, ge=1, le=20, description="Max opportunities to return"),
):
    """Scan multiple assets and return ranked trading opportunities."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    settings = get_settings(mode)
    settings.top_n_opportunities = top_n

    opportunities = await scan_opportunities(symbol_list, settings)

    enriched: list[OpportunityResponse] = []
    for opp in opportunities:
        # Compute enhanced scores from best strategy indicators
        indicators = opp.best_strategy.indicators if opp.best_strategy else []
        enhanced = compute_enhanced_scores(indicators, opp.global_score, opp.market_context)

        enriched.append(OpportunityResponse(
            rank=opp.rank,
            symbol=opp.symbol,
            direction=enhanced.direction,
            direction_label=enhanced.direction_label,
            confidence=enhanced.confidence,
            risk=enhanced.risk,
            setup_quality=enhanced.setup_quality,
            actionability=enhanced.actionability,
            action=enhanced.action,
            market_regime=enhanced.market_regime,
            signal_context=enhanced.signal_context,
            sub_scores=[
                SubScoreResponse(category=ss.category, score=ss.score, label=ss.label)
                for ss in enhanced.sub_scores
            ],
            key_reasons=enhanced.key_reasons,
            contradictions=[
                ContradictionResponse(description=c.description, severity=c.severity)
                for c in enhanced.contradictions
            ],
            signal_trade_plan=TradePlanResponse(**{
                "side": enhanced.trade_plan.side,
                "entry_zone": enhanced.trade_plan.entry_zone,
                "invalidation_zone": enhanced.trade_plan.invalidation_zone,
                "target_zone": enhanced.trade_plan.target_zone,
                "risk_reward": enhanced.trade_plan.risk_reward,
                "validity": enhanced.trade_plan.validity,
                "execution_style": enhanced.trade_plan.execution_style,
            }) if enhanced.trade_plan else None,
            # Legacy compat
            global_score=opp.global_score,
            score_100=enhanced.score_100,
            status=enhanced.actionability.lower(),
            action_label=enhanced.label,
            confidence_level=enhanced.confidence_level,
            best_strategy=_safe_dict(opp.best_strategy) if opp.best_strategy else None,
            market_context=_safe_dict(opp.market_context) if opp.market_context else None,
            trade_plan=_safe_dict(opp.trade_plan) if opp.trade_plan else None,
            timestamp=opp.timestamp,
        ))

    return ScannerResponse(
        opportunities=enriched,
        mode=mode,
        scanned=len(symbol_list),
        actionable=sum(1 for o in enriched if o.status in ("actionable", "high_conviction")),
        timestamp=_utc_now(),
    )


@router.get("/opportunities/{symbol}", response_model=DetailedSignalResponse)
async def get_symbol_detail(
    symbol: str,
    mode: str = Query("scalping", description="Trading mode"),
):
    """Get detailed signal analysis for a single symbol across all strategies."""
    settings = get_settings(mode)

    # Build TF config
    tf_config = {settings.primary_timeframe: 120}
    for tf in settings.confirmation_timeframes:
        tf_config[tf] = 60

    candles_by_tf = await fetch_multi_timeframe(symbol.upper(), tf_config)

    # BTC closes for context
    btc_closes = None
    if settings.btc_trend_filter and symbol.upper() != "BTC":
        try:
            closes, _, _ = await fetch_closes_and_volumes("BTC", "15m", 100)
            btc_closes = closes if len(closes) >= 20 else None
        except Exception:
            pass

    results, market_ctx = compute_all_strategies(
        symbol.upper(), candles_by_tf, settings, btc_closes,
    )

    return DetailedSignalResponse(
        symbol=symbol.upper(),
        mode=mode,
        strategies=[_safe_dict(r) for r in results],
        market_context=_safe_dict(market_ctx),
        timestamp=_utc_now(),
    )
