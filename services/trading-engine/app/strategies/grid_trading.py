"""Grid trading strategy for ranging/sideways markets.

Places buy orders at lower grid levels and sell orders at upper levels,
profiting from price oscillation within a defined range.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional, Set

from app.strategies.base import BaseStrategy


class GridTrading(BaseStrategy):
    """Grid trading for ranging/sideways markets.

    Places buy orders at lower grid levels and sell at upper levels.
    Profits from oscillation within a price range.
    """

    name: str = "grid_trading"
    description: str = (
        "Grid trading strategy for sideways markets - "
        "profits from price oscillation"
    )

    def __init__(self) -> None:
        self._grid_lower: Decimal = Decimal("90")
        self._grid_upper: Decimal = Decimal("110")
        self._grid_levels: int = 10
        self._quantity_per_grid: Decimal = Decimal("1")
        # Track which grid levels have active positions (bought but not sold)
        self._active_levels: Set[int] = set()
        # Cache of computed grid prices
        self._grid_prices: Optional[List[Decimal]] = None

    # ------------------------------------------------------------------
    # Grid helpers
    # ------------------------------------------------------------------

    def _compute_grid_prices(self) -> List[Decimal]:
        """Return the list of grid-line prices from lower to upper."""
        if self._grid_prices is not None:
            return self._grid_prices

        if self._grid_levels < 2:
            self._grid_prices = [self._grid_lower, self._grid_upper]
            return self._grid_prices

        step = (self._grid_upper - self._grid_lower) / Decimal(self._grid_levels - 1)
        prices: List[Decimal] = []
        for i in range(self._grid_levels):
            price = self._grid_lower + step * Decimal(i)
            prices.append(price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        self._grid_prices = prices
        return prices

    def _find_grid_level(self, price: Decimal) -> int:
        """Return the index of the nearest grid level at or below *price*.

        Returns -1 if the price is below the lowest grid line, or
        ``grid_levels - 1`` if at or above the highest line.
        """
        grid_prices = self._compute_grid_prices()
        if price < grid_prices[0]:
            return -1
        for i in range(len(grid_prices) - 1, -1, -1):
            if price >= grid_prices[i]:
                return i
        return -1

    def _invalidate_grid_cache(self) -> None:
        """Clear the cached grid prices (call after parameter changes)."""
        self._grid_prices = None

    # ------------------------------------------------------------------
    # BaseStrategy interface
    # ------------------------------------------------------------------

    async def generate_signal(self, symbol: str, market_data: dict) -> dict:
        """Determine the grid-based trading signal from the current price.

        ``market_data`` must contain a ``"current_price"`` key with the
        latest price as a :class:`~decimal.Decimal` (or a value
        convertible to one).
        """
        raw_price = market_data.get("current_price")
        if raw_price is None:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reason": "No current_price provided in market data",
                "grid_level": -1,
                "grid_price": Decimal("0"),
            }

        try:
            current_price = (
                raw_price
                if isinstance(raw_price, Decimal)
                else Decimal(str(raw_price))
            )
        except (InvalidOperation, TypeError, ValueError):
            return {
                "action": "hold",
                "confidence": 0.0,
                "reason": "Invalid current_price value",
                "grid_level": -1,
                "grid_price": Decimal("0"),
            }

        grid_prices = self._compute_grid_prices()

        # Price outside range
        if current_price < self._grid_lower:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reason": (
                    f"Price {current_price} below grid range "
                    f"({self._grid_lower} - {self._grid_upper})"
                ),
                "grid_level": -1,
                "grid_price": self._grid_lower,
            }

        if current_price > self._grid_upper:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reason": (
                    f"Price {current_price} above grid range "
                    f"({self._grid_lower} - {self._grid_upper})"
                ),
                "grid_level": self._grid_levels - 1,
                "grid_price": self._grid_upper,
            }

        level = self._find_grid_level(current_price)

        # Check for BUY: price at or below a grid level without active position
        # We look for the highest un-filled level at or below current price.
        buy_level: Optional[int] = None
        for lv in range(level, -1, -1):
            if lv not in self._active_levels:
                buy_level = lv
                break

        if buy_level is not None:
            self._active_levels.add(buy_level)
            distance_from_lower = float(current_price - self._grid_lower) / float(
                self._grid_upper - self._grid_lower
            )
            # More confident when buying near the bottom of the range
            confidence = min(1.0 - distance_from_lower + 0.3, 1.0)
            return {
                "action": "buy",
                "confidence": round(max(confidence, 0.1), 4),
                "reason": (
                    f"Price {current_price} at grid level {buy_level} "
                    f"(grid price {grid_prices[buy_level]}). "
                    f"Buying {self._quantity_per_grid} units."
                ),
                "grid_level": buy_level,
                "grid_price": grid_prices[buy_level],
            }

        # Check for SELL: price above a grid level that has an active position
        # We look for the lowest active level below the current level.
        sell_level: Optional[int] = None
        for lv in range(0, level + 1):
            if lv in self._active_levels:
                # Only sell if we are at least one grid level above the buy
                if level > lv:
                    sell_level = lv
                    break

        if sell_level is not None:
            self._active_levels.discard(sell_level)
            distance_from_upper = float(self._grid_upper - current_price) / float(
                self._grid_upper - self._grid_lower
            )
            confidence = min(1.0 - distance_from_upper + 0.3, 1.0)
            return {
                "action": "sell",
                "confidence": round(max(confidence, 0.1), 4),
                "reason": (
                    f"Price {current_price} rose above grid level {sell_level} "
                    f"(grid price {grid_prices[sell_level]}). "
                    f"Selling {self._quantity_per_grid} units."
                ),
                "grid_level": sell_level,
                "grid_price": grid_prices[sell_level],
            }

        return {
            "action": "hold",
            "confidence": 0.0,
            "reason": (
                f"No grid action at price {current_price} "
                f"(level {level}). All reachable levels filled."
            ),
            "grid_level": level,
            "grid_price": grid_prices[level] if 0 <= level < len(grid_prices) else Decimal("0"),
        }

    async def get_parameters(self) -> dict:
        return {
            "grid_lower": self._grid_lower,
            "grid_upper": self._grid_upper,
            "grid_levels": self._grid_levels,
            "quantity_per_grid": self._quantity_per_grid,
            "active_levels": sorted(self._active_levels),
        }

    async def set_parameters(self, params: dict) -> None:
        changed_grid = False
        if "grid_lower" in params:
            self._grid_lower = Decimal(str(params["grid_lower"]))
            changed_grid = True
        if "grid_upper" in params:
            self._grid_upper = Decimal(str(params["grid_upper"]))
            changed_grid = True
        if "grid_levels" in params:
            self._grid_levels = int(params["grid_levels"])
            changed_grid = True
        if "quantity_per_grid" in params:
            self._quantity_per_grid = Decimal(str(params["quantity_per_grid"]))
        if "active_levels" in params:
            self._active_levels = set(int(lv) for lv in params["active_levels"])
        if changed_grid:
            self._invalidate_grid_cache()
