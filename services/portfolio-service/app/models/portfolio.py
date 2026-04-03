"""SQLAlchemy ORM models for the portfolio domain."""

import uuid
from datetime import datetime

from typing import List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Portfolio(Base):
    """A named collection of positions belonging to a single user."""

    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    positions: Mapped[List["Position"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan", lazy="selectin"
    )
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan", lazy="selectin"
    )


class Position(Base):
    """An open or historical position within a portfolio."""

    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="crypto"
    )  # crypto | stock | forex | commodity
    exchange: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    quantity: Mapped[float] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False, default=0
    )
    average_entry_price: Mapped[float] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False, default=0
    )
    current_price: Mapped[float] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False, default=0
    )
    unrealized_pnl: Mapped[float] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False, default=0
    )
    realized_pnl: Mapped[float] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False, default=0
    )
    stop_loss_price: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=20, scale=8), nullable=True
    )
    take_profit_price: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=20, scale=8), nullable=True
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    portfolio: Mapped["Portfolio"] = relationship(back_populates="positions")
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="position", cascade="all, delete-orphan", lazy="selectin"
    )


class Transaction(Base):
    """A single executed trade or order fill."""

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    position_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("positions.id", ondelete="SET NULL"),
        nullable=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(
        String(8), nullable=False
    )  # buy | sell
    quantity: Mapped[float] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False
    )
    price: Mapped[float] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False
    )
    fee: Mapped[float] = mapped_column(
        Numeric(precision=20, scale=8), nullable=False, default=0
    )
    exchange: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    strategy: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    portfolio: Mapped["Portfolio"] = relationship(back_populates="transactions")
    position: Mapped["Optional[Position]"] = relationship(back_populates="transactions")
