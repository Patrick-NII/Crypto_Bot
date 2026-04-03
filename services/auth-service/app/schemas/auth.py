"""Pydantic schemas for authentication requests and responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Payload for registering a new user."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Payload for logging in."""

    email: EmailStr
    password: str


class TokenRefresh(BaseModel):
    """Payload for refreshing an access token."""

    refresh_token: str


class UserUpdate(BaseModel):
    """Payload for updating a user profile."""

    username: str | None = Field(None, min_length=3, max_length=100)
    telegram_chat_id: str | None = None
    risk_profile: str | None = Field(None, pattern=r"^(conservative|moderate|aggressive)$")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class UserResponse(BaseModel):
    """Public representation of a user."""

    id: uuid.UUID
    email: str
    username: str
    is_active: bool
    is_verified: bool
    risk_profile: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT token pair returned on login / register / refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str
    exp: int
