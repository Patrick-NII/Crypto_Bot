"""Market context — regime detection, BTC trend filter, volatility analysis.

Extracted from api/ml.py _classify_regime(), enriched with BTC filter and volatility percentile.
"""

from __future__ import annotations

import logging
import math

from app.core.models import Candle, MarketContext, RegimeInfo
from app.engine.regime_detector import detect_regime
from app.indicators.atr import atr_raw
from app.indicators.volume import volume_ratio

logger = logging.getLogger(__name__)


def classify_regime(closes: list[float]) -> str:
    """Classify market regime from closing prices. Same logic as original ml.py."""
    if len(closes) < 20:
        return "insufficient_data"

    latest = closes[-1]
    old = closes[-20]
    if old <= 0 or latest <= 0:
        return "unknown"

    returns = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        cur = closes[i]
        if prev > 0:
            returns.append((cur - prev) / prev)

    window = returns[-20:] if len(returns) >= 20 else returns
    volatility = math.sqrt(sum(r * r for r in window) / len(window)) if window else 0.0
    trend = (latest - old) / old

    if abs(trend) >= 0.08 and volatility < 0.04:
        return "trend_up" if trend > 0 else "trend_down"
    if volatility >= 0.05:
        return "high_volatility"
    return "range"


def classify_btc_trend(btc_closes: list[float]) -> str:
    """Simple BTC trend: bullish if 20-period return > +2%, bearish if < -2%."""
    if len(btc_closes) < 20:
        return "neutral"
    change = (btc_closes[-1] - btc_closes[-20]) / btc_closes[-20]
    if change > 0.02:
        return "bullish"
    if change < -0.02:
        return "bearish"
    return "neutral"


def compute_volatility_percentile(closes: list[float], lookback: int = 100) -> float:
    """Percentile of recent volatility vs historical volatility (0-100)."""
    if len(closes) < 30:
        return 50.0

    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1] > 0]
    if len(returns) < 20:
        return 50.0

    # Rolling 10-period realized vol
    vols: list[float] = []
    for i in range(10, len(returns)):
        window = returns[i - 10 : i]
        vol = math.sqrt(sum(r * r for r in window) / len(window))
        vols.append(vol)

    if len(vols) < 5:
        return 50.0

    current_vol = vols[-1]
    rank = sum(1 for v in vols if v <= current_vol)
    return round(rank / len(vols) * 100, 1)


# ── Regime-to-legacy mapping ──
_REGIME_MAP = {
    "RANGE": "range",
    "BREAKOUT": "high_volatility",
    "TREND_UP": "trend_up",
    "TREND_DOWN": "trend_down",
    "EXHAUSTION": "high_volatility",
}


def build_market_context(
    candles: list[Candle],
    btc_closes: list[float] | None = None,
) -> tuple[MarketContext, RegimeInfo]:
    """Build a full MarketContext + rich RegimeInfo from candle data.

    Returns a tuple for backward compatibility: callers that only
    need the old shape can ignore the second element.
    """
    closes = [c.close for c in candles]
    volumes = [c.volume for c in candles]

    regime_info = detect_regime(candles)
    legacy_regime = _REGIME_MAP.get(regime_info.regime, "range")

    btc_trend = classify_btc_trend(btc_closes) if btc_closes else "neutral"
    vol_percentile = compute_volatility_percentile(closes)
    vol_ratio_val = volume_ratio(volumes)
    atr_val = atr_raw(candles)

    ctx = MarketContext(
        regime=legacy_regime,
        btc_trend=btc_trend,
        volatility_percentile=vol_percentile,
        volume_ratio=round(vol_ratio_val, 2),
        atr=round(atr_val, 6),
    )

    return ctx, regime_info
