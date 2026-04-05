"""Volume profile indicator.

Extracted from services/signal_engine.py — identical math.
"""

from __future__ import annotations

from app.core.models import IndicatorSnapshot


def calc_volume_profile(volumes: list[float], period: int = 20) -> IndicatorSnapshot:
    """Volume analysis: above-average volume confirms trends."""
    if len(volumes) < period:
        return IndicatorSnapshot("Volume", 0, 0, "Insufficient data", category="volume")

    avg_vol = sum(volumes[-period:]) / period
    current_vol = volumes[-1]
    ratio = current_vol / avg_vol if avg_vol > 0 else 1.0

    if ratio > 2.5:
        signal, desc = 0.4, f"Volume {ratio:.1f}x average — Exceptional activity"
    elif ratio > 1.5:
        signal, desc = 0.2, f"Volume {ratio:.1f}x average — Above normal"
    elif ratio < 0.5:
        signal, desc = -0.1, f"Volume {ratio:.1f}x average — Low activity"
    else:
        signal, desc = 0.0, f"Volume {ratio:.1f}x average — Normal"

    return IndicatorSnapshot("Volume", round(ratio, 2), signal, desc, weight=0.6, category="volume")


def volume_ratio(volumes: list[float], period: int = 20) -> float:
    """Return raw volume ratio (current / average)."""
    if len(volumes) < period:
        return 1.0
    avg = sum(volumes[-period:]) / period
    return volumes[-1] / avg if avg > 0 else 1.0
