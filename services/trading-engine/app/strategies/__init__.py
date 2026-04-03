"""Trading strategies for the Okamoey Trading Platform.

All strategies inherit from :class:`BaseStrategy` and are registered in
the ``STRATEGIES`` mapping for runtime look-up by name.
"""

from __future__ import annotations

from typing import Dict, Type

from app.strategies.base import BaseStrategy
from app.strategies.dca_intelligent import IntelligentDCA
from app.strategies.grid_trading import GridTrading
from app.strategies.mean_reversion import MeanReversion
from app.strategies.momentum_rsi_macd import MomentumRsiMacd
from app.strategies.sma_crossover import SmaCrossoverStrategy

STRATEGIES: Dict[str, Type[BaseStrategy]] = {
    "sma_crossover": SmaCrossoverStrategy,
    "momentum_rsi_macd": MomentumRsiMacd,
    "grid_trading": GridTrading,
    "mean_reversion_bollinger": MeanReversion,
    "dca_intelligent": IntelligentDCA,
}
