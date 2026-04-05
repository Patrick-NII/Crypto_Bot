"""Strategy protocol — interface for all signal-generating strategies."""

from __future__ import annotations

from typing import Protocol

from app.core.models import Candle, IndicatorSnapshot, StrategyResult
from app.settings.user_settings import UserSignalSettings


class StrategyProtocol(Protocol):
    """All strategies must implement this interface."""

    name: str
    strategy_type: str  # scalping, intraday, swing

    def generate(
        self,
        symbol: str,
        primary_candles: list[Candle],
        confirmation_candles: list[Candle] | None,
        settings: UserSignalSettings,
    ) -> StrategyResult:
        """Compute a signal from candle data. Pure function, no I/O."""
        ...
