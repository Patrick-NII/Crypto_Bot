"""MACD indicator — crossover detection and momentum.

Extracted from services/signal_engine.py — identical math.
"""

from __future__ import annotations

from app.core.models import IndicatorSnapshot
from app.indicators.math_utils import ema


def calc_macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> IndicatorSnapshot:
    """MACD: crossover signal. Default 12/26/9."""
    if len(closes) < slow + signal_period:
        return IndicatorSnapshot("MACD", 0, 0, "Insufficient data", category="momentum")

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = [a - b for a, b in zip(ema_fast, ema_slow)]
    signal_line = ema(macd_line, signal_period)

    macd_val = macd_line[-1]
    signal_val = signal_line[-1]
    histogram = macd_val - signal_val
    prev_histogram = macd_line[-2] - signal_line[-2]

    if histogram > 0 and prev_histogram <= 0:
        sig, desc = 0.8, "MACD bullish crossover — Buy signal"
    elif histogram < 0 and prev_histogram >= 0:
        sig, desc = -0.8, "MACD bearish crossover — Sell signal"
    elif histogram > 0:
        strength = min(abs(histogram) / (abs(macd_val) + 0.001), 1)
        sig, desc = round(0.4 * strength, 2), "MACD positive momentum"
    elif histogram < 0:
        strength = min(abs(histogram) / (abs(macd_val) + 0.001), 1)
        sig, desc = round(-0.4 * strength, 2), "MACD negative momentum"
    else:
        sig, desc = 0.0, "MACD neutral"

    return IndicatorSnapshot("MACD", round(histogram, 4), sig, desc, weight=1.3, category="momentum")


def macd_raw(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[float, float, float]:
    """Return (macd_line, signal_line, histogram) raw values."""
    if len(closes) < slow + signal_period:
        return 0.0, 0.0, 0.0
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = [a - b for a, b in zip(ema_fast, ema_slow)]
    signal_line = ema(macd_line, signal_period)
    return macd_line[-1], signal_line[-1], macd_line[-1] - signal_line[-1]
