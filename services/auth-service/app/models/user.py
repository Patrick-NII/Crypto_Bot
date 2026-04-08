"""SQLAlchemy User model."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    """Represents a registered GlueTrade platform user."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    risk_profile: Mapped[str] = mapped_column(
        String(50),
        default="moderate",
        nullable=False,
    )
    subscription_plan: Mapped[str] = mapped_column(
        String(50),
        default="starter",
        nullable=False,
    )
    subscription_status: Mapped[str] = mapped_column(
        String(50),
        default="trial",
        nullable=False,
    )
    billing_cycle: Mapped[str] = mapped_column(
        String(20),
        default="monthly",
        nullable=False,
    )
    accepted_terms_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    terms_version: Mapped[str] = mapped_column(
        String(20),
        default="2026-04",
        nullable=False,
    )
    ai_behavior_style: Mapped[str] = mapped_column(
        String(50),
        default="balanced",
        nullable=False,
    )
    ai_assistant_tone: Mapped[str] = mapped_column(
        String(50),
        default="analytical",
        nullable=False,
    )
    wallet_access_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(
        String(50),
        default="Europe/Paris",
        nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(10),
        default="fr",
        nullable=False,
    )
    last_login_ip: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    exchange_connections: Mapped[list["ExchangeConnection"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.email})>"


class ExchangeConnection(Base):
    """Encrypted exchange API credentials owned by a user."""

    __tablename__ = "exchange_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    encrypted_api_key: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )
    encrypted_api_secret: Mapped[str] = mapped_column(
        String(4096),
        nullable=False,
    )
    encrypted_passphrase: Mapped[Optional[str]] = mapped_column(
        String(4096),
        nullable=True,
    )
    sandbox_mode: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    can_trade: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="configured",
        nullable=False,
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="exchange_connections")
