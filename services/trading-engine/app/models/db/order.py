"""ORM models for orders, fills, idempotency, OCO legs, bracket groups, paper state."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrderRow(Base):
    """Persistent representation of an order placed by the engine."""

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    client_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    order_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    quote_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)
    filled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), nullable=False, default=Decimal("0")
    )
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)
    filled_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)
    stop_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)
    take_profit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)
    trailing_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    fee: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=Decimal("0"))

    exchange: Mapped[str] = mapped_column(String(32), nullable=False, default="paper")
    exchange_order_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    strategy: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    fills: Mapped[list["OrderFillRow"]] = relationship(
        "OrderFillRow",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    legs: Mapped[list["OrderLegRow"]] = relationship(
        "OrderLegRow",
        back_populates="parent_order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "client_order_id", name="ux_orders_user_client_order_id"),
        Index("ix_orders_user_status", "user_id", "status"),
        Index("ix_orders_user_symbol", "user_id", "symbol"),
    )


class OrderFillRow(Base):
    """Individual fill events for an order. Used for partial fill tracking."""

    __tablename__ = "order_fills"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trade_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)

    fill_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    fill_quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=Decimal("0"))
    fee_asset: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    is_maker: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    order: Mapped[OrderRow] = relationship("OrderRow", back_populates="fills")


class OrderLegRow(Base):
    """Sub-orders inside an OCO group (or other multi-leg structures)."""

    __tablename__ = "order_legs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_order_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leg_type: Mapped[str] = mapped_column(String(32), nullable=False)  # stop_loss | take_profit
    exchange_order_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    filled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), nullable=False, default=Decimal("0")
    )
    filled_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    parent_order: Mapped[OrderRow] = relationship("OrderRow", back_populates="legs")


class BracketGroupRow(Base):
    """Grouping for entry + stop-loss + take-profit chained orders."""

    __tablename__ = "bracket_groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    entry_order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sl_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tp_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_entry")

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


class IdempotencyKeyRow(Base):
    """Persistent idempotency table for client_order_id reuse across restarts."""

    __tablename__ = "idempotency_keys"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    internal_order_id: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaperAccountStateRow(Base):
    """Snapshot of the paper trader's per-user state.

    Stored as JSONB for simplicity — the in-memory ``PaperAccountState``
    dataclass is serialised on every fill (debounced) and rebuilt at boot.
    """

    __tablename__ = "paper_account_states"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )
