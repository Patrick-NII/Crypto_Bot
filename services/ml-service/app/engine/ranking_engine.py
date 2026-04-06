"""Ranking engine for contextual scanner signals.

This module evaluates symbols, calibrates them with contextual metadata,
and exposes either published opportunities or full scanner snapshots.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.core.models import RankedOpportunity, TradePlan
from app.engine.enhanced_scoring import compute_enhanced_scores
from app.engine.meta_ranker import (
    apply_breadth_bonus,
    build_notrade_reasons,
    build_scanner_context,
)
from app.engine.scenario_engine import select_primary_scenario
from app.engine.signal_engine import compute_signal
from app.services.data_fetcher import fetch_closes_and_volumes, fetch_multi_timeframe
from app.settings.user_settings import UserSignalSettings

logger = logging.getLogger(__name__)


def _build_tf_config(settings: UserSignalSettings) -> dict[str, int]:
    tf_config: dict[str, int] = {settings.primary_timeframe: 180}
    for tf in settings.confirmation_timeframes:
        tf_config[tf] = 90
    if settings.anchor_timeframe:
        tf_config.setdefault(settings.anchor_timeframe, 90)
    return tf_config


def _confirmation_candles(
    candles_by_tf: dict[str, list],
    settings: UserSignalSettings,
) -> list | None:
    preferred = list(reversed(settings.confirmation_timeframes))
    for tf in preferred:
        candles = candles_by_tf.get(tf)
        if candles:
            return candles
    for tf in settings.confirmation_timeframes:
        candles = candles_by_tf.get(tf)
        if candles:
            return candles
    return None


def _status_from_result(
    opportunity: RankedOpportunity,
    settings: UserSignalSettings,
) -> str:
    if not opportunity.notrade_reasons:
        return "high_conviction" if opportunity.confidence >= 0.75 else "actionable"
    if abs(opportunity.global_score) >= settings.min_watch_score or opportunity.regime_fit >= 60:
        return "watch"
    return "ignore"


def _build_trade_plan(
    opportunity: RankedOpportunity,
    settings: UserSignalSettings,
) -> TradePlan | None:
    strategy = opportunity.best_strategy
    if strategy is None:
        return None
    if opportunity.notrade_reasons:
        return None
    if not strategy.entry_price or not strategy.stop_loss or not strategy.take_profit:
        return None

    entry = strategy.entry_price
    sl = strategy.stop_loss
    tp = strategy.take_profit
    stop_dist = abs(entry - sl)
    rr = abs(tp - entry) / stop_dist if stop_dist > 0 else 0
    risk_usd = settings.capital_usd * settings.risk_per_trade_pct / 100
    pos_usd = (risk_usd / stop_dist * entry) if stop_dist > 0 else 0

    return TradePlan(
        side="buy" if strategy.action == "BUY" else "sell",
        entry=round(entry, 4),
        stop_loss=round(sl, 4),
        take_profit=round(tp, 4),
        risk_reward=round(rr, 2),
        position_size_usd=round(pos_usd, 2),
        risk_usd=round(risk_usd, 2),
    )


async def _fetch_btc_reference(settings: UserSignalSettings, symbols: list[str]) -> list[float] | None:
    try:
        closes, _, _ = await fetch_closes_and_volumes("BTC", "15m", 120)
        return closes if len(closes) >= 20 else None
    except Exception:
        return None


async def _evaluate_symbol(
    symbol: str,
    settings: UserSignalSettings,
    btc_closes: list[float] | None,
    now_iso: str,
    now_ms: int,
) -> RankedOpportunity | None:
    tf_config = _build_tf_config(settings)
    try:
        candles_by_tf = await fetch_multi_timeframe(symbol, tf_config)
        primary_candles = candles_by_tf.get(settings.primary_timeframe, [])
        if not primary_candles:
            return None

        best_result, market_ctx, regime_info, scenarios = compute_signal(
            symbol,
            candles_by_tf,
            settings,
            btc_closes,
        )

        primary_scenario = select_primary_scenario(scenarios)
        confirmation_candles = _confirmation_candles(candles_by_tf, settings)
        anchor_candles = candles_by_tf.get(settings.anchor_timeframe, [])

        enhanced = compute_enhanced_scores(
            best_result.indicators,
            best_result.score,
            market_context=market_ctx,
            regime=regime_info,
            scenario=primary_scenario,
        )
        context = build_scanner_context(
            result=best_result,
            market_context=market_ctx,
            regime=regime_info,
            scenario=primary_scenario,
            enhanced=enhanced,
            primary_candles=primary_candles,
            confirmation_candles=confirmation_candles,
            anchor_candles=anchor_candles,
            btc_closes=btc_closes,
            settings=settings,
            now_ms=now_ms,
        )
        notrade_reasons = build_notrade_reasons(context, enhanced, settings)

        opportunity = RankedOpportunity(
            rank=0,
            symbol=symbol.upper(),
            global_score=round(best_result.score, 3),
            confidence=round(best_result.confidence, 3),
            status="ignore",
            meta_score=context.meta_score,
            best_strategy=best_result,
            market_context=market_ctx,
            regime_info=regime_info,
            scenarios=scenarios,
            horizon=context.horizon,
            setup_type=context.setup_type,
            regime=context.regime,
            regime_fit=context.regime_fit,
            confirmation_score=context.confirmation_score,
            execution_risk=context.execution_risk,
            liquidity_score=context.liquidity_score,
            expected_holding_window=context.expected_holding_window,
            freshness_ms=context.freshness_ms,
            notrade_reasons=notrade_reasons,
            timestamp=now_iso,
        )
        opportunity.trade_plan = _build_trade_plan(opportunity, settings)
        opportunity.status = _status_from_result(opportunity, settings)
        return opportunity
    except Exception:
        logger.exception("Failed to scan %s", symbol)
        return None


def _apply_breadth(results: list[RankedOpportunity], settings: UserSignalSettings) -> None:
    directional = [r for r in results if abs(r.global_score) >= settings.min_watch_score]
    if not directional:
        return

    bullish_share = sum(1 for r in directional if r.global_score > 0) / len(directional)
    for opp in results:
        direction = 1 if opp.global_score > 0 else -1 if opp.global_score < 0 else 0
        opp.meta_score = apply_breadth_bonus(opp.meta_score, direction, bullish_share)


def _rank(results: list[RankedOpportunity]) -> list[RankedOpportunity]:
    results.sort(key=lambda o: (o.meta_score, abs(o.global_score), o.regime_fit), reverse=True)
    for index, opp in enumerate(results, start=1):
        opp.rank = index
    return results


async def scan_signals(
    symbols: list[str],
    settings: UserSignalSettings,
) -> list[RankedOpportunity]:
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    now_ms = int(now.timestamp() * 1000)
    btc_closes = await _fetch_btc_reference(settings, symbols)

    tasks = [
        _evaluate_symbol(symbol, settings, btc_closes, now_iso, now_ms)
        for symbol in symbols
    ]
    raw_results = await asyncio.gather(*tasks)
    results = [result for result in raw_results if result is not None]
    _apply_breadth(results, settings)
    return _rank(results)


async def scan_opportunities(
    symbols: list[str],
    settings: UserSignalSettings,
) -> list[RankedOpportunity]:
    results = await scan_signals(symbols, settings)
    published = [r for r in results if r.status in {"actionable", "high_conviction"}]
    _rank(published)
    return published[: settings.max_published_opportunities]
