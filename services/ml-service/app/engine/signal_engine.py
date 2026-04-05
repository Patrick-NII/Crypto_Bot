"""Evolved Signal Engine — multi-timeframe, mode-aware, configurable.

Orchestrates strategies based on trading mode, fetches multi-TF data,
and produces a composite StrategyResult per symbol.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.models import (
    Candle, MarketContext, StrategyResult, TradePlan, MODE_TIMEFRAMES,
)
from app.engine.market_context import build_market_context
from app.strategies import MODE_STRATEGIES
from app.settings.user_settings import UserSignalSettings

logger = logging.getLogger(__name__)


def compute_signal(
    symbol: str,
    candles_by_tf: dict[str, list[Candle]],
    settings: UserSignalSettings,
    btc_closes: list[float] | None = None,
) -> tuple[StrategyResult, MarketContext]:
    """Run all enabled strategies for a given mode and return the best result.

    Args:
        symbol: e.g. "ETH"
        candles_by_tf: {"1m": [...], "5m": [...], "15m": [...]}
        settings: user's signal settings
        btc_closes: optional BTC closes for trend filter

    Returns:
        (best_strategy_result, market_context)
    """
    mode = settings.trading_mode
    primary_tf = settings.primary_timeframe
    conf_tfs = settings.confirmation_timeframes

    primary_candles = candles_by_tf.get(primary_tf, [])
    if not primary_candles:
        return _empty_result(symbol, settings), MarketContext(regime="no_data")

    # Pick first available confirmation TF
    confirmation_candles: list[Candle] | None = None
    for tf in conf_tfs:
        if tf in candles_by_tf and candles_by_tf[tf]:
            confirmation_candles = candles_by_tf[tf]
            break

    # Market context from primary candles
    market_ctx = build_market_context(primary_candles, btc_closes)

    # BTC trend filter: skip if bearish and filter enabled
    if settings.btc_trend_filter and market_ctx.btc_trend == "bearish":
        return StrategyResult(
            strategy_name="btc_filter",
            strategy_type=mode,
            action="HOLD",
            confidence=0.0,
            score=0.0,
            timeframe=primary_tf,
            reasoning="BTC trend bearish — filtered by btc_trend_filter",
        ), market_ctx

    # Get strategies for current mode
    strategy_classes = MODE_STRATEGIES.get(mode, {})
    enabled = settings.enabled_strategies

    results: list[StrategyResult] = []
    for name, cls in strategy_classes.items():
        if enabled and name not in enabled:
            continue
        try:
            strategy = cls()
            result = strategy.generate(symbol, primary_candles, confirmation_candles, settings)
            results.append(result)
        except Exception:
            logger.exception("Strategy %s failed for %s", name, symbol)

    if not results:
        return _empty_result(symbol, settings), market_ctx

    # Select best strategy by absolute score
    best = max(results, key=lambda r: abs(r.score))

    # Compute trade plan if actionable
    if best.entry_price and best.stop_loss and best.take_profit:
        risk_usd = settings.capital_usd * settings.risk_per_trade_pct / 100
        entry = best.entry_price
        sl = best.stop_loss
        stop_dist = abs(entry - sl)
        pos_size = risk_usd / stop_dist if stop_dist > 0 else 0
        pos_usd = pos_size * entry
        rr = abs(best.take_profit - entry) / stop_dist if stop_dist > 0 else 0

        best_with_plan = StrategyResult(
            strategy_name=best.strategy_name,
            strategy_type=best.strategy_type,
            action=best.action,
            confidence=best.confidence,
            score=best.score,
            timeframe=best.timeframe,
            indicators=best.indicators,
            reasoning=best.reasoning,
            entry_price=best.entry_price,
            stop_loss=best.stop_loss,
            take_profit=best.take_profit,
        )
        trade_plan = TradePlan(
            side="buy" if best.action == "BUY" else "sell",
            entry=entry,
            stop_loss=sl,
            take_profit=best.take_profit,
            risk_reward=round(rr, 2),
            position_size_usd=round(pos_usd, 2),
            risk_usd=round(risk_usd, 2),
        )
        return best_with_plan, market_ctx

    return best, market_ctx


def compute_all_strategies(
    symbol: str,
    candles_by_tf: dict[str, list[Candle]],
    settings: UserSignalSettings,
    btc_closes: list[float] | None = None,
) -> tuple[list[StrategyResult], MarketContext]:
    """Run ALL enabled strategies and return all results (for detail view)."""
    mode = settings.trading_mode
    primary_tf = settings.primary_timeframe
    conf_tfs = settings.confirmation_timeframes

    primary_candles = candles_by_tf.get(primary_tf, [])
    if not primary_candles:
        return [], MarketContext(regime="no_data")

    confirmation_candles: list[Candle] | None = None
    for tf in conf_tfs:
        if tf in candles_by_tf and candles_by_tf[tf]:
            confirmation_candles = candles_by_tf[tf]
            break

    market_ctx = build_market_context(primary_candles, btc_closes)

    strategy_classes = MODE_STRATEGIES.get(mode, {})
    enabled = settings.enabled_strategies

    results: list[StrategyResult] = []
    for name, cls in strategy_classes.items():
        if enabled and name not in enabled:
            continue
        try:
            strategy = cls()
            result = strategy.generate(symbol, primary_candles, confirmation_candles, settings)
            results.append(result)
        except Exception:
            logger.exception("Strategy %s failed for %s", name, symbol)

    return results, market_ctx


def _empty_result(symbol: str, settings: UserSignalSettings) -> StrategyResult:
    return StrategyResult(
        strategy_name="none",
        strategy_type=settings.trading_mode,
        action="HOLD",
        confidence=0.0,
        score=0.0,
        timeframe=settings.primary_timeframe,
        reasoning="No data available",
    )
