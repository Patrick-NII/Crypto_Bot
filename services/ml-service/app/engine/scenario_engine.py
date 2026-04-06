"""Scenario generation engine — produces multiple weighted trading scenarios.

Instead of one signal, the engine generates 2-3 plausible market outcomes
(CONTINUATION, MEAN_REVERSION, FAKEOUT, REVERSAL) and scores each against
current conditions. The primary scenario drives the final trading decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.models import Candle, IndicatorSnapshot, RegimeInfo, Scenario
from app.indicators.math_utils import ema


# ── Minimum probability to include a scenario ──
_MIN_PROBABILITY = 0.15


def generate_scenarios(
    regime: RegimeInfo,
    indicators: list[IndicatorSnapshot],
    candles: list[Candle],
    confirmation_candles: Optional[list[Candle]] = None,
) -> list[Scenario]:
    """Generate 1-3 weighted scenarios based on regime and indicators."""
    templates = _REGIME_TEMPLATES.get(regime.regime, _REGIME_TEMPLATES["RANGE"])
    scored: list[Scenario] = []

    ind_map = {i.name: i for i in indicators}
    closes = [c.close for c in candles] if candles else []

    for template in templates:
        prob, met, unmet, reasoning = template.scorer(ind_map, closes, candles, regime)
        if prob < _MIN_PROBABILITY:
            continue
        scored.append(Scenario(
            name=template.name,
            direction=template.direction_fn(ind_map, closes),
            probability=round(min(prob, 1.0), 3),
            reasoning=reasoning,
            conditions_met=met,
            conditions_unmet=unmet,
            weight_profile=dict(template.weight_profile),
        ))

    scored.sort(key=lambda s: s.probability, reverse=True)
    return scored[:3]


def select_primary_scenario(scenarios: list[Scenario]) -> Optional[Scenario]:
    """Return the highest-probability scenario."""
    return scenarios[0] if scenarios else None


# ═══════════════════════════════════════════════════════════════════
# Scenario templates
# ═══════════════════════════════════════════════════════════════════

ScorerResult = tuple[float, list[str], list[str], str]  # (probability, met, unmet, reasoning)


@dataclass
class _Template:
    name: str
    scorer: object  # Callable
    direction_fn: object  # Callable
    weight_profile: dict[str, float]


def _direction_from_momentum(ind_map: dict, closes: list[float]) -> str:
    """Infer direction from indicator consensus."""
    bullish = 0
    bearish = 0
    for ind in ind_map.values():
        if ind.signal > 0.1:
            bullish += 1
        elif ind.signal < -0.1:
            bearish += 1
    return "bullish" if bullish >= bearish else "bearish"


def _direction_opposite(ind_map: dict, closes: list[float]) -> str:
    d = _direction_from_momentum(ind_map, closes)
    return "bearish" if d == "bullish" else "bullish"


def _direction_bullish(_ind: dict, _c: list[float]) -> str:
    return "bullish"


def _direction_bearish(_ind: dict, _c: list[float]) -> str:
    return "bearish"


# ── RANGE scenarios ──

def _score_mean_reversion(ind_map: dict, closes: list, candles: list, regime: RegimeInfo) -> ScorerResult:
    prob = 0.30  # base
    met, unmet = [], []

    rsi = ind_map.get("RSI")
    bb = ind_map.get("Bollinger")

    if rsi and (rsi.value > 70 or rsi.value < 30):
        prob += 0.25
        met.append(f"RSI extreme ({rsi.value:.0f})")
    elif rsi and (rsi.value > 60 or rsi.value < 40):
        prob += 0.10
        met.append(f"RSI approaching extreme ({rsi.value:.0f})")
    else:
        unmet.append("RSI not at extreme")

    if bb and (bb.value > 0.85 or bb.value < 0.15):
        prob += 0.20
        met.append("Price at Bollinger Band extreme")
    else:
        unmet.append("Price inside bands")

    vol = ind_map.get("Volume")
    if vol and vol.value < 1.0:
        prob += 0.10
        met.append("Low volume (range confirmation)")

    return prob, met, unmet, "Mean reversion play — extreme indicator readings in range-bound market"


def _score_range_break(ind_map: dict, closes: list, candles: list, regime: RegimeInfo) -> ScorerResult:
    prob = 0.15  # low base in range
    met, unmet = [], []

    vol = ind_map.get("Volume")
    if vol and vol.value > 1.5:
        prob += 0.20
        met.append(f"Rising volume ({vol.value:.1f}x)")
    else:
        unmet.append("Volume not rising")

    macd = ind_map.get("MACD")
    if macd and abs(macd.signal) > 0.5:
        prob += 0.15
        met.append("MACD momentum building")
    else:
        unmet.append("MACD neutral")

    return prob, met, unmet, "Potential range breakout — watch for volume confirmation"


# ── BREAKOUT scenarios ──

def _score_breakout_continuation(ind_map: dict, closes: list, candles: list, regime: RegimeInfo) -> ScorerResult:
    prob = 0.40  # moderate-high base in breakout
    met, unmet = [], []

    vol = ind_map.get("Volume")
    if vol and vol.value >= 1.8:
        prob += 0.25
        met.append(f"Strong volume confirmation ({vol.value:.1f}x)")
    elif vol and vol.value >= 1.3:
        prob += 0.10
        met.append("Moderate volume support")
    else:
        prob -= 0.10
        unmet.append("Weak volume — breakout not confirmed")

    ema_ind = ind_map.get("EMA Cross")
    if ema_ind and abs(ema_ind.signal) > 0.3:
        prob += 0.15
        met.append("EMA alignment supports breakout direction")
    else:
        unmet.append("EMAs not aligned")

    if regime.confidence > 0.6:
        prob += 0.10
        met.append("High regime confidence")

    return prob, met, unmet, "Breakout continuation — volume and momentum confirm the move"


def _score_fakeout(ind_map: dict, closes: list, candles: list, regime: RegimeInfo) -> ScorerResult:
    prob = 0.20  # base
    met, unmet = [], []

    vol = ind_map.get("Volume")
    if vol and vol.value < 1.2:
        prob += 0.25
        met.append("Low volume on breakout — fakeout risk")
    else:
        unmet.append("Volume supports breakout")

    rsi = ind_map.get("RSI")
    if rsi and rsi.value > 80:
        prob += 0.15
        met.append("RSI extreme — breakout exhaustion risk")
    elif rsi and rsi.value < 20:
        prob += 0.15
        met.append("RSI extreme — breakdown exhaustion risk")
    else:
        unmet.append("RSI not extreme")

    return prob, met, unmet, "Possible fakeout — volume not confirming, may return to range"


# ── TREND_UP scenarios ──

def _score_trend_continuation_up(ind_map: dict, closes: list, candles: list, regime: RegimeInfo) -> ScorerResult:
    prob = 0.45  # high base in established trend
    met, unmet = [], []

    ema_ind = ind_map.get("EMA Cross")
    if ema_ind and ema_ind.signal > 0.2:
        prob += 0.15
        met.append("EMAs bullish — trend intact")
    else:
        prob -= 0.10
        unmet.append("EMA structure weakening")

    rsi = ind_map.get("RSI")
    if rsi and 40 <= rsi.value <= 65:
        prob += 0.15
        met.append("RSI in pullback zone — buy opportunity")
    elif rsi and rsi.value > 65:
        prob += 0.05
        met.append("RSI elevated but trend continues")

    bb = ind_map.get("Bollinger")
    if bb and 0.2 <= bb.value <= 0.5:
        prob += 0.10
        met.append("Price pulling back within trend channel")

    return prob, met, unmet, "Trend continuation — buying the pullback in established uptrend"


def _score_exhaustion_top(ind_map: dict, closes: list, candles: list, regime: RegimeInfo) -> ScorerResult:
    prob = 0.15  # low base (trend is assumed strong)
    met, unmet = [], []

    rsi = ind_map.get("RSI")
    if rsi and rsi.value > 80:
        prob += 0.20
        met.append(f"RSI overbought ({rsi.value:.0f})")

    macd = ind_map.get("MACD")
    if macd and macd.signal < 0:
        prob += 0.15
        met.append("MACD turning negative — momentum fading")
    elif macd and macd.value < 0:  # histogram shrinking
        prob += 0.10
        met.append("MACD histogram declining")
    else:
        unmet.append("MACD still bullish")

    return prob, met, unmet, "Possible trend exhaustion — momentum weakening at highs"


# ── TREND_DOWN scenarios ──

def _score_trend_continuation_down(ind_map: dict, closes: list, candles: list, regime: RegimeInfo) -> ScorerResult:
    prob = 0.45
    met, unmet = [], []

    ema_ind = ind_map.get("EMA Cross")
    if ema_ind and ema_ind.signal < -0.2:
        prob += 0.15
        met.append("EMAs bearish — downtrend intact")
    else:
        prob -= 0.10
        unmet.append("EMA structure improving")

    rsi = ind_map.get("RSI")
    if rsi and 35 <= rsi.value <= 60:
        prob += 0.15
        met.append("RSI in rally zone — sell opportunity")
    elif rsi and rsi.value < 35:
        prob += 0.05

    return prob, met, unmet, "Downtrend continuation — selling the rally"


def _score_reversal_bounce(ind_map: dict, closes: list, candles: list, regime: RegimeInfo) -> ScorerResult:
    prob = 0.15
    met, unmet = [], []

    rsi = ind_map.get("RSI")
    if rsi and rsi.value < 20:
        prob += 0.20
        met.append(f"RSI deeply oversold ({rsi.value:.0f})")

    vol = ind_map.get("Volume")
    if vol and vol.value > 2.5:
        prob += 0.15
        met.append("Volume climax — capitulation signal")
    else:
        unmet.append("No volume climax")

    return prob, met, unmet, "Possible reversal bounce — extreme oversold conditions"


# ── EXHAUSTION scenarios ──

def _score_reversal(ind_map: dict, closes: list, candles: list, regime: RegimeInfo) -> ScorerResult:
    prob = 0.35
    met, unmet = [], []

    rsi = ind_map.get("RSI")
    if rsi and (rsi.value > 75 or rsi.value < 25):
        prob += 0.20
        met.append(f"RSI extreme ({rsi.value:.0f}) — reversal zone")

    if regime.momentum_state == "decelerating":
        prob += 0.15
        met.append("Momentum decelerating")
    else:
        unmet.append("Momentum not yet decelerating")

    if regime.structure == "MIXED":
        prob += 0.10
        met.append("Structure breaking down")

    return prob, met, unmet, "Reversal scenario — exhaustion signals across multiple indicators"


def _score_weak_continuation(ind_map: dict, closes: list, candles: list, regime: RegimeInfo) -> ScorerResult:
    prob = 0.20
    met, unmet = [], []

    ema_ind = ind_map.get("EMA Cross")
    if ema_ind and abs(ema_ind.signal) > 0.3:
        prob += 0.15
        met.append("EMAs still trending")
    else:
        unmet.append("EMA flattening")

    vol = ind_map.get("Volume")
    if vol and vol.value > 1.0:
        prob += 0.10
        met.append("Volume still present")
    else:
        prob -= 0.05
        unmet.append("Volume fading")

    return prob, met, unmet, "Weak continuation — trend persists but slowing, reduce exposure"


# ═══════════════════════════════════════════════════════════════════
# Template registry
# ═══════════════════════════════════════════════════════════════════

_REGIME_TEMPLATES: dict[str, list[_Template]] = {
    "RANGE": [
        _Template(
            name="MEAN_REVERSION",
            scorer=_score_mean_reversion,
            direction_fn=_direction_opposite,
            weight_profile={"momentum": 0.15, "trend": 0.10, "volatility": 0.15, "volume": 0.25, "structure": 0.35},
        ),
        _Template(
            name="RANGE_BREAK",
            scorer=_score_range_break,
            direction_fn=_direction_from_momentum,
            weight_profile={"momentum": 0.25, "trend": 0.15, "volatility": 0.10, "volume": 0.30, "structure": 0.20},
        ),
    ],
    "BREAKOUT": [
        _Template(
            name="CONTINUATION",
            scorer=_score_breakout_continuation,
            direction_fn=_direction_from_momentum,
            weight_profile={"momentum": 0.30, "trend": 0.15, "volatility": 0.10, "volume": 0.30, "structure": 0.15},
        ),
        _Template(
            name="FAKEOUT",
            scorer=_score_fakeout,
            direction_fn=_direction_opposite,
            weight_profile={"momentum": 0.15, "trend": 0.10, "volatility": 0.20, "volume": 0.35, "structure": 0.20},
        ),
    ],
    "TREND_UP": [
        _Template(
            name="CONTINUATION",
            scorer=_score_trend_continuation_up,
            direction_fn=_direction_bullish,
            weight_profile={"momentum": 0.20, "trend": 0.35, "volatility": 0.10, "volume": 0.20, "structure": 0.15},
        ),
        _Template(
            name="EXHAUSTION_TOP",
            scorer=_score_exhaustion_top,
            direction_fn=_direction_bearish,
            weight_profile={"momentum": 0.25, "trend": 0.15, "volatility": 0.20, "volume": 0.15, "structure": 0.25},
        ),
    ],
    "TREND_DOWN": [
        _Template(
            name="CONTINUATION",
            scorer=_score_trend_continuation_down,
            direction_fn=_direction_bearish,
            weight_profile={"momentum": 0.20, "trend": 0.35, "volatility": 0.10, "volume": 0.20, "structure": 0.15},
        ),
        _Template(
            name="REVERSAL",
            scorer=_score_reversal_bounce,
            direction_fn=_direction_bullish,
            weight_profile={"momentum": 0.25, "trend": 0.10, "volatility": 0.20, "volume": 0.25, "structure": 0.20},
        ),
    ],
    "EXHAUSTION": [
        _Template(
            name="REVERSAL",
            scorer=_score_reversal,
            direction_fn=_direction_opposite,
            weight_profile={"momentum": 0.15, "trend": 0.10, "volatility": 0.25, "volume": 0.15, "structure": 0.35},
        ),
        _Template(
            name="WEAK_CONTINUATION",
            scorer=_score_weak_continuation,
            direction_fn=_direction_from_momentum,
            weight_profile={"momentum": 0.25, "trend": 0.30, "volatility": 0.15, "volume": 0.15, "structure": 0.15},
        ),
    ],
}
