"""VWAP (Volume Weighted Average Price) — institutional fair-value reference.

New indicator for scalping context.
"""

from __future__ import annotations

from app.core.models import Candle, IndicatorSnapshot


def calc_vwap(candles: list[Candle]) -> IndicatorSnapshot:
    """VWAP: price above = bullish bias, below = bearish bias."""
    vwap_val = vwap_raw(candles)
    if vwap_val == 0:
        return IndicatorSnapshot("VWAP", 0, 0, "Insufficient data", category="trend")

    price = candles[-1].close
    deviation_pct = (price - vwap_val) / vwap_val * 100

    if deviation_pct > 1.0:
        signal, desc = 0.3, f"Price {deviation_pct:.2f}% above VWAP — Bullish bias"
    elif deviation_pct > 0.2:
        signal, desc = 0.15, f"Price slightly above VWAP — Mild bullish"
    elif deviation_pct < -1.0:
        signal, desc = -0.3, f"Price {abs(deviation_pct):.2f}% below VWAP — Bearish bias"
    elif deviation_pct < -0.2:
        signal, desc = -0.15, f"Price slightly below VWAP — Mild bearish"
    else:
        signal, desc = 0.0, f"Price at VWAP — Neutral"

    return IndicatorSnapshot("VWAP", round(vwap_val, 4), signal, desc, weight=0.7, category="trend")


def vwap_raw(candles: list[Candle]) -> float:
    """Return raw VWAP value. Cumulative typical_price * volume / cumulative volume."""
    if not candles:
        return 0.0

    cum_tp_vol = 0.0
    cum_vol = 0.0
    for c in candles:
        tp = (c.high + c.low + c.close) / 3
        cum_tp_vol += tp * c.volume
        cum_vol += c.volume

    return cum_tp_vol / cum_vol if cum_vol > 0 else 0.0
