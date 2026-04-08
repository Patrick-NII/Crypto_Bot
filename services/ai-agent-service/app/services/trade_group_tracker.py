"""Trade group tracker — link every BUY to its eventual SELL.

A ``TradeGroupRow`` represents a position lifecycle:
    open → (entry filled) → ... holding ... → (exit filled) → closed

Matching is **FIFO per symbol per user**:
    - A BUY (on a long side) with no existing open group → opens a new group.
    - A SELL on the same symbol with an open group → closes the oldest one.
    - If the sell quantity > open group entry_quantity, we log a warning and
      only partially close (the surplus does not open a "short" group in spot
      trading).

The ``id`` is surfaced to the frontend as the user-visible transaction number
(shortened to 8 chars in the UI).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.repositories.auto_repository import auto_repository

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def open_trade_group(
    *,
    user_id: str,
    portfolio_id: Optional[str],
    symbol: str,
    side: str,
    entry_decision_id: str,
    entry_order_id: Optional[str],
    entry_quantity: float,
    entry_price: float,
    entry_fee: float = 0.0,
    entry_reason: Optional[str] = None,
) -> str:
    """Create a new trade group marking the start of a position. Returns the group id."""
    group_id = uuid.uuid4().hex
    now = _now()
    await auto_repository.insert_trade_group(
        {
            "id": group_id,
            "user_id": user_id,
            "portfolio_id": portfolio_id,
            "symbol": symbol.upper(),
            "side": side,
            "status": "open",
            "entry_order_id": entry_order_id,
            "entry_decision_id": entry_decision_id,
            "entry_time": now,
            "entry_quantity": Decimal(str(entry_quantity)),
            "entry_price": Decimal(str(entry_price)),
            "entry_fee": Decimal(str(entry_fee)),
            "entry_reason": entry_reason or "",
            "tags": [],
        }
    )
    logger.info(
        "TradeGroup opened %s: %s %s qty=%s price=%s user=%s",
        group_id[:8],
        side,
        symbol,
        entry_quantity,
        entry_price,
        user_id,
    )
    return group_id


async def close_trade_group(
    *,
    user_id: str,
    symbol: str,
    exit_decision_id: str,
    exit_order_id: Optional[str],
    exit_quantity: float,
    exit_price: float,
    exit_fee: float = 0.0,
    exit_reason: Optional[str] = None,
    side: str = "buy",
) -> Optional[str]:
    """Close the oldest open trade group on this symbol.

    Returns the trade group id if one was closed, None otherwise.
    Realized P&L is computed here: (exit_price - entry_price) * qty - fees.
    """
    group = await auto_repository.find_open_group(user_id, symbol.upper(), side)
    if group is None:
        logger.debug(
            "close_trade_group: no open group to close for user=%s symbol=%s",
            user_id,
            symbol,
        )
        return None

    entry_qty = Decimal(str(group.entry_quantity or 0))
    entry_price_d = Decimal(str(group.entry_price or 0))
    entry_fee_d = Decimal(str(group.entry_fee or 0))
    exit_qty_d = Decimal(str(exit_quantity))
    exit_price_d = Decimal(str(exit_price))
    exit_fee_d = Decimal(str(exit_fee))

    if exit_qty_d > entry_qty + Decimal("0.000000001"):
        logger.warning(
            "Trade group %s: sell qty %s exceeds open entry %s — partial close",
            group.id[:8],
            exit_qty_d,
            entry_qty,
        )
        matched_qty = entry_qty
    else:
        matched_qty = exit_qty_d

    realized_pnl = (exit_price_d - entry_price_d) * matched_qty - entry_fee_d - exit_fee_d
    cost_basis = entry_price_d * matched_qty
    realized_pnl_pct = (
        (realized_pnl / cost_basis) * Decimal("100") if cost_basis > 0 else Decimal("0")
    )

    now = _now()
    holding_seconds: Optional[int] = None
    if group.entry_time is not None:
        holding_seconds = int((now - group.entry_time).total_seconds())

    await auto_repository.update_trade_group(
        group.id,
        {
            "status": "closed",
            "exit_order_id": exit_order_id,
            "exit_decision_id": exit_decision_id,
            "exit_time": now,
            "holding_seconds": holding_seconds,
            "exit_quantity": matched_qty,
            "exit_price": exit_price_d,
            "exit_fee": exit_fee_d,
            "exit_reason": exit_reason or "",
            "realized_pnl": realized_pnl,
            "realized_pnl_pct": realized_pnl_pct,
        },
    )
    logger.info(
        "TradeGroup closed %s: %s %s qty=%s price=%s pnl=%s (%s%%)",
        group.id[:8],
        group.side,
        symbol,
        matched_qty,
        exit_price_d,
        realized_pnl,
        realized_pnl_pct.quantize(Decimal("0.01")) if realized_pnl_pct else 0,
    )
    return group.id
