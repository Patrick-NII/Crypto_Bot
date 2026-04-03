"""Momentum strategy using RSI + MACD confirmation.

Trend-following strategy that combines RSI oversold/overbought levels with
MACD crossover confirmation to generate buy and sell signals.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional

from app.strategies.base import BaseStrategy


class MomentumRsiMacd(BaseStrategy):
    """Trend-following strategy using RSI + MACD confirmation.

    BUY signal when: RSI < oversold (30) AND MACD crosses above signal line.
    SELL signal when: RSI > overbought (70) AND MACD crosses below signal line.
    """

    name: str = "momentum_rsi_macd"
    description: str = (
        "Momentum strategy combining RSI oversold/overbought "
        "with MACD crossover confirmation"
    )

    def __init__(self) -> None:
        self._rsi_period: int = 14
        self._rsi_overbought: Decimal = Decimal("70")
        self._rsi_oversold: Decimal = Decimal("30")
        self._macd_fast: int = 12
        self._macd_slow: int = 26
        self._macd_signal: int = 9

    # ------------------------------------------------------------------
    # Indicator calculations
    # ------------------------------------------------------------------

    @staticmethod
    def _ema(values: List[Decimal], period: int) -> List[Decimal]:
        """Compute the Exponential Moving Average for a list of Decimal values.

        Returns a list the same length as *values*.  The first element is
        seeded with a simple average of the first *period* values.
        """
        if not values or period <= 0:
            return []
        if len(values) < period:
            # Not enough data -- return simple averages as best-effort
            result: List[Decimal] = []
            running = Decimal("0")
            for i, v in enumerate(values):
                running += v
                result.append(running / Decimal(i + 1))
            return result

        multiplier = Decimal("2") / Decimal(period + 1)
        # Seed with SMA of first *period* values
        sma_seed = sum(values[:period]) / Decimal(period)
        ema_values: List[Decimal] = [Decimal("0")] * len(values)
        ema_values[period - 1] = sma_seed
        for i in range(period, len(values)):
            ema_values[i] = (values[i] - ema_values[i - 1]) * multiplier + ema_values[i - 1]
        # Fill earlier slots with zero (not meaningful)
        return ema_values

    @staticmethod
    def _compute_rsi(closes: List[Decimal], period: int) -> Optional[Decimal]:
        """Compute the RSI from a list of closing prices.

        Returns ``None`` when there are not enough data points.
        """
        if len(closes) < period + 1:
            return None

        gains: List[Decimal] = []
        losses: List[Decimal] = []
        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(Decimal("0"))
            else:
                gains.append(Decimal("0"))
                losses.append(abs(change))

        # Wilder's smoothed averages
        avg_gain = sum(gains[:period]) / Decimal(period)
        avg_loss = sum(losses[:period]) / Decimal(period)

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * Decimal(period - 1) + gains[i]) / Decimal(period)
            avg_loss = (avg_loss * Decimal(period - 1) + losses[i]) / Decimal(period)

        if avg_loss == 0:
            return Decimal("100")

        rs = avg_gain / avg_loss
        rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))
        return rsi.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _compute_macd(
        self, closes: List[Decimal]
    ) -> Optional[Dict[str, Decimal]]:
        """Compute MACD line, signal line, and histogram.

        Returns ``None`` when there is insufficient data.
        """
        min_required = self._macd_slow + self._macd_signal
        if len(closes) < min_required:
            return None

        fast_ema = self._ema(closes, self._macd_fast)
        slow_ema = self._ema(closes, self._macd_slow)

        # MACD line = fast EMA - slow EMA (meaningful from index macd_slow-1 onward)
        macd_line: List[Decimal] = []
        start = self._macd_slow - 1
        for i in range(start, len(closes)):
            macd_line.append(fast_ema[i] - slow_ema[i])

        if len(macd_line) < self._macd_signal:
            return None

        signal_line = self._ema(macd_line, self._macd_signal)

        current_macd = macd_line[-1]
        current_signal = signal_line[-1]
        histogram = current_macd - current_signal

        prev_macd = macd_line[-2] if len(macd_line) >= 2 else current_macd
        prev_signal = signal_line[-2] if len(signal_line) >= 2 else current_signal

        return {
            "macd": current_macd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "signal": current_signal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "histogram": histogram.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "prev_macd": prev_macd,
            "prev_signal": prev_signal,
        }

    # ------------------------------------------------------------------
    # BaseStrategy interface
    # ------------------------------------------------------------------

    async def generate_signal(self, symbol: str, market_data: dict) -> dict:
        """Analyse *market_data* and return a trading signal.

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

        # Ensure all values are Decimal
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

        min_data_points = self._macd_slow + self._macd_signal
        if len(closes) < min_data_points:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reason": (
                    f"Insufficient data: need {min_data_points} prices, "
                    f"got {len(closes)}"
                ),
                "indicators": {},
            }

        rsi = self._compute_rsi(closes, self._rsi_period)
        macd_data = self._compute_macd(closes)

        if rsi is None or macd_data is None:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reason": "Unable to compute indicators with available data",
                "indicators": {},
            }

        indicators = {
            "rsi": rsi,
            "macd": macd_data["macd"],
            "signal": macd_data["signal"],
            "histogram": macd_data["histogram"],
        }

        # Detect MACD crossover
        macd_crossed_above = (
            macd_data["prev_macd"] <= macd_data["prev_signal"]
            and macd_data["macd"] > macd_data["signal"]
        )
        macd_crossed_below = (
            macd_data["prev_macd"] >= macd_data["prev_signal"]
            and macd_data["macd"] < macd_data["signal"]
        )

        # BUY: RSI oversold + MACD bullish crossover
        if rsi < self._rsi_oversold and macd_crossed_above:
            # Confidence based on how oversold RSI is
            rsi_distance = float(self._rsi_oversold - rsi) / float(self._rsi_oversold)
            confidence = min(0.5 + rsi_distance, 1.0)
            return {
                "action": "buy",
                "confidence": round(confidence, 4),
                "reason": (
                    f"RSI oversold at {rsi} (< {self._rsi_oversold}) "
                    f"with bullish MACD crossover "
                    f"(MACD {macd_data['macd']} > Signal {macd_data['signal']})"
                ),
                "indicators": indicators,
            }

        # SELL: RSI overbought + MACD bearish crossover
        if rsi > self._rsi_overbought and macd_crossed_below:
            rsi_distance = float(rsi - self._rsi_overbought) / float(
                Decimal("100") - self._rsi_overbought
            )
            confidence = min(0.5 + rsi_distance, 1.0)
            return {
                "action": "sell",
                "confidence": round(confidence, 4),
                "reason": (
                    f"RSI overbought at {rsi} (> {self._rsi_overbought}) "
                    f"with bearish MACD crossover "
                    f"(MACD {macd_data['macd']} < Signal {macd_data['signal']})"
                ),
                "indicators": indicators,
            }

        return {
            "action": "hold",
            "confidence": 0.0,
            "reason": (
                f"No confirmed signal: RSI={rsi}, "
                f"MACD={macd_data['macd']}, Signal={macd_data['signal']}"
            ),
            "indicators": indicators,
        }

    async def get_parameters(self) -> dict:
        return {
            "rsi_period": self._rsi_period,
            "rsi_overbought": self._rsi_overbought,
            "rsi_oversold": self._rsi_oversold,
            "macd_fast": self._macd_fast,
            "macd_slow": self._macd_slow,
            "macd_signal": self._macd_signal,
        }

    async def set_parameters(self, params: dict) -> None:
        if "rsi_period" in params:
            self._rsi_period = int(params["rsi_period"])
        if "rsi_overbought" in params:
            self._rsi_overbought = Decimal(str(params["rsi_overbought"]))
        if "rsi_oversold" in params:
            self._rsi_oversold = Decimal(str(params["rsi_oversold"]))
        if "macd_fast" in params:
            self._macd_fast = int(params["macd_fast"])
        if "macd_slow" in params:
            self._macd_slow = int(params["macd_slow"])
        if "macd_signal" in params:
            self._macd_signal = int(params["macd_signal"])
