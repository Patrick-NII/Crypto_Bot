from __future__ import annotations

import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

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
from app.services.redis_client import (
    get_daily_trade_count,
    increment_daily_trade_count,
)
from app.services.risk_calculator import RiskCalculator
from app.services.risk_monitor import RiskMonitor

logger = logging.getLogger(__name__)
_Q2 = Decimal("0.01")
_Q4 = Decimal("0.0001")
STABLES = {"USDT", "USDC", "BUSD", "FDUSD", "DAI", "TUSD", "USD", "EUR"}

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _profile_from_preset(preset: Optional[str] = None) -> RiskProfile:
    """Return a built-in profile for a preset name."""
    if preset == "conservative":
        return RiskProfile.conservative()
    if preset == "aggressive":
        return RiskProfile.aggressive()
    if preset == "custom":
        return RiskProfile(profile_id="custom")
    return RiskProfile.moderate()


async def _fetch_authenticated_risk_profile(
    auth_header: Optional[str],
) -> Optional[RiskProfile]:
    """Resolve the user risk profile from auth-service when a token is present."""
    if not auth_header:
        return None

    url = f"{settings.AUTH_SERVICE_URL}/api/v1/auth/me"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"Authorization": auth_header})
            if resp.status_code == 401:
                logger.warning("Auth token rejected while resolving risk profile")
                return None
            resp.raise_for_status()
            data = resp.json()
            return _profile_from_preset(str(data.get("risk_profile", "moderate")))
    except Exception as exc:
        logger.warning("Failed to resolve authenticated risk profile: %s", exc)
        return None


async def _persist_authenticated_risk_profile(
    auth_header: Optional[str],
    preset: str,
) -> RiskProfile:
    """Persist a built-in profile selection to auth-service."""
    if preset not in {"conservative", "moderate", "aggressive"}:
        raise HTTPException(status_code=400, detail="Unknown risk preset")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization required")

    url = f"{settings.AUTH_SERVICE_URL}/api/v1/auth/me"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.put(
                url,
                headers={"Authorization": auth_header},
                json={"risk_profile": preset},
            )
            if resp.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid token")
            resp.raise_for_status()
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to persist authenticated risk profile: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Unable to persist risk profile to auth service",
        )

    return _profile_from_preset(preset)


async def _resolve_profile(request: Request, preset: Optional[str] = None) -> RiskProfile:
    """Resolve the active profile from explicit preset or authenticated user."""
    if preset:
        return _profile_from_preset(preset)

    auth_header = request.headers.get("Authorization")
    authenticated = await _fetch_authenticated_risk_profile(auth_header)
    if authenticated is not None:
        return authenticated
    return RiskProfile.moderate()


async def _fetch_ohlc(symbol: str, limit: int = 30) -> List[Dict[str, Any]]:
    """Fetch recent OHLC data from the market-data service.

    Falls back to empty list on failure so callers can degrade gracefully.
    """
    url = f"{settings.MARKET_DATA_SERVICE_URL}/api/v1/prices/history/{symbol}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"limit": limit, "interval": "1d"})
            resp.raise_for_status()
            data = resp.json()
            candles = data if isinstance(data, list) else data.get("data", [])
            return candles
    except Exception as exc:
        logger.warning("Failed to fetch OHLC for %s: %s", symbol, exc)
        return []


async def _fetch_current_price(symbol: str) -> Optional[Decimal]:
    """Fetch current price from market-data service."""
    url = f"{settings.MARKET_DATA_SERVICE_URL}/api/v1/prices/{symbol}"
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


async def _fetch_trading_balances(
    auth_header: Optional[str] = None,
) -> Dict[str, Decimal]:
    """Fetch current balances from the trading-engine."""
    url = f"{settings.TRADING_ENGINE_URL}/api/v1/orders/balance"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": auth_header} if auth_header else {}
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            raw = resp.json()
            return {
                symbol.upper(): Decimal(str(amount))
                for symbol, amount in raw.items()
                if Decimal(str(amount)) > 0
            }
    except Exception as exc:
        logger.warning("Failed to fetch balances from trading-engine: %s", exc)
        return {}


def _normalise_positions(pos_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalise incoming position payloads into risk-service shape."""
    normalised: List[Dict[str, Any]] = []
    for pos in pos_list:
        symbol = str(pos.get("symbol", "")).upper()
        if not symbol:
            continue
        quantity = Decimal(str(pos.get("quantity", 0)))
        if quantity <= 0:
            continue
        current_price = Decimal(
            str(pos.get("current_price", pos.get("price", "0")))
        )
        entry_price = Decimal(
            str(pos.get("entry_price", pos.get("avg_entry_price", current_price)))
        )
        normalised.append(
            {
                "symbol": symbol,
                "quantity": quantity,
                "current_price": current_price,
                "entry_price": entry_price,
            }
        )
    return normalised


async def _build_positions_from_balances(
    auth_header: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Build synthetic positions from balances when the caller sends none."""
    balances = await _fetch_trading_balances(auth_header)
    positions: List[Dict[str, Any]] = []
    for symbol, quantity in balances.items():
        if symbol in STABLES:
            current_price = Decimal("1")
        else:
            current_price = await _fetch_current_price(symbol)
            if current_price is None:
                continue
        positions.append(
            {
                "symbol": symbol,
                "quantity": quantity,
                "current_price": current_price,
                "entry_price": current_price,
            }
        )
    return positions


def _candles_to_returns(candles: List[Dict[str, Any]]) -> List[Decimal]:
    closes: List[Decimal] = []
    for candle in candles:
        close = candle.get("close", candle.get("Close"))
        if close is None:
            continue
        closes.append(Decimal(str(close)))

    returns: List[Decimal] = []
    for idx in range(1, len(closes)):
        previous = closes[idx - 1]
        current = closes[idx]
        if previous <= 0:
            continue
        returns.append(
            ((current - previous) / previous).quantize(_Q4, rounding=ROUND_HALF_UP)
        )
    return returns


def _combine_weighted_returns(
    positions: List[Dict[str, Any]],
    prices: Dict[str, Decimal],
    asset_returns: Dict[str, List[Decimal]],
) -> List[Decimal]:
    if not positions or not asset_returns:
        return [Decimal("0")] * max(settings.VAR_LOOKBACK_DAYS, 2)

    total_value = sum(
        Decimal(str(pos.get("quantity", 0))) * prices.get(pos["symbol"], Decimal("0"))
        for pos in positions
    )
    if total_value <= 0:
        return [Decimal("0")] * max(settings.VAR_LOOKBACK_DAYS, 2)

    weighted_assets = []
    min_len: Optional[int] = None
    for pos in positions:
        symbol = pos["symbol"]
        series = asset_returns.get(symbol)
        if not series:
            continue
        value = Decimal(str(pos.get("quantity", 0))) * prices.get(symbol, Decimal("0"))
        weight = value / total_value if total_value > 0 else Decimal("0")
        weighted_assets.append((weight, series))
        min_len = len(series) if min_len is None else min(min_len, len(series))

    if not weighted_assets or min_len is None or min_len == 0:
        return [Decimal("0")] * max(settings.VAR_LOOKBACK_DAYS, 2)

    combined: List[Decimal] = []
    for idx in range(min_len):
        combined.append(
            sum(
                weight * series[len(series) - min_len + idx]
                for weight, series in weighted_assets
            ).quantize(_Q4, rounding=ROUND_HALF_UP)
        )
    return combined


def _build_equity_curve(
    positions: List[Dict[str, Any]],
    prices: Dict[str, Decimal],
    asset_candles: Dict[str, List[Dict[str, Any]]],
) -> List[Decimal]:
    if not positions:
        return []

    stable_value = Decimal("0")
    dynamic_assets: List[tuple[Decimal, List[Decimal]]] = []
    min_len: Optional[int] = None

    for pos in positions:
        symbol = pos["symbol"]
        quantity = Decimal(str(pos.get("quantity", 0)))
        if symbol in STABLES:
            stable_value += quantity * prices.get(symbol, Decimal("1"))
            continue

        candles = asset_candles.get(symbol, [])
        closes = [
            Decimal(str(candle.get("close", candle.get("Close"))))
            for candle in candles
            if candle.get("close", candle.get("Close")) is not None
        ]
        if len(closes) < 2:
            continue
        dynamic_assets.append((quantity, closes))
        min_len = len(closes) if min_len is None else min(min_len, len(closes))

    if min_len is None or min_len == 0:
        return [stable_value] if stable_value > 0 else []

    curve: List[Decimal] = []
    for idx in range(min_len):
        total = stable_value
        for quantity, closes in dynamic_assets:
            total += quantity * closes[len(closes) - min_len + idx]
        curve.append(total.quantize(_Q2, rounding=ROUND_HALF_UP))
    return curve


# ------------------------------------------------------------------
# GET /profile
# ------------------------------------------------------------------

@router.get("/profile", response_model=RiskProfile)
async def get_risk_profile(
    request: Request,
    preset: Optional[str] = Query(
        None,
        description="Profile preset: conservative, moderate, aggressive.  "
        "Omit to resolve from the authenticated user or moderate default.",
    ),
) -> RiskProfile:
    """Return the active risk profile."""
    return await _resolve_profile(request, preset)


# ------------------------------------------------------------------
# PUT /profile
# ------------------------------------------------------------------

@router.put("/profile", response_model=RiskProfile)
async def update_risk_profile(request: Request, profile: RiskProfile) -> RiskProfile:
    """Persist a built-in risk profile for the authenticated user."""
    if profile.profile_id not in {"conservative", "moderate", "aggressive"}:
        raise HTTPException(
            status_code=400,
            detail="Only built-in presets are currently supported",
        )
    result = await _persist_authenticated_risk_profile(
        request.headers.get("Authorization"),
        profile.profile_id,
    )
    logger.info("Risk profile updated via /profile: %s", profile.profile_id)
    return result


@router.put("/profile/preset/{preset}", response_model=RiskProfile)
async def set_risk_profile_preset(request: Request, preset: str) -> RiskProfile:
    """Activate one of the built-in risk presets."""
    profile = await _persist_authenticated_risk_profile(
        request.headers.get("Authorization"),
        preset,
    )
    logger.info("Risk profile preset activated: %s", preset)
    return profile


# ------------------------------------------------------------------
# POST /evaluate  (MAIN ENDPOINT used by trading engine)
# ------------------------------------------------------------------

@router.post("/evaluate", response_model=RiskEvaluationResult)
async def evaluate_trade(
    request: Request,
    trade: TradeEvaluation,
    preset: Optional[str] = Query(None),
) -> RiskEvaluationResult:
    """Evaluate a proposed trade against the active risk rules.

    This is the primary endpoint consumed by the trading engine before
    placing an order.
    """
    profile = await _resolve_profile(request, preset)

    portfolio_value = trade.portfolio_value or Decimal("0")
    current_positions: List[Dict[str, Any]] = trade.current_positions or []
    daily_trade_count = await get_daily_trade_count(trade.user_id or "")

    result = RiskCalculator.evaluate_trade(
        trade=trade.dict(),
        profile=profile.dict(),
        portfolio_value=portfolio_value,
        current_positions=current_positions,
        daily_trade_count=daily_trade_count,
    )

    # If approved, increment the counter immediately so concurrent calls
    # see the right number. Idempotency lives in the trading-engine via
    # client_order_id, so a duplicate retry won't double-count anyway.
    if result.get("approved"):
        try:
            await increment_daily_trade_count(trade.user_id or "")
        except Exception:
            pass

    return RiskEvaluationResult(**result)


# ------------------------------------------------------------------
# GET /metrics
# ------------------------------------------------------------------

@router.get("/metrics", response_model=PortfolioRiskMetrics)
async def get_risk_metrics(
    request: Request,
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
    profile = await _resolve_profile(request, preset)

    pos_list: List[Dict[str, Any]] = []
    if positions:
        try:
            pos_list = _normalise_positions(json.loads(positions))
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="positions must be valid JSON",
            )
    else:
        pos_list = await _build_positions_from_balances(
            request.headers.get("Authorization")
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

    if not pos_list:
        return await RiskMonitor.get_portfolio_metrics(
            positions=[],
            prices={},
            profile=profile,
        )

    asset_candles: Dict[str, List[Dict[str, Any]]] = {}
    asset_returns: Dict[str, List[Decimal]] = {}
    for pos in pos_list:
        symbol = pos.get("symbol", "").upper()
        if not symbol or symbol in STABLES:
            continue
        candles = await _fetch_ohlc(symbol, limit=settings.VAR_LOOKBACK_DAYS + 5)
        if not candles:
            continue
        asset_candles[symbol] = candles
        returns = _candles_to_returns(candles)
        if returns:
            asset_returns[symbol] = returns

    historical_returns = _combine_weighted_returns(pos_list, prices, asset_returns)
    equity_curve = _build_equity_curve(pos_list, prices, asset_candles)

    metrics = await RiskMonitor.get_portfolio_metrics(
        positions=pos_list,
        prices=prices,
        profile=profile,
        historical_returns=historical_returns,
        equity_curve=equity_curve,
        asset_returns=asset_returns,
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
