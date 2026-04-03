"""Portfolio CRUD router."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.models.portfolio import Portfolio, Position
from typing import List
from app.schemas.portfolio import (
    AllocationEntry,
    PortfolioCreate,
    PortfolioResponse,
    PortfolioSummary,
    PortfolioUpdate,
    PortfolioWithPositions,
)
from app.services.portfolio_calculator import (
    calculate_allocation,
    calculate_portfolio_value,
    calculate_position_pnl,
    fetch_live_prices,
)

router = APIRouter(prefix="/api/v1/portfolios", tags=["portfolios"])


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
