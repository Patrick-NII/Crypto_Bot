"""RSI (Relative Strength Index) indicator.

Extracted from services/signal_engine.py — identical math.
"""

from __future__ import annotations

from app.core.models import IndicatorSnapshot


def calc_rsi(closes: list[float], period: int = 14) -> IndicatorSnapshot:
    """RSI: <30 oversold (buy), >70 overbought (sell)."""
    if len(closes) < period + 1:
        return IndicatorSnapshot("RSI", 50, 0, "Insufficient data", category="momentum")

    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    if rsi < 20:
        signal, desc = 1.0, f"RSI {rsi:.0f} — Extreme oversold, strong buy signal"
    elif rsi < 30:
        signal, desc = 0.7, f"RSI {rsi:.0f} — Oversold zone, buy signal"
    elif rsi < 45:
        signal, desc = 0.3, f"RSI {rsi:.0f} — Approaching oversold"
    elif rsi < 55:
        signal, desc = 0.0, f"RSI {rsi:.0f} — Neutral zone"
    elif rsi < 70:
        signal, desc = -0.3, f"RSI {rsi:.0f} — Approaching overbought"
    elif rsi < 80:
        signal, desc = -0.7, f"RSI {rsi:.0f} — Overbought zone, sell signal"
    else:
        signal, desc = -1.0, f"RSI {rsi:.0f} — Extreme overbought, strong sell signal"

    return IndicatorSnapshot("RSI", round(rsi, 1), signal, desc, weight=1.2, category="momentum")


def rsi_raw(closes: list[float], period: int = 14) -> float:
    """Return raw RSI value without wrapping in IndicatorSnapshot."""
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
