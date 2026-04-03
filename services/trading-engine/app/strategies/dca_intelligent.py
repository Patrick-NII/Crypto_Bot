"""Intelligent Dollar Cost Averaging strategy.

Performs regular buys with dynamic position sizing: increases buy size on
dips, decreases on pumps, and skips when RSI indicates overbought conditions.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional

from app.strategies.base import BaseStrategy


class IntelligentDCA(BaseStrategy):
    """Intelligent Dollar Cost Averaging.

    Regular buys with dynamic sizing:
    - Normal buy at regular intervals.
    - Increase buy size on dips (buy more when price drops).
    - Decrease buy size on pumps.
    - Skip buy if RSI > overbought threshold.
    """

    name: str = "dca_intelligent"
    description: str = (
        "Smart DCA with dynamic position sizing based on price dips and RSI"
    )

    def __init__(self) -> None:
        self._base_amount: Decimal = Decimal("100")  # base buy in USDT
        self._dip_multiplier: Decimal = Decimal("1.5")
        self._pump_multiplier: Decimal = Decimal("0.5")
        self._dip_threshold_pct: Decimal = Decimal("5.0")  # % drop = dip
        self._pump_threshold_pct: Decimal = Decimal("10.0")  # % rise = pump
        self._rsi_overbought_skip: int = 75  # skip buy above this RSI
        self._rsi_period: int = 14
        self._lookback_period: int = 14  # periods to measure price change

    # ------------------------------------------------------------------
    # Indicator helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_rsi(closes: List[Decimal], period: int) -> Optional[Decimal]:
        """Compute RSI from closing prices.

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

    def _compute_price_change_pct(self, closes: List[Decimal]) -> Optional[Decimal]:
        """Return the percentage price change over the lookback window.

        Positive means price went up, negative means it went down.
        """
        if len(closes) < self._lookback_period + 1:
            return None
        old_price = closes[-(self._lookback_period + 1)]
        current_price = closes[-1]
        if old_price == 0:
            return None
        pct = ((current_price - old_price) / old_price) * Decimal("100")
        return pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # ------------------------------------------------------------------
    # BaseStrategy interface
    # ------------------------------------------------------------------

    async def generate_signal(self, symbol: str, market_data: dict) -> dict:
        """Determine whether to buy, how much, or hold.

        ``market_data`` must contain a ``"closes"`` key whose value is a
        list of :class:`~decimal.Decimal` closing prices (oldest first).

        This strategy never returns ``"sell"`` -- it is a buy-only DCA
        strategy.  Selling is expected to be handled by a separate exit
        strategy or portfolio-level logic.
        """
        raw_closes = market_data.get("closes", [])
        if not raw_closes:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reason": "No closing price data provided",
                "buy_amount": Decimal("0"),
                "multiplier": Decimal("1"),
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
                "buy_amount": Decimal("0"),
                "multiplier": Decimal("1"),
            }

        min_data_points = max(self._rsi_period + 1, self._lookback_period + 1)
        if len(closes) < min_data_points:
            # Not enough history for full analysis -- fall back to a
            # standard-size DCA buy.
            return {
                "action": "buy",
                "confidence": 0.3,
                "reason": (
                    f"Insufficient data for full analysis "
                    f"(need {min_data_points}, got {len(closes)}). "
                    f"Executing standard DCA buy."
                ),
                "buy_amount": self._base_amount,
                "multiplier": Decimal("1"),
            }

        rsi = self._compute_rsi(closes, self._rsi_period)
        price_change_pct = self._compute_price_change_pct(closes)

        # Default to neutral multiplier
        multiplier = Decimal("1")
        reasons: List[str] = []

        # --- RSI gate ---
        if rsi is not None and rsi > Decimal(str(self._rsi_overbought_skip)):
            return {
                "action": "hold",
                "confidence": round(float(rsi) / 100.0, 4),
                "reason": (
                    f"RSI at {rsi} exceeds overbought threshold "
                    f"({self._rsi_overbought_skip}). Skipping DCA buy."
                ),
                "buy_amount": Decimal("0"),
                "multiplier": Decimal("0"),
            }

        # --- Price-change sizing ---
        if price_change_pct is not None:
            if price_change_pct <= -self._dip_threshold_pct:
                multiplier = self._dip_multiplier
                reasons.append(
                    f"Price dipped {price_change_pct}% "
                    f"(threshold -{self._dip_threshold_pct}%): "
                    f"increasing buy x{self._dip_multiplier}"
                )
            elif price_change_pct >= self._pump_threshold_pct:
                multiplier = self._pump_multiplier
                reasons.append(
                    f"Price pumped +{price_change_pct}% "
                    f"(threshold +{self._pump_threshold_pct}%): "
                    f"reducing buy x{self._pump_multiplier}"
                )
            else:
                reasons.append(
                    f"Price change {price_change_pct}% within normal range"
                )

        if rsi is not None:
            reasons.append(f"RSI={rsi}")

        buy_amount = (self._base_amount * multiplier).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Confidence: higher when we are buying on a dip with low RSI
        confidence = 0.5
        if multiplier > Decimal("1"):
            confidence = 0.7
        if rsi is not None and rsi < Decimal("40"):
            confidence = min(confidence + 0.15, 1.0)

        return {
            "action": "buy",
            "confidence": round(confidence, 4),
            "reason": ". ".join(reasons) if reasons else "Standard DCA buy",
            "buy_amount": buy_amount,
            "multiplier": multiplier,
        }

    async def get_parameters(self) -> dict:
        return {
            "base_amount": self._base_amount,
            "dip_multiplier": self._dip_multiplier,
            "pump_multiplier": self._pump_multiplier,
            "dip_threshold_pct": self._dip_threshold_pct,
            "pump_threshold_pct": self._pump_threshold_pct,
            "rsi_overbought_skip": self._rsi_overbought_skip,
            "rsi_period": self._rsi_period,
            "lookback_period": self._lookback_period,
        }

    async def set_parameters(self, params: dict) -> None:
        if "base_amount" in params:
            self._base_amount = Decimal(str(params["base_amount"]))
        if "dip_multiplier" in params:
            self._dip_multiplier = Decimal(str(params["dip_multiplier"]))
        if "pump_multiplier" in params:
            self._pump_multiplier = Decimal(str(params["pump_multiplier"]))
        if "dip_threshold_pct" in params:
            self._dip_threshold_pct = Decimal(str(params["dip_threshold_pct"]))
        if "pump_threshold_pct" in params:
            self._pump_threshold_pct = Decimal(str(params["pump_threshold_pct"]))
        if "rsi_overbought_skip" in params:
            self._rsi_overbought_skip = int(params["rsi_overbought_skip"])
        if "rsi_period" in params:
            self._rsi_period = int(params["rsi_period"])
        if "lookback_period" in params:
            self._lookback_period = int(params["lookback_period"])
