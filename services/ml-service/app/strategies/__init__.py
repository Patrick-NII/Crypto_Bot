"""Strategy registry — organized by trading mode."""

from app.strategies.scalping.breakout import BreakoutStrategy
from app.strategies.scalping.momentum_burst import MomentumBurstStrategy
from app.strategies.scalping.micro_pullback import MicroPullbackStrategy

SCALPING_STRATEGIES = {
    "breakout": BreakoutStrategy,
    "momentum_burst": MomentumBurstStrategy,
    "micro_pullback": MicroPullbackStrategy,
}

# TODO Phase 2: add intraday and swing strategies migrated from trading-engine
INTRADAY_STRATEGIES: dict = {}
SWING_STRATEGIES: dict = {}

ALL_STRATEGIES = {**SCALPING_STRATEGIES, **INTRADAY_STRATEGIES, **SWING_STRATEGIES}

MODE_STRATEGIES = {
    "scalping": SCALPING_STRATEGIES,
    "intraday": INTRADAY_STRATEGIES,
    "swing": SWING_STRATEGIES,
}
