"""Contextual indicator re-interpretation based on market regime.

Core insight: RSI > 70 in a RANGE = overbought (sell).
             RSI > 70 in a BREAKOUT = momentum (continuation).

This module takes raw indicator snapshots and adjusts their signal
values and descriptions according to the detected regime.
Never mutates the original — always returns new copies.
"""

from __future__ import annotations

from copy import copy
from typing import Callable

from app.core.models import IndicatorSnapshot, RegimeInfo


def reinterpret_indicators(
    indicators: list[IndicatorSnapshot],
    regime: RegimeInfo,
) -> list[IndicatorSnapshot]:
    """Return regime-adjusted copies of each indicator."""
    regime_name = regime.regime
    result: list[IndicatorSnapshot] = []

    for ind in indicators:
        handler = _HANDLERS.get(ind.name)
        if handler:
            result.append(handler(ind, regime_name))
        else:
            result.append(copy(ind))

    return result


# ═══════════════════════════════════════════════════════════════════
# Per-indicator reinterpretation
# ═══════════════════════════════════════════════════════════════════


def _reinterpret_rsi(ind: IndicatorSnapshot, regime: str) -> IndicatorSnapshot:
    rsi = ind.value
    new = copy(ind)

    if regime == "BREAKOUT":
        if rsi > 70:
            new.signal = 0.3
            new.description = f"RSI {rsi:.0f} — Elevated momentum (breakout), not overbought"
        elif rsi < 30:
            new.signal = -0.3
            new.description = f"RSI {rsi:.0f} — Weak momentum, possible failed breakout"
        else:
            new.signal = ind.signal * 0.5  # dampen in breakout
            new.description = f"RSI {rsi:.0f} — Neutral during breakout"

    elif regime == "TREND_UP":
        if rsi > 70:
            new.signal = 0.2
            new.description = f"RSI {rsi:.0f} — Strong momentum, normal for uptrend"
        elif rsi < 30:
            new.signal = 0.8
            new.description = f"RSI {rsi:.0f} — Deep pullback in uptrend, buy opportunity"
        elif rsi < 45:
            new.signal = 0.5
            new.description = f"RSI {rsi:.0f} — Pullback zone in uptrend"
        # else: keep original (neutral zone)

    elif regime == "TREND_DOWN":
        if rsi > 70:
            new.signal = -0.8
            new.description = f"RSI {rsi:.0f} — Bear rally exhaustion, sell signal"
        elif rsi < 30:
            new.signal = -0.2
            new.description = f"RSI {rsi:.0f} — Oversold but downtrend, risky buy"
        elif rsi > 55:
            new.signal = -0.5
            new.description = f"RSI {rsi:.0f} — Relief rally in downtrend"
        # else: keep original

    elif regime == "EXHAUSTION":
        if rsi > 70:
            new.signal = -0.4
            new.description = f"RSI {rsi:.0f} — Exhaustion zone, reversal warning"
        elif rsi < 30:
            new.signal = 0.4
            new.description = f"RSI {rsi:.0f} — Exhaustion zone, bounce opportunity"
        else:
            new.signal = ind.signal * 0.3  # low confidence in exhaustion
            new.description = f"RSI {rsi:.0f} — Low conviction during exhaustion"

    # RANGE: keep original interpretation (mean-reversion logic is correct)

    return new


def _reinterpret_bollinger(ind: IndicatorSnapshot, regime: str) -> IndicatorSnapshot:
    position = ind.value  # 0 = lower band, 1 = upper band
    new = copy(ind)

    if regime == "BREAKOUT":
        if position > 0.95:
            new.signal = 0.4
            new.description = "Above upper band — Breakout continuation"
        elif position < 0.05:
            new.signal = -0.4
            new.description = "Below lower band — Breakdown continuation"
        else:
            new.signal = ind.signal * 0.3
            new.description = "Inside bands during breakout — Neutral"

    elif regime == "TREND_UP":
        if position > 0.8:
            new.signal = 0.0
            new.description = "Near upper band — Normal in uptrend"
        elif position < 0.3:
            new.signal = 0.6
            new.description = "Pullback to lower band in uptrend — Buy zone"
        # else: keep original

    elif regime == "TREND_DOWN":
        if position < 0.2:
            new.signal = 0.0
            new.description = "Near lower band — Normal in downtrend"
        elif position > 0.7:
            new.signal = -0.6
            new.description = "Rally to upper band in downtrend — Sell zone"
        # else: keep original

    elif regime == "EXHAUSTION":
        if position > 0.9:
            new.signal = -0.6
            new.description = "Extreme upper band — Top signal"
        elif position < 0.1:
            new.signal = 0.6
            new.description = "Extreme lower band — Bottom signal"
        # else: keep original

    # RANGE: keep original (mean-reversion interpretation is correct)

    return new


def _reinterpret_macd(ind: IndicatorSnapshot, regime: str) -> IndicatorSnapshot:
    new = copy(ind)
    raw_signal = ind.signal

    if regime == "BREAKOUT":
        # Amplify MACD signals in breakout
        if raw_signal > 0:
            new.signal = min(raw_signal * 1.3, 1.0)
            new.description = "MACD bullish momentum — Breakout confirmation"
        elif raw_signal < 0:
            new.signal = max(raw_signal * 1.3, -1.0)
            new.description = "MACD bearish momentum — Breakdown confirmation"

    elif regime == "RANGE":
        # Dampen MACD in range (trends are weaker)
        new.signal = raw_signal * 0.5
        if raw_signal > 0:
            new.description = "MACD positive but range-bound — Weaker signal"
        elif raw_signal < 0:
            new.description = "MACD negative but range-bound — Weaker signal"

    elif regime == "TREND_UP":
        if raw_signal > 0:
            new.signal = min(raw_signal * 1.1, 1.0)
            new.description = "MACD bullish — Trend continuation"
        elif raw_signal < -0.5:
            new.signal = raw_signal * 0.7
            new.description = "MACD bearish in uptrend — Possible pullback, not reversal"

    elif regime == "TREND_DOWN":
        if raw_signal < 0:
            new.signal = max(raw_signal * 1.1, -1.0)
            new.description = "MACD bearish — Downtrend continuation"
        elif raw_signal > 0.5:
            new.signal = raw_signal * 0.7
            new.description = "MACD bullish in downtrend — Possible bounce, not reversal"

    elif regime == "EXHAUSTION":
        new.signal = raw_signal * 0.4
        new.description = "MACD weakened — Exhaustion phase, low conviction"

    return new


def _reinterpret_ema(ind: IndicatorSnapshot, regime: str) -> IndicatorSnapshot:
    new = copy(ind)
    raw_signal = ind.signal

    if regime == "BREAKOUT":
        # EMA crosses are strong during breakout
        if abs(raw_signal) >= 0.7:  # cross event
            new.signal = raw_signal * 1.2
            new.signal = max(-1.0, min(1.0, new.signal))
            new.description = f"EMA cross during breakout — Strong confirmation"
        else:
            new.signal = raw_signal * 0.8

    elif regime == "RANGE":
        # EMA crosses are noisy in range
        new.signal = raw_signal * 0.4
        new.description = "EMA signal dampened — Range-bound market"

    elif regime == "EXHAUSTION":
        new.signal = raw_signal * 0.5
        new.description = "EMA signal weakened — Exhaustion phase"

    # TREND_UP / TREND_DOWN: keep original (EMA signals are reliable in trends)

    return new


def _reinterpret_volume(ind: IndicatorSnapshot, regime: str) -> IndicatorSnapshot:
    new = copy(ind)

    if regime == "BREAKOUT":
        # Volume is critical for breakout confirmation
        if ind.value > 2.0:  # volume ratio > 2x
            new.signal = 0.6
            new.description = "High volume — Breakout confirmation"
            new.weight = 1.5  # boost weight in breakout
        elif ind.value > 1.5:
            new.signal = 0.4
            new.description = "Above average volume — Moderate breakout support"
        elif ind.value < 0.8:
            new.signal = -0.3
            new.description = "Low volume breakout — Fakeout risk"
            new.weight = 1.5

    elif regime == "EXHAUSTION":
        if ind.value > 2.5:
            new.signal = -0.2
            new.description = "Volume climax — Possible exhaustion blow-off"
        elif ind.value < 0.5:
            new.signal = -0.1
            new.description = "Volume fading — Exhaustion confirmation"

    elif regime == "RANGE":
        new.signal = ind.signal * 0.5
        new.description = "Volume neutral in range — Low significance"

    # TREND: keep original

    return new


# ═══════════════════════════════════════════════════════════════════
# Handler registry
# ═══════════════════════════════════════════════════════════════════

_HANDLERS: dict[str, Callable[[IndicatorSnapshot, str], IndicatorSnapshot]] = {
    "RSI": _reinterpret_rsi,
    "MACD": _reinterpret_macd,
    "Bollinger": _reinterpret_bollinger,
    "EMA Cross": _reinterpret_ema,
    "Volume": _reinterpret_volume,
}
