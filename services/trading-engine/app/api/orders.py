"""Orders API - Phase 1 stub.

Provides endpoints for order creation, listing, retrieval, and cancellation.
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


# --- Schemas ---


class OrderSide(str, Enum):
    buy = "buy"
    sell = "sell"


class OrderType(str, Enum):
    market = "market"
    limit = "limit"
    stop_loss = "stop_loss"


class OrderCreate(BaseModel):
    symbol: str = Field(..., description="Trading pair symbol, e.g. BTC/USDT")
    side: OrderSide
    order_type: OrderType
    quantity: float = Field(..., gt=0)
    price: float | None = Field(None, description="Limit price (required for limit orders)")
    stop_price: float | None = Field(None, description="Stop price (required for stop_loss orders)")


class OrderResponse(BaseModel):
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None
    stop_price: float | None
    status: str
    created_at: str


# --- Endpoints ---


@router.post("/", response_model=OrderResponse, status_code=201)
async def create_order(order: OrderCreate) -> OrderResponse:
    """Create a new order.

    Phase 1 stub: accepts the order and returns it with status 'pending'.
    """
    # TODO: implement order execution via CCXT / exchange integration
    # TODO: validate order against risk service
    # TODO: persist order to database
    # TODO: publish order event to Redis for downstream consumers
    logger.info("TODO: implement order execution | received order: %s %s %s %s", order.side, order.quantity, order.symbol, order.order_type)

    return OrderResponse(
        id=str(uuid.uuid4()),
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        price=order.price,
        stop_price=order.stop_price,
        status="pending",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/", response_model=list[OrderResponse])
async def list_orders() -> list[OrderResponse]:
    """List all orders.

    Phase 1 stub: returns an empty list.
    """
    # TODO: query orders from database with filtering and pagination
    return []


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str) -> OrderResponse:
    """Get a specific order by ID.

    Phase 1 stub: not yet implemented.
    """
    # TODO: fetch order from database by ID
    raise HTTPException(status_code=404, detail="Phase 2")


@router.delete("/{order_id}")
async def cancel_order(order_id: str) -> dict:
    """Cancel an existing order.

    Phase 1 stub: not yet implemented.
    """
    # TODO: cancel order on exchange via CCXT
    # TODO: update order status in database
    raise HTTPException(status_code=404, detail="Phase 2")
