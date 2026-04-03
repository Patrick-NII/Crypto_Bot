"""Position and Transaction router."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.models.portfolio import Portfolio, Position, Transaction
from app.schemas.portfolio import (
    PositionCreate,
    PositionResponse,
    PositionUpdate,
    TransactionCreate,
    TransactionResponse,
)
from app.services.portfolio_calculator import calculate_position_pnl

router = APIRouter(prefix="/api/v1/positions", tags=["positions"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _verify_portfolio_ownership(
    portfolio_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Portfolio:
    """Ensure the portfolio exists and belongs to *user_id*."""
    result = await db.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id)
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    if portfolio.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised")
    return portfolio


async def _get_position_or_404(
    position_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Position:
    """Return a position after validating the owning portfolio belongs to *user_id*."""
    result = await db.execute(
        select(Position)
        .options(selectinload(Position.portfolio))
        .where(Position.id == position_id)
    )
    position = result.scalar_one_or_none()
    if position is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    if position.portfolio.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised")
    return position


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[PositionResponse])
async def list_positions(
    portfolio_id: uuid.UUID | None = Query(None),
    symbol: str | None = Query(None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List positions across all of the user's portfolios.

    Optionally filter by *portfolio_id* and/or *symbol*.
    """
    stmt = (
        select(Position)
        .join(Portfolio)
        .where(Portfolio.user_id == user_id)
        .order_by(Position.opened_at.desc())
    )
    if portfolio_id is not None:
        stmt = stmt.where(Position.portfolio_id == portfolio_id)
    if symbol is not None:
        stmt = stmt.where(Position.symbol == symbol.upper())

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=PositionResponse, status_code=status.HTTP_201_CREATED)
async def open_position(
    body: PositionCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Open a new position inside a portfolio."""
    await _verify_portfolio_ownership(body.portfolio_id, user_id, db)

    # Calculate initial PnL (likely zero when just opened)
    unrealized_pnl, _ = calculate_position_pnl(
        body.quantity, body.average_entry_price, body.current_price
    )

    position = Position(
        portfolio_id=body.portfolio_id,
        symbol=body.symbol.upper(),
        asset_type=body.asset_type,
        exchange=body.exchange,
        quantity=body.quantity,
        average_entry_price=body.average_entry_price,
        current_price=body.current_price,
        unrealized_pnl=unrealized_pnl,
        stop_loss_price=body.stop_loss_price,
        take_profit_price=body.take_profit_price,
    )
    db.add(position)
    await db.flush()
    await db.refresh(position)
    return position


@router.get("/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Return a single position."""
    return await _get_position_or_404(position_id, user_id, db)


@router.put("/{position_id}", response_model=PositionResponse)
async def update_position(
    position_id: uuid.UUID,
    body: PositionUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update mutable fields of a position (stop-loss, take-profit, etc.)."""
    position = await _get_position_or_404(position_id, user_id, db)

    if body.quantity is not None:
        position.quantity = body.quantity
    if body.average_entry_price is not None:
        position.average_entry_price = body.average_entry_price
    if body.current_price is not None:
        position.current_price = body.current_price
    if body.stop_loss_price is not None:
        position.stop_loss_price = body.stop_loss_price
    if body.take_profit_price is not None:
        position.take_profit_price = body.take_profit_price

    # Recompute PnL after any changes
    unrealized_pnl, _ = calculate_position_pnl(
        Decimal(str(position.quantity)),
        Decimal(str(position.average_entry_price)),
        Decimal(str(position.current_price)),
    )
    position.unrealized_pnl = unrealized_pnl

    await db.flush()
    await db.refresh(position)
    return position


@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def close_position(
    position_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Close (delete) a position."""
    position = await _get_position_or_404(position_id, user_id, db)
    await db.delete(position)
    await db.flush()


@router.get("/{position_id}/transactions", response_model=list[TransactionResponse])
async def list_position_transactions(
    position_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all transactions linked to a specific position."""
    # Verify ownership
    await _get_position_or_404(position_id, user_id, db)

    stmt = (
        select(Transaction)
        .where(Transaction.position_id == position_id)
        .order_by(Transaction.executed_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Transaction creation (convenience endpoint on positions router)
# ---------------------------------------------------------------------------

@router.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["transactions"],
)
async def create_transaction(
    body: TransactionCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Record a new transaction."""
    await _verify_portfolio_ownership(body.portfolio_id, user_id, db)

    # Validate position if provided
    if body.position_id is not None:
        await _get_position_or_404(body.position_id, user_id, db)

    transaction = Transaction(
        portfolio_id=body.portfolio_id,
        position_id=body.position_id,
        symbol=body.symbol.upper(),
        side=body.side,
        quantity=body.quantity,
        price=body.price,
        fee=body.fee,
        exchange=body.exchange,
        order_id=body.order_id,
        strategy=body.strategy,
        notes=body.notes,
        executed_at=body.executed_at,
    )
    db.add(transaction)
    await db.flush()
    await db.refresh(transaction)
    return transaction
