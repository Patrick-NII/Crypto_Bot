"""Base strategy abstract class.

All trading strategies must inherit from BaseStrategy and implement
the generate_signal, get_parameters, and set_parameters methods.
"""

from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    name: str
    description: str

    @abstractmethod
    async def generate_signal(self, symbol: str, market_data: dict) -> dict:
        """Analyze market data and return a trading signal.

        Returns:
            {"action": "buy"|"sell"|"hold", "confidence": float, "reason": str}
        """
        pass

    @abstractmethod
    async def get_parameters(self) -> dict:
        """Return the current strategy parameters."""
        pass

    @abstractmethod
    async def set_parameters(self, params: dict) -> None:
        """Update strategy parameters."""
        pass
