"""Async SQLAlchemy setup for the trading-engine.

Creates the ``gluetrade_trading`` database on first boot if it doesn't exist,
runs ``CREATE TABLE IF NOT EXISTS`` for the ORM models, and exposes a
session factory + ``get_db`` dependency.

Pattern copied from auth-service so the trading-engine matches the rest of
the platform's persistence story.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for trading-engine ORM models."""


# Lazy-initialised engines so they don't fail at import time when Postgres
# isn't available yet (e.g. during unit tests or container startup race).
_engine = None
_session_maker = None


def _build_engine():
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def get_engine():
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_maker():
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async session."""
    session = get_session_maker()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def _ensure_database_exists() -> None:
    """Create the application database if it does not yet exist.

    Connects to the Postgres ``postgres`` admin DB, checks for the target
    database name, and runs ``CREATE DATABASE`` if missing. Idempotent.
    """
    target_db_name = settings.DATABASE_URL.rsplit("/", 1)[-1]
    if not target_db_name:
        return

    admin_engine = create_async_engine(
        settings.DATABASE_ADMIN_URL,
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with admin_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target_db_name},
            )
            exists = result.scalar() is not None
            if not exists:
                logger.info("Creating database %s", target_db_name)
                # CREATE DATABASE cannot use parameter binding
                await conn.execute(text(f'CREATE DATABASE "{target_db_name}"'))
                logger.info("Database %s created", target_db_name)
            else:
                logger.debug("Database %s already exists", target_db_name)
    except SQLAlchemyError as exc:
        logger.warning("Could not ensure trading database exists: %s", exc)
    finally:
        await admin_engine.dispose()


async def init_db() -> None:
    """Create application tables on startup. Safe to call repeatedly."""
    await _ensure_database_exists()

    # Import models so SQLAlchemy is aware of them before create_all
    from app.models.db import order as _order_models  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Forward-compatible ALTER TABLE for evolution without migrations
        await conn.execute(
            text(
                """
                ALTER TABLE orders
                ADD COLUMN IF NOT EXISTS portfolio_id VARCHAR(64) NULL,
                ADD COLUMN IF NOT EXISTS quote_quantity NUMERIC(38, 18) NULL,
                ADD COLUMN IF NOT EXISTS stop_price NUMERIC(38, 18) NULL,
                ADD COLUMN IF NOT EXISTS take_profit_price NUMERIC(38, 18) NULL,
                ADD COLUMN IF NOT EXISTS trailing_pct NUMERIC(20, 8) NULL,
                ADD COLUMN IF NOT EXISTS error_message TEXT NULL
                """
            )
        )

    logger.info("trading-engine database initialised")
