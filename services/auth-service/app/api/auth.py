"""Authentication API router.

Provides endpoints for user registration, login, token refresh,
and profile management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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
    TokenRefresh,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


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

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate a user and return tokens.

    Validates email + password, then issues an access / refresh pair.
    """
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
