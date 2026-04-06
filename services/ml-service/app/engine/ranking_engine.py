"""Ranking Engine — multi-asset scanning, scoring, and prioritization.

Scans N symbols, computes signals, ranks by score, filters by thresholds.
Returns only top opportunities.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.core.models import (
    Candle, MarketContext, RankedOpportunity, RegimeInfo, Scenario, StrategyResult, TradePlan,
    MODE_TIMEFRAMES,
)
from app.engine.signal_engine import compute_signal
from app.services.data_fetcher import fetch_candles, fetch_closes_and_volumes, fetch_multi_timeframe
from app.settings.user_settings import UserSignalSettings

logger = logging.getLogger(__name__)


async def scan_opportunities(
    symbols: list[str],
    settings: UserSignalSettings,
) -> list[RankedOpportunity]:
    """Scan multiple symbols and return ranked opportunities.

    1. Fetch BTC closes for trend filter (if enabled)
    2. For each symbol, fetch multi-TF candles + compute signal
    3. Rank by absolute score
    4. Filter by score thresholds
    5. Return top_n
    """
    now = datetime.now(timezone.utc).isoformat()

    # BTC trend data (shared across all symbols)
    btc_closes: list[float] | None = None
    if settings.btc_trend_filter and "BTC" not in [s.upper() for s in symbols]:
        try:
            closes, _, _ = await fetch_closes_and_volumes("BTC", "15m", 100)
            btc_closes = closes if len(closes) >= 20 else None
        except Exception:
            pass

    # Build TF config from settings
    primary_tf = settings.primary_timeframe
    conf_tfs = settings.confirmation_timeframes
    tf_config: dict[str, int] = {primary_tf: 120}
    for tf in conf_tfs:
        tf_config[tf] = 60

    # Fetch and compute for each symbol in parallel
    async def _process_symbol(symbol: str) -> RankedOpportunity | None:
        try:
            candles_by_tf = await fetch_multi_timeframe(symbol, tf_config)
            best_result, market_ctx, regime_info, scenarios = compute_signal(
                symbol, candles_by_tf, settings, btc_closes,
            )

            abs_score = abs(best_result.score)

            # Classify status
            if abs_score >= settings.min_actionable_score:
                status = "actionable"
            elif abs_score >= settings.min_watch_score:
                status = "watch"
            else:
                status = "ignore"

            # Build trade plan if actionable and entry/sl/tp available
            trade_plan: TradePlan | None = None
            if status == "actionable" and best_result.entry_price and best_result.stop_loss and best_result.take_profit:
                entry = best_result.entry_price
                sl = best_result.stop_loss
                tp = best_result.take_profit
                stop_dist = abs(entry - sl)
                rr = abs(tp - entry) / stop_dist if stop_dist > 0 else 0
                risk_usd = settings.capital_usd * settings.risk_per_trade_pct / 100
                pos_usd = (risk_usd / stop_dist * entry) if stop_dist > 0 else 0

                trade_plan = TradePlan(
                    side="buy" if best_result.action == "BUY" else "sell",
                    entry=round(entry, 4),
                    stop_loss=round(sl, 4),
                    take_profit=round(tp, 4),
                    risk_reward=round(rr, 2),
                    position_size_usd=round(pos_usd, 2),
                    risk_usd=round(risk_usd, 2),
                )

            opp = RankedOpportunity(
                rank=0,  # assigned after sorting
                symbol=symbol.upper(),
                global_score=round(best_result.score, 3),
                confidence=best_result.confidence,
                status=status,
                best_strategy=best_result,
                market_context=market_ctx,
                trade_plan=trade_plan,
                timestamp=now,
            )
            # Attach regime + scenarios as private attrs for the scanner API
            opp._regime_info = regime_info  # type: ignore[attr-defined]
            opp._scenarios = scenarios  # type: ignore[attr-defined]
            return opp
        except Exception:
            logger.exception("Failed to scan %s", symbol)
            return None

    tasks = [_process_symbol(s) for s in symbols]
    raw_results = await asyncio.gather(*tasks)

    # Filter None and ignored
    opportunities = [r for r in raw_results if r is not None and r.status != "ignore"]

    # Sort by absolute score descending
    opportunities.sort(key=lambda o: abs(o.global_score), reverse=True)

    # Assign ranks and limit to top_n
    for i, opp in enumerate(opportunities):
        opp.rank = i + 1

    top_n = settings.top_n_opportunities
    return opportunities[:top_n]
