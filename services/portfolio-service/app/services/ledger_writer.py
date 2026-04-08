"""Ledger writer — turns trading-engine fills into Position + Transaction rows.

This is the **only** place where the portfolio ledger is mutated as a result
of a fill event. It is used by:
  - the Redis ``FillConsumer`` worker (production path)
  - any future replay / backfill scripts

Cost basis policy: **weighted average** (V1).
  BUY  → avg_cost = (old_qty * old_avg + fill_qty * fill_price) / total_qty
  SELL → realized_pnl += (fill_price - avg_cost) * fill_qty - fee
         qty -= fill_qty; if qty <= 0 → close position (avg_cost reset to 0)

Idempotency is guaranteed by ``Transaction.order_id`` (now UNIQUE in DB).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import Portfolio, Position, Transaction

logger = logging.getLogger(__name__)


@dataclass
class FillPayload:
    """Subset of an order event payload that the ledger needs."""

    user_id: str
    order_id: str
    symbol: str
    side: str  # buy | sell
    filled_quantity: Decimal
    avg_price: Decimal
    fee: Decimal
    exchange: str
    portfolio_id: Optional[str] = None  # may be NULL → resolve to default

    @classmethod
    def from_redis_payload(cls, payload: dict) -> Optional["FillPayload"]:
        try:
            qty_raw = payload.get("filled_quantity") or payload.get("quantity") or "0"
            price_raw = payload.get("avg_price") or payload.get("filled_price") or "0"
            qty = Decimal(str(qty_raw))
            price = Decimal(str(price_raw))
            if qty <= 0 or price <= 0:
                return None
            return cls(
                user_id=str(payload.get("user_id") or "default"),
                order_id=str(payload.get("order_id") or ""),
                symbol=str(payload.get("symbol") or ""),
                side=str(payload.get("side") or "").lower(),
                filled_quantity=qty,
                avg_price=price,
                fee=Decimal(str(payload.get("fee") or "0")),
                exchange=str(payload.get("exchange") or "binance"),
                portfolio_id=payload.get("portfolio_id"),
            )
        except Exception as exc:
            logger.debug("Could not parse fill payload: %s", exc)
            return None


def _normalise_symbol_base(symbol: str) -> str:
    """Return the base asset alone (e.g. 'BTC/USDT' → 'BTC')."""
    return symbol.split("/")[0].upper() if symbol else ""


async def _resolve_portfolio(
    db: AsyncSession,
    user_id: str,
    portfolio_id_hint: Optional[str],
) -> Optional[Portfolio]:
    """Pick the portfolio that owns this fill.

    1. If the trading-engine forwarded a `portfolio_id`, use it.
    2. Otherwise pick the user's default portfolio (`is_default=True`).
    3. Otherwise the first portfolio for this user.
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, AttributeError):
        return None

    if portfolio_id_hint:
        try:
            pid = uuid.UUID(portfolio_id_hint)
            row = await db.get(Portfolio, pid)
            if row is not None and row.user_id == user_uuid:
                return row
        except (ValueError, TypeError):
            pass

    stmt = (
        select(Portfolio)
        .where(Portfolio.user_id == user_uuid)
        .order_by(Portfolio.is_default.desc(), Portfolio.created_at)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def _load_or_create_position(
    db: AsyncSession,
    portfolio_id: uuid.UUID,
    symbol_base: str,
    exchange: str,
) -> Position:
    stmt = select(Position).where(
        Position.portfolio_id == portfolio_id,
        Position.symbol == symbol_base,
    )
    result = await db.execute(stmt)
    position = result.scalars().first()
    if position is None:
        position = Position(
            portfolio_id=portfolio_id,
            symbol=symbol_base,
            asset_type="crypto",
            exchange=exchange,
            quantity=Decimal("0"),
            average_entry_price=Decimal("0"),
            current_price=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
        )
        db.add(position)
        await db.flush()
    return position


def _apply_buy_weighted_avg(position: Position, fill: FillPayload) -> None:
    old_qty = position.quantity or Decimal("0")
    old_avg = position.average_entry_price or Decimal("0")
    new_qty = old_qty + fill.filled_quantity
    if new_qty <= 0:
        return
    old_cost = old_qty * old_avg
    new_cost = fill.filled_quantity * fill.avg_price
    position.average_entry_price = (old_cost + new_cost) / new_qty
    position.quantity = new_qty
    position.current_price = fill.avg_price


def _apply_sell_realize_pnl(position: Position, fill: FillPayload) -> Decimal:
    avg_cost = position.average_entry_price or Decimal("0")
    realized = (fill.avg_price - avg_cost) * fill.filled_quantity - fill.fee
    position.realized_pnl = (position.realized_pnl or Decimal("0")) + realized
    new_qty = (position.quantity or Decimal("0")) - fill.filled_quantity
    if new_qty <= Decimal("0.000000001"):
        position.quantity = Decimal("0")
        position.average_entry_price = Decimal("0")
    else:
        position.quantity = new_qty
    position.current_price = fill.avg_price
    return realized


async def apply_fill(
    db: AsyncSession,
    fill: FillPayload,
) -> Optional[Transaction]:
    """Apply a fill to the portfolio ledger.

    Idempotent: if a Transaction with this ``order_id`` already exists,
    returns ``None`` and does nothing.

    Returns the freshly inserted Transaction on success.
    """
    if not fill.order_id:
        logger.debug("Fill without order_id skipped: %s", fill.symbol)
        return None
    if fill.side not in ("buy", "sell"):
        logger.debug("Fill with unknown side skipped: %s", fill.side)
        return None

    # Idempotency check (the table also has a UNIQUE constraint as backstop)
    existing_stmt = select(Transaction).where(Transaction.order_id == fill.order_id)
    existing = (await db.execute(existing_stmt)).scalars().first()
    if existing is not None:
        logger.debug("Fill %s already applied, skipping", fill.order_id)
        return None

    portfolio = await _resolve_portfolio(db, fill.user_id, fill.portfolio_id)
    if portfolio is None:
        logger.warning(
            "Fill %s: no portfolio found for user %s — skipping",
            fill.order_id,
            fill.user_id,
        )
        return None

    symbol_base = _normalise_symbol_base(fill.symbol)
    if not symbol_base:
        return None

    position = await _load_or_create_position(
        db, portfolio.id, symbol_base, fill.exchange
    )

    if fill.side == "buy":
        _apply_buy_weighted_avg(position, fill)
    else:
        _apply_sell_realize_pnl(position, fill)

    await db.flush()  # so position.id is populated for the FK below

    tx = Transaction(
        portfolio_id=portfolio.id,
        position_id=position.id,
        symbol=symbol_base,
        side=fill.side,
        quantity=fill.filled_quantity,
        price=fill.avg_price,
        fee=fill.fee,
        exchange=fill.exchange,
        order_id=fill.order_id,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    logger.info(
        "Fill applied: portfolio=%s symbol=%s %s %s @ %s (order_id=%s)",
        portfolio.id,
        symbol_base,
        fill.side,
        fill.filled_quantity,
        fill.avg_price,
        fill.order_id,
    )
    return tx
