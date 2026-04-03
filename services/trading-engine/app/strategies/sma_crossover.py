"""Simple Moving Average crossover strategy.

A concrete strategy that generates buy/sell signals based on the
crossover of a short-period SMA and a long-period SMA.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.strategies.base import BaseStrategy


class SmaCrossoverStrategy(BaseStrategy):
    """SMA crossover: buy when short SMA crosses above long SMA."""

    name: str = "sma_crossover"
    description: str = (
        "Generates signals based on the crossover of a short-period and "
        "long-period simple moving average."
    )

    def __init__(self) -> None:
        self._short_period: int = 10
        self._long_period: int = 30

    @staticmethod
    def _sma(values: List[float], period: int) -> float:
        """Compute the simple moving average over the last *period* values."""
        if len(values) < period:
            return sum(values) / len(values) if values else 0.0
        window = values[-period:]
        return sum(window) / period

    async def generate_signal(self, symbol: str, market_data: dict) -> dict:
        """Analyse *market_data* and return a trading signal.

        ``market_data`` is expected to contain a ``"prices"`` key with a
        list of recent closing prices (oldest first).  If not enough
        data is available the strategy returns ``"hold"``.
        """
        prices: List[float] = market_data.get("prices", [])
        if len(prices) < self._long_period:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reason": (
                    f"Insufficient data: need {self._long_period} prices, "
                    f"got {len(prices)}"
                ),
            }

        short_sma = self._sma(prices, self._short_period)
        long_sma = self._sma(prices, self._long_period)

        # Previous values for crossover detection
        prev_prices = prices[:-1]
        prev_short = self._sma(prev_prices, self._short_period)
        prev_long = self._sma(prev_prices, self._long_period)

        # Bullish crossover: short crosses above long
        if prev_short <= prev_long and short_sma > long_sma:
            diff_pct = abs(short_sma - long_sma) / long_sma * 100
            confidence = min(diff_pct / 2, 1.0)  # cap at 1.0
            return {
                "action": "buy",
                "confidence": round(confidence, 4),
                "reason": (
                    f"Bullish SMA crossover: SMA({self._short_period})={short_sma:.2f} "
                    f"crossed above SMA({self._long_period})={long_sma:.2f}"
                ),
            }

        # Bearish crossover: short crosses below long
        if prev_short >= prev_long and short_sma < long_sma:
            diff_pct = abs(long_sma - short_sma) / long_sma * 100
            confidence = min(diff_pct / 2, 1.0)
            return {
                "action": "sell",
                "confidence": round(confidence, 4),
                "reason": (
                    f"Bearish SMA crossover: SMA({self._short_period})={short_sma:.2f} "
                    f"crossed below SMA({self._long_period})={long_sma:.2f}"
                ),
            }

        return {
            "action": "hold",
            "confidence": 0.0,
            "reason": (
                f"No crossover: SMA({self._short_period})={short_sma:.2f}, "
                f"SMA({self._long_period})={long_sma:.2f}"
            ),
        }

    async def get_parameters(self) -> dict:
        return {
            "short_period": self._short_period,
            "long_period": self._long_period,
        }

    async def set_parameters(self, params: dict) -> None:
        if "short_period" in params:
            self._short_period = int(params["short_period"])
        if "long_period" in params:
            self._long_period = int(params["long_period"])
