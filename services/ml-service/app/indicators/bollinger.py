"""Bollinger Bands indicator.

Extracted from services/signal_engine.py — identical math.
"""

from __future__ import annotations

from app.core.models import IndicatorSnapshot
from app.indicators.math_utils import sma, std


def calc_bollinger(closes: list[float], period: int = 20, num_std: float = 2.0) -> IndicatorSnapshot:
    """Bollinger Bands: price position relative to bands."""
    if len(closes) < period:
        return IndicatorSnapshot("Bollinger", 0, 0, "Insufficient data", category="volatility")

    sma_vals = sma(closes, period)
    std_vals = std(closes, period)

    upper = sma_vals[-1] + num_std * std_vals[-1]
    lower = sma_vals[-1] - num_std * std_vals[-1]
    price = closes[-1]
    band_width = upper - lower

    if band_width == 0:
        return IndicatorSnapshot("Bollinger", 0, 0, "Zero bandwidth", category="volatility")

    position = (price - lower) / band_width

    if position < 0.05:
        signal, desc = 0.9, "Price below lower Bollinger Band — Strong buy"
    elif position < 0.2:
        signal, desc = 0.5, "Price near lower band — Buy zone"
    elif position < 0.4:
        signal, desc = 0.2, "Price in lower half — Slightly bullish"
    elif position < 0.6:
        signal, desc = 0.0, "Price at middle band — Neutral"
    elif position < 0.8:
        signal, desc = -0.2, "Price in upper half — Slightly bearish"
    elif position < 0.95:
        signal, desc = -0.5, "Price near upper band — Sell zone"
    else:
        signal, desc = -0.9, "Price above upper Bollinger Band — Strong sell"

    return IndicatorSnapshot("Bollinger", round(position, 2), signal, desc, weight=1.0, category="volatility")


def bollinger_raw(closes: list[float], period: int = 20, num_std: float = 2.0) -> tuple[float, float, float, float]:
    """Return (upper, middle, lower, bandwidth) raw values."""
    if len(closes) < period:
        return 0.0, 0.0, 0.0, 0.0
    sma_vals = sma(closes, period)
    std_vals = std(closes, period)
    middle = sma_vals[-1]
    upper = middle + num_std * std_vals[-1]
    lower = middle - num_std * std_vals[-1]
    bandwidth = (upper - lower) / middle if middle > 0 else 0.0
    return upper, middle, lower, bandwidth
