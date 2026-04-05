"""Lightweight auth helpers for user-scoped paper trading."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_PAPER_USER_ID = "default"


def resolve_user_id_from_auth_header(auth_header: Optional[str]) -> str:
    """Return the JWT subject, defaulting only when auth is absent."""
    if not auth_header:
        return DEFAULT_PAPER_USER_ID

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed Authorization header",
        )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        logger.debug("Invalid JWT for trading-engine")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    user_id = str(payload.get("sub", "")).strip()
    return user_id or DEFAULT_PAPER_USER_ID


def resolve_request_user_id(request: Request) -> str:
    """Resolve the effective user for a FastAPI request."""
    return resolve_user_id_from_auth_header(request.headers.get("Authorization"))
