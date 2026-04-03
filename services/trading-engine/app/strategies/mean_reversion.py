"""Mean reversion strategy using Bollinger Bands.

Buys when price touches or crosses below the lower band (oversold) and
sells when price touches or crosses above the upper band (overbought).
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional

from app.strategies.base import BaseStrategy


class MeanReversion(BaseStrategy):
    """Mean reversion using Bollinger Bands.

    BUY when price touches/crosses lower band (oversold).
    SELL when price touches/crosses upper band (overbought).
    """

    name: str = "mean_reversion_bollinger"
    description: str = (
        "Mean reversion using Bollinger Bands - "
        "buy at lower band, sell at upper band"
    )

    def __init__(self) -> None:
        self._bb_period: int = 20
        self._bb_std_dev: Decimal = Decimal("2.0")
        # Fraction beyond the band that strengthens the signal (0.02 = 2%)
        self._entry_threshold: Decimal = Decimal("0.02")

    # ------------------------------------------------------------------
    # Bollinger Band calculations
    # ------------------------------------------------------------------

    @staticmethod
    def _sma(values: List[Decimal], period: int) -> Optional[Decimal]:
        """Compute the Simple Moving Average of the last *period* values."""
        if not values or period <= 0 or len(values) < period:
            return None
        window = values[-period:]
        return sum(window) / Decimal(period)

    @staticmethod
    def _std_dev(values: List[Decimal], period: int, mean: Decimal) -> Optional[Decimal]:
        """Compute the population standard deviation of the last *period* values."""
        if not values or period <= 0 or len(values) < period:
            return None
        window = values[-period:]
        variance = sum((v - mean) ** 2 for v in window) / Decimal(period)
        # Decimal does not have a built-in sqrt; use float and convert back.
        std = Decimal(str(float(variance) ** 0.5))
        return std

    def _compute_bands(
        self, closes: List[Decimal]
    ) -> Optional[Dict[str, Decimal]]:
        """Return upper, middle, and lower Bollinger Band values.

        Returns ``None`` when there is not enough data.
        """
        if len(closes) < self._bb_period:
            return None

        middle = self._sma(closes, self._bb_period)
        if middle is None:
            return None

        std = self._std_dev(closes, self._bb_period, middle)
        if std is None:
            return None

        upper = middle + self._bb_std_dev * std
        lower = middle - self._bb_std_dev * std

        return {
            "upper_band": upper.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "middle_band": middle.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "lower_band": lower.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        }

    # ------------------------------------------------------------------
    # BaseStrategy interface
    # ------------------------------------------------------------------

    async def generate_signal(self, symbol: str, market_data: dict) -> dict:
        """Analyse *market_data* and return a mean-reversion signal.

        ``market_data`` must contain a ``"closes"`` key whose value is a
        list of :class:`~decimal.Decimal` closing prices (oldest first).
        """
        raw_closes = market_data.get("closes", [])
        if not raw_closes:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reason": "No closing price data provided",
                "indicators": {},
            }

        try:
            closes: List[Decimal] = [
                v if isinstance(v, Decimal) else Decimal(str(v))
                for v in raw_closes
            ]
        except (InvalidOperation, TypeError, ValueError):
            return {
                "action": "hold",
                "confidence": 0.0,
                "reason": "Invalid price data",
                "indicators": {},
            }

        if len(closes) < self._bb_period:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reason": (
                    f"Insufficient data: need {self._bb_period} prices, "
                    f"got {len(closes)}"
                ),
                "indicators": {},
            }

        bands = self._compute_bands(closes)
        if bands is None:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reason": "Unable to compute Bollinger Bands",
                "indicators": {},
            }

        current_price = closes[-1]
        indicators = {
            "upper_band": bands["upper_band"],
            "middle_band": bands["middle_band"],
            "lower_band": bands["lower_band"],
            "current_price": current_price,
        }

        band_width = bands["upper_band"] - bands["lower_band"]
        if band_width <= 0:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reason": "Bollinger Band width is zero or negative",
                "indicators": indicators,
            }

        # How far beyond the lower band the price has fallen (positive = below band)
        lower_breach = bands["lower_band"] - current_price
        # How far beyond the upper band the price has risen (positive = above band)
        upper_breach = current_price - bands["upper_band"]

        threshold_amount = self._entry_threshold * bands["middle_band"]

        # BUY: price at or below the lower band
        if current_price <= bands["lower_band"]:
            # Confidence increases the further below the band we are
            breach_ratio = float(lower_breach) / float(band_width)
            base_confidence = 0.5
            if lower_breach >= threshold_amount:
                base_confidence = 0.7
            confidence = min(base_confidence + breach_ratio, 1.0)
            return {
                "action": "buy",
                "confidence": round(max(confidence, 0.1), 4),
                "reason": (
                    f"Price {current_price} at/below lower Bollinger Band "
                    f"{bands['lower_band']} (middle {bands['middle_band']}). "
                    f"Mean reversion buy signal."
                ),
                "indicators": indicators,
            }

        # SELL: price at or above the upper band
        if current_price >= bands["upper_band"]:
            breach_ratio = float(upper_breach) / float(band_width)
            base_confidence = 0.5
            if upper_breach >= threshold_amount:
                base_confidence = 0.7
            confidence = min(base_confidence + breach_ratio, 1.0)
            return {
                "action": "sell",
                "confidence": round(max(confidence, 0.1), 4),
                "reason": (
                    f"Price {current_price} at/above upper Bollinger Band "
                    f"{bands['upper_band']} (middle {bands['middle_band']}). "
                    f"Mean reversion sell signal."
                ),
                "indicators": indicators,
            }

        # Price is between bands -- no signal
        position_in_band = float(current_price - bands["lower_band"]) / float(band_width)
        return {
            "action": "hold",
            "confidence": 0.0,
            "reason": (
                f"Price {current_price} within Bollinger Bands "
                f"({bands['lower_band']} - {bands['upper_band']}). "
                f"Position in band: {position_in_band:.1%}."
            ),
            "indicators": indicators,
        }

    async def get_parameters(self) -> dict:
        return {
            "bb_period": self._bb_period,
            "bb_std_dev": self._bb_std_dev,
            "entry_threshold": self._entry_threshold,
        }

    async def set_parameters(self, params: dict) -> None:
        if "bb_period" in params:
            self._bb_period = int(params["bb_period"])
        if "bb_std_dev" in params:
            self._bb_std_dev = Decimal(str(params["bb_std_dev"]))
        if "entry_threshold" in params:
            self._entry_threshold = Decimal(str(params["entry_threshold"]))
