"""Async SQLAlchemy setup for ai-agent-service.

The ai-agent-service shares the ``gluetrade_trading`` database with the
trading-engine (schema owned there). This module only exposes an engine and
session factory — it does NOT run migrations (``init_db`` in trading-engine
is the single source of truth for the schema).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base used for the models this service reads/writes."""


_engine = None
_session_maker = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
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
    session = get_session_maker()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
