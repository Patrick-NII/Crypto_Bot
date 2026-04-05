"""ATR (Average True Range) — volatility and stop-loss placement.

Ported from risk-service risk_calculator.py (Decimal -> float).
"""

from __future__ import annotations

from app.core.models import Candle, IndicatorSnapshot


def calc_atr(candles: list[Candle], period: int = 14) -> IndicatorSnapshot:
    """ATR as an IndicatorSnapshot. Higher ATR = more volatile."""
    atr_val = atr_raw(candles, period)
    if atr_val == 0:
        return IndicatorSnapshot("ATR", 0, 0, "Insufficient data", category="volatility")

    price = candles[-1].close if candles else 0
    pct = (atr_val / price * 100) if price > 0 else 0

    if pct > 3.0:
        signal, desc = -0.3, f"ATR {atr_val:.2f} ({pct:.1f}%) — High volatility, widen stops"
    elif pct > 1.5:
        signal, desc = 0.0, f"ATR {atr_val:.2f} ({pct:.1f}%) — Normal volatility"
    else:
        signal, desc = 0.1, f"ATR {atr_val:.2f} ({pct:.1f}%) — Low volatility, tight range"

    return IndicatorSnapshot("ATR", round(atr_val, 4), signal, desc, weight=0.5, category="volatility")


def atr_raw(candles: list[Candle], period: int = 14) -> float:
    """Return raw ATR value (float)."""
    if len(candles) < 2:
        return 0.0

    true_ranges: list[float] = []
    for i in range(1, len(candles)):
        high = candles[i].high
        low = candles[i].low
        prev_close = candles[i - 1].close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    recent = true_ranges[-period:]
    if not recent:
        return 0.0
    return sum(recent) / len(recent)
