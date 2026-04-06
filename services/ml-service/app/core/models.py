"""Core data models for the signal engine.

All domain types live here — indicators, strategies, ranking, trade plans.
Backward-compatible re-exports keep existing imports working.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


# ── Action enum (migrated from services/signal_engine.py) ──

class Action(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    ACCUMULATE = "ACCUMULATE"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


# ── Raw market data ──

@dataclass(slots=True)
class Candle:
    time: int      # unix seconds
    open: float
    high: float
    low: float
    close: float
    volume: float


# ── Indicator output ──

@dataclass
class IndicatorSnapshot:
    name: str
    value: float
    signal: float       # -1 (sell) to +1 (buy)
    description: str
    weight: float = 1.0
    category: str = "general"  # momentum, trend, volatility, volume


# Backward-compat alias
IndicatorResult = IndicatorSnapshot


# ── Market context ──

@dataclass
class MarketContext:
    regime: str                    # trend_up, trend_down, range, high_volatility
    btc_trend: str = "neutral"     # bullish, bearish, neutral
    volatility_percentile: float = 50.0
    volume_ratio: float = 1.0      # vs 20-period average
    atr: float = 0.0


# ── Regime detection ──

@dataclass
class RegimeInfo:
    """Rich market regime classification with confidence."""

    regime: str                    # RANGE, BREAKOUT, TREND_UP, TREND_DOWN, EXHAUSTION
    confidence: float = 0.0        # 0.0-1.0 — strength of the classification
    evidence: dict[str, float] = field(default_factory=dict)   # per-regime evidence scores
    structure: str = "NONE"        # HH_HL, LH_LL, NONE, MIXED
    volatility_state: str = "normal"   # compressed, expanding, normal, extreme
    momentum_state: str = "neutral"    # accelerating, decelerating, neutral


# ── Scenario ──

@dataclass
class Scenario:
    """A plausible market outcome with its probability."""

    name: str                      # CONTINUATION, MEAN_REVERSION, FAKEOUT, REVERSAL, etc.
    direction: str                 # bullish, bearish
    probability: float = 0.0       # 0.0-1.0
    reasoning: str = ""
    conditions_met: list[str] = field(default_factory=list)
    conditions_unmet: list[str] = field(default_factory=list)
    weight_profile: dict[str, float] = field(default_factory=dict)


# ── Strategy result ──

@dataclass
class StrategyResult:
    strategy_name: str
    strategy_type: str             # scalping, intraday, swing
    action: str                    # BUY, SELL, HOLD
    confidence: float              # 0-1
    score: float                   # -1 to +1
    timeframe: str
    indicators: list[IndicatorSnapshot] = field(default_factory=list)
    reasoning: str = ""
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None


# ── Trade plan ──

@dataclass
class TradePlan:
    side: str              # buy, sell
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    position_size_usd: float = 0.0
    risk_usd: float = 0.0


# ── Composite trading signal (backward-compat with old TradingSignal) ──

@dataclass
class TradingSignal:
    symbol: str
    action: Action
    confidence: float
    score: float
    indicators: list[IndicatorSnapshot] = field(default_factory=list)
    reasoning: str = ""


# ── Ranked opportunity (scanner output) ──

@dataclass
class RankedOpportunity:
    rank: int
    symbol: str
    global_score: float
    confidence: float
    status: str                    # actionable, watch, ignore
    best_strategy: StrategyResult | None = None
    all_strategies: list[StrategyResult] = field(default_factory=list)
    market_context: MarketContext | None = None
    trade_plan: TradePlan | None = None
    timestamp: str = ""


# ── Trading mode ──

TradingMode = Literal["scalping", "intraday", "swing"]

# ── Timeframe presets per mode ──

MODE_TIMEFRAMES: dict[str, dict[str, str | list[str]]] = {
    "scalping": {
        "primary": "1m",
        "confirmation": ["5m", "15m"],
    },
    "intraday": {
        "primary": "15m",
        "confirmation": ["1h", "4h"],
    },
    "swing": {
        "primary": "4h",
        "confirmation": ["1d"],
    },
}
