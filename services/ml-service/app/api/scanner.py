"""Scanner API for contextual signals and published opportunities."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.engine.enhanced_scoring import compute_enhanced_scores
from app.engine.ranking_engine import scan_opportunities, scan_signals
from app.engine.scenario_engine import select_primary_scenario
from app.engine.signal_engine import compute_all_strategies
from app.services.data_fetcher import fetch_closes_and_volumes, fetch_multi_timeframe
from app.settings.user_settings import get_settings

router = APIRouter(prefix="/api/v1/scanner", tags=["scanner"])


class IndicatorResponse(BaseModel):
    name: str
    value: float
    signal: float
    description: str


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


class ScenarioResponse(BaseModel):
    name: str
    direction: str
    probability: float
    reasoning: str = ""


class OpportunityResponse(BaseModel):
    rank: int
    symbol: str
    horizon: str = ""
    setup_type: str = ""
    regime: str = "RANGE"
    reasoning: str = ""
    indicators: list[IndicatorResponse] = Field(default_factory=list)
    direction: int = 50
    direction_label: str = "Neutre / attente"
    confidence: float = 0.0
    confidence_score: int = 0
    regime_fit: int = 0
    confirmation_score: int = 0
    execution_risk: int = 50
    liquidity_score: int = 50
    risk: int = 50
    setup_quality: int = 50
    actionability: str = "IGNORE"
    action: str = "HOLD"
    market_regime: str = "UNKNOWN"
    signal_context: str = "mixed"
    sub_scores: list[SubScoreResponse] = Field(default_factory=list)
    key_reasons: list[str] = Field(default_factory=list)
    contradictions: list[ContradictionResponse] = Field(default_factory=list)
    notrade_reasons: list[str] = Field(default_factory=list)
    expected_holding_window: str = ""
    freshness_ms: int = 0
    signal_trade_plan: TradePlanResponse | None = None
    scenario: str | None = None
    scenario_probability: float | None = None
    alternative_scenarios: list[ScenarioResponse] = Field(default_factory=list)
    global_score: float = 0.0
    score_100: int = 50
    status: str = "ignore"
    action_label: str = "Neutre / attente"
    confidence_level: str = "faible"
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


class SignalSnapshotResponse(BaseModel):
    signals: list[OpportunityResponse]
    mode: str
    scanned: int
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
    if obj is None:
        return {}
    data = asdict(obj)
    return {key: value for key, value in data.items() if value is not None}


def _serialize_opportunity(opp) -> OpportunityResponse:
    indicators = opp.best_strategy.indicators if opp.best_strategy else []
    primary_scenario = select_primary_scenario(opp.scenarios)
    enhanced = compute_enhanced_scores(
        indicators,
        opp.global_score,
        market_context=opp.market_context,
        regime=opp.regime_info,
        scenario=primary_scenario,
    )

    return OpportunityResponse(
        rank=opp.rank,
        symbol=opp.symbol,
        horizon=opp.horizon,
        setup_type=opp.setup_type,
        regime=opp.regime,
        reasoning=opp.best_strategy.reasoning if opp.best_strategy else "",
        indicators=[
            IndicatorResponse(
                name=item.name,
                value=item.value,
                signal=item.signal,
                description=item.description,
            )
            for item in indicators
        ],
        direction=enhanced.direction,
        direction_label=enhanced.direction_label,
        confidence=round(float(opp.confidence), 3),
        confidence_score=enhanced.confidence,
        regime_fit=opp.regime_fit,
        confirmation_score=opp.confirmation_score,
        execution_risk=opp.execution_risk,
        liquidity_score=opp.liquidity_score,
        risk=enhanced.risk,
        setup_quality=enhanced.setup_quality,
        actionability=enhanced.actionability,
        action=enhanced.action,
        market_regime=enhanced.market_regime,
        signal_context=enhanced.signal_context,
        sub_scores=[
            SubScoreResponse(category=score.category, score=score.score, label=score.label)
            for score in enhanced.sub_scores
        ],
        key_reasons=enhanced.key_reasons,
        contradictions=[
            ContradictionResponse(description=item.description, severity=item.severity)
            for item in enhanced.contradictions
        ],
        notrade_reasons=list(opp.notrade_reasons),
        expected_holding_window=opp.expected_holding_window,
        freshness_ms=opp.freshness_ms,
        signal_trade_plan=TradePlanResponse(
            side=enhanced.trade_plan.side,
            entry_zone=enhanced.trade_plan.entry_zone,
            invalidation_zone=enhanced.trade_plan.invalidation_zone,
            target_zone=enhanced.trade_plan.target_zone,
            risk_reward=enhanced.trade_plan.risk_reward,
            validity=enhanced.trade_plan.validity,
            execution_style=enhanced.trade_plan.execution_style,
        ) if enhanced.trade_plan else None,
        scenario=primary_scenario.name if primary_scenario else None,
        scenario_probability=primary_scenario.probability if primary_scenario else None,
        alternative_scenarios=[
            ScenarioResponse(
                name=scenario.name,
                direction=scenario.direction,
                probability=scenario.probability,
                reasoning=scenario.reasoning,
            )
            for scenario in opp.scenarios
        ],
        global_score=opp.global_score,
        score_100=enhanced.score_100,
        status=opp.status,
        action_label=enhanced.label,
        confidence_level=enhanced.confidence_level,
        best_strategy=_safe_dict(opp.best_strategy) if opp.best_strategy else None,
        market_context=_safe_dict(opp.market_context) if opp.market_context else None,
        trade_plan=_safe_dict(opp.trade_plan) if opp.trade_plan else None,
        timestamp=opp.timestamp,
    )


@router.get("/signals", response_model=SignalSnapshotResponse)
async def get_signals(
    symbols: str = Query("BTC,ETH,SOL,BNB,XRP", description="Comma-separated symbols"),
    mode: str = Query("scalping", description="Trading mode: scalping, intraday, swing"),
):
    symbol_list = [item.strip().upper() for item in symbols.split(",") if item.strip()]
    settings = get_settings(mode)
    ranked = await scan_signals(symbol_list, settings)

    return SignalSnapshotResponse(
        signals=[_serialize_opportunity(item) for item in ranked],
        mode=mode,
        scanned=len(symbol_list),
        timestamp=_utc_now(),
    )


@router.get("/signals/{symbol}", response_model=OpportunityResponse)
async def get_signal(
    symbol: str,
    mode: str = Query("scalping", description="Trading mode: scalping, intraday, swing"),
):
    settings = get_settings(mode)
    ranked = await scan_signals([symbol.upper()], settings)
    if not ranked:
        raise HTTPException(status_code=404, detail="Signal unavailable")
    return _serialize_opportunity(ranked[0])


@router.get("/opportunities", response_model=ScannerResponse)
async def get_opportunities(
    symbols: str = Query("BTC,ETH,SOL,BNB,XRP", description="Comma-separated symbols"),
    mode: str = Query("scalping", description="Trading mode: scalping, intraday, swing"),
    top_n: int = Query(5, ge=1, le=5, description="Max opportunities to return"),
):
    symbol_list = [item.strip().upper() for item in symbols.split(",") if item.strip()]
    settings = get_settings(mode)
    settings.max_published_opportunities = top_n

    opportunities = await scan_opportunities(symbol_list, settings)
    serialized = [_serialize_opportunity(item) for item in opportunities[:top_n]]

    return ScannerResponse(
        opportunities=serialized,
        mode=mode,
        scanned=len(symbol_list),
        actionable=len(serialized),
        timestamp=_utc_now(),
    )


@router.get("/opportunities/{symbol}", response_model=DetailedSignalResponse)
async def get_symbol_detail(
    symbol: str,
    mode: str = Query("scalping", description="Trading mode"),
):
    settings = get_settings(mode)
    tf_config = {settings.primary_timeframe: 120}
    for tf in settings.confirmation_timeframes:
        tf_config[tf] = 60
    if settings.anchor_timeframe:
        tf_config.setdefault(settings.anchor_timeframe, 60)

    candles_by_tf = await fetch_multi_timeframe(symbol.upper(), tf_config)

    btc_closes = None
    if settings.btc_trend_filter and symbol.upper() != "BTC":
        try:
            closes, _, _ = await fetch_closes_and_volumes("BTC", "15m", 100)
            btc_closes = closes if len(closes) >= 20 else None
        except Exception:
            pass

    results, market_ctx, _, _ = compute_all_strategies(
        symbol.upper(),
        candles_by_tf,
        settings,
        btc_closes,
    )

    return DetailedSignalResponse(
        symbol=symbol.upper(),
        mode=mode,
        strategies=[_safe_dict(result) for result in results],
        market_context=_safe_dict(market_ctx),
        timestamp=_utc_now(),
    )
