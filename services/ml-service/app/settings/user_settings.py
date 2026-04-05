"""User signal settings — per-mode defaults and configurable parameters.

Stored in-memory for V1.  Phase 3 will persist to DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class UserSignalSettings:
    # ── Universe ──
    watched_symbols: list[str] = field(
        default_factory=lambda: ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"],
    )

    # ── Mode ──
    trading_mode: Literal["scalping", "intraday", "swing"] = "scalping"

    # ── Timeframes (auto-set by mode via preset(), overridable) ──
    primary_timeframe: str = "1m"
    confirmation_timeframes: list[str] = field(default_factory=lambda: ["5m", "15m"])

    # ── Strategies enabled ──
    enabled_strategies: list[str] = field(
        default_factory=lambda: ["breakout", "momentum_burst", "micro_pullback"],
    )

    # ── Indicator parameters ──
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: float = 2.0
    ema_fast: int = 9
    ema_slow: int = 21
    atr_period: int = 14
    volume_spike_threshold: float = 2.0

    # ── Score thresholds ──
    min_actionable_score: float = 0.35
    min_watch_score: float = 0.15
    strong_signal_score: float = 0.6

    # ── Market filters ──
    min_volume_24h_usd: float = 1_000_000.0
    max_volatility_pct: float = 50.0
    btc_trend_filter: bool = True

    # ── Risk management ──
    capital_usd: float = 10_000.0
    risk_per_trade_pct: float = 1.0
    max_trades_per_day: int = 10
    default_stop_loss_pct: float = 1.5
    default_take_profit_pct: float = 3.0
    min_risk_reward: float = 1.5
    trailing_stop: bool = True

    # ── Notifications ──
    top_n_opportunities: int = 3
    include_reasoning: bool = True
    include_trade_plan: bool = True

    # ── Execution ──
    execution_mode: Literal["analysis", "simulation", "paper"] = "analysis"


# ── Presets per trading mode ──

def scalping_preset() -> UserSignalSettings:
    return UserSignalSettings(
        trading_mode="scalping",
        primary_timeframe="1m",
        confirmation_timeframes=["5m", "15m"],
        enabled_strategies=["breakout", "momentum_burst", "micro_pullback"],
        default_stop_loss_pct=0.8,
        default_take_profit_pct=1.6,
        min_risk_reward=1.5,
        volume_spike_threshold=2.0,
        max_trades_per_day=20,
        risk_per_trade_pct=0.5,
    )


def intraday_preset() -> UserSignalSettings:
    return UserSignalSettings(
        trading_mode="intraday",
        primary_timeframe="15m",
        confirmation_timeframes=["1h", "4h"],
        enabled_strategies=["momentum_rsi_macd", "mean_reversion"],
        default_stop_loss_pct=2.0,
        default_take_profit_pct=4.0,
        min_risk_reward=1.8,
        volume_spike_threshold=1.5,
        max_trades_per_day=8,
        risk_per_trade_pct=1.0,
    )


def swing_preset() -> UserSignalSettings:
    return UserSignalSettings(
        trading_mode="swing",
        primary_timeframe="4h",
        confirmation_timeframes=["1d"],
        enabled_strategies=["sma_crossover", "trend_following"],
        default_stop_loss_pct=5.0,
        default_take_profit_pct=12.0,
        min_risk_reward=2.0,
        volume_spike_threshold=1.3,
        max_trades_per_day=3,
        risk_per_trade_pct=2.0,
    )


PRESETS = {
    "scalping": scalping_preset,
    "intraday": intraday_preset,
    "swing": swing_preset,
}


def get_settings(mode: str | None = None) -> UserSignalSettings:
    """Return settings for a given mode, or default (scalping)."""
    # TODO Phase 3: load from DB per user
    factory = PRESETS.get(mode or "scalping", scalping_preset)
    return factory()
