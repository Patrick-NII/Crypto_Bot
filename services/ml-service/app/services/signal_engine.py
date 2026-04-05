"""Trading Signal Engine — V1 (backward-compat) + V2 (advanced multi-dimensional).

generate_signal()          — V1, unchanged interface
generate_advanced_signal() — V2, returns SignalResult with 5 dimensions
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from app.core.models import Action, IndicatorSnapshot as IndicatorResult, TradingSignal
from app.indicators.rsi import calc_rsi, rsi_raw
from app.indicators.macd import calc_macd, macd_raw
from app.indicators.bollinger import calc_bollinger, bollinger_raw
from app.indicators.ema_cross import calc_ema_cross
from app.indicators.volume import calc_volume_profile, volume_ratio
from app.indicators.atr import atr_raw
from app.indicators.math_utils import sma as _sma, ema as _ema, std as _std

logger = logging.getLogger(__name__)

__all__ = [
    "Action", "IndicatorResult", "TradingSignal",
    "calc_rsi", "calc_macd", "calc_bollinger", "calc_ema_cross", "calc_volume_profile",
    "generate_signal", "generate_advanced_signal", "SignalResult",
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# V2 Data Structures
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class Contradiction:
    description: str
    severity: str        # mild, moderate, strong
    penalty_conf: int    # how much to subtract from confidence
    penalty_setup: int   # how much to subtract from setup quality


@dataclass
class TradePlan:
    side: str            # buy, sell, none
    entry_zone: str
    invalidation_zone: str
    target_zone: str
    risk_reward: str
    validity: str
    style: str           # scalping, intraday, swing


@dataclass
class TimeframeBias:
    micro: str           # bullish, bearish, neutral
    higher: str          # bullish, bearish, neutral
    alignment: str       # aligned, counter_trend, mixed


@dataclass
class SignalResult:
    symbol: str
    # 5 core dimensions
    direction_score: int        # 0-100
    confidence_score: int       # 0-100
    risk_score: int             # 0-100 (higher = riskier)
    setup_quality_score: int    # 0-100
    actionability: str          # IGNORE, WATCH, ACTIONABLE, HIGH_CONVICTION
    # Context
    action: str                 # STRONG_BUY..STRONG_SELL
    direction_label: str
    market_regime: str          # TRENDING, RANGING, COMPRESSED, EXPANDING, CHAOTIC
    signal_context: str         # trend_aligned, counter_trend, mixed, breakout_candidate, exhaustion_zone
    timeframe_bias: TimeframeBias
    # Details
    sub_scores: dict[str, int] = field(default_factory=dict)  # momentum, trend, volatility, volume, structure
    reasons: list[str] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    trade_plan: TradePlan | None = None
    # Raw for legacy compat
    indicators: list[IndicatorResult] = field(default_factory=list)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# V1 — generate_signal (unchanged)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_signal(
    symbol: str,
    closes: list[float],
    volumes: list[float] | None = None,
) -> TradingSignal:
    indicators = [calc_rsi(closes), calc_macd(closes), calc_bollinger(closes), calc_ema_cross(closes)]
    if volumes and len(volumes) >= 20:
        indicators.append(calc_volume_profile(volumes))

    total_weight = sum(ind.weight for ind in indicators)
    weighted_score = sum(ind.signal * ind.weight for ind in indicators) / total_weight if total_weight > 0 else 0

    if weighted_score > 0.6: action = Action.STRONG_BUY
    elif weighted_score > 0.3: action = Action.BUY
    elif weighted_score > 0.1: action = Action.ACCUMULATE
    elif weighted_score > -0.1: action = Action.HOLD
    elif weighted_score > -0.3: action = Action.REDUCE
    elif weighted_score > -0.6: action = Action.SELL
    else: action = Action.STRONG_SELL

    bullish = [i for i in indicators if i.signal > 0.2]
    bearish = [i for i in indicators if i.signal < -0.2]
    parts = []
    if bullish: parts.append(f"Bullish: {', '.join(i.name for i in bullish)}")
    if bearish: parts.append(f"Bearish: {', '.join(i.name for i in bearish)}")

    return TradingSignal(
        symbol=symbol, action=action,
        confidence=round(min(abs(weighted_score), 1.0), 2),
        score=round(weighted_score, 3),
        indicators=indicators,
        reasoning=". ".join(parts) or "Mixed signals — hold position",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# V2 — generate_advanced_signal
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_advanced_signal(
    symbol: str,
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
    higher_tf_closes: list[float] | None = None,
) -> SignalResult:
    """V2 advanced signal with 5 dimensions, contradictions, trade plan."""

    if len(closes) < 20:
        return _empty_result(symbol)

    h = highs or closes
    l = lows or closes
    v = volumes or []

    # ── Compute all indicators ──
    indicators = [calc_rsi(closes), calc_macd(closes), calc_bollinger(closes), calc_ema_cross(closes)]
    if len(v) >= 20:
        indicators.append(calc_volume_profile(v))

    # ── Sub-scores (0-100 each) ──
    rsi_val = rsi_raw(closes)
    _, _, macd_hist = macd_raw(closes)
    _, _, _, bb_bw = bollinger_raw(closes)
    vol_rat = volume_ratio(v) if len(v) >= 20 else 1.0

    momentum_score = _compute_momentum(rsi_val, macd_hist)
    trend_score = _compute_trend(closes)
    volume_score = _compute_volume(vol_rat)
    volatility_score = _compute_volatility(closes, bb_bw)
    structure_score = _compute_structure(closes, h, l)

    sub_scores = {
        "momentum": momentum_score,
        "trend": trend_score,
        "volume": volume_score,
        "volatility": volatility_score,
        "structure": structure_score,
    }

    # ── Direction score (weighted composite) ──
    direction_score = _clamp(round(
        momentum_score * 0.30 +
        trend_score * 0.25 +
        structure_score * 0.20 +
        volume_score * 0.15 +
        volatility_score * 0.10
    ))

    # ── Market regime ──
    market_regime = _detect_regime(closes, bb_bw, volatility_score)

    # ── Multi-timeframe bias ──
    micro_bias = "bullish" if direction_score >= 55 else "bearish" if direction_score <= 45 else "neutral"
    higher_bias = _compute_higher_tf_bias(higher_tf_closes) if higher_tf_closes else "neutral"
    if micro_bias == higher_bias:
        alignment = "aligned"
    elif micro_bias == "neutral" or higher_bias == "neutral":
        alignment = "mixed"
    else:
        alignment = "counter_trend"
    tf_bias = TimeframeBias(micro=micro_bias, higher=higher_bias, alignment=alignment)

    # ── Signal context ──
    signal_context = _detect_signal_context(direction_score, market_regime, alignment)

    # ── Contradictions ──
    contradictions = _detect_contradictions(
        rsi_val, macd_hist, vol_rat, bb_bw,
        direction_score, trend_score, momentum_score, volume_score,
        alignment, market_regime,
    )

    # ── Confidence score ──
    confidence_score = _compute_confidence(indicators, contradictions)

    # ── Risk score ──
    risk_score = _compute_risk(volatility_score, contradictions, direction_score, alignment, rsi_val)

    # ── Setup quality ──
    setup_quality_score = _compute_setup_quality(confidence_score, risk_score, contradictions, volume_score, structure_score)

    # ── Actionability ──
    actionability = _compute_actionability(direction_score, confidence_score, risk_score, setup_quality_score)

    # ── Direction label + action ──
    direction_label = _direction_label(direction_score)
    action = _action_from_direction(direction_score)

    # ── Reasons ──
    reasons = _build_reasons(sub_scores, contradictions, market_regime, rsi_val, vol_rat)

    # ── Trade plan ──
    trade_plan = _build_trade_plan(direction_score, actionability, closes, h, l, market_regime)

    return SignalResult(
        symbol=symbol,
        direction_score=direction_score,
        confidence_score=confidence_score,
        risk_score=risk_score,
        setup_quality_score=setup_quality_score,
        actionability=actionability,
        action=action,
        direction_label=direction_label,
        market_regime=market_regime,
        signal_context=signal_context,
        timeframe_bias=tf_bias,
        sub_scores=sub_scores,
        reasons=reasons,
        contradictions=contradictions,
        trade_plan=trade_plan,
        indicators=indicators,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Sub-score computations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _clamp(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, v))


def _compute_momentum(rsi: float, macd_hist: float) -> int:
    """RSI position + MACD histogram direction → 0-100."""
    # RSI contribution: 30=oversold→bullish, 70=overbought→bearish
    if rsi < 25: rsi_c = 85
    elif rsi < 35: rsi_c = 70
    elif rsi < 45: rsi_c = 55
    elif rsi < 55: rsi_c = 50
    elif rsi < 65: rsi_c = 45
    elif rsi < 75: rsi_c = 30
    else: rsi_c = 15

    # MACD histogram: positive = bullish momentum
    macd_c = 50 + _clamp(round(macd_hist * 200), -40, 40)

    return _clamp(round(rsi_c * 0.55 + macd_c * 0.45))


def _compute_trend(closes: list[float]) -> int:
    """EMA alignment + slope → 0-100."""
    if len(closes) < 25:
        return 50

    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    price = closes[-1]

    # EMA alignment
    above_fast = price > ema9[-1]
    above_slow = price > ema21[-1]
    fast_above_slow = ema9[-1] > ema21[-1]

    alignment_score = 50
    if above_fast and above_slow and fast_above_slow:
        alignment_score = 75
    elif not above_fast and not above_slow and not fast_above_slow:
        alignment_score = 25
    elif fast_above_slow:
        alignment_score = 60
    elif not fast_above_slow:
        alignment_score = 40

    # Slope of EMA21 (last 5 values)
    if len(ema21) >= 5:
        slope = (ema21[-1] - ema21[-5]) / (ema21[-5] + 1e-10) * 100
        slope_score = 50 + _clamp(round(slope * 10), -30, 30)
    else:
        slope_score = 50

    return _clamp(round(alignment_score * 0.6 + slope_score * 0.4))


def _compute_volume(vol_ratio: float) -> int:
    """Volume ratio → 0-100 confirmation score."""
    if vol_ratio >= 3.0: return 90
    if vol_ratio >= 2.0: return 75
    if vol_ratio >= 1.5: return 65
    if vol_ratio >= 1.0: return 50
    if vol_ratio >= 0.7: return 35
    return 20


def _compute_volatility(closes: list[float], bb_bandwidth: float) -> int:
    """Volatility regime → 0-100. Higher = more volatile (riskier)."""
    if len(closes) < 20:
        return 50

    returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes)) if closes[i-1] > 0]
    if not returns:
        return 50

    recent = returns[-20:]
    realized_vol = math.sqrt(sum(r*r for r in recent) / len(recent)) * 100  # as pct

    vol_score = 50
    if realized_vol > 5.0: vol_score = 90
    elif realized_vol > 3.0: vol_score = 75
    elif realized_vol > 1.5: vol_score = 55
    elif realized_vol > 0.5: vol_score = 40
    else: vol_score = 20

    # BB bandwidth adds compression/expansion info
    if bb_bandwidth < 0.01:
        vol_score = min(vol_score, 25)  # compressed
    elif bb_bandwidth > 0.06:
        vol_score = max(vol_score, 70)  # expanding

    return _clamp(vol_score)


def _compute_structure(closes: list[float], highs: list[float], lows: list[float]) -> int:
    """Price structure: higher highs/lows vs lower highs/lows → 0-100."""
    n = min(len(closes), len(highs), len(lows))
    if n < 10:
        return 50

    # Check last 3 swing points
    recent_highs = highs[-10:]
    recent_lows = lows[-10:]

    # Simple: compare last third vs first third
    first_h = max(recent_highs[:4])
    last_h = max(recent_highs[-4:])
    first_l = min(recent_lows[:4])
    last_l = min(recent_lows[-4:])

    hh = last_h > first_h  # higher highs
    hl = last_l > first_l  # higher lows
    lh = last_h < first_h  # lower highs
    ll = last_l < first_l  # lower lows

    if hh and hl: return 75  # bullish structure
    if lh and ll: return 25  # bearish structure
    if hh and ll: return 50  # range / confusion
    if lh and hl: return 50  # compression
    if hh: return 60
    if ll: return 40
    return 50


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Regime, context, contradictions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _detect_regime(closes: list[float], bb_bw: float, vol_score: int) -> str:
    if len(closes) < 20:
        return "UNKNOWN"
    change_20 = (closes[-1] - closes[-20]) / closes[-20]
    if vol_score >= 80:
        return "CHAOTIC"
    if bb_bw < 0.012:
        return "COMPRESSED"
    if vol_score >= 65:
        return "EXPANDING"
    if abs(change_20) >= 0.05:
        return "TRENDING"
    return "RANGING"


def _detect_signal_context(direction: int, regime: str, alignment: str) -> str:
    if alignment == "counter_trend":
        return "counter_trend"
    if regime == "COMPRESSED":
        return "breakout_candidate"
    if direction >= 75 or direction <= 25:
        return "exhaustion_zone"
    if alignment == "aligned" and regime == "TRENDING":
        return "trend_aligned"
    return "mixed"


def _detect_contradictions(
    rsi: float, macd_hist: float, vol_ratio: float, bb_bw: float,
    direction: int, trend: int, momentum: int, volume: int,
    alignment: str, regime: str,
) -> list[Contradiction]:
    cs: list[Contradiction] = []

    # RSI vs MACD direction disagree
    rsi_bullish = rsi < 40
    rsi_bearish = rsi > 60
    macd_bullish = macd_hist > 0
    macd_bearish = macd_hist < 0
    if (rsi_bullish and macd_bearish) or (rsi_bearish and macd_bullish):
        cs.append(Contradiction("RSI et MACD en desaccord", "moderate", 10, 8))

    # Directional signal without volume
    if abs(direction - 50) > 15 and volume < 35:
        cs.append(Contradiction("Signal directionnel sans confirmation volume", "moderate", 8, 10))

    # Momentum vs trend divergence
    if abs(momentum - trend) > 30:
        cs.append(Contradiction("Momentum et tendance divergent", "strong", 15, 12))

    # Breakout without expansion
    if regime == "COMPRESSED" and abs(direction - 50) > 20 and bb_bw < 0.015:
        cs.append(Contradiction("Signal breakout sans expansion BB", "moderate", 8, 8))

    # Counter-trend signal
    if alignment == "counter_trend" and abs(direction - 50) > 15:
        cs.append(Contradiction("Signal contre la tendance higher TF", "strong", 12, 10))

    # Extreme RSI + volume fade
    if (rsi > 80 or rsi < 20) and vol_ratio < 0.8:
        cs.append(Contradiction("RSI extreme sans volume — epuisement probable", "mild", 5, 5))

    return cs


def _compute_higher_tf_bias(higher_closes: list[float]) -> str:
    if not higher_closes or len(higher_closes) < 20:
        return "neutral"
    ema9 = _ema(higher_closes, 9)
    ema21 = _ema(higher_closes, 21)
    if ema9[-1] > ema21[-1]:
        return "bullish"
    if ema9[-1] < ema21[-1]:
        return "bearish"
    return "neutral"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Confidence, Risk, Setup Quality, Actionability
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _compute_confidence(indicators: list[IndicatorResult], contradictions: list[Contradiction]) -> int:
    if not indicators:
        return 20
    signals = [i.signal for i in indicators]
    pos = sum(1 for s in signals if s > 0.15)
    neg = sum(1 for s in signals if s < -0.15)
    total = max(len(signals), 1)
    agreement = max(pos, neg) / total
    conf = _clamp(round(agreement * 100))
    for c in contradictions:
        conf -= c.penalty_conf
    return _clamp(conf)


def _compute_risk(vol: int, contradictions: list[Contradiction], direction: int, alignment: str, rsi: float) -> int:
    risk = 25  # baseline
    if vol >= 80: risk += 25
    elif vol >= 65: risk += 12
    for c in contradictions:
        risk += 6 if c.severity == "strong" else 3
    if direction >= 85 or direction <= 15:
        risk += 10  # extended
    if alignment == "counter_trend":
        risk += 10
    if rsi > 80 or rsi < 20:
        risk += 8  # extreme RSI
    return _clamp(risk)


def _compute_setup_quality(conf: int, risk: int, contradictions: list[Contradiction], volume: int, structure: int) -> int:
    quality = round(conf * 0.35 + structure * 0.3 + volume * 0.2 + (100 - risk) * 0.15)
    for c in contradictions:
        quality -= c.penalty_setup
    return _clamp(quality)


def _compute_actionability(direction: int, confidence: int, risk: int, setup: int) -> str:
    # IGNORE
    if confidence < 35 or setup < 30 or risk > 85:
        return "IGNORE"
    # HIGH_CONVICTION
    if confidence >= 75 and risk <= 55 and setup >= 70 and abs(direction - 50) >= 20:
        return "HIGH_CONVICTION"
    # ACTIONABLE
    if confidence >= 60 and risk <= 70 and setup >= 55 and abs(direction - 50) >= 12:
        return "ACTIONABLE"
    # WATCH
    if confidence >= 35:
        return "WATCH"
    return "IGNORE"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Labels, Reasons, Trade Plan
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _direction_label(s: int) -> str:
    if s >= 80: return "Forte impulsion acheteuse"
    if s >= 65: return "Biais acheteur"
    if s >= 55: return "Leger biais haussier"
    if s >= 45: return "Neutre / attente"
    if s >= 35: return "Leger biais baissier"
    if s >= 20: return "Biais vendeur"
    return "Forte pression vendeuse"


def _action_from_direction(s: int) -> str:
    if s >= 80: return "STRONG_BUY"
    if s >= 65: return "BUY"
    if s >= 55: return "ACCUMULATE"
    if s >= 45: return "HOLD"
    if s >= 35: return "REDUCE"
    if s >= 20: return "SELL"
    return "STRONG_SELL"


SUB_LABELS = {
    "momentum": {(0,20):"Epuisement vendeur",(21,40):"Pression baissiere",(41,59):"Neutre",(60,79):"En acceleration",(80,100):"Impulsion forte"},
    "trend": {(0,20):"Baissiere forte",(21,40):"Fragile",(41,59):"Consolidation",(60,79):"Haussiere",(80,100):"Tres forte"},
    "volume": {(0,20):"Aucune conviction",(21,40):"Faible",(41,59):"Normal",(60,79):"Solide",(80,100):"Spike"},
    "volatility": {(0,20):"Calme",(21,40):"Faible",(41,59):"Moderee",(60,79):"Elevee",(80,100):"Extreme"},
    "structure": {(0,20):"Cassee baissiere",(21,40):"Fragile",(41,59):"Neutre",(60,79):"Constructive",(80,100):"Forte haussiere"},
}


def _sub_label(cat: str, score: int) -> str:
    for (lo, hi), label in SUB_LABELS.get(cat, {}).items():
        if lo <= score <= hi:
            return label
    return "Neutre"


def _build_reasons(sub_scores: dict[str, int], contradictions: list[Contradiction], regime: str, rsi: float, vol_ratio: float) -> list[str]:
    reasons: list[str] = []

    # Top insight per sub-score
    for cat in ["momentum", "trend", "structure"]:
        s = sub_scores.get(cat, 50)
        if abs(s - 50) > 10:
            reasons.append(f"{cat.capitalize()} : {_sub_label(cat, s)} ({s})")

    # Volume insight
    vs = sub_scores.get("volume", 50)
    if vs < 35:
        reasons.append(f"Volume non confirme ({vol_ratio:.1f}x)")
    elif vs >= 70:
        reasons.append(f"Volume confirme ({vol_ratio:.1f}x)")

    # RSI extreme
    if rsi > 75:
        reasons.append(f"RSI en surachat ({rsi:.0f})")
    elif rsi < 25:
        reasons.append(f"RSI en survente ({rsi:.0f})")

    # Regime
    if regime in ("CHAOTIC", "EXPANDING"):
        reasons.append(f"Regime {regime.lower()} — prudence sizing")

    # Contradictions
    for c in contradictions:
        if c.severity == "strong":
            reasons.append(f"Attention: {c.description}")

    return reasons[:4]


def _build_trade_plan(direction: int, actionability: str, closes: list[float], highs: list[float], lows: list[float], regime: str) -> TradePlan | None:
    if actionability == "IGNORE" or abs(direction - 50) < 10:
        return None

    price = closes[-1]
    bullish = direction >= 55

    # ATR-like: average of recent true ranges
    trs: list[float] = []
    for i in range(1, min(15, len(closes))):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    atr = sum(trs) / len(trs) if trs else price * 0.01

    # Recent support/resistance from last 20 bars
    recent_h = highs[-20:] if len(highs) >= 20 else highs
    recent_l = lows[-20:] if len(lows) >= 20 else lows
    resistance = max(recent_h)
    support = min(recent_l)

    multiplier = 2.0 if actionability == "HIGH_CONVICTION" else 1.5
    stop_dist = round(atr * multiplier, 2)

    if bullish:
        entry = f"{price:.2f}"
        invalidation = f"{price - stop_dist:.2f} (-{stop_dist:.2f})"
        target = f"{min(resistance, price + stop_dist * 2):.2f}"
        rr = f"{min(2.0 * multiplier, (resistance - price) / stop_dist if stop_dist > 0 else 1):.1f}:1"
    else:
        entry = f"{price:.2f}"
        invalidation = f"{price + stop_dist:.2f} (+{stop_dist:.2f})"
        target = f"{max(support, price - stop_dist * 2):.2f}"
        rr = f"{min(2.0 * multiplier, (price - support) / stop_dist if stop_dist > 0 else 1):.1f}:1"

    validity = "5-15 min" if regime != "RANGING" else "15-60 min"
    style = "scalping"  # TODO: derive from settings

    return TradePlan(
        side="buy" if bullish else "sell",
        entry_zone=entry,
        invalidation_zone=invalidation,
        target_zone=target,
        risk_reward=rr,
        validity=validity,
        style=style,
    )


def _empty_result(symbol: str) -> SignalResult:
    return SignalResult(
        symbol=symbol, direction_score=50, confidence_score=0,
        risk_score=50, setup_quality_score=0, actionability="IGNORE",
        action="HOLD", direction_label="Donnees insuffisantes",
        market_regime="UNKNOWN", signal_context="mixed",
        timeframe_bias=TimeframeBias("neutral", "neutral", "mixed"),
        reasons=["Donnees insuffisantes"],
    )
