"""Portfolio CRUD router."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.database import get_db
from app.models.portfolio import Portfolio, Position, Transaction
from typing import List
from app.schemas.portfolio import (
    AllocationEntry,
    ExecutionFeedItem,
    PortfolioCreate,
    PortfolioSnapshot,
    PortfolioResponse,
    SnapshotBalance,
    SnapshotHolding,
    SnapshotRiskMetrics,
    SnapshotSummary,
    PortfolioSummary,
    PortfolioUpdate,
    PortfolioWithPositions,
)
from app.services.portfolio_calculator import (
    calculate_allocation,
    calculate_portfolio_value,
    calculate_position_pnl,
    fetch_live_market_data,
    fetch_live_prices,
    fetch_trading_balances,
)

router = APIRouter(prefix="/api/v1/portfolios", tags=["portfolios"])
STABLES = {"USDT", "USDC", "BUSD", "FDUSD", "DAI", "TUSD", "USD", "EUR"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_portfolio_or_404(
    portfolio_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    *,
    load_positions: bool = False,
) -> Portfolio:
    """Return the portfolio or raise 404 / 403."""
    stmt = select(Portfolio).where(Portfolio.id == portfolio_id)
    if load_positions:
        stmt = stmt.options(selectinload(Portfolio.positions))
    result = await db.execute(stmt)
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    if portfolio.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised")
    return portfolio


async def _fetch_risk_snapshot(auth_header: str | None) -> SnapshotRiskMetrics | None:
    """Fetch canonical risk metrics from the risk-service."""
    headers = {"Authorization": auth_header} if auth_header else {}
    url = f"{settings.RISK_SERVICE_URL}/api/v1/risk/metrics"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return SnapshotRiskMetrics(**resp.json())
    except Exception:
        return None


async def _ensure_wallet_access(auth_header: str | None) -> None:
    """Verify the user is authenticated before exposing wallet endpoints."""
    if not auth_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization required")

    url = f"{settings.AUTH_SERVICE_URL}/api/v1/auth/me"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"Authorization": auth_header})
            if resp.status_code == 401:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            resp.raise_for_status()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to validate access: {exc}",
        )


async def _fetch_trading_orders(
    auth_header: str | None,
    limit: int = 50,
) -> List[dict]:
    """Fetch recent orders from the trading-engine."""
    url = f"{settings.TRADING_ENGINE_URL}/api/v1/orders"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": auth_header} if auth_header else {}
            resp = await client.get(
                url,
                params={"limit": limit, "offset": 0},
                headers=headers,
            )
            resp.raise_for_status()
            payload = resp.json()
            return payload.get("orders", [])
    except Exception:
        return []


def _build_execution_feed(
    orders: List[dict],
    transactions: List[Transaction],
) -> List[ExecutionFeedItem]:
    """Merge order history and portfolio transactions into a single execution feed."""
    feed: List[ExecutionFeedItem] = []
    matched_transaction_ids: set[uuid.UUID] = set()

    tx_by_order_id: dict[str, Transaction] = {}
    for transaction in transactions:
        if transaction.order_id:
            tx_by_order_id[transaction.order_id] = transaction

    for order in orders:
        order_id = order.get("id")
        symbol = str(order.get("symbol", "")).upper()
        side = str(order.get("side", "buy"))
        quantity = Decimal(str(order.get("quantity", 0)))
        filled_quantity = Decimal(str(order.get("filled_quantity", order.get("quantity", 0))))
        execution_price = order.get("filled_price")
        requested_price = order.get("price")
        tx = tx_by_order_id.get(order_id) if order_id else None
        if tx is not None:
            matched_transaction_ids.add(tx.id)

        effective_price = (
            Decimal(str(execution_price))
            if execution_price is not None
            else Decimal(str(requested_price))
            if requested_price is not None
            else Decimal(str(tx.price))
            if tx is not None
            else Decimal("0")
        )
        notional = quantity * effective_price
        fee = (
            Decimal(str(tx.fee))
            if tx is not None
            else Decimal(str(order.get("fee", 0)))
        )
        timestamp = tx.executed_at if tx is not None else datetime.fromisoformat(order["created_at"])
        updated_at = datetime.fromisoformat(order["updated_at"]) if order.get("updated_at") else None

        feed.append(
            ExecutionFeedItem(
                id=f"order-{order_id}",
                source="execution" if tx is not None else "order",
                order_id=order_id,
                transaction_id=tx.id if tx is not None else None,
                portfolio_id=tx.portfolio_id if tx is not None else None,
                symbol=symbol,
                side=side,
                status=str(order.get("status", "unknown")),
                quantity=quantity,
                filled_quantity=filled_quantity,
                requested_price=Decimal(str(requested_price)) if requested_price is not None else None,
                execution_price=Decimal(str(execution_price)) if execution_price is not None else (
                    Decimal(str(tx.price)) if tx is not None else None
                ),
                notional=notional,
                fee=fee,
                exchange=tx.exchange if tx is not None else order.get("exchange"),
                strategy=tx.strategy if tx is not None else order.get("strategy"),
                notes=tx.notes if tx is not None else None,
                timestamp=timestamp,
                updated_at=updated_at,
            )
        )

    for transaction in transactions:
        if transaction.id in matched_transaction_ids:
            continue
        quantity = Decimal(str(transaction.quantity))
        execution_price = Decimal(str(transaction.price))
        feed.append(
            ExecutionFeedItem(
                id=f"tx-{transaction.id}",
                source="transaction",
                order_id=transaction.order_id,
                transaction_id=transaction.id,
                portfolio_id=transaction.portfolio_id,
                symbol=transaction.symbol.upper(),
                side=transaction.side,
                status="executed",
                quantity=quantity,
                filled_quantity=quantity,
                requested_price=execution_price,
                execution_price=execution_price,
                notional=quantity * execution_price,
                fee=Decimal(str(transaction.fee)),
                exchange=transaction.exchange,
                strategy=transaction.strategy,
                notes=transaction.notes,
                timestamp=transaction.executed_at,
                updated_at=transaction.executed_at,
            )
        )

    feed.sort(key=lambda item: item.timestamp, reverse=True)
    return feed[:50]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[PortfolioResponse])
async def list_portfolios(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Return all portfolios belonging to the authenticated user."""
    stmt = (
        select(Portfolio)
        .where(Portfolio.user_id == user_id)
        .order_by(Portfolio.created_at)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    body: PortfolioCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new portfolio for the authenticated user."""
    # If this portfolio is marked as default, clear any existing default.
    if body.is_default:
        existing = await db.execute(
            select(Portfolio).where(
                Portfolio.user_id == user_id, Portfolio.is_default.is_(True)
            )
        )
        for p in existing.scalars():
            p.is_default = False

    portfolio = Portfolio(
        user_id=user_id,
        name=body.name,
        description=body.description,
        is_default=body.is_default,
    )
    db.add(portfolio)
    await db.flush()
    await db.refresh(portfolio)
    return portfolio


@router.get("/snapshot", response_model=PortfolioSnapshot)
async def get_portfolio_snapshot(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Return a live cross-page snapshot for dashboard, trading and portfolio views."""
    auth_header = request.headers.get("Authorization")
    await _ensure_wallet_access(auth_header)
    portfolio_result = await db.execute(
        select(Portfolio)
        .where(Portfolio.user_id == user_id)
        .order_by(Portfolio.is_default.desc(), Portfolio.created_at)
    )
    portfolios = portfolio_result.scalars().all()
    active_portfolio = portfolios[0] if portfolios else None

    positions_result = await db.execute(
        select(Position)
        .join(Portfolio)
        .where(Portfolio.user_id == user_id)
        .order_by(Position.opened_at.desc())
    )
    positions = positions_result.scalars().all()

    transaction_result = await db.execute(
        select(Transaction)
        .join(Portfolio)
        .where(Portfolio.user_id == user_id)
        .order_by(Transaction.executed_at.desc())
        .limit(20)
    )
    transactions = transaction_result.scalars().all()
    orders = await _fetch_trading_orders(auth_header, limit=50)
    execution_feed = _build_execution_feed(orders, transactions)

    balances_raw = await fetch_trading_balances(auth_header)
    market_symbols = sorted(
        {
            *(pos.symbol.upper() for pos in positions),
            *(
                str(balance["currency"]).upper()
                for balance in balances_raw
                if str(balance["currency"]).upper() not in STABLES
            ),
        }
    )
    market = await fetch_live_market_data(market_symbols)
    prices = {
        symbol: Decimal(str(payload.get("price", payload.get("current_price", 0))))
        for symbol, payload in market.items()
        if payload.get("price", payload.get("current_price")) is not None
    }

    open_pnl = Decimal("0")
    open_cost_basis = Decimal("0")
    for pos in positions:
        live_price = prices.get(pos.symbol.upper(), Decimal(str(pos.current_price)))
        pos.current_price = live_price
        pnl, _ = calculate_position_pnl(
            Decimal(str(pos.quantity)),
            Decimal(str(pos.average_entry_price)),
            live_price,
        )
        pos.unrealized_pnl = pnl
        open_pnl += pnl
        open_cost_basis += Decimal(str(pos.quantity)) * Decimal(str(pos.average_entry_price))
    await db.flush()

    balances = [
        SnapshotBalance(
            currency=str(item["currency"]),
            available=Decimal(str(item["available"])),
            reserved=Decimal(str(item["reserved"])),
            total=Decimal(str(item["total"])),
        )
        for item in balances_raw
    ]

    holdings: List[SnapshotHolding] = []
    equity = Decimal("0")
    cash = Decimal("0")
    day_change_value = Decimal("0")

    for balance in balances:
        symbol = balance.currency.upper()
        stable = symbol in STABLES
        payload = market.get(symbol, {})
        price = Decimal("1") if stable else prices.get(symbol, Decimal("0"))
        value = balance.total if stable else balance.total * price
        change_pct = Decimal(str(payload.get("change_pct_24h", 0))) if payload else Decimal("0")

        equity += value
        if stable:
            cash += value
        elif change_pct != 0 and value > 0:
            day_change_value += value - (value / (Decimal("1") + (change_pct / Decimal("100"))))

        holdings.append(
            SnapshotHolding(
                symbol=symbol,
                available=balance.available,
                reserved=balance.reserved,
                total=balance.total,
                price=price,
                value=value,
                change_pct_24h=change_pct,
                stable=stable,
            )
        )

    holdings.sort(key=lambda item: item.value, reverse=True)

    market_exposure = max(equity - cash, Decimal("0"))
    open_pnl_pct = (open_pnl / open_cost_basis * Decimal("100")) if open_cost_basis > 0 else Decimal("0")
    day_change_base = equity - day_change_value
    day_change_pct = (day_change_value / day_change_base * Decimal("100")) if day_change_base > 0 else Decimal("0")

    risk = await _fetch_risk_snapshot(auth_header)

    return PortfolioSnapshot(
        updated_at=datetime.now(timezone.utc),
        portfolio=active_portfolio,
        portfolios=portfolios,
        balances=balances,
        holdings=holdings,
        positions=positions,
        recent_transactions=transactions,
        summary=SnapshotSummary(
            equity=equity,
            cash=cash,
            market_exposure=market_exposure,
            open_pnl=open_pnl,
            open_pnl_pct=round(open_pnl_pct, 2),
            day_change_value=day_change_value,
            day_change_pct=round(day_change_pct, 2),
            holdings_count=len(holdings),
            positions_count=len(positions),
            open_orders_count=sum(
                1 for item in execution_feed if item.status in {"open", "pending"}
            ),
        ),
        execution_feed=execution_feed,
        risk=risk,
    )


@router.get("/{portfolio_id}", response_model=PortfolioWithPositions)
async def get_portfolio(
    portfolio_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Return a single portfolio with all its positions."""
    portfolio = await _get_portfolio_or_404(
        portfolio_id, user_id, db, load_positions=True
    )
    return portfolio


@router.put("/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio(
    portfolio_id: uuid.UUID,
    body: PortfolioUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update portfolio metadata."""
    portfolio = await _get_portfolio_or_404(portfolio_id, user_id, db)

    if body.name is not None:
        portfolio.name = body.name
    if body.description is not None:
        portfolio.description = body.description
    if body.is_default is not None:
        if body.is_default:
            existing = await db.execute(
                select(Portfolio).where(
                    Portfolio.user_id == user_id, Portfolio.is_default.is_(True)
                )
            )
            for p in existing.scalars():
                p.is_default = False
        portfolio.is_default = body.is_default

    await db.flush()
    await db.refresh(portfolio)
    return portfolio


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
    portfolio_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a portfolio and all its positions / transactions."""
    portfolio = await _get_portfolio_or_404(portfolio_id, user_id, db)
    await db.delete(portfolio)
    await db.flush()


@router.get("/{portfolio_id}/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(
    portfolio_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Compute a live summary (value, PnL, allocation) for a portfolio.

    Current prices are fetched from the market-data-service.  If that service
    is unavailable the last stored ``current_price`` per position is used.
    """
    portfolio = await _get_portfolio_or_404(
        portfolio_id, user_id, db, load_positions=True
    )
    positions: List[Position] = portfolio.positions

    # Gather live prices -------------------------------------------------------
    symbols = list({p.symbol for p in positions})
    prices = await fetch_live_prices(symbols)

    # Update stored current_price on each position while we have fresh data ----
    for pos in positions:
        if pos.symbol in prices:
            pos.current_price = prices[pos.symbol]
            pnl, _ = calculate_position_pnl(
                Decimal(str(pos.quantity)),
                Decimal(str(pos.average_entry_price)),
                prices[pos.symbol],
            )
            pos.unrealized_pnl = pnl
    await db.flush()

    # Aggregate ----------------------------------------------------------------
    total_value = calculate_portfolio_value(positions, prices)
    total_cost = sum(
        Decimal(str(p.quantity)) * Decimal(str(p.average_entry_price))
        for p in positions
    )
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else Decimal("0")

    raw_allocation = calculate_allocation(positions, prices)
    allocation = [AllocationEntry(**entry) for entry in raw_allocation]

    return PortfolioSummary(
        portfolio_id=portfolio.id,
        portfolio_name=portfolio.name,
        total_value=total_value,
        total_pnl=total_pnl,
        total_pnl_pct=round(total_pnl_pct, 2),
        positions_count=len(positions),
        allocation=allocation,
    )
