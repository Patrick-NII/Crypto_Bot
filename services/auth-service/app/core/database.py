"""Async SQLAlchemy database setup."""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    The session is automatically closed when the request finishes.
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables defined on Base.metadata.

    Called once during application startup.
    """
    from app.models import ExchangeConnection, User  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(50) NOT NULL DEFAULT 'starter',
                ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50) NOT NULL DEFAULT 'trial',
                ADD COLUMN IF NOT EXISTS billing_cycle VARCHAR(20) NOT NULL DEFAULT 'monthly',
                ADD COLUMN IF NOT EXISTS accepted_terms_at TIMESTAMPTZ NULL,
                ADD COLUMN IF NOT EXISTS terms_version VARCHAR(20) NOT NULL DEFAULT '2026-04',
                ADD COLUMN IF NOT EXISTS ai_behavior_style VARCHAR(50) NOT NULL DEFAULT 'balanced',
                ADD COLUMN IF NOT EXISTS ai_assistant_tone VARCHAR(50) NOT NULL DEFAULT 'analytical',
                ADD COLUMN IF NOT EXISTS wallet_access_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS preferences JSONB NOT NULL DEFAULT '{}'::jsonb
                """
            )
        )
