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

from pydantic import BaseModel, Field


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
    """Request body for creating a new order."""

    symbol: str = Field(..., description="Trading pair symbol, e.g. BTC/USDT or BTC")
    side: OrderSide
    order_type: OrderType
    quantity: Decimal = Field(..., gt=0, description="Quantity to buy/sell")
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


class OrderListResponse(BaseModel):
    """Paginated list of orders."""

    orders: List[OrderResponse]
    total: int
    limit: int
    offset: int
