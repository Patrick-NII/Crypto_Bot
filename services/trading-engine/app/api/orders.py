"""Orders REST API -- Phase 2 full implementation.

Provides endpoints for order creation, listing, retrieval, cancellation,
balance queries, and pending-order checks.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.order import (
    Order,
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


def _get_order_manager():
    """Return the global OrderManager instance (set during app lifespan)."""
    from app.main import order_manager

    if order_manager is None:
        raise HTTPException(status_code=503, detail="Order manager not initialised")
    return order_manager


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("/", response_model=OrderResponse, status_code=201)
async def create_order(order: OrderCreate) -> OrderResponse:
    """Create a new order.

    The order is validated against the risk service, then executed via
    the paper trader (default) or the live exchange.
    """
    mgr = _get_order_manager()
    try:
        result: Order = await mgr.create_order(order, user_id="default")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if result.status == OrderStatus.FAILED:
        raise HTTPException(
            status_code=422,
            detail=result.error_message or "Order execution failed",
        )

    return OrderResponse.from_order(result)


@router.get("/", response_model=OrderListResponse)
async def list_orders(
    status: Optional[str] = Query(None, description="Filter by order status"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> OrderListResponse:
    """List orders with optional filtering and pagination."""
    mgr = _get_order_manager()
    orders = await mgr.list_orders(
        status=status, symbol=symbol, limit=limit, offset=offset
    )
    total = await mgr.count_orders(status=status, symbol=symbol)
    return OrderListResponse(
        orders=[OrderResponse.from_order(o) for o in orders],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/balance")
async def get_balance() -> Dict[str, str]:
    """Return current trading balances (paper or live).

    Decimal values are serialised as strings for JSON safety.
    """
    mgr = _get_order_manager()
    balances = await mgr.get_balance()
    return {k: str(v) for k, v in balances.items()}


@router.post("/check-pending")
async def check_pending_orders() -> Dict[str, object]:
    """Trigger a check of all pending paper orders against current prices.

    Returns the list of orders that were filled as a result.
    """
    mgr = _get_order_manager()
    changed = await mgr.check_pending_orders()
    return {
        "checked": True,
        "filled_count": len(changed),
        "filled_orders": [OrderResponse.from_order(o).dict() for o in changed],
    }


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str) -> OrderResponse:
    """Retrieve a single order by ID."""
    mgr = _get_order_manager()
    order = await mgr.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderResponse.from_order(order)


@router.delete("/{order_id}", response_model=OrderResponse)
async def cancel_order(order_id: str) -> OrderResponse:
    """Cancel an open or pending order."""
    mgr = _get_order_manager()
    try:
        order = await mgr.cancel_order(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return OrderResponse.from_order(order)
