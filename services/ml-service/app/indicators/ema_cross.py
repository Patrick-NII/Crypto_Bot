"""EMA Cross indicator — short-term trend detection.

Extracted from services/signal_engine.py — identical math.
"""

from __future__ import annotations

from app.core.models import IndicatorSnapshot
from app.indicators.math_utils import ema


def calc_ema_cross(closes: list[float], fast: int = 9, slow: int = 21) -> IndicatorSnapshot:
    """EMA fast/slow crossover — trend signal."""
    if len(closes) < slow + 2:
        return IndicatorSnapshot("EMA Cross", 0, 0, "Insufficient data", category="trend")

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)

    current_diff = ema_fast[-1] - ema_slow[-1]
    prev_diff = ema_fast[-2] - ema_slow[-2]

    if current_diff > 0 and prev_diff <= 0:
        signal, desc = 0.7, f"EMA {fast}/{slow} golden cross — Bullish trend starting"
    elif current_diff < 0 and prev_diff >= 0:
        signal, desc = -0.7, f"EMA {fast}/{slow} death cross — Bearish trend starting"
    elif current_diff > 0:
        signal, desc = 0.3, f"EMA {fast} above EMA {slow} — Uptrend"
    elif current_diff < 0:
        signal, desc = -0.3, f"EMA {fast} below EMA {slow} — Downtrend"
    else:
        signal, desc = 0.0, "EMAs converging — Neutral"

    return IndicatorSnapshot("EMA Cross", round(current_diff, 4), signal, desc, weight=1.1, category="trend")
