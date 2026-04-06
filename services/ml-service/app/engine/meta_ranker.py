"""Contextual scanner calibration and publication rules.

This module keeps the scanner deterministic today while exposing
an optional model-loading hook for future tabular ML calibration.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import os
import pickle
from typing import Any

from app.core.config import settings as app_settings
from app.core.models import Candle, MarketContext, RegimeInfo, Scenario, StrategyResult
from app.engine.enhanced_scoring import EnhancedScore
from app.engine.regime_detector import detect_regime
from app.indicators.atr import atr_raw
from app.indicators.math_utils import ema
from app.settings.user_settings import UserSignalSettings

_BUY_ACTIONS = {"BUY", "STRONG_BUY", "ACCUMULATE"}
_SELL_ACTIONS = {"SELL", "STRONG_SELL", "REDUCE"}

_STRATEGY_REGIME_FIT: dict[str, dict[str, int]] = {
    "breakout": {"BREAKOUT": 92, "TREND_UP": 74, "TREND_DOWN": 74, "RANGE": 35, "EXHAUSTION": 28},
    "momentum_burst": {"BREAKOUT": 86, "TREND_UP": 82, "TREND_DOWN": 82, "RANGE": 38, "EXHAUSTION": 42},
    "micro_pullback": {"TREND_UP": 90, "TREND_DOWN": 84, "RANGE": 58, "BREAKOUT": 48, "EXHAUSTION": 64},
}

_REGIME_DIRECTION_ALIGNMENT: dict[int, dict[str, int]] = {
    1: {"TREND_UP": 88, "BREAKOUT": 76, "RANGE": 55, "EXHAUSTION": 34, "TREND_DOWN": 20},
    -1: {"TREND_DOWN": 88, "BREAKOUT": 76, "RANGE": 55, "EXHAUSTION": 34, "TREND_UP": 20},
    0: {"TREND_UP": 50, "BREAKOUT": 50, "RANGE": 60, "EXHAUSTION": 45, "TREND_DOWN": 50},
}

_SETUP_WINDOWS = {
    "breakout_continuation": "5-20 min",
    "pullback_in_trend": "10-30 min",
    "momentum_burst": "3-15 min",
    "range_mean_reversion": "15-45 min",
    "exhaustion_reversal": "5-25 min",
    "contextual_setup": "5-30 min",
}


@dataclass
class ScannerContext:
    horizon: str
    setup_type: str
    regime: str
    regime_fit: int
    confirmation_score: int
    composite_score: int
    reliability_score: int
    trend_context_score: int
    trend_reliability_score: int
    execution_risk: int
    liquidity_score: int
    expected_holding_window: str
    freshness_ms: int
    meta_score: float
    model_name: str = "heuristic_v1"


@dataclass
class FrameTrendContext:
    score: int
    reliability: int
    persistence: int
    efficiency: int
    stabilization: int
    shock_risk: int
    multiplier: float


def clamp(value: float, lo: int | float = 0, hi: int | float = 100) -> float:
    return max(lo, min(hi, value))


def _direction_sign(result: StrategyResult, enhanced: EnhancedScore) -> int:
    if result.action in _BUY_ACTIONS or enhanced.direction >= 55:
        return 1
    if result.action in _SELL_ACTIONS or enhanced.direction <= 45:
        return -1
    return 0


def _mode_label(mode: str) -> str:
    if mode == "scalping":
        return "Scalp"
    if mode == "intraday":
        return "Intraday"
    if mode == "swing":
        return "Swing"
    return mode.title()


def build_horizon_label(settings: UserSignalSettings) -> str:
    frames = [settings.primary_timeframe, *settings.confirmation_timeframes]
    if settings.anchor_timeframe and settings.anchor_timeframe not in frames:
        frames.append(settings.anchor_timeframe)
    return f"{_mode_label(settings.trading_mode)} {'/'.join(frames)}"


def infer_setup_type(
    result: StrategyResult,
    regime: RegimeInfo | None,
    scenario: Scenario | None,
) -> str:
    regime_name = regime.regime if regime else "RANGE"
    scenario_name = scenario.name if scenario else ""

    if regime_name == "BREAKOUT" and scenario_name == "CONTINUATION":
        return "breakout_continuation"
    if regime_name in ("TREND_UP", "TREND_DOWN") and result.strategy_name == "micro_pullback":
        return "pullback_in_trend"
    if scenario_name == "MEAN_REVERSION":
        return "range_mean_reversion"
    if regime_name == "EXHAUSTION" or scenario_name in {"REVERSAL", "EXHAUSTION_TOP"}:
        return "exhaustion_reversal"
    if result.strategy_name == "momentum_burst":
        return "momentum_burst"
    if result.strategy_name == "breakout":
        return "breakout_continuation"
    if result.strategy_name == "micro_pullback":
        return "pullback_in_trend"
    return "contextual_setup"


def _average_notional(candles: list[Candle], lookback: int = 20) -> float:
    if not candles:
        return 0.0
    sample = candles[-lookback:]
    notionals = [max(c.close, 0) * max(c.volume, 0) for c in sample]
    return sum(notionals) / len(notionals) if notionals else 0.0


def _liquidity_score(candles: list[Candle], market_context: MarketContext | None) -> int:
    avg_notional = _average_notional(candles)
    if avg_notional >= 5_000_000:
        notional_score = 95
    elif avg_notional >= 1_000_000:
        notional_score = 86
    elif avg_notional >= 250_000:
        notional_score = 74
    elif avg_notional >= 50_000:
        notional_score = 58
    else:
        notional_score = 36

    vol_ratio = market_context.volume_ratio if market_context else 1.0
    ratio_score = clamp(round(50 + (vol_ratio - 1.0) * 25), 20, 95)
    return int(round(notional_score * 0.6 + ratio_score * 0.4))


def _alignment_score(direction: int, regime: RegimeInfo | None) -> int:
    if not regime:
        return 50
    score = _REGIME_DIRECTION_ALIGNMENT[direction].get(regime.regime, 50)
    score += round(regime.confidence * 10)
    if regime.volatility_state == "extreme":
        score -= 12
    elif regime.volatility_state == "compressed" and regime.regime == "BREAKOUT":
        score += 6
    if regime.momentum_state == "accelerating" and direction != 0:
        score += 6
    return int(clamp(score))


def _detect_tf_regime(candles: list[Candle] | None) -> RegimeInfo | None:
    if not candles or len(candles) < 30:
        return None
    return detect_regime(candles)


def _confirmation_score(
    direction: int,
    primary_regime: RegimeInfo | None,
    confirmation_regimes: list[RegimeInfo | None],
    confirmation_candles: list[Candle] | None,
    anchor_candles: list[Candle] | None,
) -> int:
    regimes = [primary_regime, *confirmation_regimes]
    weights = [0.40, 0.25, 0.20, 0.15]
    weighted_regime = 0.0
    total_regime_weight = 0.0
    for weight, regime in zip(weights, regimes):
        if regime is None:
            continue
        weighted_regime += _alignment_score(direction, regime) * weight
        total_regime_weight += weight

    regime_score = weighted_regime / total_regime_weight if total_regime_weight > 0 else 50.0

    def directional_move_score(candles: list[Candle] | None, lookback: int) -> tuple[float, float]:
        if not candles or len(candles) <= lookback:
            return 50.0, 0.0
        start = candles[-(lookback + 1)].close
        end = candles[-1].close
        move_pct = ((end - start) / max(abs(start), 1e-9)) * 100
        if direction > 0:
            score = 52 + move_pct * 38
        elif direction < 0:
            score = 52 - move_pct * 38
        else:
            score = 64 - abs(move_pct) * 28
        return clamp(round(score), 10, 95), 1.0

    confirmation_move, confirmation_weight = directional_move_score(confirmation_candles, 6)
    anchor_move, anchor_weight = directional_move_score(anchor_candles, 4)
    total_move_weight = confirmation_weight * 0.6 + anchor_weight * 0.4
    if total_move_weight == 0:
        return int(round(regime_score))

    move_score = (
        confirmation_move * confirmation_weight * 0.6
        + anchor_move * anchor_weight * 0.4
    ) / total_move_weight

    return int(round(regime_score * 0.58 + move_score * 0.42))


def _relative_strength_score(
    direction: int,
    confirmation_candles: list[Candle] | None,
    btc_closes: list[float] | None,
) -> int:
    if not confirmation_candles or len(confirmation_candles) < 6 or not btc_closes or len(btc_closes) < 6:
        return 50

    asset_ret = (confirmation_candles[-1].close - confirmation_candles[-6].close) / max(confirmation_candles[-6].close, 1e-9)
    btc_ret = (btc_closes[-1] - btc_closes[-6]) / max(btc_closes[-6], 1e-9)
    diff = (asset_ret - btc_ret) * 100
    if direction >= 0:
        return int(clamp(round(50 + diff * 8)))
    return int(clamp(round(50 - diff * 8)))


def _candle_quality_score(candles: list[Candle], direction: int) -> int:
    if not candles:
        return 50
    candle = candles[-1]
    candle_range = max(candle.high - candle.low, 1e-9)
    body = abs(candle.close - candle.open) / candle_range
    close_bias = (candle.close - candle.low) / candle_range if direction >= 0 else (candle.high - candle.close) / candle_range
    adverse_wick = (
        (candle.high - max(candle.open, candle.close)) / candle_range
        if direction >= 0
        else (min(candle.open, candle.close) - candle.low) / candle_range
    )
    score = 42 + body * 30 + close_bias * 30 - adverse_wick * 20
    return int(clamp(round(score), 20, 95))


def _level_proximity_score(candles: list[Candle], direction: int) -> int:
    if len(candles) < 21:
        return 50
    recent = candles[-21:-1]
    recent_high = max(c.high for c in recent)
    recent_low = min(c.low for c in recent)
    current_price = candles[-1].close
    recent_range = max(recent_high - recent_low, 1e-9)
    if direction >= 0:
        distance = abs(current_price - recent_high) / recent_range
    else:
        distance = abs(current_price - recent_low) / recent_range
    return int(clamp(round(96 - distance * 150), 15, 96))


def _regime_fit(
    result: StrategyResult,
    regime: RegimeInfo | None,
    scenario: Scenario | None,
) -> int:
    regime_name = regime.regime if regime else "RANGE"
    strategy_base = _STRATEGY_REGIME_FIT.get(result.strategy_name, {}).get(regime_name, 50)
    scenario_boost = round((scenario.probability if scenario else 0.0) * 18)
    if scenario and scenario.name == "CONTINUATION" and result.strategy_name in {"breakout", "micro_pullback", "momentum_burst"}:
        scenario_boost += 6
    if scenario and scenario.name in {"REVERSAL", "MEAN_REVERSION"} and regime_name in {"RANGE", "EXHAUSTION"}:
        scenario_boost += 8
    regime_confidence = round((regime.confidence if regime else 0.0) * 12)
    return int(clamp(strategy_base + scenario_boost + regime_confidence))


def _expected_holding_window(setup_type: str) -> str:
    return _SETUP_WINDOWS.get(setup_type, _SETUP_WINDOWS["contextual_setup"])


def _freshness_ms(candles: list[Candle], now_ms: int) -> int:
    if not candles:
        return 0
    return max(0, now_ms - int(candles[-1].time * 1000))


def _timeframe_hours(timeframe: str) -> float:
    normalized = timeframe.strip().lower()
    if normalized.endswith("m"):
        return max(float(normalized[:-1]), 1.0) / 60.0
    if normalized.endswith("h"):
        return max(float(normalized[:-1]), 1.0)
    if normalized.endswith("d"):
        return max(float(normalized[:-1]), 1.0) * 24.0
    if normalized.endswith("w"):
        return max(float(normalized[:-1]), 1.0) * 24.0 * 7.0
    return 1.0


def _bars_for_standard_window(timeframe: str, hours_window: float = 24.0) -> int:
    return max(2, round(hours_window / max(_timeframe_hours(timeframe), 1e-6)))


def _tanh_normalized(value: float, scale: float) -> float:
    return math.tanh(value / max(scale, 1e-6))


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _realized_volatility(values: list[float]) -> float:
    if not values:
        return 0.0
    return math.sqrt(sum(value * value for value in values) / len(values))


def _curve_structure_profile(
    candles: list[Candle],
    timeframe: str,
) -> tuple[int, int, int, float]:
    if len(candles) < 18:
        return 50, 50, 50, 1.0

    lookback = min(len(candles) - 1, max(12, _bars_for_standard_window(timeframe)))
    sample = candles[-(lookback + 1):]
    closes = [c.close for c in sample]
    opens = [c.open for c in sample]
    highs = [c.high for c in sample]
    lows = [c.low for c in sample]

    current_price = closes[-1]
    reference_price = closes[0]
    if current_price <= 0 or reference_price <= 0:
        return 50, 50, 50, 1.0

    atr_pct = atr_raw(sample) / max(current_price, 1e-9) * 100
    atr_pct = max(atr_pct, 0.10)

    close_returns_pct = [
        ((closes[index] - closes[index - 1]) / max(closes[index - 1], 1e-9)) * 100
        for index in range(1, len(closes))
    ]
    gap_returns_pct = [
        ((opens[index] - closes[index - 1]) / max(closes[index - 1], 1e-9)) * 100
        for index in range(1, len(closes))
    ]
    recent_window = min(max(4, lookback // 4), len(close_returns_pct))
    recent_returns = close_returns_pct[-recent_window:]
    prior_returns = close_returns_pct[:-recent_window] or close_returns_pct
    overall_ret_pct = ((current_price - reference_price) / reference_price) * 100

    up_impulse = max(close_returns_pct, default=0.0)
    down_impulse = abs(min(close_returns_pct, default=0.0))
    up_signal = _tanh_normalized(max(up_impulse, 0.0), atr_pct * 1.35)
    down_signal = _tanh_normalized(max(down_impulse, 0.0), atr_pct * 1.35)
    directional_impulse = up_signal - down_signal

    strongest_gap = max(gap_returns_pct, key=lambda value: abs(value), default=0.0)
    gap_signal = _tanh_normalized(abs(strongest_gap), atr_pct * 1.10)
    gap_direction = 1 if strongest_gap > 0 else -1 if strongest_gap < 0 else 0

    overall_sign = 1 if overall_ret_pct > 0 else -1 if overall_ret_pct < 0 else 0
    if overall_sign == 0:
        overall_sign = 1 if directional_impulse > 0 else -1 if directional_impulse < 0 else 0

    bullish_extreme_move = ((max(highs) - reference_price) / max(reference_price, 1e-9)) * 100
    bearish_extreme_move = ((reference_price - min(lows)) / max(reference_price, 1e-9)) * 100

    if overall_sign >= 0:
        extreme_move = max(bullish_extreme_move, abs(overall_ret_pct), 0.01)
        retention = clamp(overall_ret_pct / extreme_move, 0.0, 1.0)
    else:
        extreme_move = max(bearish_extreme_move, abs(overall_ret_pct), 0.01)
        retention = clamp(abs(overall_ret_pct) / extreme_move, 0.0, 1.0)

    ema21 = ema(closes, 21)
    recent_candles = sample[-min(6, len(sample)):]
    recent_ema = ema21[-1]
    if overall_sign >= 0:
        hold_bias = _mean([1.0 if candle.close >= recent_ema else 0.0 for candle in recent_candles])
        recent_direction_bias = _mean([1.0 if value > 0 else 0.0 for value in recent_returns])
    else:
        hold_bias = _mean([1.0 if candle.close <= recent_ema else 0.0 for candle in recent_candles])
        recent_direction_bias = _mean([1.0 if value < 0 else 0.0 for value in recent_returns])

    recent_vol = _realized_volatility(recent_returns)
    prior_vol = max(_realized_volatility(prior_returns), atr_pct * 0.20)
    compression = clamp(1.0 - recent_vol / max(prior_vol, 1e-9), -0.5, 1.0)

    recent_closes = closes[-recent_window:]
    cluster_range_pct = ((max(recent_closes) - min(recent_closes)) / max(current_price, 1e-9)) * 100 if recent_closes else 0.0
    clustering = clamp(1.0 - cluster_range_pct / max(atr_pct * 2.4, 0.35), 0.0, 1.0)

    gap_followthrough = 0.0
    if gap_direction != 0:
        if gap_direction == overall_sign:
            gap_followthrough = gap_signal * retention
        else:
            gap_followthrough = -gap_signal * (1.0 - retention * 0.5)

    directional_signal = (
        _tanh_normalized(overall_ret_pct, atr_pct * 2.6) * 0.36
        + directional_impulse * 0.28
        + (hold_bias * 2 - 1) * 0.20
        + gap_followthrough * 0.16
    )
    direction_score = int(clamp(round(50 + directional_signal * 44)))

    stabilization_score = int(clamp(round(
        18
        + max(compression, 0.0) * 34
        + retention * 24
        + hold_bias * 16
        + recent_direction_bias * 12
        + clustering * 10
    ), 12, 97))
    shock_risk = int(clamp(round(
        18
        + max(up_signal, down_signal) * 36
        + abs(gap_followthrough) * 16
        + max(recent_vol - prior_vol, 0.0) / max(atr_pct, 0.10) * 12
        - retention * 16
        - max(compression, 0.0) * 12
        - hold_bias * 8
    ), 12, 96))
    continuation_score = int(clamp(round(
        20
        + abs(directional_signal) * 28
        + retention * 26
        + max(compression, 0.0) * 14
        + hold_bias * 12
        + recent_direction_bias * 10
        - max(0, shock_risk - 55) * 0.45
    ), 10, 96))
    multiplier = float(clamp(
        0.76
        + continuation_score / 100 * 0.34
        + stabilization_score / 100 * 0.16
        - shock_risk / 100 * 0.24,
        0.72,
        1.42,
    ))

    return direction_score, stabilization_score, shock_risk, multiplier


def _frame_trend_context(
    candles: list[Candle] | None,
    timeframe: str,
) -> FrameTrendContext:
    if not candles or len(candles) < 25:
        return FrameTrendContext(
            score=50,
            reliability=0,
            persistence=0,
            efficiency=0,
            stabilization=50,
            shock_risk=50,
            multiplier=1.0,
        )

    closes = [c.close for c in candles]
    lookback = min(len(closes) - 1, _bars_for_standard_window(timeframe))
    if lookback < 2:
        return FrameTrendContext(
            score=50,
            reliability=0,
            persistence=0,
            efficiency=0,
            stabilization=50,
            shock_risk=50,
            multiplier=1.0,
        )

    current_price = closes[-1]
    reference_price = closes[-(lookback + 1)]
    if current_price <= 0 or reference_price <= 0:
        return FrameTrendContext(
            score=50,
            reliability=0,
            persistence=0,
            efficiency=0,
            stabilization=50,
            shock_risk=50,
            multiplier=1.0,
        )

    ema_fast = ema(closes, 9)
    ema_slow = ema(closes, 21)
    atr_pct = atr_raw(candles) / max(current_price, 1e-9) * 100
    atr_pct = max(atr_pct, 0.12)

    ret_pct = (current_price - reference_price) / reference_price * 100
    ema_spread_pct = (ema_fast[-1] - ema_slow[-1]) / current_price * 100
    ema_slow_ref = ema_slow[-(lookback + 1)] if len(ema_slow) > lookback else ema_slow[0]
    ema_slope_pct = (ema_slow[-1] - ema_slow_ref) / max(reference_price, 1e-9) * 100
    price_vs_ema_pct = (current_price - ema_slow[-1]) / current_price * 100

    return_signal = _tanh_normalized(ret_pct, atr_pct * 2.8)
    spread_signal = _tanh_normalized(ema_spread_pct, atr_pct * 1.4)
    slope_signal = _tanh_normalized(ema_slope_pct, atr_pct * 1.8)
    price_signal = _tanh_normalized(price_vs_ema_pct, atr_pct * 1.2)

    combined = (
        return_signal * 0.38
        + spread_signal * 0.24
        + slope_signal * 0.23
        + price_signal * 0.15
    )
    base_score = 50 + combined * 42
    curve_direction_score, stabilization_score, shock_risk, multiplier = _curve_structure_profile(candles, timeframe)
    merged_signal = (
        ((base_score - 50) / 50) * 0.62
        + ((curve_direction_score - 50) / 50) * 0.38
        + ((stabilization_score - 50) / 50) * 0.10
        - ((shock_risk - 50) / 50) * 0.16
    )
    score = int(clamp(round(50 + merged_signal * 44)))

    directional_returns = [
        closes[index] - closes[index - 1]
        for index in range(len(closes) - lookback, len(closes))
    ]
    positive_steps = sum(1 for step in directional_returns if step > 0)
    negative_steps = sum(1 for step in directional_returns if step < 0)
    persistence = max(positive_steps, negative_steps) / max(len(directional_returns), 1)
    path = sum(abs(step) for step in directional_returns)
    net_move = abs(current_price - reference_price)
    efficiency = net_move / max(path, 1e-9)
    persistence_score = int(clamp(round(18 + persistence * 82), 10, 100))
    efficiency_score = int(clamp(round(20 + efficiency * 80), 10, 100))
    strength = min(abs(score - 50) * 2, 100)
    coverage = min(len(closes) / (lookback + 10), 1.0)
    reliability = int(clamp(round(
        18
        + strength * 0.20
        + persistence_score * 0.18
        + efficiency_score * 0.14
        + stabilization_score * 0.18
        + (100 - shock_risk) * 0.14
        + coverage * 18
    ), 15, 97))

    return FrameTrendContext(
        score=score,
        reliability=reliability,
        persistence=persistence_score,
        efficiency=efficiency_score,
        stabilization=stabilization_score,
        shock_risk=shock_risk,
        multiplier=multiplier,
    )


def _aggregate_trend_context(
    primary_candles: list[Candle],
    anchor_candles: list[Candle] | None,
    context_candles_by_tf: dict[str, list[Candle]],
    settings: UserSignalSettings,
) -> tuple[int, int, int, int, float, int, int]:
    frames: list[tuple[str, list[Candle] | None, float]] = []
    if anchor_candles:
        frames.append((settings.anchor_timeframe, anchor_candles, 0.20))

    context_weights = [0.18, 0.27, 0.35]
    for index, timeframe in enumerate(settings.context_timeframes):
        candles = context_candles_by_tf.get(timeframe)
        weight = context_weights[index] if index < len(context_weights) else 0.20
        frames.append((timeframe, candles, weight))

    if not frames:
        frames.append((settings.anchor_timeframe, primary_candles, 1.0))

    weighted_score = 0.0
    weighted_reliability = 0.0
    weighted_persistence = 0.0
    weighted_efficiency = 0.0
    weighted_stabilization = 0.0
    weighted_shock_risk = 0.0
    weighted_multiplier = 0.0
    total_weight = 0.0
    frame_results: list[tuple[FrameTrendContext, float]] = []
    for timeframe, candles, weight in frames:
        context = _frame_trend_context(candles, timeframe)
        if context.reliability <= 0:
            continue
        weighted_score += context.score * weight
        weighted_reliability += context.reliability * weight
        weighted_persistence += context.persistence * weight
        weighted_efficiency += context.efficiency * weight
        weighted_stabilization += context.stabilization * weight
        weighted_shock_risk += context.shock_risk * weight
        weighted_multiplier += context.multiplier * weight
        total_weight += weight
        frame_results.append((context, weight))

    if total_weight == 0:
        return 50, 35, 35, 35, 1.0, 50, 50

    aggregated_score = weighted_score / total_weight
    aggregated_reliability = weighted_reliability / total_weight
    aggregated_persistence = weighted_persistence / total_weight
    aggregated_efficiency = weighted_efficiency / total_weight
    aggregated_stabilization = weighted_stabilization / total_weight
    aggregated_shock_risk = weighted_shock_risk / total_weight
    aggregated_multiplier = weighted_multiplier / total_weight
    weighted_deviation = sum(
        abs(context.score - aggregated_score) * weight
        for context, weight in frame_results
    ) / total_weight
    consensus_score = int(clamp(round(100 - weighted_deviation * 2.1), 20, 98))
    historical_consistency = int(clamp(round(
        aggregated_persistence * 0.58 + aggregated_efficiency * 0.42
    ), 15, 98))
    reliability_score = int(clamp(round(
        aggregated_reliability * 0.36
        + consensus_score * 0.24
        + historical_consistency * 0.16
        + aggregated_stabilization * 0.14
        + (100 - aggregated_shock_risk) * 0.10
    ), 15, 98))

    return (
        int(round(aggregated_score)),
        reliability_score,
        consensus_score,
        historical_consistency,
        float(aggregated_multiplier),
        int(round(aggregated_stabilization)),
        int(round(aggregated_shock_risk)),
    )


def _feature_vector(
    direction_strength: float,
    regime_fit: int,
    confirmation_score: int,
    composite_score: int,
    reliability_score: int,
    trend_context_score: int,
    trend_reliability_score: int,
    execution_risk: int,
    liquidity_score: int,
    setup_quality: int,
    relative_strength_score: int,
    candle_quality_score: int,
    level_proximity_score: int,
) -> list[float]:
    return [
        round(direction_strength, 3),
        float(regime_fit),
        float(confirmation_score),
        float(composite_score),
        float(reliability_score),
        float(trend_context_score),
        float(trend_reliability_score),
        float(execution_risk),
        float(liquidity_score),
        float(setup_quality),
        float(relative_strength_score),
        float(candle_quality_score),
        float(level_proximity_score),
    ]


def _load_optional_model() -> Any | None:
    model_path = getattr(app_settings, "SCANNER_META_MODEL_PATH", "") or os.getenv("SCANNER_META_MODEL_PATH", "")
    if not model_path:
        return None
    path = Path(model_path)
    if not path.exists():
        return None
    try:
        with path.open("rb") as fh:
            return pickle.load(fh)
    except Exception:
        return None


def _model_score(vector: list[float]) -> tuple[float | None, str]:
    model = _load_optional_model()
    if model is None:
        return None, "heuristic_v1"
    try:
        if hasattr(model, "predict_proba"):
            score = float(model.predict_proba([vector])[0][1] * 100)
        else:
            score = float(model.predict([vector])[0])
        return float(clamp(score)), getattr(model, "__class__", type(model)).__name__
    except Exception:
        return None, "heuristic_v1"


def build_scanner_context(
    *,
    result: StrategyResult,
    market_context: MarketContext | None,
    regime: RegimeInfo | None,
    scenario: Scenario | None,
    enhanced: EnhancedScore,
    primary_candles: list[Candle],
    confirmation_candles: list[Candle] | None,
    anchor_candles: list[Candle] | None,
    context_candles_by_tf: dict[str, list[Candle]],
    btc_closes: list[float] | None,
    settings: UserSignalSettings,
    now_ms: int,
) -> ScannerContext:
    direction = _direction_sign(result, enhanced)
    confirmation_regimes = [
        _detect_tf_regime(confirmation_candles),
        _detect_tf_regime(anchor_candles),
    ]
    regime_fit = _regime_fit(result, regime, scenario)
    confirmation_score = _confirmation_score(
        direction,
        regime,
        confirmation_regimes,
        confirmation_candles,
        anchor_candles,
    )
    (
        trend_context_score,
        trend_reliability_score,
        timeframe_consensus_score,
        historical_consistency_score,
        curve_multiplier,
        curve_stabilization_score,
        curve_shock_risk,
    ) = _aggregate_trend_context(
        primary_candles,
        anchor_candles,
        context_candles_by_tf,
        settings,
    )
    liquidity_score = _liquidity_score(primary_candles, market_context)
    relative_strength_score = _relative_strength_score(direction, confirmation_candles, btc_closes)
    candle_quality_score = _candle_quality_score(primary_candles, direction)
    level_proximity_score = _level_proximity_score(primary_candles, direction)
    trend_alignment = 100 - abs(trend_context_score - enhanced.direction)
    execution_risk = int(clamp(round(
        enhanced.risk * 0.48
        + (100 - liquidity_score) * 0.14
        + (100 - confirmation_score) * 0.10
        + (100 - trend_alignment) * 0.12
        + curve_shock_risk * 0.12
        + (100 - curve_stabilization_score) * 0.04,
    )))

    direction_strength = abs(enhanced.direction - 50) * 2
    contradiction_penalty = (
        sum(10 for item in enhanced.contradictions if item.severity == "strong")
        + sum(5 for item in enhanced.contradictions if item.severity == "moderate")
    )
    reliability_score = int(clamp(round(
        trend_reliability_score * 0.28
        + confirmation_score * 0.16
        + regime_fit * 0.12
        + timeframe_consensus_score * 0.10
        + historical_consistency_score * 0.08
        + curve_stabilization_score * 0.14
        + (100 - curve_shock_risk) * 0.10
        + liquidity_score * 0.05
        + (100 - execution_risk) * 0.07
        - contradiction_penalty * 0.45
    ), 10, 98))

    raw_composite = clamp(
        direction_strength * 0.06
        + regime_fit * 0.14
        + confirmation_score * 0.15
        + trend_alignment * 0.11
        + timeframe_consensus_score * 0.11
        + historical_consistency_score * 0.08
        + trend_context_score * 0.08
        + curve_stabilization_score * 0.08
        + (100 - curve_shock_risk) * 0.05
        + (100 - execution_risk) * 0.09
        + liquidity_score * 0.05
        + enhanced.setup_quality * 0.14
        + relative_strength_score * 0.05
        + candle_quality_score * 0.04
        + level_proximity_score * 0.03
        + (scenario.probability * 100 * 0.05 if scenario else 0.0),
    )
    blocker_penalty = (
        max(0, settings.min_regime_fit_score - regime_fit) * 0.18
        + max(0, settings.min_confirmation_score - confirmation_score) * 0.20
        + max(0, settings.min_setup_quality_score - enhanced.setup_quality) * 0.20
        + max(0, execution_risk - settings.max_execution_risk_score) * 0.18
        + max(0, settings.min_reliability_score - reliability_score) * 0.16
        + max(0, 58 - timeframe_consensus_score) * 0.12
        + max(0, curve_shock_risk - 65) * 0.12
        + contradiction_penalty
    )
    reliability_factor = clamp(0.32 + reliability_score / 100 * 0.68, 0.32, 1.0)
    composite_score = int(clamp(round(
        50 + ((raw_composite - blocker_penalty) - 50) * reliability_factor * curve_multiplier
    )))

    vector = _feature_vector(
        direction_strength,
        regime_fit,
        confirmation_score,
        composite_score,
        reliability_score,
        trend_context_score,
        trend_reliability_score,
        execution_risk,
        liquidity_score,
        enhanced.setup_quality,
        relative_strength_score,
        candle_quality_score,
        level_proximity_score,
    )

    heuristic_score = float(composite_score)

    model_score, model_name = _model_score(vector)
    calibrated_score = heuristic_score if model_score is None else clamp(heuristic_score * 0.72 + model_score * 0.28)
    calibrated_score = 50 + (calibrated_score - 50) * reliability_factor * curve_multiplier

    setup_type = infer_setup_type(result, regime, scenario)
    return ScannerContext(
        horizon=build_horizon_label(settings),
        setup_type=setup_type,
        regime=regime.regime if regime else "RANGE",
        regime_fit=regime_fit,
        confirmation_score=confirmation_score,
        composite_score=int(clamp(round(calibrated_score))),
        reliability_score=reliability_score,
        trend_context_score=trend_context_score,
        trend_reliability_score=trend_reliability_score,
        execution_risk=execution_risk,
        liquidity_score=liquidity_score,
        expected_holding_window=_expected_holding_window(setup_type),
        freshness_ms=_freshness_ms(primary_candles, now_ms),
        meta_score=round(float(calibrated_score), 2),
        model_name=model_name,
    )


def build_notrade_reasons(
    context: ScannerContext,
    enhanced: EnhancedScore,
    settings: UserSignalSettings,
) -> list[str]:
    reasons: list[str] = []

    if context.regime_fit < settings.min_regime_fit_score:
        reasons.append(f"Regime fit insuffisant ({context.regime_fit}/100)")
    if enhanced.setup_quality < settings.min_setup_quality_score:
        reasons.append(f"Setup trop faible ({enhanced.setup_quality}/100)")
    if context.confirmation_score < settings.min_confirmation_score:
        reasons.append(f"Confirmation multi-timeframe insuffisante ({context.confirmation_score}/100)")
    if context.reliability_score < settings.min_reliability_score:
        reasons.append(f"Fiabilite insuffisante ({context.reliability_score}/100)")
    if abs(context.trend_context_score - 50) >= 15 and context.trend_reliability_score >= 60:
        reasons.append(
            "Contexte HTF oppose"
            if (enhanced.direction >= 55 and context.trend_context_score <= 40) or (enhanced.direction <= 45 and context.trend_context_score >= 60)
            else f"Contexte HTF partiel ({context.trend_context_score}/100)"
        )
    if context.execution_risk > settings.max_execution_risk_score:
        reasons.append(f"Risque d'execution trop eleve ({context.execution_risk}/100)")
    if any(c.severity == "strong" for c in enhanced.contradictions):
        reasons.append("Contradiction forte detectee")
    if enhanced.actionability not in {"ACTIONABLE", "HIGH_CONVICTION"}:
        reasons.append(f"Signal non publiable ({enhanced.actionability.lower()})")

    return reasons


def apply_breadth_bonus(meta_score: float, direction: int, bullish_share: float) -> float:
    if direction == 0:
        return meta_score
    if direction > 0 and bullish_share >= 0.60:
        return round(float(clamp(meta_score + 4, 0, 100)), 2)
    if direction < 0 and bullish_share <= 0.40:
        return round(float(clamp(meta_score + 4, 0, 100)), 2)
    if direction > 0 and bullish_share <= 0.35:
        return round(float(clamp(meta_score - 5, 0, 100)), 2)
    if direction < 0 and bullish_share >= 0.65:
        return round(float(clamp(meta_score - 5, 0, 100)), 2)
    return round(float(meta_score), 2)
