"""Auto-trading repository for ai-agent-service.

Same shape as ``trading-engine.app.repositories.auto_repository`` but uses
ai-agent-service's local async engine. Both services hit the same tables in
``gluetrade_trading``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_maker
from app.models.db.auto import (
    AutoDecisionRow,
    AutoSessionRow,
    SmsNotificationRow,
    TradeGroupRow,
)

logger = logging.getLogger(__name__)


class AutoRepository:
    """Shared CRUD against gluetrade_trading tables."""

    async def _session(self) -> AsyncSession:
        return get_session_maker()()

    # ------------------------------------------------------------------
    # auto_sessions
    # ------------------------------------------------------------------

    async def upsert_session(self, session_state: Dict[str, Any]) -> None:
        user_id = session_state.get("user_id")
        if not user_id:
            return
        try:
            db = await self._session()
            try:
                stmt = pg_insert(AutoSessionRow).values(**session_state)
                update_cols = {
                    k: stmt.excluded[k]
                    for k in session_state.keys()
                    if k != "user_id"
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=[AutoSessionRow.user_id],
                    set_=update_cols,
                )
                await db.execute(stmt)
                await db.commit()
            finally:
                await db.close()
        except SQLAlchemyError as exc:
            logger.warning("upsert_session failed for %s: %s", user_id, exc)

    async def get_session_row(self, user_id: str) -> Optional[AutoSessionRow]:
        try:
            db = await self._session()
            try:
                return await db.get(AutoSessionRow, user_id)
            finally:
                await db.close()
        except SQLAlchemyError as exc:
            logger.warning("get_session_row failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # auto_decisions
    # ------------------------------------------------------------------

    async def insert_decision(self, decision: Dict[str, Any]) -> None:
        try:
            db = await self._session()
            try:
                row = AutoDecisionRow(**decision)
                db.add(row)
                await db.commit()
            finally:
                await db.close()
        except SQLAlchemyError as exc:
            logger.warning(
                "insert_decision failed for %s: %s",
                decision.get("id") or "?",
                exc,
            )

    async def update_decision(
        self,
        decision_id: str,
        *,
        outcome: Optional[str] = None,
        outcome_reason: Optional[str] = None,
        execution_order_id: Optional[str] = None,
        trade_group_id: Optional[str] = None,
    ) -> None:
        try:
            db = await self._session()
            try:
                row = await db.get(AutoDecisionRow, decision_id)
                if row is None:
                    return
                if outcome is not None:
                    row.decision_outcome = outcome
                if outcome_reason is not None:
                    row.outcome_reason = outcome_reason
                if execution_order_id is not None:
                    row.execution_order_id = execution_order_id
                if trade_group_id is not None:
                    row.trade_group_id = trade_group_id
                await db.commit()
            finally:
                await db.close()
        except SQLAlchemyError as exc:
            logger.warning("update_decision failed for %s: %s", decision_id, exc)

    async def last_decision_hash(self, user_id: str) -> Optional[str]:
        try:
            db = await self._session()
            try:
                stmt = (
                    select(AutoDecisionRow.entry_hash)
                    .where(AutoDecisionRow.user_id == user_id)
                    .order_by(AutoDecisionRow.decided_at.desc())
                    .limit(1)
                )
                result = await db.execute(stmt)
                return result.scalar_one_or_none()
            finally:
                await db.close()
        except SQLAlchemyError as exc:
            logger.debug("last_decision_hash failed: %s", exc)
            return None

    async def list_decisions(
        self,
        user_id: str,
        *,
        cycle_id: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AutoDecisionRow]:
        try:
            db = await self._session()
            try:
                conditions = [AutoDecisionRow.user_id == user_id]
                if cycle_id:
                    conditions.append(AutoDecisionRow.cycle_id == cycle_id)
                if outcome:
                    conditions.append(AutoDecisionRow.decision_outcome == outcome)
                stmt = (
                    select(AutoDecisionRow)
                    .where(and_(*conditions))
                    .order_by(AutoDecisionRow.decided_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
                result = await db.execute(stmt)
                return list(result.scalars())
            finally:
                await db.close()
        except SQLAlchemyError as exc:
            logger.warning("list_decisions failed: %s", exc)
            return []

    async def decisions_for_export(
        self,
        user_id: str,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
    ) -> List[AutoDecisionRow]:
        try:
            db = await self._session()
            try:
                conditions = [AutoDecisionRow.user_id == user_id]
                if from_ts is not None:
                    conditions.append(AutoDecisionRow.decided_at >= from_ts)
                if to_ts is not None:
                    conditions.append(AutoDecisionRow.decided_at <= to_ts)
                stmt = (
                    select(AutoDecisionRow)
                    .where(and_(*conditions))
                    .order_by(AutoDecisionRow.decided_at.asc())
                )
                result = await db.execute(stmt)
                return list(result.scalars())
            finally:
                await db.close()
        except SQLAlchemyError as exc:
            logger.warning("decisions_for_export failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # trade_groups
    # ------------------------------------------------------------------

    async def insert_trade_group(self, group: Dict[str, Any]) -> None:
        try:
            db = await self._session()
            try:
                row = TradeGroupRow(**group)
                db.add(row)
                await db.commit()
            finally:
                await db.close()
        except SQLAlchemyError as exc:
            logger.warning("insert_trade_group failed: %s", exc)

    async def update_trade_group(
        self,
        group_id: str,
        updates: Dict[str, Any],
    ) -> None:
        try:
            db = await self._session()
            try:
                row = await db.get(TradeGroupRow, group_id)
                if row is None:
                    return
                for key, value in updates.items():
                    if hasattr(row, key):
                        setattr(row, key, value)
                row.updated_at = datetime.now(timezone.utc)
                await db.commit()
            finally:
                await db.close()
        except SQLAlchemyError as exc:
            logger.warning("update_trade_group failed: %s", exc)

    async def find_open_group(
        self,
        user_id: str,
        symbol: str,
        side: str = "buy",
    ) -> Optional[TradeGroupRow]:
        try:
            db = await self._session()
            try:
                stmt = (
                    select(TradeGroupRow)
                    .where(
                        and_(
                            TradeGroupRow.user_id == user_id,
                            TradeGroupRow.symbol == symbol,
                            TradeGroupRow.side == side,
                            TradeGroupRow.status == "open",
                        )
                    )
                    .order_by(TradeGroupRow.created_at.asc())
                    .limit(1)
                )
                result = await db.execute(stmt)
                return result.scalars().first()
            finally:
                await db.close()
        except SQLAlchemyError as exc:
            logger.warning("find_open_group failed: %s", exc)
            return None

    async def list_trade_groups(
        self,
        user_id: str,
        *,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TradeGroupRow]:
        try:
            db = await self._session()
            try:
                conditions = [TradeGroupRow.user_id == user_id]
                if status:
                    conditions.append(TradeGroupRow.status == status)
                stmt = (
                    select(TradeGroupRow)
                    .where(and_(*conditions))
                    .order_by(TradeGroupRow.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
                result = await db.execute(stmt)
                return list(result.scalars())
            finally:
                await db.close()
        except SQLAlchemyError as exc:
            logger.warning("list_trade_groups failed: %s", exc)
            return []

    async def get_trade_group(self, group_id: str) -> Optional[TradeGroupRow]:
        try:
            db = await self._session()
            try:
                return await db.get(TradeGroupRow, group_id)
            finally:
                await db.close()
        except SQLAlchemyError as exc:
            logger.debug("get_trade_group failed: %s", exc)
            return None

    async def groups_needing_backfill(self, limit: int = 100) -> List[TradeGroupRow]:
        try:
            db = await self._session()
            try:
                stmt = (
                    select(TradeGroupRow)
                    .where(
                        and_(
                            TradeGroupRow.status == "closed",
                            TradeGroupRow.max_drawdown_during_hold.is_(None),
                        )
                    )
                    .order_by(TradeGroupRow.exit_time.asc())
                    .limit(limit)
                )
                result = await db.execute(stmt)
                return list(result.scalars())
            finally:
                await db.close()
        except SQLAlchemyError as exc:
            logger.debug("groups_needing_backfill failed: %s", exc)
            return []


# Module-level singleton
auto_repository = AutoRepository()
