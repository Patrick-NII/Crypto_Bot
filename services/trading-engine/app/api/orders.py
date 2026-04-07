"""Orders REST API -- Phase 2 full implementation.

Provides endpoints for order creation, listing, retrieval, cancellation,
balance queries, and pending-order checks.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

from app.core.auth import resolve_request_user_id
from app.core.config import settings
from app.models.order import (
    Order,
    OrderCreate,
    OrderListResponse,
    OrderPreflightResponse,
    OrderSide,
    OrderResponse,
    OrderStatus,
)

from app.services.error_catalog import get_full_catalog, classify_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


@router.get("/error-catalog")
async def error_catalog() -> dict:
    """Return the full structured error catalog (public, no auth required).

    Frontend fetches this at startup to display consistent error messages.
    Cached for 1 hour client-side.
    """
    return {"version": "1.0", "entries": get_full_catalog()}


def _get_order_manager():
    """Return the global OrderManager instance (set during app lifespan)."""
    from app.main import order_manager

    if order_manager is None:
        raise HTTPException(status_code=503, detail="Order manager not initialised")
    return order_manager


async def _ensure_wallet_access(auth_header: Optional[str]) -> None:
    """Verify the user is authenticated before exposing trading routes."""
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization required")

    url = f"{settings.AUTH_SERVICE_URL}/api/v1/auth/me"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"Authorization": auth_header})
            if resp.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid token")
            resp.raise_for_status()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unable to validate access: {exc}")


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("/", response_model=OrderResponse, status_code=201)
async def create_order(request: Request, order: OrderCreate) -> OrderResponse:
    """Create a new order.

    The order is validated against the risk service, then executed via
    the paper trader (default) or the live exchange.
    """
    mgr = _get_order_manager()
    await _ensure_wallet_access(request.headers.get("Authorization"))
    user_id = resolve_request_user_id(request)
    try:
        result: Order = await mgr.create_order(
            order,
            user_id=user_id,
            auth_header=request.headers.get("Authorization"),
        )
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
    request: Request,
    status: Optional[str] = Query(None, description="Filter by order status"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> OrderListResponse:
    """List orders with optional filtering and pagination."""
    mgr = _get_order_manager()
    await _ensure_wallet_access(request.headers.get("Authorization"))
    user_id = resolve_request_user_id(request)
    orders = await mgr.list_orders(
        user_id=user_id,
        status=status,
        symbol=symbol,
        limit=limit,
        offset=offset,
    )
    total = await mgr.count_orders(user_id=user_id, status=status, symbol=symbol)
    return OrderListResponse(
        orders=[OrderResponse.from_order(o) for o in orders],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/balance")
async def get_balance(request: Request) -> Dict[str, str]:
    """Return current trading balances (paper or live).

    Decimal values are serialised as strings for JSON safety.
    """
    mgr = _get_order_manager()
    auth_header = request.headers.get("Authorization")
    await _ensure_wallet_access(auth_header)
    balances = await mgr.get_balance(
        resolve_request_user_id(request),
        auth_header=auth_header,
    )
    return {k: str(v) for k, v in balances.items()}


@router.get("/preflight", response_model=OrderPreflightResponse)
async def preflight_order(
    request: Request,
    symbol: str = Query(..., min_length=2, description="Asset or pair to trade"),
    side: OrderSide = Query(OrderSide.BUY, description="Trade side"),
    quantity: float = Query(..., gt=0, description="Base quantity requested"),
    reference_price: Optional[float] = Query(None, gt=0, description="Reference price used by the UI"),
) -> OrderPreflightResponse:
    """Preview pair resolution, balances, fees and blockers before placing an order."""
    mgr = _get_order_manager()
    auth_header = request.headers.get("Authorization")
    await _ensure_wallet_access(auth_header)
    try:
        return await mgr.preview_order(
            symbol=symbol,
            side=side.value,
            quantity=Decimal(str(quantity)),
            user_id=resolve_request_user_id(request),
            reference_price=Decimal(str(reference_price)) if reference_price is not None else None,
            auth_header=auth_header,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


from pydantic import BaseModel, Field


class ExecuteWithConversionRequest(BaseModel):
    symbol: str = Field(..., description="Asset or pair to trade (BTC, ETH, BTC/USDT...)")
    side: OrderSide
    quantity: float = Field(..., gt=0)
    max_retries: int = Field(3, ge=1, le=5)


@router.post("/execute-with-conversion")
async def execute_with_conversion(
    request: Request,
    payload: ExecuteWithConversionRequest,
) -> Dict:
    """Execute an order with automatic conversion chain if needed.

    Used by auto-trader: if EUR balance but order is BTC/USDT,
    the engine will first convert EUR→USDT then place BTC/USDT order.
    """
    mgr = _get_order_manager()
    auth_header = request.headers.get("Authorization")
    await _ensure_wallet_access(auth_header)

    try:
        result = await mgr.execute_chain(
            symbol=payload.symbol,
            side=payload.side.value,
            quantity=Decimal(str(payload.quantity)),
            user_id=resolve_request_user_id(request),
            auth_header=auth_header,
            max_retries=payload.max_retries,
        )
        return result
    except Exception as exc:
        detail = classify_error(exc)
        raise HTTPException(status_code=500, detail=detail.to_dict())


@router.post("/check-pending")
async def check_pending_orders(request: Request) -> Dict[str, object]:
    """Trigger a check of all pending paper orders against current prices.

    Returns the list of orders that were filled as a result.
    """
    mgr = _get_order_manager()
    await _ensure_wallet_access(request.headers.get("Authorization"))
    changed = await mgr.check_pending_orders(resolve_request_user_id(request))
    return {
        "checked": True,
        "filled_count": len(changed),
        "filled_orders": [OrderResponse.from_order(o).dict() for o in changed],
    }


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, request: Request) -> OrderResponse:
    """Retrieve a single order by ID."""
    mgr = _get_order_manager()
    await _ensure_wallet_access(request.headers.get("Authorization"))
    order = await mgr.get_order(order_id, resolve_request_user_id(request))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderResponse.from_order(order)


@router.delete("/{order_id}", response_model=OrderResponse)
async def cancel_order(order_id: str, request: Request) -> OrderResponse:
    """Cancel an open or pending order."""
    mgr = _get_order_manager()
    await _ensure_wallet_access(request.headers.get("Authorization"))
    try:
        order = await mgr.cancel_order(order_id, resolve_request_user_id(request))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return OrderResponse.from_order(order)
