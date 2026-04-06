"""Advanced market regime detection with confidence scoring.

Classifies the market into one of five regimes:
  RANGE, BREAKOUT, TREND_UP, TREND_DOWN, EXHAUSTION

Each regime is scored independently (0-1 evidence), and the highest wins.
Hysteresis prevents flickering: 0.4 to enter a regime, 0.5 to override.
"""

from __future__ import annotations

import math
from typing import Optional

from app.core.models import Candle, RegimeInfo
from app.indicators.math_utils import ema, sma, std
from app.indicators.rsi import rsi_raw
from app.indicators.macd import macd_raw
from app.indicators.bollinger import bollinger_raw

# ── Constants ──

_MIN_CANDLES = 30
_ENTRY_THRESHOLD = 0.40   # minimum evidence to classify
_OVERRIDE_THRESHOLD = 0.50  # evidence needed to switch regime
_BB_SQUEEZE_PERCENTILE = 0.15
_BB_EXPANSION_FACTOR = 2.0
_VOLUME_SPIKE = 1.8
_TREND_SWING_COUNT = 3
_WICK_RATIO = 0.60
_MACD_DECEL_BARS = 3


def detect_regime(
    candles: list[Candle],
    previous_regime: Optional[str] = None,
) -> RegimeInfo:
    """Detect market regime from OHLCV candles.

    Returns a RegimeInfo with the classified regime, confidence,
    evidence per regime, and descriptive metadata.
    """
    if len(candles) < _MIN_CANDLES:
        return RegimeInfo(regime="RANGE", confidence=0.0, evidence={}, structure="NONE")

    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    volumes = [c.volume for c in candles]

    # ── Compute shared features ──
    rsi = rsi_raw(closes)
    _, _, _, bb_bandwidth = bollinger_raw(closes)
    _, _, macd_hist = macd_raw(closes)
    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    vol_ratio = _volume_ratio(volumes)
    has_hh, has_hl, has_lh, has_ll = _detect_structure(highs, lows)
    bear_div, bull_div = _detect_rsi_divergence(closes, highs, lows)
    wick_score = _detect_wick_exhaustion(candles)
    bb_bw_history = _bb_bandwidth_history(closes)
    macd_decel = _macd_decelerating(closes)

    # ── Score each regime ──
    evidence: dict[str, float] = {}

    evidence["RANGE"] = _score_range(
        bb_bandwidth, bb_bw_history, rsi, has_hh, has_hl, has_lh, has_ll, vol_ratio,
    )
    evidence["BREAKOUT"] = _score_breakout(
        bb_bandwidth, bb_bw_history, vol_ratio, highs, lows, closes,
    )
    evidence["TREND_UP"] = _score_trend_up(
        has_hh, has_hl, ema9, ema21, rsi, closes,
    )
    evidence["TREND_DOWN"] = _score_trend_down(
        has_lh, has_ll, ema9, ema21, rsi, closes,
    )
    evidence["EXHAUSTION"] = _score_exhaustion(
        bear_div, bull_div, macd_decel, wick_score, rsi,
    )

    # ── Select winner with hysteresis ──
    best_regime = max(evidence, key=lambda k: evidence[k])
    best_score = evidence[best_regime]

    if best_score < _ENTRY_THRESHOLD:
        best_regime = "RANGE"  # safest default
        best_score = max(evidence.get("RANGE", 0.0), _ENTRY_THRESHOLD)

    if previous_regime and previous_regime != best_regime:
        if best_score < _OVERRIDE_THRESHOLD:
            best_regime = previous_regime
            best_score = evidence.get(previous_regime, best_score)

    # ── Metadata ──
    structure = _structure_label(has_hh, has_hl, has_lh, has_ll)
    vol_state = _volatility_state(bb_bandwidth, bb_bw_history)
    mom_state = _momentum_state(macd_hist, macd_decel)

    return RegimeInfo(
        regime=best_regime,
        confidence=round(min(best_score, 1.0), 3),
        evidence={k: round(v, 3) for k, v in evidence.items()},
        structure=structure,
        volatility_state=vol_state,
        momentum_state=mom_state,
    )


# ═══════════════════════════════════════════════════════════════════
# Regime scoring functions
# ═══════════════════════════════════════════════════════════════════


def _score_range(
    bb_bw: float,
    bb_bw_history: list[float],
    rsi: float,
    has_hh: bool, has_hl: bool, has_lh: bool, has_ll: bool,
    vol_ratio: float,
) -> float:
    """RANGE: low vol, no directional structure, RSI mid-zone."""
    score = 0.0

    # BB squeeze — bandwidth in low percentile
    if bb_bw_history:
        percentile = sum(1 for v in bb_bw_history if v <= bb_bw) / len(bb_bw_history)
        if percentile < _BB_SQUEEZE_PERCENTILE:
            score += 0.35
        elif percentile < 0.30:
            score += 0.20
        elif percentile < 0.50:
            score += 0.10

    # No clear directional structure
    if not (has_hh and has_hl) and not (has_lh and has_ll):
        score += 0.25
    elif (has_hh and has_ll) or (has_hl and has_lh):
        score += 0.15  # mixed structure = range-like

    # RSI oscillating in neutral zone
    if 35 <= rsi <= 65:
        score += 0.20
    elif 25 <= rsi <= 75:
        score += 0.10

    # Low volume = quiet market
    if vol_ratio < 0.8:
        score += 0.10

    return min(score, 1.0)


def _score_breakout(
    bb_bw: float,
    bb_bw_history: list[float],
    vol_ratio: float,
    highs: list[float],
    lows: list[float],
    closes: list[float],
) -> float:
    """BREAKOUT: BB expansion after squeeze, volume spike, structure break."""
    score = 0.0

    # BB expanding from compressed state
    if bb_bw_history:
        min_bw = min(bb_bw_history[-20:]) if len(bb_bw_history) >= 20 else min(bb_bw_history)
        if min_bw > 0 and bb_bw > min_bw * _BB_EXPANSION_FACTOR:
            score += 0.30
        elif min_bw > 0 and bb_bw > min_bw * 1.5:
            score += 0.15

    # Volume spike
    if vol_ratio >= _VOLUME_SPIKE:
        score += 0.25
    elif vol_ratio >= 1.5:
        score += 0.15

    # Structure break — new high or new low
    if len(highs) >= 20 and len(closes) >= 2:
        recent_high = max(highs[-20:-1])
        recent_low = min(lows[-20:-1])
        if closes[-1] > recent_high:
            score += 0.25
        elif closes[-1] < recent_low:
            score += 0.25
        elif closes[-1] > recent_high * 0.998 or closes[-1] < recent_low * 1.002:
            score += 0.10  # near break

    # Recency: was there a squeeze recently (last 10 bars)?
    if bb_bw_history and len(bb_bw_history) >= 10:
        recent_min = min(bb_bw_history[-10:])
        all_min = min(bb_bw_history)
        if recent_min <= all_min * 1.1:
            score += 0.10

    return min(score, 1.0)


def _score_trend_up(
    has_hh: bool, has_hl: bool,
    ema9: list[float], ema21: list[float],
    rsi: float, closes: list[float],
) -> float:
    """TREND_UP: HH/HL structure, aligned EMAs, RSI > 50."""
    score = 0.0

    # Structure: higher highs + higher lows
    if has_hh and has_hl:
        score += 0.35
    elif has_hh or has_hl:
        score += 0.15

    # EMA alignment
    if len(ema9) >= 2 and len(ema21) >= 2:
        if ema9[-1] > ema21[-1]:
            score += 0.20
            if ema9[-2] > ema21[-2]:  # sustained
                score += 0.10

    # RSI above 50 = bullish momentum
    if rsi > 55:
        score += 0.15
    elif rsi > 50:
        score += 0.08

    # Price above EMA21
    if closes and len(ema21) > 0 and closes[-1] > ema21[-1]:
        score += 0.10

    return min(score, 1.0)


def _score_trend_down(
    has_lh: bool, has_ll: bool,
    ema9: list[float], ema21: list[float],
    rsi: float, closes: list[float],
) -> float:
    """TREND_DOWN: LH/LL structure, bearish EMAs, RSI < 50."""
    score = 0.0

    if has_lh and has_ll:
        score += 0.35
    elif has_lh or has_ll:
        score += 0.15

    if len(ema9) >= 2 and len(ema21) >= 2:
        if ema9[-1] < ema21[-1]:
            score += 0.20
            if ema9[-2] < ema21[-2]:
                score += 0.10

    if rsi < 45:
        score += 0.15
    elif rsi < 50:
        score += 0.08

    if closes and len(ema21) > 0 and closes[-1] < ema21[-1]:
        score += 0.10

    return min(score, 1.0)


def _score_exhaustion(
    bear_div: bool, bull_div: bool,
    macd_decel: bool, wick_score: float,
    rsi: float,
) -> float:
    """EXHAUSTION: divergence, decelerating momentum, long wicks, extreme RSI."""
    score = 0.0

    # RSI divergence
    if bear_div or bull_div:
        score += 0.30

    # MACD decelerating
    if macd_decel:
        score += 0.20

    # Long wicks = indecision / reversal
    if wick_score > 0.6:
        score += 0.25
    elif wick_score > 0.3:
        score += 0.12

    # Extreme RSI
    if rsi > 80 or rsi < 20:
        score += 0.20
    elif rsi > 75 or rsi < 25:
        score += 0.10

    return min(score, 1.0)


# ═══════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════


def _detect_structure(
    highs: list[float], lows: list[float],
) -> tuple[bool, bool, bool, bool]:
    """Detect HH/HL/LH/LL by comparing last 3 swing points.

    Returns (has_higher_highs, has_higher_lows, has_lower_highs, has_lower_lows).
    """
    swing_highs = _find_swing_points(highs, is_high=True)
    swing_lows = _find_swing_points(lows, is_high=False)

    has_hh = False
    has_hl = False
    has_lh = False
    has_ll = False

    if len(swing_highs) >= _TREND_SWING_COUNT:
        recent = swing_highs[-_TREND_SWING_COUNT:]
        has_hh = all(recent[i] > recent[i - 1] for i in range(1, len(recent)))
        has_lh = all(recent[i] < recent[i - 1] for i in range(1, len(recent)))

    if len(swing_lows) >= _TREND_SWING_COUNT:
        recent = swing_lows[-_TREND_SWING_COUNT:]
        has_hl = all(recent[i] > recent[i - 1] for i in range(1, len(recent)))
        has_ll = all(recent[i] < recent[i - 1] for i in range(1, len(recent)))

    return has_hh, has_hl, has_lh, has_ll


def _find_swing_points(values: list[float], is_high: bool, lookback: int = 5) -> list[float]:
    """Find swing highs or swing lows in a price series."""
    swings: list[float] = []
    if len(values) < lookback * 2 + 1:
        return swings

    for i in range(lookback, len(values) - lookback):
        window = values[i - lookback : i + lookback + 1]
        pivot = values[i]
        if is_high and pivot == max(window):
            swings.append(pivot)
        elif not is_high and pivot == min(window):
            swings.append(pivot)

    return swings


def _detect_rsi_divergence(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    rsi_period: int = 14,
) -> tuple[bool, bool]:
    """Detect bearish and bullish RSI divergences.

    Bearish: price makes higher high but RSI makes lower high.
    Bullish: price makes lower low but RSI makes higher low.
    """
    if len(closes) < rsi_period + 20:
        return False, False

    # Compute RSI for the full series
    rsi_values = _rsi_series(closes, rsi_period)
    if len(rsi_values) < 20:
        return False, False

    # Find recent swing highs/lows in price and RSI
    price_swing_highs = _find_swing_points(highs, is_high=True, lookback=3)
    rsi_swing_highs = _find_swing_points(rsi_values, is_high=True, lookback=3)

    price_swing_lows = _find_swing_points(lows, is_high=False, lookback=3)
    rsi_swing_lows = _find_swing_points(rsi_values, is_high=False, lookback=3)

    bear_div = False
    bull_div = False

    # Bearish divergence: price HH + RSI LH
    if len(price_swing_highs) >= 2 and len(rsi_swing_highs) >= 2:
        if price_swing_highs[-1] > price_swing_highs[-2] and rsi_swing_highs[-1] < rsi_swing_highs[-2]:
            bear_div = True

    # Bullish divergence: price LL + RSI HL
    if len(price_swing_lows) >= 2 and len(rsi_swing_lows) >= 2:
        if price_swing_lows[-1] < price_swing_lows[-2] and rsi_swing_lows[-1] > rsi_swing_lows[-2]:
            bull_div = True

    return bear_div, bull_div


def _rsi_series(closes: list[float], period: int = 14) -> list[float]:
    """Compute RSI for every point in the series (for divergence detection)."""
    if len(closes) < period + 1:
        return []

    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    result: list[float] = []
    for i in range(period, len(closes)):
        avg_gain = sum(gains[i - period + 1 : i + 1]) / period
        avg_loss = sum(losses[i - period + 1 : i + 1]) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100 - (100 / (1 + rs)))

    return result


def _detect_wick_exhaustion(candles: list[Candle], lookback: int = 5) -> float:
    """Score 0-1 based on proportion of recent candles with long wicks."""
    if len(candles) < lookback:
        return 0.0

    recent = candles[-lookback:]
    wick_count = 0
    for c in recent:
        body = abs(c.close - c.open)
        full_range = c.high - c.low
        if full_range <= 0:
            continue
        wick_ratio = 1 - (body / full_range)
        if wick_ratio >= _WICK_RATIO:
            wick_count += 1

    return wick_count / lookback


def _bb_bandwidth_history(closes: list[float], period: int = 20, num_std: float = 2.0) -> list[float]:
    """Rolling Bollinger Band bandwidth for percentile comparison."""
    if len(closes) < period:
        return []

    sma_vals = sma(closes, period)
    std_vals = std(closes, period)
    result: list[float] = []

    for i in range(period - 1, len(closes)):
        mid = sma_vals[i]
        if mid <= 0:
            result.append(0.0)
            continue
        upper = mid + num_std * std_vals[i]
        lower = mid - num_std * std_vals[i]
        result.append((upper - lower) / mid)

    return result


def _macd_decelerating(closes: list[float], bars: int = _MACD_DECEL_BARS) -> bool:
    """Check if MACD histogram has been shrinking for N consecutive bars."""
    if len(closes) < 35 + bars:
        return False

    ema_fast = ema(closes, 12)
    ema_slow = ema(closes, 26)
    macd_line = [a - b for a, b in zip(ema_fast, ema_slow)]
    signal_line = ema(macd_line, 9)
    histogram = [m - s for m, s in zip(macd_line, signal_line)]

    if len(histogram) < bars + 1:
        return False

    recent = histogram[-(bars + 1) :]
    abs_vals = [abs(v) for v in recent]

    # Shrinking = absolute value decreasing for N bars
    return all(abs_vals[i] < abs_vals[i - 1] for i in range(1, len(abs_vals)))


def _volume_ratio(volumes: list[float], period: int = 20) -> float:
    """Current volume / average of last N periods."""
    if len(volumes) < period + 1:
        return 1.0
    avg = sum(volumes[-period - 1 : -1]) / period
    if avg <= 0:
        return 1.0
    return volumes[-1] / avg


# ── Metadata helpers ──

def _structure_label(has_hh: bool, has_hl: bool, has_lh: bool, has_ll: bool) -> str:
    if has_hh and has_hl:
        return "HH_HL"
    if has_lh and has_ll:
        return "LH_LL"
    if (has_hh or has_hl) and (has_lh or has_ll):
        return "MIXED"
    return "NONE"


def _volatility_state(bb_bw: float, bb_bw_history: list[float]) -> str:
    if not bb_bw_history:
        return "normal"
    percentile = sum(1 for v in bb_bw_history if v <= bb_bw) / len(bb_bw_history)
    if percentile < 0.15:
        return "compressed"
    if percentile > 0.85:
        return "extreme"
    if percentile > 0.70:
        return "expanding"
    return "normal"


def _momentum_state(macd_hist: float, decel: bool) -> str:
    if decel:
        return "decelerating"
    if abs(macd_hist) > 0:
        return "accelerating"
    return "neutral"
