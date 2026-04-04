"""Trading Signal Engine — RSI, MACD, Bollinger Bands, EMA Cross + Composite Scoring.

Generates professional trading signals: STRONG BUY, BUY, HOLD, SELL, STRONG SELL.
Each indicator votes, then a composite score determines the final signal.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Action(str, Enum):
    STRONG_BUY = "STRONG_BUY"    # Acheter massivement
    BUY = "BUY"                  # Acheter
    ACCUMULATE = "ACCUMULATE"    # Renforcer la position
    HOLD = "HOLD"                # Conserver
    REDUCE = "REDUCE"            # Alleger la position
    SELL = "SELL"                # Vendre
    STRONG_SELL = "STRONG_SELL"  # Liquider


@dataclass
class IndicatorResult:
    name: str
    value: float
    signal: float  # -1 (sell) to +1 (buy)
    description: str
    weight: float = 1.0


@dataclass
class TradingSignal:
    symbol: str
    action: Action
    confidence: float  # 0 to 1
    score: float       # -1 to +1
    indicators: list[IndicatorResult] = field(default_factory=list)
    reasoning: str = ""


# ──────────────────────────────────────────
# Technical Indicators (pure numpy-free math)
# ──────────────────────────────────────────

def _sma(prices: list[float], period: int) -> list[float]:
    result = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(prices[i])
        else:
            result.append(sum(prices[i - period + 1:i + 1]) / period)
    return result


def _ema(prices: list[float], period: int) -> list[float]:
    k = 2 / (period + 1)
    result = [prices[0]]
    for i in range(1, len(prices)):
        result.append(prices[i] * k + result[-1] * (1 - k))
    return result


def _std(prices: list[float], period: int) -> list[float]:
    result = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(0.0)
        else:
            window = prices[i - period + 1:i + 1]
            mean = sum(window) / len(window)
            variance = sum((x - mean) ** 2 for x in window) / len(window)
            result.append(math.sqrt(variance))
    return result


def calc_rsi(closes: list[float], period: int = 14) -> IndicatorResult:
    """RSI: <30 oversold (buy), >70 overbought (sell)."""
    if len(closes) < period + 1:
        return IndicatorResult("RSI", 50, 0, "Insufficient data")

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

    return IndicatorResult("RSI", round(rsi, 1), signal, desc, weight=1.2)


def calc_macd(closes: list[float]) -> IndicatorResult:
    """MACD: crossover signal. Uses 12/26/9 standard."""
    if len(closes) < 35:
        return IndicatorResult("MACD", 0, 0, "Insufficient data")

    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = [a - b for a, b in zip(ema12, ema26)]
    signal_line = _ema(macd_line, 9)

    macd_val = macd_line[-1]
    signal_val = signal_line[-1]
    histogram = macd_val - signal_val
    prev_histogram = macd_line[-2] - signal_line[-2]

    # Bullish crossover
    if histogram > 0 and prev_histogram <= 0:
        signal, desc = 0.8, f"MACD bullish crossover — Buy signal"
    elif histogram < 0 and prev_histogram >= 0:
        signal, desc = -0.8, f"MACD bearish crossover — Sell signal"
    elif histogram > 0:
        strength = min(abs(histogram) / (abs(macd_val) + 0.001), 1)
        signal, desc = 0.4 * strength, f"MACD positive momentum"
    elif histogram < 0:
        strength = min(abs(histogram) / (abs(macd_val) + 0.001), 1)
        signal, desc = -0.4 * strength, f"MACD negative momentum"
    else:
        signal, desc = 0.0, "MACD neutral"

    return IndicatorResult("MACD", round(histogram, 4), round(signal, 2), desc, weight=1.3)


def calc_bollinger(closes: list[float], period: int = 20) -> IndicatorResult:
    """Bollinger Bands: price relative to bands."""
    if len(closes) < period:
        return IndicatorResult("Bollinger", 0, 0, "Insufficient data")

    sma = _sma(closes, period)
    std = _std(closes, period)

    upper = sma[-1] + 2 * std[-1]
    lower = sma[-1] - 2 * std[-1]
    price = closes[-1]
    band_width = upper - lower

    if band_width == 0:
        return IndicatorResult("Bollinger", 0, 0, "Zero bandwidth")

    position = (price - lower) / band_width  # 0 = lower band, 1 = upper band

    if position < 0.05:
        signal, desc = 0.9, f"Price below lower Bollinger Band — Strong buy"
    elif position < 0.2:
        signal, desc = 0.5, f"Price near lower band — Buy zone"
    elif position < 0.4:
        signal, desc = 0.2, f"Price in lower half — Slightly bullish"
    elif position < 0.6:
        signal, desc = 0.0, f"Price at middle band — Neutral"
    elif position < 0.8:
        signal, desc = -0.2, f"Price in upper half — Slightly bearish"
    elif position < 0.95:
        signal, desc = -0.5, f"Price near upper band — Sell zone"
    else:
        signal, desc = -0.9, f"Price above upper Bollinger Band — Strong sell"

    return IndicatorResult("Bollinger", round(position, 2), signal, desc, weight=1.0)


def calc_ema_cross(closes: list[float]) -> IndicatorResult:
    """EMA 9/21 crossover — short-term trend signal."""
    if len(closes) < 25:
        return IndicatorResult("EMA Cross", 0, 0, "Insufficient data")

    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)

    current_diff = ema9[-1] - ema21[-1]
    prev_diff = ema9[-2] - ema21[-2]

    if current_diff > 0 and prev_diff <= 0:
        signal, desc = 0.7, "EMA 9/21 golden cross — Bullish trend starting"
    elif current_diff < 0 and prev_diff >= 0:
        signal, desc = -0.7, "EMA 9/21 death cross — Bearish trend starting"
    elif current_diff > 0:
        signal, desc = 0.3, "EMA 9 above EMA 21 — Uptrend"
    elif current_diff < 0:
        signal, desc = -0.3, "EMA 9 below EMA 21 — Downtrend"
    else:
        signal, desc = 0.0, "EMAs converging — Neutral"

    return IndicatorResult("EMA Cross", round(current_diff, 4), signal, desc, weight=1.1)


def calc_volume_profile(volumes: list[float]) -> IndicatorResult:
    """Volume analysis: above-average volume confirms trends."""
    if len(volumes) < 20:
        return IndicatorResult("Volume", 0, 0, "Insufficient data")

    avg_vol = sum(volumes[-20:]) / 20
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

    return IndicatorResult("Volume", round(ratio, 2), signal, desc, weight=0.6)


# ──────────────────────────────────────────
# Composite Signal Generator
# ──────────────────────────────────────────

def generate_signal(
    symbol: str,
    closes: list[float],
    volumes: list[float] | None = None,
) -> TradingSignal:
    """Generate a composite trading signal from all indicators."""
    indicators = [
        calc_rsi(closes),
        calc_macd(closes),
        calc_bollinger(closes),
        calc_ema_cross(closes),
    ]

    if volumes and len(volumes) >= 20:
        indicators.append(calc_volume_profile(volumes))

    # Weighted score
    total_weight = sum(ind.weight for ind in indicators)
    weighted_score = sum(ind.signal * ind.weight for ind in indicators) / total_weight if total_weight > 0 else 0

    # Map score to action
    if weighted_score > 0.6:
        action = Action.STRONG_BUY
    elif weighted_score > 0.3:
        action = Action.BUY
    elif weighted_score > 0.1:
        action = Action.ACCUMULATE
    elif weighted_score > -0.1:
        action = Action.HOLD
    elif weighted_score > -0.3:
        action = Action.REDUCE
    elif weighted_score > -0.6:
        action = Action.SELL
    else:
        action = Action.STRONG_SELL

    confidence = min(abs(weighted_score), 1.0)

    # Build reasoning
    bullish = [i for i in indicators if i.signal > 0.2]
    bearish = [i for i in indicators if i.signal < -0.2]
    reasoning_parts = []
    if bullish:
        reasoning_parts.append(f"Bullish: {', '.join(i.name for i in bullish)}")
    if bearish:
        reasoning_parts.append(f"Bearish: {', '.join(i.name for i in bearish)}")
    reasoning = ". ".join(reasoning_parts) or "Mixed signals — hold position"

    return TradingSignal(
        symbol=symbol,
        action=action,
        confidence=round(confidence, 2),
        score=round(weighted_score, 3),
        indicators=indicators,
        reasoning=reasoning,
    )
