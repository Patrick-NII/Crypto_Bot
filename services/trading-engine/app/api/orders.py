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
    SymbolInfoResponse,
)

from app.services.error_catalog import get_full_catalog, classify_error
from app.services.exchange_client import ExchangeClient
from app.services.symbol_info import symbol_info_service

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

    Supports both ``quantity`` (base asset) and ``quote_quantity`` (quote
    asset) — exactly one must be provided. When ``client_order_id`` is set,
    retries with the same value return the existing order instead of
    creating a duplicate.
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


@router.get("/symbol-info/{symbol:path}", response_model=SymbolInfoResponse)
async def get_symbol_info(request: Request, symbol: str) -> SymbolInfoResponse:
    """Return Binance exchange filters for a trading pair.

    Used by the frontend to validate user input (stepSize, tickSize,
    minNotional) BEFORE submission. The path accepts any form: ``BTC``,
    ``BTC/USDT``, ``BTCUSDT``.
    """
    mgr = _get_order_manager()
    auth_header = request.headers.get("Authorization")
    await _ensure_wallet_access(auth_header)

    from app.services.order_manager import OrderManager  # noqa: F401

    # Try per-user client first, fallback to global
    client = None
    close_client = False
    if auth_header:
        client = await mgr._get_user_exchange_client(auth_header)  # noqa: SLF001
        close_client = client is not None
    if client is None:
        client = mgr._exchange_client  # noqa: SLF001
    if client is None:
        # Build an anonymous read-only client (public markets endpoint)
        client = ExchangeClient(
            exchange_id=settings.DEFAULT_EXCHANGE,
            api_key=None,
            api_secret=None,
            sandbox=False,
        )
        close_client = True

    try:
        info = await symbol_info_service.get_symbol_info(symbol, client)
    finally:
        if close_client and client is not None:
            try:
                await client.close()
            except Exception:
                pass

    if info is None:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    return SymbolInfoResponse(**info.to_dict())


@router.get("/open", response_model=OrderListResponse)
async def list_open_orders_endpoint(
    request: Request,
    symbol: Optional[str] = Query(None, description="Optional symbol filter"),
) -> OrderListResponse:
    """Return only the user's open/pending orders (optimised for polling)."""
    mgr = _get_order_manager()
    auth_header = request.headers.get("Authorization")
    await _ensure_wallet_access(auth_header)
    user_id = resolve_request_user_id(request)
    orders = await mgr.list_open_orders(
        user_id=user_id,
        symbol=symbol,
        auth_header=auth_header,
    )
    return OrderListResponse(
        orders=[OrderResponse.from_order(o) for o in orders],
        total=len(orders),
        limit=len(orders),
        offset=0,
    )


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
    auth_header = request.headers.get("Authorization")
    await _ensure_wallet_access(auth_header)
    user_id = resolve_request_user_id(request)
    orders = await mgr.list_orders(
        user_id=user_id,
        status=status,
        symbol=symbol,
        limit=limit,
        offset=offset,
        auth_header=auth_header,
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


class BracketOrderRequest(BaseModel):
    symbol: str
    side: OrderSide
    quantity: float = Field(..., gt=0)
    entry_type: str = Field("market", pattern="^(market|limit)$")
    entry_price: Optional[float] = Field(None, gt=0)
    stop_loss_price: float = Field(..., gt=0)
    take_profit_price: float = Field(..., gt=0)
    client_order_id: Optional[str] = None
    portfolio_id: Optional[str] = None


@router.post("/bracket")
async def place_bracket_order(
    request: Request,
    payload: BracketOrderRequest,
) -> Dict:
    """Place an entry + stop-loss + take-profit bracket in one call.

    1. Place the entry order (market or limit).
    2. If the entry is filled (market path), immediately place a Binance OCO
       on the opposite side covering both SL and TP.
    3. Returns the entry order id and the OCO ids when applicable.

    For LIMIT entries, the OCO is NOT placed immediately — the user (or a
    background watcher) places it once the entry actually fills. This is a
    deliberate V1 simplification.
    """
    mgr = _get_order_manager()
    auth_header = request.headers.get("Authorization")
    await _ensure_wallet_access(auth_header)
    user_id = resolve_request_user_id(request)

    # 1. Entry
    entry_create = OrderCreate(
        symbol=payload.symbol,
        side=payload.side,
        order_type="market" if payload.entry_type == "market" else "limit",
        quantity=Decimal(str(payload.quantity)),
        price=Decimal(str(payload.entry_price)) if payload.entry_price else None,
        client_order_id=payload.client_order_id,
        portfolio_id=payload.portfolio_id,
    )
    try:
        entry_order = await mgr.create_order(
            entry_create, user_id=user_id, auth_header=auth_header
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if entry_order.status == OrderStatus.FAILED:
        raise HTTPException(
            status_code=422,
            detail=entry_order.error_message or "Bracket entry failed",
        )

    bracket_response: Dict = {
        "entry": OrderResponse.from_order(entry_order).dict(),
        "oco": None,
        "status": "entry_placed",
    }

    # 2. OCO only if entry was a market and is filled
    if payload.entry_type != "market" or entry_order.status != OrderStatus.FILLED:
        bracket_response["status"] = "entry_pending_oco"
        return bracket_response

    opposite_side = OrderSide.SELL if payload.side == OrderSide.BUY else OrderSide.BUY
    oco_create = OrderCreate(
        symbol=payload.symbol,
        side=opposite_side,
        order_type="oco",
        quantity=entry_order.filled_quantity or Decimal(str(payload.quantity)),
        price=Decimal(str(payload.take_profit_price)),
        stop_price=Decimal(str(payload.stop_loss_price)),
        # Use stop_loss_price as the limit too (post-trigger price)
        take_profit_price=Decimal(str(payload.stop_loss_price)),
        portfolio_id=payload.portfolio_id,
    )
    try:
        oco_order = await mgr.create_order(
            oco_create, user_id=user_id, auth_header=auth_header
        )
        bracket_response["oco"] = OrderResponse.from_order(oco_order).dict()
        bracket_response["status"] = (
            "complete" if oco_order.status != OrderStatus.FAILED else "oco_failed"
        )
    except Exception as exc:
        bracket_response["oco_error"] = str(exc)
        bracket_response["status"] = "oco_failed"

    return bracket_response


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
    auth_header = request.headers.get("Authorization")
    await _ensure_wallet_access(auth_header)
    order = await mgr.get_order(
        order_id,
        resolve_request_user_id(request),
        auth_header=auth_header,
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderResponse.from_order(order)


class ReplaceOrderRequest(BaseModel):
    """Cancel + replace a limit order with new price/quantity."""

    price: Optional[float] = Field(None, gt=0)
    quantity: Optional[float] = Field(None, gt=0)


@router.patch("/{order_id}", response_model=OrderResponse)
async def replace_order(
    order_id: str,
    request: Request,
    payload: ReplaceOrderRequest,
) -> OrderResponse:
    """Cancel and replace an open order with new parameters.

    Binance does not support a native replace, so this is implemented as
    cancel-then-place. If the cancel fails (e.g. the order already filled),
    we return the current state untouched.
    """
    mgr = _get_order_manager()
    auth_header = request.headers.get("Authorization")
    await _ensure_wallet_access(auth_header)
    user_id = resolve_request_user_id(request)

    existing = await mgr.get_order(order_id, user_id, auth_header=auth_header)
    if existing is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if existing.status not in (OrderStatus.OPEN, OrderStatus.PENDING):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot replace an order in status '{existing.status.value}'",
        )

    new_qty = (
        Decimal(str(payload.quantity))
        if payload.quantity is not None
        else existing.quantity
    )
    new_price = (
        Decimal(str(payload.price))
        if payload.price is not None
        else existing.price
    )

    # 1. Cancel the existing order
    try:
        await mgr.cancel_order(order_id, user_id, auth_header=auth_header)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=f"Cancel failed: {exc}")

    # 2. Place a new order with the same logical parameters
    new_create = OrderCreate(
        symbol=existing.symbol,
        side=existing.side,
        order_type=existing.order_type,
        quantity=new_qty,
        price=new_price,
        stop_price=existing.stop_price,
        take_profit_price=existing.take_profit_price,
        trailing_pct=existing.trailing_pct,
        portfolio_id=existing.portfolio_id,
        strategy=existing.strategy,
    )
    try:
        new_order = await mgr.create_order(
            new_create, user_id=user_id, auth_header=auth_header
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return OrderResponse.from_order(new_order)


@router.delete("/{order_id}", response_model=OrderResponse)
async def cancel_order(order_id: str, request: Request) -> OrderResponse:
    """Cancel an open or pending order."""
    mgr = _get_order_manager()
    auth_header = request.headers.get("Authorization")
    await _ensure_wallet_access(auth_header)
    try:
        order = await mgr.cancel_order(
            order_id,
            resolve_request_user_id(request),
            auth_header=auth_header,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return OrderResponse.from_order(order)
