"""Authentication API router.

Provides endpoints for user registration, login, token refresh,
profile management, email verification, password reset, and logout.
"""

import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import get_redis
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    verify_password,
    verify_token,
)
from app.models.user import User
from app.schemas.auth import (
    LogoutRequest,
    MessageResponse,
    PasswordReset,
    PasswordResetRequest,
    TokenRefresh,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Rate limiting helper
# ---------------------------------------------------------------------------

async def _check_rate_limit(key: str, limit: int, window: int) -> None:
    """Raise 429 if rate limit exceeded for the given key."""
    r = await get_redis()
    current = await r.incr(key)
    if current == 1:
        await r.expire(key, window)
    if current > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
        )


# ---------------------------------------------------------------------------
# POST /register
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user account.

    Returns an access / refresh token pair on success.
    """
    # Check for existing email
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Check for existing username
    result = await db.execute(select(User).where(User.username == payload.username))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    # Send verification email
    token = secrets.token_urlsafe(32)
    r = await get_redis()
    await r.setex(
        f"verify:{token}",
        settings.VERIFICATION_TOKEN_EXPIRE_HOURS * 3600,
        str(user.id),
    )
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.MAILING_SERVICE_URL}/api/v1/mail/send",
                json={
                    "to": user.email,
                    "template": "verify_email",
                    "data": {"username": user.username, "verify_url": verify_url},
                },
            )
    except Exception:
        pass  # Non-blocking

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    """Authenticate a user and return tokens.

    Validates email + password, then issues an access / refresh pair.
    """
    # Rate limit by IP
    client_ip = request.client.host if request.client else "unknown"
    await _check_rate_limit(
        f"ratelimit:login:{client_ip}",
        settings.LOGIN_RATE_LIMIT,
        settings.LOGIN_RATE_WINDOW,
    )

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: TokenRefresh, db: AsyncSession = Depends(get_db)):
    """Exchange a valid refresh token for a new access / refresh pair."""
    token_data = verify_token(payload.refresh_token, expected_type="refresh")

    user_id = token_data.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    from uuid import UUID

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token = create_access_token(str(user.id))
    new_refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return current_user


# ---------------------------------------------------------------------------
# PUT /me
# ---------------------------------------------------------------------------


@router.put("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's profile.

    Only the fields provided in the request body are modified.
    """
    if payload.username is not None:
        # Ensure uniqueness of the new username
        result = await db.execute(
            select(User).where(
                User.username == payload.username,
                User.id != current_user.id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )
        current_user.username = payload.username

    if payload.telegram_chat_id is not None:
        current_user.telegram_chat_id = payload.telegram_chat_id

    if payload.risk_profile is not None:
        current_user.risk_profile = payload.risk_profile

    db.add(current_user)
    await db.flush()
    await db.refresh(current_user)

    return current_user


# ---------------------------------------------------------------------------
# POST /verify-email
# ---------------------------------------------------------------------------


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    """Verify a user's email using the token sent via email."""
    r = await get_redis()
    user_id = await r.get(f"verify:{payload.token}")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    from uuid import UUID
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_verified = True
    db.add(user)
    await db.flush()
    await r.delete(f"verify:{payload.token}")

    return MessageResponse(message="Email verified successfully")


# ---------------------------------------------------------------------------
# POST /resend-verification
# ---------------------------------------------------------------------------


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(current_user: User = Depends(get_current_user)):
    """Resend the email verification link."""
    if current_user.is_verified:
        return MessageResponse(message="Email already verified")

    token = secrets.token_urlsafe(32)
    r = await get_redis()
    await r.setex(
        f"verify:{token}",
        settings.VERIFICATION_TOKEN_EXPIRE_HOURS * 3600,
        str(current_user.id),
    )

    # Send verification email via mailing service
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.MAILING_SERVICE_URL}/api/v1/mail/send",
                json={
                    "to": current_user.email,
                    "template": "verify_email",
                    "data": {"username": current_user.username, "verify_url": verify_url},
                },
            )
    except Exception:
        pass  # Non-blocking; user can retry

    return MessageResponse(message="Verification email sent")


# ---------------------------------------------------------------------------
# POST /password-reset-request
# ---------------------------------------------------------------------------


@router.post("/password-reset-request", response_model=MessageResponse)
async def password_reset_request(
    payload: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset email."""
    client_ip = request.client.host if request.client else "unknown"
    await _check_rate_limit(f"ratelimit:reset:{client_ip}", 3, 600)

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Always return success to prevent email enumeration
    if user:
        token = secrets.token_urlsafe(32)
        r = await get_redis()
        await r.setex(
            f"reset:{token}",
            settings.RESET_TOKEN_EXPIRE_HOURS * 3600,
            str(user.id),
        )
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{settings.MAILING_SERVICE_URL}/api/v1/mail/send",
                    json={
                        "to": user.email,
                        "template": "password_reset",
                        "data": {"username": user.username, "reset_url": reset_url},
                    },
                )
        except Exception:
            pass

    return MessageResponse(message="If the email exists, a reset link has been sent")


# ---------------------------------------------------------------------------
# POST /password-reset
# ---------------------------------------------------------------------------


@router.post("/password-reset", response_model=MessageResponse)
async def password_reset(payload: PasswordReset, db: AsyncSession = Depends(get_db)):
    """Reset password using a valid token."""
    r = await get_redis()
    user_id = await r.get(f"reset:{payload.token}")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    from uuid import UUID
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(payload.new_password)
    db.add(user)
    await db.flush()
    await r.delete(f"reset:{payload.token}")

    return MessageResponse(message="Password reset successfully")


# ---------------------------------------------------------------------------
# POST /logout
# ---------------------------------------------------------------------------


@router.post("/logout", response_model=MessageResponse)
async def logout(payload: LogoutRequest):
    """Blacklist a refresh token to log out."""
    r = await get_redis()
    # Blacklist the refresh token for its remaining lifetime
    await r.setex(
        f"blacklist:{payload.refresh_token}",
        settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        "1",
    )
    return MessageResponse(message="Logged out successfully")
