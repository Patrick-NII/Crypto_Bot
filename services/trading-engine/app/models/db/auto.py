"""ORM models for the auto-trading stack.

Tables created:
- auto_sessions          : one row per user with live auto-trading state
- auto_decisions         : one row per decision (executed OR rejected OR hold)
- trade_groups           : one row per position lifecycle (entry → exit)
- sms_notifications      : durable log of every SMS dispatched (audit / billing)

Pattern copied from ``app.models.db.order`` — Declarative Base, timezone-aware
timestamps, JSONB for flexible payloads, indexed for the frequent queries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AutoSessionRow(Base):
    """Live auto-trading state snapshot (one row per user)."""

    __tablename__ = "auto_sessions"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="paper"
    )  # paper | live | dry_run
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_cycle_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_cycle_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    cycles_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trades_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    realized_pnl_today: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), nullable=False, default=Decimal("0")
    )
    consecutive_losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    portfolio_value_start_of_day: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(38, 18), nullable=True
    )

    cooldown_symbols: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trade_day: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )


class AutoDecisionRow(Base):
    """A single decision taken by the auto-trader during a cycle.

    Records every opportunity seen (executed, rejected, or hold). The
    ``signals`` JSONB holds the full indicator snapshot and scoring from the
    ml-service, while ``context`` holds the regime / scenarios / ranking
    metadata. Downstream retraining consumes these two columns as the
    feature store.
    """

    __tablename__ = "auto_decisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cycle_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # buy | sell | hold

    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)
    target_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=Decimal("0"))
    score: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=Decimal("0"))

    regime: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    scenario: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Feature store — signals and context snapshots (JSONB)
    signals: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Outcome
    decision_outcome: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )  # executed | rejected_filter | rejected_risk | rejected_balance | dry_run | hold | pending
    outcome_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    trade_group_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Audit chain (tamper-evident)
    prev_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    __table_args__ = (
        Index("ix_auto_decisions_user_decided", "user_id", "decided_at"),
        Index("ix_auto_decisions_cycle", "cycle_id"),
        Index("ix_auto_decisions_group", "trade_group_id"),
        Index("ix_auto_decisions_outcome", "user_id", "decision_outcome"),
    )


class TradeGroupRow(Base):
    """Position lifecycle linking an entry order to its exit order.

    The ``id`` is surfaced to the frontend as the user-visible "transaction
    number" that ties a buy and its eventual sell. Matching is FIFO on the
    same symbol for the same user.
    """

    __tablename__ = "trade_groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # direction of the entry
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open"
    )  # open | closed | cancelled

    entry_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    exit_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    entry_decision_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    exit_decision_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    entry_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    holding_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    entry_quantity: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), nullable=False, default=Decimal("0")
    )
    exit_quantity: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), nullable=False, default=Decimal("0")
    )
    entry_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)
    exit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)
    entry_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)
    exit_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)

    entry_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    realized_pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)
    realized_pnl_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    max_drawdown_during_hold: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)

    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_trade_groups_user_status", "user_id", "status", "created_at"),
        Index("ix_trade_groups_symbol_status", "user_id", "symbol", "status"),
    )


class SmsNotificationRow(Base):
    """Durable log of every SMS dispatched via Twilio (audit + billing)."""

    __tablename__ = "sms_notifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    twilio_sid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="queued"
    )  # queued | sent | delivered | failed
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_sms_user_sent", "user_id", "sent_at"),
        Index("ix_sms_event", "event_type"),
    )
