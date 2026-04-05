"""Paper trading simulator.

Simulates order execution without connecting to a real exchange.
Maintains in-memory balances, positions, and an order book so that
limit / stop / trailing-stop orders are triggered when price updates
arrive.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Iterable, List, Optional

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


@dataclass
class PaperAccountState:
    """Isolated paper account state for a single user."""

    orders: Dict[str, Order] = field(default_factory=dict)
    balances: Dict[str, Decimal] = field(
        default_factory=lambda: {"USDT": _STARTING_USDT}
    )
    positions: Dict[str, Decimal] = field(default_factory=dict)
    trailing_prices: Dict[str, Decimal] = field(default_factory=dict)


class PaperTrader:
    """Simulates trades without a real exchange connection.

    All state is kept in memory; a service restart resets it.
    """

    def __init__(self) -> None:
        self._accounts: Dict[str, PaperAccountState] = {}
        self._order_owners: Dict[str, str] = {}
        self._fee_rate: Decimal = _DEFAULT_FEE_RATE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def place_order(
        self,
        user_id: str,
        order_create: OrderCreate,
        current_price: Decimal,
    ) -> Order:
        """Accept a new order and, for market orders, fill immediately."""
        state = self._get_account_state(user_id)
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
        self._validate_balance(state, order, current_price)

        if order.order_type == OrderType.MARKET:
            order = self._fill_order(state, order, current_price)
        elif order.order_type == OrderType.LIMIT:
            # Check if limit can fill immediately
            if self._limit_can_fill(order, current_price):
                fill_price = order.price if order.price is not None else current_price
                order = self._fill_order(state, order, fill_price)
            else:
                order.status = OrderStatus.OPEN
        elif order.order_type in (OrderType.STOP_LOSS, OrderType.TAKE_PROFIT):
            order.status = OrderStatus.OPEN
        elif order.order_type == OrderType.TRAILING_STOP:
            order.status = OrderStatus.OPEN
            # Initialise trailing anchor price
            state.trailing_prices[order.id] = current_price
        elif order.order_type == OrderType.OCO:
            # OCO has both stop_price and take_profit_price
            order.status = OrderStatus.OPEN
        else:
            order.status = OrderStatus.OPEN

        state.orders[order.id] = order
        self._order_owners[order.id] = user_id
        logger.info(
            "Paper order %s user=%s %s %s %s @ %s -> %s",
            order.id[:8],
            user_id,
            order.side.value,
            order.quantity,
            order.symbol,
            current_price,
            order.status.value,
        )
        return order

    async def check_pending_orders(
        self,
        prices: Dict[str, Decimal],
        user_id: Optional[str] = None,
    ) -> List[Order]:
        """Check all open orders against *prices* and fill where triggered.

        Returns the list of orders whose status changed.
        """
        changed: List[Order] = []

        for account_user_id in self._iter_user_ids(user_id):
            state = self._accounts.get(account_user_id)
            if state is None:
                continue

            for order in list(state.orders.values()):
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
                        self._fill_order(state, order, fill_price)
                        filled = True

                elif order.order_type == OrderType.STOP_LOSS:
                    if self._stop_loss_triggered(order, current_price):
                        self._fill_order(state, order, current_price)
                        filled = True

                elif order.order_type == OrderType.TAKE_PROFIT:
                    if self._take_profit_triggered(order, current_price):
                        self._fill_order(state, order, current_price)
                        filled = True

                elif order.order_type == OrderType.TRAILING_STOP:
                    if self._trailing_stop_triggered(state, order, current_price):
                        self._fill_order(state, order, current_price)
                        filled = True
                    else:
                        # Update anchor price
                        self._update_trailing_anchor(state, order, current_price)

                elif order.order_type == OrderType.OCO:
                    if self._stop_loss_triggered(order, current_price):
                        self._fill_order(state, order, current_price)
                        filled = True
                    elif self._take_profit_triggered(order, current_price):
                        self._fill_order(state, order, current_price)
                        filled = True

                if filled:
                    changed.append(order)
                    logger.info(
                        "Pending order %s user=%s filled @ %s",
                        order.id[:8],
                        account_user_id,
                        order.filled_price,
                    )

        return changed

    async def get_balance(self, user_id: str) -> Dict[str, Decimal]:
        """Return current balances including base-asset positions."""
        state = self._get_account_state(user_id)
        combined: Dict[str, Decimal] = dict(state.balances)
        for asset, qty in state.positions.items():
            current = combined.get(asset, Decimal("0"))
            combined[asset] = current + qty
        return combined

    async def get_order(self, user_id: str, order_id: str) -> Optional[Order]:
        """Look up an order by ID."""
        state = self._accounts.get(user_id)
        if state is None:
            return None
        return state.orders.get(order_id)

    async def cancel_order(self, user_id: str, order_id: str) -> Optional[Order]:
        """Cancel an open order and return it (or ``None``)."""
        state = self._accounts.get(user_id)
        if state is None:
            return None
        order = state.orders.get(order_id)
        if order is None:
            return None
        if order.status not in (OrderStatus.OPEN, OrderStatus.PENDING):
            return order
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)
        # Release any reserved trailing data
        state.trailing_prices.pop(order.id, None)
        logger.info("Paper order %s user=%s cancelled", order.id[:8], user_id)
        return order

    async def get_open_orders(
        self,
        user_id: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> List[Order]:
        """Return all open orders, optionally filtered by symbol."""
        result: List[Order] = []
        for account_user_id in self._iter_user_ids(user_id):
            state = self._accounts.get(account_user_id)
            if state is None:
                continue
            for order in state.orders.values():
                if order.status not in (OrderStatus.OPEN, OrderStatus.PENDING):
                    continue
                if symbol and order.symbol != symbol:
                    continue
                result.append(order)
        return result

    async def get_all_orders(
        self,
        user_id: str,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Order]:
        """Return orders with optional filtering and pagination."""
        state = self._accounts.get(user_id)
        if state is None:
            return []
        result: List[Order] = []
        for order in state.orders.values():
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
        user_id: str,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> int:
        """Return total order count matching the filters."""
        state = self._accounts.get(user_id)
        if state is None:
            return 0
        count = 0
        for order in state.orders.values():
            if status and order.status.value != status:
                continue
            if symbol and order.symbol != symbol:
                continue
            count += 1
        return count

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def get_order_owner(self, order_id: str) -> Optional[str]:
        """Return the owning user for an order ID."""
        return self._order_owners.get(order_id)

    def _get_account_state(self, user_id: str) -> PaperAccountState:
        state = self._accounts.get(user_id)
        if state is None:
            state = PaperAccountState()
            self._accounts[user_id] = state
        return state

    def _iter_user_ids(self, user_id: Optional[str]) -> Iterable[str]:
        if user_id is not None:
            return (user_id,)
        return tuple(self._accounts.keys())

    def _validate_balance(
        self,
        state: PaperAccountState,
        order: Order,
        price: Decimal,
    ) -> None:
        """Raise ``ValueError`` if the account cannot cover the order."""
        if order.side == OrderSide.BUY:
            cost = order.quantity * price * (Decimal("1") + self._fee_rate)
            available = state.balances.get("USDT", Decimal("0"))
            if cost > available:
                raise ValueError(
                    f"Insufficient USDT balance: need {cost}, have {available}"
                )
        else:
            # Selling -- need the base asset
            base = order.symbol.split("/")[0] if "/" in order.symbol else order.symbol
            available = state.positions.get(base, Decimal("0"))
            if order.quantity > available:
                raise ValueError(
                    f"Insufficient {base} balance: need {order.quantity}, have {available}"
                )

    def _fill_order(
        self,
        state: PaperAccountState,
        order: Order,
        fill_price: Decimal,
    ) -> Order:
        """Execute the fill: update balances, positions, and order fields."""
        fee = (order.quantity * fill_price * self._fee_rate).quantize(
            Decimal("0.00000001"), rounding=ROUND_DOWN
        )
        base = order.symbol.split("/")[0] if "/" in order.symbol else order.symbol

        if order.side == OrderSide.BUY:
            total_cost = order.quantity * fill_price + fee
            state.balances["USDT"] = state.balances.get("USDT", Decimal("0")) - total_cost
            state.positions[base] = state.positions.get(base, Decimal("0")) + order.quantity
        else:
            total_proceeds = order.quantity * fill_price - fee
            state.positions[base] = state.positions.get(base, Decimal("0")) - order.quantity
            state.balances["USDT"] = state.balances.get("USDT", Decimal("0")) + total_proceeds
            # Clean up zero/negative dust positions
            if state.positions[base] <= Decimal("0"):
                del state.positions[base]

        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.filled_price = fill_price
        order.fee = fee
        order.updated_at = datetime.now(timezone.utc)

        # Clean up trailing data if present
        state.trailing_prices.pop(order.id, None)

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

    def _trailing_stop_triggered(
        self,
        state: PaperAccountState,
        order: Order,
        current_price: Decimal,
    ) -> bool:
        """Trailing stop triggers when price retraces by *trailing_pct* from
        the best price seen since the order was placed."""
        if order.trailing_pct is None:
            return False
        anchor = state.trailing_prices.get(order.id)
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

    def _update_trailing_anchor(
        self,
        state: PaperAccountState,
        order: Order,
        current_price: Decimal,
    ) -> None:
        """Update the anchor price for a trailing stop order."""
        anchor = state.trailing_prices.get(order.id)
        if anchor is None:
            state.trailing_prices[order.id] = current_price
            return

        if order.side == OrderSide.SELL:
            # Track highest price
            if current_price > anchor:
                state.trailing_prices[order.id] = current_price
        else:
            # Track lowest price
            if current_price < anchor:
                state.trailing_prices[order.id] = current_price
