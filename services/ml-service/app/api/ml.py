"""ML Service API — trading signals and market regime analysis."""

from __future__ import annotations

from datetime import datetime, timezone
import math

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.config import settings
from app.services.signal_engine import generate_signal

router = APIRouter(prefix="/api/v1/ml", tags=["ml"])

CG_BASE = "https://api.coingecko.com/api/v3"

# CoinGecko fallback mapping for symbols not available from the market service.
SYM_TO_CG = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
    "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin", "AVAX": "avalanche-2",
    "DOT": "polkadot", "LINK": "chainlink", "UNI": "uniswap", "ATOM": "cosmos",
    "LTC": "litecoin", "NEAR": "near", "APT": "aptos", "ARB": "arbitrum",
    "OP": "optimism", "FIL": "filecoin", "AAVE": "aave", "SHIB": "shiba-inu",
    "MATIC": "matic-network", "TRX": "tron", "TON": "the-open-network",
    "SUI": "sui", "SEI": "sei-network", "PEPE": "pepe", "ALGO": "algorand",
    "FTM": "fantom", "XLM": "stellar", "HBAR": "hedera-hashgraph",
}


class SubScoreItem(BaseModel):
    category: str
    score: int
    label: str


class SignalResponse(BaseModel):
    symbol: str
    action: str
    confidence: float
    score: float
    reasoning: str
    indicators: list[dict]
    timestamp: str
    price: float | None = None
    regime: str | None = None
    source: str = "market-data-service"
    # Enhanced scoring V2
    score_100: int | None = None
    action_label: str | None = None
    confidence_level: str | None = None
    status: str | None = None
    sub_scores: list[SubScoreItem] | None = None
    key_reasons: list[str] | None = None
    # V3 multi-dimensional
    direction: int | None = None
    direction_label: str | None = None
    confidence_score: int | None = None
    risk: int | None = None
    setup_quality: int | None = None
    actionability: str | None = None
    market_regime: str | None = None
    signal_context: str | None = None
    contradictions: list[dict] | None = None
    signal_trade_plan: dict | None = None


class MultiSignalResponse(BaseModel):
    signals: list[SignalResponse]
    timestamp: str
    source: str = "market-data-service"


class StrategyPerformance(BaseModel):
    strategy_name: str
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    period_days: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _classify_regime(closes: list[float]) -> str:
    if len(closes) < 20:
        return "insufficient_data"

    latest = closes[-1]
    old = closes[-20]
    if old <= 0 or latest <= 0:
        return "unknown"

    returns = []
    for index in range(1, len(closes)):
        previous = closes[index - 1]
        current = closes[index]
        if previous > 0:
            returns.append((current - previous) / previous)

    window = returns[-20:] if len(returns) >= 20 else returns
    volatility = math.sqrt(sum(r * r for r in window) / len(window)) if window else 0.0
    trend = (latest - old) / old

    if abs(trend) >= 0.08 and volatility < 0.04:
        return "trend_up" if trend > 0 else "trend_down"
    if volatility >= 0.05:
        return "high_volatility"
    return "range"


async def _fetch_market_history(symbol: str, interval: str = "1h", limit: int = 120) -> tuple[list[float], list[float], str]:
    url = f"{settings.MARKET_DATA_SERVICE_URL}/api/v1/prices/history/{symbol.upper()}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params={"interval": interval, "limit": limit})
            resp.raise_for_status()
            payload = resp.json()
            candles = payload.get("data", payload)
            closes = [float(candle["close"]) for candle in candles if candle.get("close") is not None]
            volumes = [float(candle.get("volume", 0)) for candle in candles]
            if closes:
                return closes, volumes, "market-data-service"
    except Exception:
        pass

    cg_id = SYM_TO_CG.get(symbol.upper())
    if not cg_id:
        return [], [], "unavailable"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{CG_BASE}/coins/{cg_id}/market_chart",
                params={"vs_currency": "usd", "days": "30", "interval": "hourly"},
            )
            if resp.status_code == 200:
                payload = resp.json()
                prices = [float(row[1]) for row in payload.get("prices", [])]
                volumes = [float(row[1]) for row in payload.get("total_volumes", [])]
                return prices[-limit:], volumes[-limit:], "coingecko"
    except Exception:
        pass

    return [], [], "unavailable"


async def _fetch_top_symbols(limit: int = 10) -> list[str]:
    url = f"{settings.MARKET_DATA_SERVICE_URL}/api/v1/markets/top"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"limit": limit})
            resp.raise_for_status()
            payload = resp.json()
            rows = payload.get("data", payload)
            symbols = [str(row.get("symbol", "")).upper() for row in rows if row.get("symbol")]
            if symbols:
                return symbols[:limit]
    except Exception:
        pass

    return list(SYM_TO_CG.keys())[:limit]


async def _compute_signal(symbol: str, interval: str = "1h", lookback: int = 120) -> SignalResponse:
    closes, volumes, source = await _fetch_market_history(symbol, interval=interval, limit=lookback)
    if len(closes) < 15:
        return SignalResponse(
            symbol=symbol.upper(),
            action="HOLD",
            confidence=0.0,
            score=0.0,
            reasoning="Insufficient data",
            indicators=[],
            timestamp=_utc_now(),
            price=closes[-1] if closes else None,
            regime="insufficient_data",
            source=source,
        )

    signal = generate_signal(symbol.upper(), closes, volumes if len(volumes) >= len(closes) else None)

    # Enhanced scoring
    from app.engine.enhanced_scoring import compute_enhanced_scores
    enhanced = compute_enhanced_scores(signal.indicators, signal.score)

    return SignalResponse(
        symbol=signal.symbol,
        action=signal.action.value,
        confidence=signal.confidence,
        score=signal.score,
        reasoning=signal.reasoning,
        indicators=[
            {"name": item.name, "value": item.value, "signal": item.signal, "description": item.description}
            for item in signal.indicators
        ],
        timestamp=_utc_now(),
        price=closes[-1],
        regime=_classify_regime(closes),
        source=source,
        score_100=enhanced.score_100,
        action_label=enhanced.label,
        confidence_level=enhanced.confidence_level,
        status=enhanced.actionability.lower(),
        sub_scores=[
            SubScoreItem(category=ss.category, score=ss.score, label=ss.label)
            for ss in enhanced.sub_scores
        ],
        key_reasons=enhanced.key_reasons,
        direction=enhanced.direction,
        direction_label=enhanced.direction_label,
        confidence_score=enhanced.confidence,
        risk=enhanced.risk,
        setup_quality=enhanced.setup_quality,
        actionability=enhanced.actionability,
        market_regime=enhanced.market_regime,
        signal_context=enhanced.signal_context,
        contradictions=[
            {"description": c.description, "severity": c.severity}
            for c in enhanced.contradictions
        ],
        signal_trade_plan={
            "side": enhanced.trade_plan.side,
            "entry_zone": enhanced.trade_plan.entry_zone,
            "invalidation_zone": enhanced.trade_plan.invalidation_zone,
            "target_zone": enhanced.trade_plan.target_zone,
            "risk_reward": enhanced.trade_plan.risk_reward,
            "validity": enhanced.trade_plan.validity,
            "execution_style": enhanced.trade_plan.execution_style,
        } if enhanced.trade_plan else None,
    )


@router.get("/signals/{symbol}", response_model=SignalResponse)
async def get_signal(
    symbol: str,
    interval: str = Query("1h", description="Candlestick interval"),
    lookback: int = Query(120, ge=30, le=500, description="Number of candles"),
    mode: str | None = Query(None, description="Trading mode: scalping, intraday, swing (optional, uses legacy path if omitted)"),
):
    """Get a trading signal for a single symbol from the unified market feed.

    Without `mode`: legacy behavior (backward-compatible).
    With `mode`: uses the new multi-TF signal engine.
    """
    if mode and mode in ("scalping", "intraday", "swing"):
        # New path: use evolved signal engine
        from app.services.data_fetcher import fetch_multi_timeframe, fetch_closes_and_volumes
        from app.engine.signal_engine import compute_signal as engine_compute
        from app.engine.market_context import build_market_context
        from app.settings.user_settings import get_settings
        from dataclasses import asdict

        settings = get_settings(mode)
        tf_config = {settings.primary_timeframe: lookback}
        for tf in settings.confirmation_timeframes:
            tf_config[tf] = min(lookback, 60)

        candles_by_tf = await fetch_multi_timeframe(symbol.upper(), tf_config)
        btc_closes = None
        if settings.btc_trend_filter and symbol.upper() != "BTC":
            try:
                c, _, _ = await fetch_closes_and_volumes("BTC", "15m", 100)
                btc_closes = c if len(c) >= 20 else None
            except Exception:
                pass

        result, ctx = engine_compute(symbol.upper(), candles_by_tf, settings, btc_closes)
        primary_candles = candles_by_tf.get(settings.primary_timeframe, [])
        price = primary_candles[-1].close if primary_candles else None

        return SignalResponse(
            symbol=symbol.upper(),
            action=result.action,
            confidence=result.confidence,
            score=result.score,
            reasoning=result.reasoning,
            indicators=[
                {"name": i.name, "value": i.value, "signal": i.signal, "description": i.description}
                for i in result.indicators
            ],
            timestamp=_utc_now(),
            price=price,
            regime=ctx.regime,
            source="signal-engine-v2",
        )

    # Legacy path: unchanged behavior
    return await _compute_signal(symbol.upper(), interval=interval, lookback=lookback)


@router.get("/signals", response_model=MultiSignalResponse)
async def get_all_signals(
    symbols: str | None = Query(None, description="Comma-separated symbols"),
    limit: int = Query(10, ge=1, le=50, description="How many symbols to analyze"),
    interval: str = Query("1h", description="Candlestick interval"),
    lookback: int = Query(120, ge=30, le=500, description="Number of candles"),
):
    """Get trading signals for a dynamic symbol universe."""
    universe = (
        [item.strip().upper() for item in symbols.split(",") if item.strip()]
        if symbols
        else await _fetch_top_symbols(limit=limit)
    )
    universe = universe[:limit]

    results = []
    for symbol in universe:
        results.append(await _compute_signal(symbol, interval=interval, lookback=lookback))

    return MultiSignalResponse(
        signals=results,
        timestamp=_utc_now(),
        source=results[0].source if results else "market-data-service",
    )


@router.get("/performance", response_model=list[StrategyPerformance])
async def get_strategy_performance():
    """Performance registry placeholder.

    No fabricated metrics are returned until a real backtest/performance registry exists.
    """
    return []
