"""Evolved Signal Engine — multi-timeframe, mode-aware, contextual.

Pipeline:
  candles → regime_detector → contextual_interpreter → scenario_engine
         → strategy selection (regime-boosted) → enhanced_scoring → decision

Orchestrates strategies based on trading mode, fetches multi-TF data,
and produces a composite StrategyResult per symbol with full context.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.models import (
    Candle, MarketContext, RegimeInfo, Scenario, StrategyResult, TradePlan, MODE_TIMEFRAMES,
)
from app.engine.market_context import build_market_context
from app.engine.regime_detector import detect_regime
from app.engine.contextual_interpreter import reinterpret_indicators
from app.engine.scenario_engine import generate_scenarios, select_primary_scenario
from app.strategies import MODE_STRATEGIES
from app.settings.user_settings import UserSignalSettings

logger = logging.getLogger(__name__)

# Regime-aware strategy boost factors
_REGIME_STRATEGY_BOOST: dict[str, dict[str, float]] = {
    "BREAKOUT": {"breakout": 1.2, "momentum_burst": 1.1},
    "RANGE": {"micro_pullback": 1.2},
    "TREND_UP": {"momentum_burst": 1.1, "micro_pullback": 1.1},
    "TREND_DOWN": {"momentum_burst": 1.1},
    "EXHAUSTION": {"micro_pullback": 1.1},
}


def compute_signal(
    symbol: str,
    candles_by_tf: dict[str, list[Candle]],
    settings: UserSignalSettings,
    btc_closes: list[float] | None = None,
) -> tuple[StrategyResult, MarketContext, RegimeInfo, list[Scenario]]:
    """Run the full contextual signal pipeline for a symbol.

    Returns:
        (best_strategy_result, market_context, regime_info, scenarios)
    """
    mode = settings.trading_mode
    primary_tf = settings.primary_timeframe
    conf_tfs = settings.confirmation_timeframes

    primary_candles = candles_by_tf.get(primary_tf, [])
    empty_regime = RegimeInfo(regime="RANGE", confidence=0.0)

    if not primary_candles:
        return _empty_result(symbol, settings), MarketContext(regime="no_data"), empty_regime, []

    # Pick first available confirmation TF
    confirmation_candles: list[Candle] | None = None
    for tf in conf_tfs:
        if tf in candles_by_tf and candles_by_tf[tf]:
            confirmation_candles = candles_by_tf[tf]
            break

    # ── 1. Market context + advanced regime detection ──
    market_ctx, regime_info = build_market_context(primary_candles, btc_closes)

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
        ), market_ctx, regime_info, []

    # ── 2. Run all strategies ──
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
        return _empty_result(symbol, settings), market_ctx, regime_info, []

    # ── 3. Regime-boosted strategy selection ──
    boost_map = _REGIME_STRATEGY_BOOST.get(regime_info.regime, {})
    best = max(
        results,
        key=lambda r: abs(r.score) * boost_map.get(r.strategy_name, 1.0),
    )

    # ── 4. Contextual indicator re-interpretation ──
    reinterpreted = reinterpret_indicators(best.indicators, regime_info)

    # ── 5. Scenario generation ──
    scenarios = generate_scenarios(regime_info, reinterpreted, primary_candles, confirmation_candles)

    # ── 6. Multi-TF regime filter ──
    if confirmation_candles and len(confirmation_candles) >= 30:
        higher_regime = detect_regime(confirmation_candles)
        scenarios = _apply_multi_tf_filter(regime_info, higher_regime, scenarios)

    # ── 7. Build final result with reinterpreted indicators ──
    best_final = StrategyResult(
        strategy_name=best.strategy_name,
        strategy_type=best.strategy_type,
        action=best.action,
        confidence=best.confidence,
        score=best.score,
        timeframe=best.timeframe,
        indicators=reinterpreted,
        reasoning=best.reasoning,
        entry_price=best.entry_price,
        stop_loss=best.stop_loss,
        take_profit=best.take_profit,
    )

    # Compute trade plan if actionable
    if best.entry_price and best.stop_loss and best.take_profit:
        risk_usd = settings.capital_usd * settings.risk_per_trade_pct / 100
        entry = best.entry_price
        sl = best.stop_loss
        stop_dist = abs(entry - sl)
        pos_size = risk_usd / stop_dist if stop_dist > 0 else 0
        pos_usd = pos_size * entry
        rr = abs(best.take_profit - entry) / stop_dist if stop_dist > 0 else 0

    return best_final, market_ctx, regime_info, scenarios


def compute_all_strategies(
    symbol: str,
    candles_by_tf: dict[str, list[Candle]],
    settings: UserSignalSettings,
    btc_closes: list[float] | None = None,
) -> tuple[list[StrategyResult], MarketContext, RegimeInfo, list[Scenario]]:
    """Run ALL enabled strategies and return all results (for detail view)."""
    mode = settings.trading_mode
    primary_tf = settings.primary_timeframe
    conf_tfs = settings.confirmation_timeframes

    primary_candles = candles_by_tf.get(primary_tf, [])
    empty_regime = RegimeInfo(regime="RANGE", confidence=0.0)

    if not primary_candles:
        return [], MarketContext(regime="no_data"), empty_regime, []

    confirmation_candles: list[Candle] | None = None
    for tf in conf_tfs:
        if tf in candles_by_tf and candles_by_tf[tf]:
            confirmation_candles = candles_by_tf[tf]
            break

    market_ctx, regime_info = build_market_context(primary_candles, btc_closes)

    strategy_classes = MODE_STRATEGIES.get(mode, {})
    enabled = settings.enabled_strategies

    results: list[StrategyResult] = []
    for name, cls in strategy_classes.items():
        if enabled and name not in enabled:
            continue
        try:
            strategy = cls()
            result = strategy.generate(symbol, primary_candles, confirmation_candles, settings)
            # Re-interpret indicators per regime
            result_ctx = StrategyResult(
                strategy_name=result.strategy_name,
                strategy_type=result.strategy_type,
                action=result.action,
                confidence=result.confidence,
                score=result.score,
                timeframe=result.timeframe,
                indicators=reinterpret_indicators(result.indicators, regime_info),
                reasoning=result.reasoning,
                entry_price=result.entry_price,
                stop_loss=result.stop_loss,
                take_profit=result.take_profit,
            )
            results.append(result_ctx)
        except Exception:
            logger.exception("Strategy %s failed for %s", name, symbol)

    scenarios = generate_scenarios(
        regime_info,
        results[0].indicators if results else [],
        primary_candles,
        confirmation_candles,
    )

    return results, market_ctx, regime_info, scenarios


def _apply_multi_tf_filter(
    primary_regime: RegimeInfo,
    higher_regime: RegimeInfo,
    scenarios: list[Scenario],
) -> list[Scenario]:
    """Adjust scenario probabilities based on higher-TF regime alignment."""
    if not scenarios:
        return scenarios

    adjusted: list[Scenario] = []
    for s in scenarios:
        prob = s.probability

        # Higher TF confirms primary → boost
        if primary_regime.regime == higher_regime.regime:
            prob = min(prob * 1.15, 1.0)

        # Primary = BREAKOUT but higher TF = RANGE → reduce (resistance overhead)
        elif primary_regime.regime == "BREAKOUT" and higher_regime.regime in ("RANGE", "EXHAUSTION"):
            prob *= 0.70

        # Primary = TREND but higher TF = EXHAUSTION → dampen continuation
        elif primary_regime.regime in ("TREND_UP", "TREND_DOWN") and higher_regime.regime == "EXHAUSTION":
            if s.name == "CONTINUATION":
                prob *= 0.75

        # Counter-regime → general dampening
        elif (primary_regime.regime == "TREND_UP" and higher_regime.regime == "TREND_DOWN") or \
             (primary_regime.regime == "TREND_DOWN" and higher_regime.regime == "TREND_UP"):
            prob *= 0.60

        adjusted.append(Scenario(
            name=s.name,
            direction=s.direction,
            probability=round(prob, 3),
            reasoning=s.reasoning,
            conditions_met=s.conditions_met,
            conditions_unmet=s.conditions_unmet,
            weight_profile=s.weight_profile,
        ))

    adjusted.sort(key=lambda s: s.probability, reverse=True)
    return adjusted


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
