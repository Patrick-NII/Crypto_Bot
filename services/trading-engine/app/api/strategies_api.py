"""Strategy management REST API.

Provides endpoints for listing available strategies, inspecting
parameters, and generating trading signals.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.strategies.base import BaseStrategy
from app.strategies.sma_crossover import SmaCrossoverStrategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


# ------------------------------------------------------------------
# Strategy registry
# ------------------------------------------------------------------

_STRATEGIES: Dict[str, BaseStrategy] = {}


def _init_strategies() -> None:
    """Instantiate all known strategies and register them."""
    if _STRATEGIES:
        return
    sma = SmaCrossoverStrategy()
    _STRATEGIES[sma.name] = sma


def _get_strategy(name: str) -> BaseStrategy:
    _init_strategies()
    strategy = _STRATEGIES.get(name)
    if strategy is None:
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    return strategy


# ------------------------------------------------------------------
# Request / response schemas
# ------------------------------------------------------------------


class StrategyInfo(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]


class SignalRequest(BaseModel):
    symbol: str
    market_data: Dict[str, Any]


class SignalResponse(BaseModel):
    strategy: str
    symbol: str
    action: str
    confidence: float
    reason: str


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("/", response_model=List[StrategyInfo])
async def list_strategies() -> List[StrategyInfo]:
    """Return all available strategies with their current parameters."""
    _init_strategies()
    result: List[StrategyInfo] = []
    for strategy in _STRATEGIES.values():
        params = await strategy.get_parameters()
        result.append(
            StrategyInfo(
                name=strategy.name,
                description=strategy.description,
                parameters=params,
            )
        )
    return result


@router.get("/{name}", response_model=StrategyInfo)
async def get_strategy_details(name: str) -> StrategyInfo:
    """Return details and parameters for a specific strategy."""
    strategy = _get_strategy(name)
    params = await strategy.get_parameters()
    return StrategyInfo(
        name=strategy.name,
        description=strategy.description,
        parameters=params,
    )


@router.post("/{name}/signal", response_model=SignalResponse)
async def generate_signal(name: str, request: SignalRequest) -> SignalResponse:
    """Generate a trading signal for the given symbol using the named strategy.

    ``market_data`` should contain the data the strategy expects.
    For the *sma_crossover* strategy this is ``{"prices": [float, ...]}``.
    """
    strategy = _get_strategy(name)
    try:
        signal = await strategy.generate_signal(request.symbol, request.market_data)
    except Exception as exc:
        logger.error("Strategy %s signal generation failed: %s", name, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return SignalResponse(
        strategy=name,
        symbol=request.symbol,
        action=signal.get("action", "hold"),
        confidence=signal.get("confidence", 0.0),
        reason=signal.get("reason", ""),
    )
