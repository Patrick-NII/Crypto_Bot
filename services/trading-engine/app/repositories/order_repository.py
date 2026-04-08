"""Order repository: persist orders, fills, and idempotency keys.

Translates between the ORM rows in ``app.models.db.order`` and the domain
``Order`` Pydantic model used by the rest of the trading-engine.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import and_, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_maker
from app.models.db.order import (
    BracketGroupRow,
    IdempotencyKeyRow,
    OrderFillRow,
    OrderLegRow,
    OrderRow,
    PaperAccountStateRow,
)
from app.models.order import Order, OrderSide, OrderStatus, OrderType

logger = logging.getLogger(__name__)


def _row_to_order(row: OrderRow) -> Order:
    """Convert an ORM row to the domain Order model."""
    return Order(
        id=row.id,
        symbol=row.symbol,
        side=OrderSide(row.side),
        order_type=OrderType(row.order_type),
        status=OrderStatus(row.status),
        quantity=row.quantity,
        filled_quantity=row.filled_quantity,
        price=row.price,
        filled_price=row.filled_price,
        stop_price=row.stop_price,
        take_profit_price=row.take_profit_price,
        trailing_pct=row.trailing_pct,
        fee=row.fee,
        exchange=row.exchange,
        exchange_order_id=row.exchange_order_id,
        portfolio_id=row.portfolio_id,
        strategy=row.strategy,
        created_at=row.created_at,
        updated_at=row.updated_at,
        error_message=row.error_message,
    )


def _order_to_row_kwargs(
    user_id: str,
    order: Order,
    *,
    client_order_id: Optional[str],
    quote_quantity: Optional[Decimal],
) -> dict:
    return dict(
        id=order.id,
        user_id=user_id,
        portfolio_id=order.portfolio_id,
        client_order_id=client_order_id,
        symbol=order.symbol,
        side=order.side.value,
        order_type=order.order_type.value,
        status=order.status.value,
        quantity=order.quantity,
        quote_quantity=quote_quantity,
        filled_quantity=order.filled_quantity,
        price=order.price,
        filled_price=order.filled_price,
        stop_price=order.stop_price,
        take_profit_price=order.take_profit_price,
        trailing_pct=order.trailing_pct,
        fee=order.fee,
        exchange=order.exchange,
        exchange_order_id=order.exchange_order_id,
        strategy=order.strategy,
        error_message=order.error_message,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


class OrderRepository:
    """All database access for the trading-engine order persistence."""

    async def _session(self) -> AsyncSession:
        return get_session_maker()()

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    async def save_order(
        self,
        user_id: str,
        order: Order,
        *,
        client_order_id: Optional[str] = None,
        quote_quantity: Optional[Decimal] = None,
    ) -> None:
        """Insert or update an order row."""
        kwargs = _order_to_row_kwargs(
            user_id, order, client_order_id=client_order_id, quote_quantity=quote_quantity
        )
        try:
            session = await self._session()
            try:
                stmt = pg_insert(OrderRow).values(**kwargs)
                update_cols = {
                    k: stmt.excluded[k]
                    for k in kwargs.keys()
                    if k not in ("id", "user_id", "created_at")
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=[OrderRow.id],
                    set_=update_cols,
                )
                await session.execute(stmt)
                await session.commit()
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("save_order failed for %s: %s", order.id, exc)

    async def update_status(
        self,
        order_id: str,
        status: OrderStatus,
        *,
        filled_quantity: Optional[Decimal] = None,
        filled_price: Optional[Decimal] = None,
        fee: Optional[Decimal] = None,
        error_message: Optional[str] = None,
    ) -> None:
        try:
            session = await self._session()
            try:
                row = await session.get(OrderRow, order_id)
                if row is None:
                    return
                row.status = status.value
                if filled_quantity is not None:
                    row.filled_quantity = filled_quantity
                if filled_price is not None:
                    row.filled_price = filled_price
                if fee is not None:
                    row.fee = fee
                if error_message is not None:
                    row.error_message = error_message
                row.updated_at = datetime.now(timezone.utc)
                await session.commit()
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("update_status failed for %s: %s", order_id, exc)

    async def get_order(self, order_id: str) -> Optional[Order]:
        try:
            session = await self._session()
            try:
                row = await session.get(OrderRow, order_id)
                return _row_to_order(row) if row else None
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("get_order failed for %s: %s", order_id, exc)
            return None

    async def find_by_exchange_order_id(
        self,
        user_id: str,
        exchange_order_id: str,
    ) -> Optional[Order]:
        try:
            session = await self._session()
            try:
                stmt = select(OrderRow).where(
                    and_(
                        OrderRow.user_id == user_id,
                        OrderRow.exchange_order_id == exchange_order_id,
                    )
                )
                result = await session.execute(stmt)
                row = result.scalars().first()
                return _row_to_order(row) if row else None
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("find_by_exchange_order_id failed: %s", exc)
            return None

    async def list_open_orders(self, user_id: str) -> List[Order]:
        try:
            session = await self._session()
            try:
                stmt = select(OrderRow).where(
                    and_(
                        OrderRow.user_id == user_id,
                        OrderRow.status.in_(["pending", "open", "partially_filled"]),
                    )
                )
                result = await session.execute(stmt)
                return [_row_to_order(r) for r in result.scalars()]
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("list_open_orders failed: %s", exc)
            return []

    async def list_recent_orders(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Order]:
        try:
            session = await self._session()
            try:
                stmt = (
                    select(OrderRow)
                    .where(OrderRow.user_id == user_id)
                    .order_by(OrderRow.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
                result = await session.execute(stmt)
                return [_row_to_order(r) for r in result.scalars()]
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("list_recent_orders failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Idempotency keys
    # ------------------------------------------------------------------

    async def remember_client_order_id(
        self,
        user_id: str,
        client_order_id: str,
        internal_order_id: str,
        ttl_seconds: int = 86400,
    ) -> None:
        try:
            session = await self._session()
            try:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
                stmt = pg_insert(IdempotencyKeyRow).values(
                    user_id=user_id,
                    client_order_id=client_order_id,
                    internal_order_id=internal_order_id,
                    expires_at=expires_at,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[IdempotencyKeyRow.user_id, IdempotencyKeyRow.client_order_id],
                    set_=dict(internal_order_id=internal_order_id, expires_at=expires_at),
                )
                await session.execute(stmt)
                await session.commit()
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("remember_client_order_id failed: %s", exc)

    async def lookup_client_order_id(
        self,
        user_id: str,
        client_order_id: str,
    ) -> Optional[str]:
        try:
            session = await self._session()
            try:
                row = await session.get(
                    IdempotencyKeyRow, {"user_id": user_id, "client_order_id": client_order_id}
                )
                if row is None:
                    return None
                if row.expires_at < datetime.now(timezone.utc):
                    return None
                return row.internal_order_id
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("lookup_client_order_id failed: %s", exc)
            return None

    async def cleanup_expired_idempotency(self) -> int:
        try:
            session = await self._session()
            try:
                stmt = delete(IdempotencyKeyRow).where(
                    IdempotencyKeyRow.expires_at < datetime.now(timezone.utc)
                )
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount or 0
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("cleanup_expired_idempotency failed: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # Order legs (OCO)
    # ------------------------------------------------------------------

    async def add_order_leg(
        self,
        parent_order_id: str,
        leg_type: str,
        exchange_order_id: Optional[str],
        status: str = "open",
    ) -> None:
        try:
            session = await self._session()
            try:
                row = OrderLegRow(
                    parent_order_id=parent_order_id,
                    leg_type=leg_type,
                    exchange_order_id=exchange_order_id,
                    status=status,
                )
                session.add(row)
                await session.commit()
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("add_order_leg failed: %s", exc)

    # ------------------------------------------------------------------
    # Bracket groups
    # ------------------------------------------------------------------

    async def save_bracket_group(self, group: BracketGroupRow) -> None:
        try:
            session = await self._session()
            try:
                session.add(group)
                await session.commit()
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("save_bracket_group failed: %s", exc)

    async def update_bracket_status(self, bracket_id: str, status: str) -> None:
        try:
            session = await self._session()
            try:
                row = await session.get(BracketGroupRow, bracket_id)
                if row is None:
                    return
                row.status = status
                row.updated_at = datetime.now(timezone.utc)
                await session.commit()
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("update_bracket_status failed: %s", exc)

    # ------------------------------------------------------------------
    # Paper account state
    # ------------------------------------------------------------------

    async def save_paper_state(self, user_id: str, state_json: dict) -> None:
        try:
            session = await self._session()
            try:
                stmt = pg_insert(PaperAccountStateRow).values(
                    user_id=user_id,
                    state_json=state_json,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[PaperAccountStateRow.user_id],
                    set_=dict(
                        state_json=state_json,
                        updated_at=datetime.now(timezone.utc),
                    ),
                )
                await session.execute(stmt)
                await session.commit()
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("save_paper_state failed: %s", exc)

    async def load_paper_state(self, user_id: str) -> Optional[dict]:
        try:
            session = await self._session()
            try:
                row = await session.get(PaperAccountStateRow, user_id)
                return row.state_json if row else None
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("load_paper_state failed: %s", exc)
            return None

    async def load_all_paper_states(self) -> dict[str, dict]:
        try:
            session = await self._session()
            try:
                stmt = select(PaperAccountStateRow)
                result = await session.execute(stmt)
                return {row.user_id: row.state_json for row in result.scalars()}
            finally:
                await session.close()
        except SQLAlchemyError as exc:
            logger.warning("load_all_paper_states failed: %s", exc)
            return {}


# Module-level singleton
order_repository = OrderRepository()
