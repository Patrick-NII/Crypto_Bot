"""Pydantic schemas for authentication requests and responses."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field

RiskProfileValue = "conservative|moderate|aggressive"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Payload for registering a new user."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    accept_terms: bool
    terms_version: str = Field(default="2026-04", min_length=4, max_length=20)
    subscription_plan: str = Field(default="starter", pattern=r"^(discover|starter|pro|elite)$")
    billing_cycle: str = Field(default="monthly", pattern=r"^(monthly|yearly)$")


class UserLogin(BaseModel):
    """Payload for logging in."""

    email: EmailStr
    password: str


class TokenRefresh(BaseModel):
    """Payload for refreshing an access token."""

    refresh_token: str


class UserUpdate(BaseModel):
    """Payload for updating a user profile."""

    username: Optional[str] = Field(None, min_length=3, max_length=100)
    telegram_chat_id: Optional[str] = None
    risk_profile: Optional[str] = Field(None, pattern=r"^(conservative|moderate|aggressive)$")
    subscription_plan: Optional[str] = Field(None, pattern=r"^(discover|starter|pro|elite)$")
    billing_cycle: Optional[str] = Field(None, pattern=r"^(monthly|yearly)$")
    ai_behavior_style: Optional[str] = Field(None, pattern=r"^(gentle|balanced|assertive|aggressive)$")
    ai_assistant_tone: Optional[str] = Field(None, pattern=r"^(concise|coach|analytical)$")
    preferences: Optional[dict[str, Any]] = None


class TermsAcceptance(BaseModel):
    """Accept the platform terms."""

    terms_version: str = Field(default="2026-04", min_length=4, max_length=20)


class ExchangeConnectionCreate(BaseModel):
    """Payload for registering encrypted exchange credentials."""

    provider: str = Field(..., min_length=2, max_length=50)
    label: Optional[str] = Field(None, min_length=2, max_length=100)
    api_key: str = Field(..., min_length=6, max_length=512)
    api_secret: str = Field(..., min_length=6, max_length=1024)
    passphrase: Optional[str] = Field(None, min_length=2, max_length=512)
    sandbox_mode: bool = False
    can_trade: bool = False


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ExchangeConnectionResponse(BaseModel):
    """Safe exchange connection representation without secrets."""

    id: uuid.UUID
    provider: str
    label: str
    api_key_hint: str
    has_passphrase: bool
    sandbox_mode: bool
    can_trade: bool
    is_active: bool
    status: str
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime


class ExchangeProviderResponse(BaseModel):
    """Metadata and setup guidance for a supported provider."""

    provider: str
    label: str
    supports_testnet: bool
    requires_passphrase: bool
    recommended_permissions: list[str]
    setup_steps: list[str]


class UserResponse(BaseModel):
    """Public representation of a user."""

    id: uuid.UUID
    email: str
    username: str
    is_active: bool
    is_verified: bool
    risk_profile: str
    subscription_plan: str
    subscription_status: str
    billing_cycle: str
    accepted_terms_at: Optional[datetime]
    terms_version: str
    ai_behavior_style: str
    ai_assistant_tone: str
    wallet_access_enabled: bool
    wallet_access_reason: str
    connected_exchanges_count: int
    live_trading_enabled: bool
    preferences: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TokenResponse(BaseModel):
    """JWT token pair returned on login / register / refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str
    exp: int


# ---------------------------------------------------------------------------
# Email verification & password reset
# ---------------------------------------------------------------------------


class VerifyEmailRequest(BaseModel):
    """Token received via email link."""

    token: str


class PasswordResetRequest(BaseModel):
    """Request a password reset email."""

    email: EmailStr


class PasswordReset(BaseModel):
    """Reset password using a token."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class LogoutRequest(BaseModel):
    """Payload for logging out."""

    refresh_token: str


class ExchangeCredentialsResponse(BaseModel):
    """Decrypted credentials returned to internal services only."""

    provider: str
    api_key: str
    api_secret: str
    passphrase: Optional[str] = None
    sandbox_mode: bool


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
