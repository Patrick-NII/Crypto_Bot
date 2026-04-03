from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.models.risk import (
    PortfolioRiskMetrics,
    RiskEvaluationResult,
    RiskProfile,
    StopLossRecommendation,
    TakeProfitLevel,
    TakeProfitRecommendation,
    TradeEvaluation,
)
from app.services.risk_calculator import RiskCalculator
from app.services.risk_monitor import RiskMonitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])

# In-memory custom profile (would be per-user in production with DB backing)
_custom_profile: Optional[RiskProfile] = None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _resolve_profile(preset: Optional[str] = None) -> RiskProfile:
    """Return a RiskProfile based on preset name or custom override."""
    if preset == "conservative":
        return RiskProfile.conservative()
    if preset == "aggressive":
        return RiskProfile.aggressive()
    if preset == "moderate":
        return RiskProfile.moderate()
    if _custom_profile is not None:
        return _custom_profile
    return RiskProfile.moderate()


async def _fetch_ohlc(symbol: str, limit: int = 30) -> List[Dict[str, Any]]:
    """Fetch recent OHLC data from the market-data service.

    Falls back to empty list on failure so callers can degrade gracefully.
    """
    url = f"{settings.MARKET_DATA_SERVICE_URL}/api/v1/market/ohlc/{symbol}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"limit": limit})
            resp.raise_for_status()
            data = resp.json()
            # The market-data service may wrap candles in a "data" key
            candles = data if isinstance(data, list) else data.get("data", data.get("candles", []))
            return candles
    except Exception as exc:
        logger.warning("Failed to fetch OHLC for %s: %s", symbol, exc)
        return []


async def _fetch_current_price(symbol: str) -> Optional[Decimal]:
    """Fetch current price from market-data service."""
    url = f"{settings.MARKET_DATA_SERVICE_URL}/api/v1/market/price/{symbol}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            price = data.get("price", data.get("last", data.get("data", {}).get("price")))
            if price is not None:
                return Decimal(str(price))
    except Exception as exc:
        logger.warning("Failed to fetch price for %s: %s", symbol, exc)
    return None


# ------------------------------------------------------------------
# GET /profile
# ------------------------------------------------------------------

@router.get("/profile", response_model=RiskProfile)
async def get_risk_profile(
    preset: Optional[str] = Query(
        None,
        description="Profile preset: conservative, moderate, aggressive.  "
        "Omit to use the custom profile (or moderate default).",
    ),
) -> RiskProfile:
    """Return the active risk profile."""
    return _resolve_profile(preset)


# ------------------------------------------------------------------
# PUT /profile
# ------------------------------------------------------------------

@router.put("/profile", response_model=RiskProfile)
async def update_risk_profile(profile: RiskProfile) -> RiskProfile:
    """Update the custom risk profile."""
    global _custom_profile
    _custom_profile = profile
    logger.info("Custom risk profile updated: %s", profile.dict())
    return _custom_profile


# ------------------------------------------------------------------
# POST /evaluate  (MAIN ENDPOINT used by trading engine)
# ------------------------------------------------------------------

@router.post("/evaluate", response_model=RiskEvaluationResult)
async def evaluate_trade(
    trade: TradeEvaluation,
    preset: Optional[str] = Query(None),
) -> RiskEvaluationResult:
    """Evaluate a proposed trade against the active risk rules.

    This is the primary endpoint consumed by the trading engine before
    placing an order.
    """
    profile = _resolve_profile(preset)

    portfolio_value = trade.portfolio_value or Decimal("0")
    current_positions: List[Dict[str, Any]] = trade.current_positions or []
    daily_trade_count = 0  # TODO: track via Redis in production

    result = RiskCalculator.evaluate_trade(
        trade=trade.dict(),
        profile=profile.dict(),
        portfolio_value=portfolio_value,
        current_positions=current_positions,
        daily_trade_count=daily_trade_count,
    )

    return RiskEvaluationResult(**result)


# ------------------------------------------------------------------
# GET /metrics
# ------------------------------------------------------------------

@router.get("/metrics", response_model=PortfolioRiskMetrics)
async def get_risk_metrics(
    portfolio_value: Decimal = Query(Decimal("0"), description="Total portfolio value"),
    positions: Optional[str] = Query(
        None,
        description="JSON-encoded list of position objects "
        '(e.g. [{"symbol":"BTC","quantity":"0.5","current_price":"60000"}])',
    ),
    preset: Optional[str] = Query(None),
) -> PortfolioRiskMetrics:
    """Return portfolio-level risk metrics.

    Accepts portfolio positions as a JSON query param and computes VaR,
    drawdown, volatility, Sharpe, and concentration risk.
    """
    profile = _resolve_profile(preset)

    pos_list: List[Dict[str, Any]] = []
    if positions:
        try:
            pos_list = json.loads(positions)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="positions must be valid JSON",
            )

    # Build a price map from positions (use current_price if available)
    prices: Dict[str, Decimal] = {}
    for pos in pos_list:
        sym = pos.get("symbol", "").upper()
        cp = pos.get("current_price", pos.get("price"))
        if sym and cp is not None:
            prices[sym] = Decimal(str(cp))

    # Try to fetch live prices for any symbols missing from the map
    for pos in pos_list:
        sym = pos.get("symbol", "").upper()
        if sym and sym not in prices:
            live = await _fetch_current_price(sym)
            if live is not None:
                prices[sym] = live

    metrics = await RiskMonitor.get_portfolio_metrics(
        positions=pos_list,
        prices=prices,
        profile=profile,
    )

    return metrics


# ------------------------------------------------------------------
# GET /stop-loss/{symbol}
# ------------------------------------------------------------------

@router.get("/stop-loss/{symbol}", response_model=StopLossRecommendation)
async def get_stop_loss(
    symbol: str,
    method: str = Query("atr", description="Stop-loss method: atr or percentage"),
    multiplier: Decimal = Query(Decimal("2.0"), description="ATR multiplier"),
    period: int = Query(14, ge=2, le=100, description="ATR look-back period"),
    pct: Decimal = Query(
        Decimal("5.0"),
        description="Percentage for percentage-based stop-loss",
    ),
) -> StopLossRecommendation:
    """Calculate recommended stop-loss for a symbol.

    Fetches price data from the market-data service and computes
    either an ATR-based or simple percentage-based stop-loss.
    """
    # Fetch current price
    current_price = await _fetch_current_price(symbol)
    if current_price is None:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to fetch current price for {symbol}",
        )

    if method == "atr":
        candles = await _fetch_ohlc(symbol, limit=period + 5)
        if len(candles) < 2:
            raise HTTPException(
                status_code=502,
                detail=f"Insufficient OHLC data for {symbol} (got {len(candles)} candles)",
            )

        # Normalise candle keys to lower-case
        normalised: List[Dict[str, Decimal]] = []
        for c in candles:
            normalised.append(
                {
                    "high": Decimal(str(c.get("high", c.get("High", 0)))),
                    "low": Decimal(str(c.get("low", c.get("Low", 0)))),
                    "close": Decimal(str(c.get("close", c.get("Close", 0)))),
                }
            )

        stop_price = RiskCalculator.calculate_stop_loss_atr(
            prices=normalised,
            multiplier=multiplier,
            period=period,
        )
        atr_value = RiskCalculator.calculate_atr(normalised, period=period)
        sl_pct = (
            ((current_price - stop_price) / current_price * Decimal("100"))
            if current_price > 0
            else Decimal("0")
        )
        return StopLossRecommendation(
            symbol=symbol.upper(),
            current_price=current_price,
            stop_loss_price=stop_price,
            stop_loss_pct=sl_pct.quantize(Decimal("0.01")),
            method="atr",
            atr_value=atr_value,
        )
    else:
        # Percentage-based
        stop_price = current_price * (Decimal("1") - pct / Decimal("100"))
        stop_price = max(stop_price, Decimal("0"))
        return StopLossRecommendation(
            symbol=symbol.upper(),
            current_price=current_price,
            stop_loss_price=stop_price.quantize(Decimal("0.00000001")),
            stop_loss_pct=pct,
            method="percentage",
            atr_value=None,
        )


# ------------------------------------------------------------------
# GET /take-profit/{symbol}
# ------------------------------------------------------------------

@router.get("/take-profit/{symbol}", response_model=TakeProfitRecommendation)
async def get_take_profit(
    symbol: str,
    side: str = Query("buy", description="Trade side: buy or sell"),
    entry_price: Optional[Decimal] = Query(
        None, description="Entry price (fetched from market if omitted)"
    ),
    target_pct: Decimal = Query(
        Decimal("15.0"),
        description="Total take-profit target percentage",
    ),
) -> TakeProfitRecommendation:
    """Calculate multi-level take-profit targets for a symbol."""
    if side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side must be 'buy' or 'sell'")

    price = entry_price
    if price is None:
        price = await _fetch_current_price(symbol)
    if price is None:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to determine entry price for {symbol}",
        )

    level_dicts = RiskCalculator.calculate_take_profit_levels(
        entry_price=price,
        side=side,
        total_target_pct=target_pct,
    )

    levels = [TakeProfitLevel(**ld) for ld in level_dicts]

    return TakeProfitRecommendation(
        symbol=symbol.upper(),
        entry_price=price,
        side=side,
        levels=levels,
    )
