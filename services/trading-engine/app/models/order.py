"""Order models for the Trading Engine service.

Defines all order-related Pydantic models: enums for side/type/status,
request models (OrderCreate), response models (Order, OrderResponse),
and list wrappers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class OrderSide(str, Enum):
    """Side of the trade."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Supported order types."""

    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    OCO = "oco"


class OrderStatus(str, Enum):
    """Lifecycle states of an order."""

    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    FAILED = "failed"
    EXPIRED = "expired"


class OrderCreate(BaseModel):
    """Request body for creating a new order.

    Either ``quantity`` (base asset) OR ``quote_quantity`` (quote asset) must
    be provided — exactly one of the two. ``quote_quantity`` is only valid for
    ``order_type=market`` because Binance does not support it for limit orders.
    """

    symbol: str = Field(..., description="Trading pair symbol, e.g. BTC/USDT or BTC")
    side: OrderSide
    order_type: OrderType
    quantity: Optional[Decimal] = Field(
        None, gt=0, description="Base-asset quantity (e.g. 0.5 BTC)"
    )
    quote_quantity: Optional[Decimal] = Field(
        None,
        gt=0,
        description="Quote-asset quantity (e.g. 20 USDT). Market orders only.",
    )
    price: Optional[Decimal] = Field(None, description="Limit price (required for limit orders)")
    stop_price: Optional[Decimal] = Field(None, description="Stop price (for stop/OCO orders)")
    take_profit_price: Optional[Decimal] = Field(
        None, description="Take-profit price (for OCO orders)"
    )
    trailing_pct: Optional[Decimal] = Field(
        None, description="Trailing percentage (for trailing stop orders)"
    )
    portfolio_id: Optional[str] = Field(None, description="Portfolio to attribute trade to")
    strategy: Optional[str] = Field(None, description="Strategy that generated this order")
    client_order_id: Optional[str] = Field(
        None,
        description=(
            "Client-supplied idempotency key. When provided, retries with the "
            "same value return the existing order instead of creating a duplicate."
        ),
        max_length=36,
    )

    @model_validator(mode="after")
    def _validate_quantity_exclusivity(self) -> "OrderCreate":
        has_qty = self.quantity is not None
        has_quote = self.quote_quantity is not None
        if has_qty == has_quote:
            raise ValueError(
                "Exactly one of 'quantity' or 'quote_quantity' must be provided."
            )
        if has_quote and self.order_type != OrderType.MARKET:
            raise ValueError(
                "'quote_quantity' is only supported for market orders."
            )
        if self.order_type == OrderType.LIMIT and self.price is None:
            raise ValueError("Limit orders require 'price'.")
        return self

    class Config:
        json_encoders = {Decimal: str}


class Order(BaseModel):
    """Full order representation used internally and for API responses."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus = OrderStatus.PENDING
    quantity: Decimal
    filled_quantity: Decimal = Decimal("0")
    price: Optional[Decimal] = None
    filled_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    trailing_pct: Optional[Decimal] = None
    fee: Decimal = Decimal("0")
    exchange: str = "paper"
    exchange_order_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    strategy: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: Optional[str] = None

    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class OrderResponse(BaseModel):
    """Serialised order returned by API endpoints."""

    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    quantity: str  # Decimal serialised as string for JSON
    filled_quantity: str
    price: Optional[str] = None
    filled_price: Optional[str] = None
    stop_price: Optional[str] = None
    take_profit_price: Optional[str] = None
    trailing_pct: Optional[str] = None
    fee: str
    exchange: str
    exchange_order_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    strategy: Optional[str] = None
    created_at: str
    updated_at: str
    error_message: Optional[str] = None

    @classmethod
    def from_order(cls, order: Order) -> OrderResponse:
        """Convert an internal Order to an API-safe OrderResponse."""
        return cls(
            id=order.id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            status=order.status,
            quantity=str(order.quantity),
            filled_quantity=str(order.filled_quantity),
            price=str(order.price) if order.price is not None else None,
            filled_price=str(order.filled_price) if order.filled_price is not None else None,
            stop_price=str(order.stop_price) if order.stop_price is not None else None,
            take_profit_price=(
                str(order.take_profit_price) if order.take_profit_price is not None else None
            ),
            trailing_pct=str(order.trailing_pct) if order.trailing_pct is not None else None,
            fee=str(order.fee),
            exchange=order.exchange,
            exchange_order_id=order.exchange_order_id,
            portfolio_id=order.portfolio_id,
            strategy=order.strategy,
            created_at=order.created_at.isoformat(),
            updated_at=order.updated_at.isoformat(),
            error_message=order.error_message,
        )


class OrderPreflightResponse(BaseModel):
    """Preflight preview returned before placing an order."""

    requested_symbol: str
    resolved_symbol: str
    side: OrderSide
    base_asset: str
    quote_asset: str
    input_quantity: str
    adjusted_quantity: str
    reference_price: Optional[str] = None
    estimated_price: Optional[str] = None
    estimated_notional: Optional[str] = None
    estimated_fee: Optional[str] = None
    fee_rate: str = "0.001"
    min_notional: Optional[str] = None
    available_quote: Optional[str] = None
    available_base: Optional[str] = None
    conversion_symbol: Optional[str] = None
    conversion_side: Optional[OrderSide] = None
    conversion_from_asset: Optional[str] = None
    conversion_required_quantity: Optional[str] = None
    conversion_estimated_spend: Optional[str] = None
    can_execute: bool
    blocking_reason: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class OrderListResponse(BaseModel):
    """Paginated list of orders."""

    orders: List[OrderResponse]
    total: int
    limit: int
    offset: int


class SymbolInfoResponse(BaseModel):
    """Exchange filters for a trading pair (LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL).

    Consumed by the frontend to validate user input before submission.
    All numeric fields are serialised as strings so that the frontend can
    parse them into ``BigNumber`` or ``Decimal`` without losing precision.
    """

    symbol: str
    base_asset: str
    quote_asset: str
    step_size: str
    tick_size: str
    min_qty: str
    max_qty: str
    min_notional: str
    base_precision: int
    quote_precision: int
    is_spot: bool = True
