"""Enhanced Scoring V2 — multi-dimensional decision engine.

5 independent scoring dimensions:
  1. DirectionScore (0-100) — where is price going?
  2. ConfidenceScore (0-100) — how coherent is the signal?
  3. RiskScore (0-100) — how dangerous is the entry? (higher = riskier)
  4. SetupQualityScore (0-100) — how clean is the setup?
  5. Actionability — categorical: IGNORE / WATCH / ACTIONABLE / HIGH_CONVICTION

Plus: MarketRegime, SignalContext, contradiction detection, trade plan stub.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.models import IndicatorSnapshot, MarketContext, RegimeInfo, Scenario


# ── Direction labels ──

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


# ── Regime labels ──

def _regime_label(ctx: MarketContext | None) -> str:
    if not ctx:
        return "UNKNOWN"
    r = ctx.regime
    if r == "trend_up" or r == "trend_down":
        return "TRENDING"
    if r == "high_volatility":
        if ctx.volatility_percentile >= 80:
            return "CHAOTIC"
        return "EXPANDING"
    if r == "range":
        if ctx.volatility_percentile <= 25:
            return "COMPRESSED"
        return "RANGING"
    return "UNKNOWN"


# ── Signal context ──

def _signal_context(direction: int, ctx: MarketContext | None) -> str:
    if not ctx:
        return "mixed"

    bullish_dir = direction >= 55
    bearish_dir = direction <= 45
    trend_up = ctx.regime == "trend_up"
    trend_down = ctx.regime == "trend_down"

    if bullish_dir and trend_up:
        return "trend_aligned"
    if bearish_dir and trend_down:
        return "trend_aligned"
    if bullish_dir and trend_down:
        return "counter_trend"
    if bearish_dir and trend_up:
        return "counter_trend"
    if ctx.volatility_percentile <= 20:
        return "breakout_candidate"
    if direction <= 25 or direction >= 75:
        return "exhaustion_zone"
    return "mixed"


# ── Interpretation helpers ──

INTERPRETATIONS = {
    "momentum": {
        (0, 20): "Pression vendeuse encore peu mature",
        (21, 40): "Momentum baissier en cours",
        (41, 59): "Pas de momentum clair",
        (60, 79): "Momentum haussier en construction",
        (80, 100): "Acceleration haussiere forte",
    },
    "trend": {
        (0, 20): "Structure baissiere dominante",
        (21, 40): "Tendance fragile, risque de cassure",
        (41, 59): "Consolidation, pas de tendance claire",
        (60, 79): "Tendance de fond haussiere",
        (80, 100): "Tendance tres forte et soutenue",
    },
    "volatility": {
        (0, 20): "Marche calme, compression potentielle",
        (21, 40): "Volatilite faible, attente de catalyseur",
        (41, 59): "Volatilite moderee, conditions normales",
        (60, 79): "Volatilite elevee, prudence sur le sizing",
        (80, 100): "Volatilite extreme, risque de faux signal",
    },
    "volume": {
        (0, 20): "Aucune conviction, mouvement non soutenu",
        (21, 40): "Volume faible, signal non confirme",
        (41, 59): "Volume normal, confirmation partielle",
        (60, 79): "Volume solide, mouvement credible",
        (80, 100): "Spike de volume, activite exceptionnelle",
    },
}


def _interpret(cat: str, score: int) -> str:
    m = INTERPRETATIONS.get(cat, INTERPRETATIONS["momentum"])
    for (lo, hi), text in m.items():
        if lo <= score <= hi:
            return text
    return "Neutre"


# ── Data structures ──

@dataclass
class SubScore:
    category: str
    score: int
    label: str
    indicator_count: int = 0


@dataclass
class Contradiction:
    description: str
    severity: str  # mild, moderate, strong


@dataclass
class TradePlanStub:
    side: str              # buy, sell, none
    entry_zone: str        # "current price area"
    invalidation_zone: str
    target_zone: str
    risk_reward: str
    validity: str          # "next 5-15 min" etc.
    execution_style: str   # scalping, intraday, swing


@dataclass
class EnhancedScore:
    # 5 core dimensions
    direction: int              # 0-100
    direction_label: str
    confidence: int             # 0-100
    risk: int                   # 0-100 (higher = riskier)
    setup_quality: int          # 0-100
    actionability: str          # IGNORE, WATCH, ACTIONABLE, HIGH_CONVICTION

    # Context
    action: str                 # STRONG_BUY..STRONG_SELL
    market_regime: str          # TRENDING, RANGING, COMPRESSED, EXPANDING, CHAOTIC
    signal_context: str         # trend_aligned, counter_trend, mixed, etc.

    # Details
    sub_scores: list[SubScore] = field(default_factory=list)
    key_reasons: list[str] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    trade_plan: TradePlanStub | None = None

    # Scenario context (new)
    scenario_name: str = ""
    scenario_probability: float = 0.0
    alternative_scenarios: list[dict] = field(default_factory=list)

    # Legacy compat
    score_100: int = 50
    label: str = ""
    confidence_level: str = "moyen"


def _signal_to_100(signal: float) -> int:
    return max(0, min(100, round((signal + 1) / 2 * 100)))


def _cat_score(indicators: list[IndicatorSnapshot], category: str) -> tuple[int, int]:
    """Compute weighted sub-score for a category. Returns (score_0_100, count)."""
    inds = [i for i in indicators if (i.category == category) or (i.category == "general" and category == "momentum")]
    if not inds:
        return 50, 0
    tw = sum(i.weight for i in inds)
    ws = sum(i.signal * i.weight for i in inds) / tw if tw > 0 else 0
    return _signal_to_100(ws), len(inds)


# ── Contradiction detection ──

def _detect_contradictions(
    indicators: list[IndicatorSnapshot],
    direction: int,
    sub_scores: dict[str, int],
    ctx: MarketContext | None,
) -> list[Contradiction]:
    cs: list[Contradiction] = []

    mom = sub_scores.get("momentum", 50)
    trend = sub_scores.get("trend", 50)
    vol = sub_scores.get("volatility", 50)
    volume = sub_scores.get("volume", 50)

    # Direction vs volume
    if abs(direction - 50) > 15 and volume < 35:
        cs.append(Contradiction(
            "Signal directionnel fort mais volume non confirme",
            "moderate",
        ))

    # Momentum vs trend divergence
    if (mom >= 60 and trend <= 35) or (mom <= 40 and trend >= 65):
        cs.append(Contradiction(
            "Momentum et tendance en desaccord",
            "strong",
        ))

    # Extreme volatility with directional signal
    if vol >= 75 and abs(direction - 50) > 10:
        cs.append(Contradiction(
            "Volatilite excessive, risque de faux signal",
            "moderate",
        ))

    # Counter-trend
    if ctx and ((direction >= 60 and ctx.regime == "trend_down") or (direction <= 40 and ctx.regime == "trend_up")):
        cs.append(Contradiction(
            "Signal contre la tendance de fond",
            "strong",
        ))

    return cs


# ── Risk score ──

def _compute_risk(
    vol_score: int,
    contradictions: list[Contradiction],
    direction: int,
    ctx: MarketContext | None,
) -> int:
    risk = 30  # baseline

    # Volatility contribution
    if vol_score >= 80:
        risk += 30
    elif vol_score >= 60:
        risk += 15
    elif vol_score <= 20:
        risk += 5  # compressed = slightly risky (breakout could go either way)

    # Contradictions
    for c in contradictions:
        if c.severity == "strong":
            risk += 15
        elif c.severity == "moderate":
            risk += 8

    # Extreme direction = extended move risk
    if direction >= 85 or direction <= 15:
        risk += 10

    # Counter-trend penalty
    if ctx and ((direction >= 55 and ctx.regime == "trend_down") or (direction <= 45 and ctx.regime == "trend_up")):
        risk += 12

    return max(0, min(100, risk))


# ── Setup quality ──

def _compute_setup_quality(
    confidence: int,
    risk: int,
    contradictions: list[Contradiction],
    volume_score: int,
    direction: int,
    trend_score: int,
    momentum_score: int,
) -> int:
    direction_strength = min(abs(direction - 50) * 2, 100)
    bullish = direction >= 50
    trend_alignment = trend_score if bullish else 100 - trend_score
    momentum_alignment = momentum_score if bullish else 100 - momentum_score
    structure_alignment = (trend_alignment + momentum_alignment) / 2

    quality = (
        confidence * 0.34
        + (100 - risk) * 0.18
        + volume_score * 0.16
        + direction_strength * 0.18
        + structure_alignment * 0.14
    )

    strong_contradictions = sum(1 for item in contradictions if item.severity == "strong")
    moderate_contradictions = sum(1 for item in contradictions if item.severity == "moderate")
    quality -= strong_contradictions * 14
    quality -= moderate_contradictions * 7

    if volume_score < 35:
        quality -= 8
    elif volume_score >= 70:
        quality += 4

    if direction_strength < 14:
        quality -= 10
    elif direction_strength >= 28:
        quality += 5

    if risk >= 70:
        quality -= 12
    elif risk >= 55:
        quality -= 6

    return max(0, min(100, round(quality)))


# ── Actionability ──

def _compute_actionability(
    direction: int,
    confidence: int,
    risk: int,
    setup_quality: int,
    contradictions: list[Contradiction],
) -> str:
    strong_contradictions = sum(1 for c in contradictions if c.severity == "strong")

    # Too many contradictions → never high conviction
    if strong_contradictions >= 2:
        return "WATCH" if abs(direction - 50) > 15 else "IGNORE"

    # High conviction: strong direction + high confidence + low risk + good setup
    if abs(direction - 50) >= 25 and confidence >= 70 and risk <= 45 and setup_quality >= 60:
        return "HIGH_CONVICTION"

    # Actionable: decent direction + reasonable confidence + acceptable risk
    if abs(direction - 50) >= 15 and confidence >= 45 and risk <= 65:
        return "ACTIONABLE"

    # Watch: some signal but not clean enough
    if abs(direction - 50) >= 10:
        return "WATCH"

    return "IGNORE"


# ── Trade plan stub ──

def _build_trade_plan(
    direction: int,
    actionability: str,
    ctx: MarketContext | None,
) -> TradePlanStub | None:
    if actionability == "IGNORE":
        return None

    bullish = direction >= 55
    side = "buy" if bullish else "sell" if direction <= 45 else "none"
    if side == "none":
        return None

    atr = ctx.atr if ctx else 0
    atr_str = f"{atr:.2f}" if atr > 0 else "N/A"

    return TradePlanStub(
        side=side,
        entry_zone="Prix actuel",
        invalidation_zone=f"{'Sous' if bullish else 'Au-dessus de'} {('1.5' if actionability == 'HIGH_CONVICTION' else '1.0')} x ATR ({atr_str})",
        target_zone=f"{'1.5' if actionability != 'HIGH_CONVICTION' else '2.0'} x ATR dans la direction",
        risk_reward=f"{'1.5' if actionability != 'HIGH_CONVICTION' else '2.0'}:1 estime",
        validity="5-15 min" if not ctx or ctx.regime != "range" else "15-60 min",
        execution_style="scalping",
    )


# ── Key reasons with interpretive phrasing ──

def _build_reasons(indicators: list[IndicatorSnapshot], sub_scores: dict[str, int], max_n: int = 3) -> list[str]:
    if not indicators:
        return ["Donnees insuffisantes"]

    reasons: list[str] = []
    sorted_inds = sorted(indicators, key=lambda i: abs(i.signal), reverse=True)

    for ind in sorted_inds[:max_n]:
        if abs(ind.signal) < 0.1:
            continue
        cat = ind.category if ind.category in INTERPRETATIONS else "momentum"
        cat_s = sub_scores.get(cat, 50)
        reasons.append(_interpret(cat, cat_s))

    return reasons or ["Signaux mixtes, pas de direction claire"]


# ── Improved confidence: strength-weighted + correlation penalty ──

# Indicators that measure similar things (correlated pairs)
_CORRELATED_PAIRS = [
    {"RSI", "Bollinger"},       # both measure mean-reversion / extremes
    {"MACD", "EMA Cross"},      # both measure trend / momentum crossovers
]


def _compute_confidence(indicators: list[IndicatorSnapshot]) -> int:
    """Confidence based on strength-weighted agreement with correlation penalty.

    - Each indicator votes with abs(signal) * weight, not just +1/-1
    - Correlated indicators count as 1.3 votes instead of 2
    - Strong convergence (3+ agree strongly) gets a bonus
    """
    if not indicators:
        return 50

    bullish_strength = 0.0
    bearish_strength = 0.0
    total_weight = 0.0
    active_names: set[str] = set()

    for ind in indicators:
        if abs(ind.signal) < 0.05:
            continue
        active_names.add(ind.name)

        # Weight by signal strength (not just direction)
        vote = abs(ind.signal) * ind.weight

        # Check if this indicator is correlated with one already counted
        corr_discount = 1.0
        for pair in _CORRELATED_PAIRS:
            if ind.name in pair and (pair - {ind.name}) & active_names:
                corr_discount = 0.65  # correlated pair → 65% weight instead of 100%
                break

        effective_vote = vote * corr_discount
        total_weight += effective_vote

        if ind.signal > 0:
            bullish_strength += effective_vote
        else:
            bearish_strength += effective_vote

    if total_weight <= 0:
        return 50

    # Agreement = dominant side / total
    dominant = max(bullish_strength, bearish_strength)
    agreement = dominant / total_weight

    # Convergence bonus: if 3+ indicators agree strongly
    strong_bull = sum(1 for i in indicators if i.signal > 0.4)
    strong_bear = sum(1 for i in indicators if i.signal < -0.4)
    convergence_bonus = 0
    if max(strong_bull, strong_bear) >= 3:
        convergence_bonus = 12  # strong convergence
    elif max(strong_bull, strong_bear) >= 2:
        convergence_bonus = 5

    raw = round(agreement * 100) + convergence_bonus
    return max(0, min(100, raw))


# ── Improved direction: non-linear scoring ──

def _compute_direction_nonlinear(indicators: list[IndicatorSnapshot], raw_score: float) -> int:
    """Direction with convergence multiplier.

    When 3+ indicators strongly agree, boost the signal beyond linear average.
    """
    base = _signal_to_100(raw_score)

    strong_bull = sum(1 for i in indicators if i.signal > 0.4)
    strong_bear = sum(1 for i in indicators if i.signal < -0.4)
    max_strong = max(strong_bull, strong_bear)

    if max_strong >= 3:
        # Push direction further from neutral (amplify conviction)
        distance = base - 50
        amplified = 50 + distance * 1.20  # 20% boost
        return max(0, min(100, round(amplified)))
    elif max_strong >= 2:
        distance = base - 50
        amplified = 50 + distance * 1.08  # 8% boost
        return max(0, min(100, round(amplified)))

    return base


# ── Improved risk: ATR-relative instead of fixed bonuses ──

def _compute_risk_v2(
    vol_score: int,
    contradictions: list[Contradiction],
    direction: int,
    ctx: MarketContext | None,
    indicators: list[IndicatorSnapshot],
) -> int:
    """Risk scoring using relative ATR + proportional contradiction penalty."""
    risk = 25  # lower baseline than before

    # Volatility: use ATR-relative if available
    if ctx and ctx.atr > 0:
        # Normalize ATR as % of typical crypto price movement
        atr_pct = ctx.atr * 100  # rough normalization
        if atr_pct > 3.0:
            risk += 25  # very high volatility
        elif atr_pct > 1.5:
            risk += 15
        elif atr_pct > 0.5:
            risk += 5
    else:
        # Fallback to vol_score
        if vol_score >= 80:
            risk += 25
        elif vol_score >= 60:
            risk += 12

    # Contradictions: proportional to severity count
    strong_count = sum(1 for c in contradictions if c.severity == "strong")
    moderate_count = sum(1 for c in contradictions if c.severity == "moderate")
    risk += strong_count * 12 + moderate_count * 6

    # Extreme direction = extended move risk (diminishing)
    dist = abs(direction - 50)
    if dist >= 35:
        risk += 10
    elif dist >= 25:
        risk += 5

    # Counter-trend (only if clear trend detected)
    if ctx and ((direction >= 55 and ctx.regime == "trend_down") or (direction <= 45 and ctx.regime == "trend_up")):
        risk += 10

    return max(0, min(100, risk))


# ── Regime-aware risk adjustment ──

_REGIME_RISK_BONUS: dict[str, int] = {
    "EXHAUSTION": 15,
    "BREAKOUT": 5,
    "RANGE": -5,
}


def _regime_adjusted_risk(base_risk: int, regime: RegimeInfo | None) -> int:
    if not regime:
        return base_risk
    return max(0, min(100, base_risk + _REGIME_RISK_BONUS.get(regime.regime, 0)))


# ── Scenario-aware actionability ──

def _scenario_adjusted_actionability(
    base: str,
    scenario: Scenario | None,
    direction: int,
    confidence: int,
    risk: int,
    setup_quality: int,
) -> str:
    if not scenario:
        return base
    if scenario.probability < 0.30 and base in ("ACTIONABLE", "HIGH_CONVICTION"):
        return "WATCH"
    if scenario.probability > 0.60 and base == "ACTIONABLE":
        if abs(direction - 50) >= 20 and confidence >= 55 and risk <= 55:
            return "HIGH_CONVICTION"
    return base


# ── Main entry point ──

def compute_enhanced_scores(
    indicators: list[IndicatorSnapshot],
    raw_score: float = 0.0,
    market_context: MarketContext | None = None,
    regime: RegimeInfo | None = None,
    scenario: Scenario | None = None,
) -> EnhancedScore:

    # 1. Direction (non-linear with convergence boost)
    direction = _compute_direction_nonlinear(indicators, raw_score)

    # 2. Sub-scores
    sub_score_map: dict[str, int] = {}
    sub_scores: list[SubScore] = []
    for cat in ["momentum", "trend", "volatility", "volume"]:
        s, cnt = _cat_score(indicators, cat)
        sub_score_map[cat] = s
        sub_scores.append(SubScore(cat, s, _interpret(cat, s), cnt))

    # 3. Confidence (strength-weighted agreement + correlation penalty)
    confidence = _compute_confidence(indicators)

    # 4. Contradictions
    contradictions = _detect_contradictions(indicators, direction, sub_score_map, market_context)

    # Reduce confidence for contradictions
    for c in contradictions:
        if c.severity == "strong":
            confidence = max(0, confidence - 15)
        elif c.severity == "moderate":
            confidence = max(0, confidence - 8)

    # 5. Risk (ATR-relative + regime-aware)
    risk = _compute_risk_v2(sub_score_map.get("volatility", 50), contradictions, direction, market_context, indicators)
    risk = _regime_adjusted_risk(risk, regime)

    # 6. Setup quality
    setup_quality = _compute_setup_quality(
        confidence,
        risk,
        contradictions,
        sub_score_map.get("volume", 50),
        direction,
        sub_score_map.get("trend", 50),
        sub_score_map.get("momentum", 50),
    )

    # 7. Actionability (scenario-aware)
    actionability = _compute_actionability(direction, confidence, risk, setup_quality, contradictions)
    actionability = _scenario_adjusted_actionability(actionability, scenario, direction, confidence, risk, setup_quality)

    # 8. Context
    regime_label = _regime_label(market_context)
    sig_ctx = _signal_context(direction, market_context)

    # 9. Trade plan
    trade_plan = _build_trade_plan(direction, actionability, market_context)

    # 10. Key reasons
    key_reasons = _build_reasons(indicators, sub_score_map)

    # Add contradiction warnings to reasons
    for c in contradictions:
        if c.severity == "strong":
            key_reasons.append(f"Attention : {c.description}")

    # Confidence level label
    conf_level = "tres eleve" if confidence >= 80 else "eleve" if confidence >= 60 else "moyen" if confidence >= 40 else "faible"

    # Scenario metadata
    scenario_name = scenario.name if scenario else ""
    scenario_prob = scenario.probability if scenario else 0.0
    alt_scenarios: list[dict] = []
    # (populated by caller when multiple scenarios exist)

    return EnhancedScore(
        direction=direction,
        direction_label=_direction_label(direction),
        confidence=confidence,
        risk=risk,
        setup_quality=setup_quality,
        actionability=actionability,
        action=_action_from_direction(direction),
        market_regime=regime_label,
        signal_context=sig_ctx,
        sub_scores=sub_scores,
        key_reasons=key_reasons[:4],
        contradictions=contradictions,
        trade_plan=trade_plan,
        scenario_name=scenario_name,
        scenario_probability=scenario_prob,
        alternative_scenarios=alt_scenarios,
        # Legacy compat
        score_100=direction,
        label=_direction_label(direction),
        confidence_level=conf_level,
    )
