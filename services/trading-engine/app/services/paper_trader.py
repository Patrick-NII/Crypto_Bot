"""Paper trading simulator.

Simulates order execution without connecting to a real exchange.
Maintains in-memory balances, positions, and an order book so that
limit / stop / trailing-stop orders are triggered when price updates
arrive.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional

from app.models.order import (
    Order,
    OrderCreate,
    OrderSide,
    OrderStatus,
    OrderType,
)

logger = logging.getLogger(__name__)

# Default trading fee as a fraction (0.1 %)
_DEFAULT_FEE_RATE = Decimal("0.001")

# Starting paper balance
_STARTING_USDT = Decimal("10000")


class PaperTrader:
    """Simulates trades without a real exchange connection.

    All state is kept in memory; a service restart resets it.
    """

    def __init__(self) -> None:
        self._orders: Dict[str, Order] = {}
        self._balances: Dict[str, Decimal] = {"USDT": _STARTING_USDT}
        self._positions: Dict[str, Decimal] = {}
        self._fee_rate: Decimal = _DEFAULT_FEE_RATE
        # Track highest/lowest price seen for trailing stop orders
        self._trailing_prices: Dict[str, Decimal] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def place_order(
        self, order_create: OrderCreate, current_price: Decimal
    ) -> Order:
        """Accept a new order and, for market orders, fill immediately."""
        order = Order(
            id=str(uuid.uuid4()),
            symbol=order_create.symbol,
            side=order_create.side,
            order_type=order_create.order_type,
            status=OrderStatus.PENDING,
            quantity=order_create.quantity,
            price=order_create.price,
            stop_price=order_create.stop_price,
            take_profit_price=order_create.take_profit_price,
            trailing_pct=order_create.trailing_pct,
            exchange="paper",
            portfolio_id=order_create.portfolio_id,
            strategy=order_create.strategy,
        )

        # Validate balance before accepting
        self._validate_balance(order, current_price)

        if order.order_type == OrderType.MARKET:
            order = self._fill_order(order, current_price)
        elif order.order_type == OrderType.LIMIT:
            # Check if limit can fill immediately
            if self._limit_can_fill(order, current_price):
                fill_price = order.price if order.price is not None else current_price
                order = self._fill_order(order, fill_price)
            else:
                order.status = OrderStatus.OPEN
        elif order.order_type in (OrderType.STOP_LOSS, OrderType.TAKE_PROFIT):
            order.status = OrderStatus.OPEN
        elif order.order_type == OrderType.TRAILING_STOP:
            order.status = OrderStatus.OPEN
            # Initialise trailing anchor price
            self._trailing_prices[order.id] = current_price
        elif order.order_type == OrderType.OCO:
            # OCO has both stop_price and take_profit_price
            order.status = OrderStatus.OPEN
        else:
            order.status = OrderStatus.OPEN

        self._orders[order.id] = order
        logger.info(
            "Paper order %s %s %s %s @ %s -> %s",
            order.id[:8],
            order.side.value,
            order.quantity,
            order.symbol,
            current_price,
            order.status.value,
        )
        return order

    async def check_pending_orders(self, prices: Dict[str, Decimal]) -> List[Order]:
        """Check all open orders against *prices* and fill where triggered.

        Returns the list of orders whose status changed.
        """
        changed: List[Order] = []

        for order in list(self._orders.values()):
            if order.status not in (OrderStatus.OPEN, OrderStatus.PENDING):
                continue

            symbol = order.symbol
            current_price = prices.get(symbol)
            if current_price is None:
                continue

            filled = False

            if order.order_type == OrderType.LIMIT:
                if self._limit_can_fill(order, current_price):
                    fill_price = order.price if order.price is not None else current_price
                    self._fill_order(order, fill_price)
                    filled = True

            elif order.order_type == OrderType.STOP_LOSS:
                if self._stop_loss_triggered(order, current_price):
                    self._fill_order(order, current_price)
                    filled = True

            elif order.order_type == OrderType.TAKE_PROFIT:
                if self._take_profit_triggered(order, current_price):
                    self._fill_order(order, current_price)
                    filled = True

            elif order.order_type == OrderType.TRAILING_STOP:
                if self._trailing_stop_triggered(order, current_price):
                    self._fill_order(order, current_price)
                    filled = True
                else:
                    # Update anchor price
                    self._update_trailing_anchor(order, current_price)

            elif order.order_type == OrderType.OCO:
                if self._stop_loss_triggered(order, current_price):
                    self._fill_order(order, current_price)
                    filled = True
                elif self._take_profit_triggered(order, current_price):
                    self._fill_order(order, current_price)
                    filled = True

            if filled:
                changed.append(order)
                logger.info(
                    "Pending order %s filled @ %s", order.id[:8], order.filled_price
                )

        return changed

    async def get_balance(self) -> Dict[str, Decimal]:
        """Return current balances including base-asset positions."""
        combined: Dict[str, Decimal] = dict(self._balances)
        for asset, qty in self._positions.items():
            current = combined.get(asset, Decimal("0"))
            combined[asset] = current + qty
        return combined

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Look up an order by ID."""
        return self._orders.get(order_id)

    async def cancel_order(self, order_id: str) -> Optional[Order]:
        """Cancel an open order and return it (or ``None``)."""
        order = self._orders.get(order_id)
        if order is None:
            return None
        if order.status not in (OrderStatus.OPEN, OrderStatus.PENDING):
            return order
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)
        # Release any reserved trailing data
        self._trailing_prices.pop(order.id, None)
        logger.info("Paper order %s cancelled", order.id[:8])
        return order

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Return all open orders, optionally filtered by symbol."""
        result: List[Order] = []
        for order in self._orders.values():
            if order.status not in (OrderStatus.OPEN, OrderStatus.PENDING):
                continue
            if symbol and order.symbol != symbol:
                continue
            result.append(order)
        return result

    async def get_all_orders(
        self,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Order]:
        """Return orders with optional filtering and pagination."""
        result: List[Order] = []
        for order in self._orders.values():
            if status and order.status.value != status:
                continue
            if symbol and order.symbol != symbol:
                continue
            result.append(order)
        # Sort newest first
        result.sort(key=lambda o: o.created_at, reverse=True)
        return result[offset: offset + limit]

    async def count_orders(
        self,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> int:
        """Return total order count matching the filters."""
        count = 0
        for order in self._orders.values():
            if status and order.status.value != status:
                continue
            if symbol and order.symbol != symbol:
                continue
            count += 1
        return count

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_balance(self, order: Order, price: Decimal) -> None:
        """Raise ``ValueError`` if the account cannot cover the order."""
        if order.side == OrderSide.BUY:
            cost = order.quantity * price * (Decimal("1") + self._fee_rate)
            available = self._balances.get("USDT", Decimal("0"))
            if cost > available:
                raise ValueError(
                    f"Insufficient USDT balance: need {cost}, have {available}"
                )
        else:
            # Selling -- need the base asset
            base = order.symbol.split("/")[0] if "/" in order.symbol else order.symbol
            available = self._positions.get(base, Decimal("0"))
            if order.quantity > available:
                raise ValueError(
                    f"Insufficient {base} balance: need {order.quantity}, have {available}"
                )

    def _fill_order(self, order: Order, fill_price: Decimal) -> Order:
        """Execute the fill: update balances, positions, and order fields."""
        fee = (order.quantity * fill_price * self._fee_rate).quantize(
            Decimal("0.00000001"), rounding=ROUND_DOWN
        )
        base = order.symbol.split("/")[0] if "/" in order.symbol else order.symbol

        if order.side == OrderSide.BUY:
            total_cost = order.quantity * fill_price + fee
            self._balances["USDT"] = self._balances.get("USDT", Decimal("0")) - total_cost
            self._positions[base] = self._positions.get(base, Decimal("0")) + order.quantity
        else:
            total_proceeds = order.quantity * fill_price - fee
            self._positions[base] = self._positions.get(base, Decimal("0")) - order.quantity
            self._balances["USDT"] = self._balances.get("USDT", Decimal("0")) + total_proceeds
            # Clean up zero/negative dust positions
            if self._positions[base] <= Decimal("0"):
                del self._positions[base]

        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.filled_price = fill_price
        order.fee = fee
        order.updated_at = datetime.now(timezone.utc)

        # Clean up trailing data if present
        self._trailing_prices.pop(order.id, None)

        return order

    # -- trigger checks --

    @staticmethod
    def _limit_can_fill(order: Order, current_price: Decimal) -> bool:
        """A limit BUY fills when price <= limit; SELL when price >= limit."""
        if order.price is None:
            return False
        if order.side == OrderSide.BUY:
            return current_price <= order.price
        return current_price >= order.price

    @staticmethod
    def _stop_loss_triggered(order: Order, current_price: Decimal) -> bool:
        """Stop-loss triggers when price drops to/below stop for a SELL,
        or rises to/above stop for a BUY."""
        if order.stop_price is None:
            return False
        if order.side == OrderSide.SELL:
            return current_price <= order.stop_price
        return current_price >= order.stop_price

    @staticmethod
    def _take_profit_triggered(order: Order, current_price: Decimal) -> bool:
        """Take-profit triggers when price rises to/above target for SELL,
        or drops to/below target for BUY."""
        tp = order.take_profit_price
        if tp is None:
            return False
        if order.side == OrderSide.SELL:
            return current_price >= tp
        return current_price <= tp

    def _trailing_stop_triggered(self, order: Order, current_price: Decimal) -> bool:
        """Trailing stop triggers when price retraces by *trailing_pct* from
        the best price seen since the order was placed."""
        if order.trailing_pct is None:
            return False
        anchor = self._trailing_prices.get(order.id)
        if anchor is None:
            return False

        pct = order.trailing_pct / Decimal("100")

        if order.side == OrderSide.SELL:
            # Anchor tracks the highest price; trigger if price drops pct% from it
            trigger_price = anchor * (Decimal("1") - pct)
            return current_price <= trigger_price
        else:
            # BUY trailing: anchor tracks lowest price; trigger if price rises pct%
            trigger_price = anchor * (Decimal("1") + pct)
            return current_price >= trigger_price

    def _update_trailing_anchor(self, order: Order, current_price: Decimal) -> None:
        """Update the anchor price for a trailing stop order."""
        anchor = self._trailing_prices.get(order.id)
        if anchor is None:
            self._trailing_prices[order.id] = current_price
            return

        if order.side == OrderSide.SELL:
            # Track highest price
            if current_price > anchor:
                self._trailing_prices[order.id] = current_price
        else:
            # Track lowest price
            if current_price < anchor:
                self._trailing_prices[order.id] = current_price
