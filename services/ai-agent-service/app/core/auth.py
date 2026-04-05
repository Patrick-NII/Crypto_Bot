"""Auth helpers for user-scoped AI features."""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_AI_USER_ID = "default"


def _decode_payload(auth_header: Optional[str]) -> dict:
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed Authorization header",
        )

    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        logger.debug("Invalid JWT for ai-agent-service")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


def resolve_user_id_from_auth_header(auth_header: Optional[str]) -> str:
    """Return the JWT subject, defaulting only when auth is absent."""
    if not auth_header:
        return DEFAULT_AI_USER_ID

    payload = _decode_payload(auth_header)
    user_id = str(payload.get("sub", "")).strip()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )
    return user_id


def resolve_request_user_id(request: Request) -> str:
    """Resolve the effective user for a FastAPI request."""
    return resolve_user_id_from_auth_header(request.headers.get("Authorization"))


def get_auth_ttl_seconds(auth_header: Optional[str]) -> Optional[int]:
    """Return a safe Redis TTL for a valid bearer token."""
    if not auth_header:
        return None

    payload = _decode_payload(auth_header)
    exp = payload.get("exp")
    if exp is None:
        return None

    try:
        ttl = int(exp) - int(time.time())
    except (TypeError, ValueError):
        return None

    return max(ttl, 0)
