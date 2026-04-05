"""Strategy management REST API.

Provides endpoints for listing available strategies, updating parameters,
and generating signals directly from live market data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import settings
from app.strategies import STRATEGIES
from app.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])

_STRATEGIES: Dict[str, BaseStrategy] = {}
_CREATED_AT: Dict[str, str] = {}
_HTTP = httpx.AsyncClient(timeout=15.0)


def _init_strategies() -> None:
    """Instantiate all known strategies and register them."""
    if _STRATEGIES:
        return

    now = datetime.now(timezone.utc).isoformat()
    for name, strategy_cls in STRATEGIES.items():
        _STRATEGIES[name] = strategy_cls()
        _CREATED_AT[name] = now


def _get_strategy(name: str) -> BaseStrategy:
    _init_strategies()
    strategy = _STRATEGIES.get(name)
    if strategy is None:
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    return strategy


async def _fetch_history(symbol: str, interval: str, limit: int) -> List[dict[str, Any]]:
    url = f"{settings.MARKET_DATA_SERVICE_URL}/api/v1/prices/history/{symbol.upper()}"
    try:
        resp = await _HTTP.get(url, params={"interval": interval, "limit": limit})
        resp.raise_for_status()
        payload = resp.json()
        candles = payload.get("data", payload)
        if isinstance(candles, list):
            return candles
    except Exception as exc:
        logger.warning("Failed to fetch strategy history for %s: %s", symbol, exc)
    return []


async def _fetch_current_price(symbol: str) -> Decimal | None:
    url = f"{settings.MARKET_DATA_SERVICE_URL}/api/v1/prices/{symbol.upper()}"
    try:
        resp = await _HTTP.get(url)
        resp.raise_for_status()
        payload = resp.json()
        price_data = payload.get("data", payload)
        price = price_data.get("price") or price_data.get("current_price") or price_data.get("last")
        if price is not None:
            return Decimal(str(price))
    except Exception as exc:
        logger.warning("Failed to fetch current price for strategy %s: %s", symbol, exc)
    return None


async def _build_market_data(symbol: str, interval: str, limit: int) -> Dict[str, Any]:
    candles = await _fetch_history(symbol, interval=interval, limit=limit)
    closes = [Decimal(str(candle.get("close", 0))) for candle in candles if candle.get("close") is not None]
    highs = [Decimal(str(candle.get("high", 0))) for candle in candles if candle.get("high") is not None]
    lows = [Decimal(str(candle.get("low", 0))) for candle in candles if candle.get("low") is not None]
    volumes = [Decimal(str(candle.get("volume", 0))) for candle in candles if candle.get("volume") is not None]

    current_price = closes[-1] if closes else await _fetch_current_price(symbol)
    if current_price is None:
      raise HTTPException(status_code=502, detail=f"Unable to load market data for {symbol.upper()}")

    return {
        "symbol": symbol.upper(),
        "current_price": current_price,
        "prices": [float(value) for value in closes],
        "closes": closes,
        "highs": highs,
        "lows": lows,
        "volumes": volumes,
        "candles": candles,
        "interval": interval,
        "lookback": limit,
    }


async def _signal_payload(strategy_name: str, signal: Dict[str, Any], symbol: str) -> "SignalResponse":
    return SignalResponse(
        strategy_id=strategy_name,
        symbol=symbol.upper(),
        action=str(signal.get("action", "hold")),
        confidence=float(signal.get("confidence", 0.0)),
        reason=str(signal.get("reason", "")),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


class StrategyPerformance(BaseModel):
    total_trades: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0


class StrategyInfo(BaseModel):
    id: str
    name: str
    description: str
    status: str = "active"
    parameters: Dict[str, Any]
    performance: StrategyPerformance | None = None
    created_at: str


class SignalRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    interval: str = Field(default="1h")
    lookback: int = Field(default=120, ge=30, le=1000)


class StrategyUpdateRequest(BaseModel):
    parameters: Dict[str, Any]


class SignalResponse(BaseModel):
    strategy_id: str
    symbol: str
    action: str
    confidence: float
    reason: str
    timestamp: str


class EnsembleSignalResponse(BaseModel):
    symbol: str
    interval: str
    lookback: int
    consensus_action: str
    consensus_confidence: float
    top_signal: SignalResponse | None = None
    signals: List[SignalResponse]


async def _strategy_info(strategy_name: str, strategy: BaseStrategy) -> StrategyInfo:
    params = await strategy.get_parameters()
    return StrategyInfo(
        id=strategy_name,
        name=strategy.name,
        description=strategy.description,
        status="active",
        parameters=params,
        performance=None,
        created_at=_CREATED_AT.get(strategy_name, datetime.now(timezone.utc).isoformat()),
    )


@router.get("/", response_model=List[StrategyInfo])
async def list_strategies() -> List[StrategyInfo]:
    """Return all available strategies with their current parameters."""
    _init_strategies()
    return [await _strategy_info(name, strategy) for name, strategy in _STRATEGIES.items()]


@router.get("/{name}", response_model=StrategyInfo)
async def get_strategy_details(name: str) -> StrategyInfo:
    """Return details and parameters for a specific strategy."""
    strategy = _get_strategy(name)
    return await _strategy_info(name, strategy)


@router.patch("/{name}", response_model=StrategyInfo)
async def update_strategy(name: str, request: StrategyUpdateRequest) -> StrategyInfo:
    """Update parameters for a specific strategy."""
    strategy = _get_strategy(name)
    try:
        await strategy.set_parameters(request.parameters)
    except Exception as exc:
        logger.error("Strategy %s parameter update failed: %s", name, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    return await _strategy_info(name, strategy)


@router.post("/{name}/signal", response_model=SignalResponse)
async def generate_signal(name: str, request: SignalRequest) -> SignalResponse:
    """Generate a trading signal using live market data for the requested symbol."""
    strategy = _get_strategy(name)
    market_data = await _build_market_data(
        request.symbol,
        interval=request.interval,
        limit=request.lookback,
    )
    try:
        signal = await strategy.generate_signal(request.symbol, market_data)
    except Exception as exc:
        logger.error("Strategy %s signal generation failed: %s", name, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return await _signal_payload(name, signal, request.symbol)


@router.get("/ensemble/{symbol}", response_model=EnsembleSignalResponse)
async def generate_ensemble_signal(
    symbol: str,
    interval: str = Query("1h", description="Candlestick interval"),
    lookback: int = Query(120, ge=30, le=1000, description="Number of candles"),
) -> EnsembleSignalResponse:
    """Run all registered strategies on the same symbol and build a consensus."""
    _init_strategies()
    market_data = await _build_market_data(symbol, interval=interval, limit=lookback)

    signal_rows: List[SignalResponse] = []
    weighted_sum = Decimal("0")
    weight_total = Decimal("0")
    top_signal: SignalResponse | None = None

    for strategy_name, strategy in _STRATEGIES.items():
        try:
            raw_signal = await strategy.generate_signal(symbol, market_data)
        except Exception as exc:
            logger.warning("Strategy %s failed during ensemble run: %s", strategy_name, exc)
            continue

        signal = await _signal_payload(strategy_name, raw_signal, symbol)
        signal_rows.append(signal)

        confidence = Decimal(str(max(signal.confidence, 0.0)))
        action = signal.action.lower()
        direction = Decimal("0")
        if action == "buy":
            direction = Decimal("1")
        elif action == "sell":
            direction = Decimal("-1")

        weighted_sum += direction * confidence
        weight_total += max(confidence, Decimal("0.25"))

        if top_signal is None or signal.confidence > top_signal.confidence:
            top_signal = signal

    consensus_score = float(weighted_sum / weight_total) if weight_total > 0 else 0.0
    if consensus_score > 0.2:
        consensus_action = "buy"
    elif consensus_score < -0.2:
        consensus_action = "sell"
    else:
        consensus_action = "hold"

    return EnsembleSignalResponse(
        symbol=symbol.upper(),
        interval=interval,
        lookback=lookback,
        consensus_action=consensus_action,
        consensus_confidence=round(min(abs(consensus_score), 1.0), 4),
        top_signal=top_signal,
        signals=signal_rows,
    )
