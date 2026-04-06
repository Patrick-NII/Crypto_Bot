"""Authentication API router.

Provides endpoints for user registration, login, token refresh,
profile management, email verification, password reset, and logout.
"""

import secrets
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.credentials import decrypt_secret, encrypt_secret, mask_api_key
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
from app.models.user import ExchangeConnection, User
from app.schemas.auth import (
    ExchangeConnectionCreate,
    ExchangeConnectionResponse,
    ExchangeCredentialsResponse,
    ExchangeProviderResponse,
    LogoutRequest,
    MessageResponse,
    PasswordReset,
    PasswordResetRequest,
    TermsAcceptance,
    TokenRefresh,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

EXCHANGE_PROVIDER_GUIDES = {
    "binance": ExchangeProviderResponse(
        provider="binance",
        label="Binance",
        supports_testnet=True,
        requires_passphrase=False,
        recommended_permissions=["Read balances", "Read trade history", "Spot trading (optional)"],
        setup_steps=[
            "Create an API key from Binance API Management.",
            "Whitelist this app IP if your security policy requires it.",
            "Enable read access first. Only enable trading when you trust the setup.",
            "Paste API key and secret below, then save the connection.",
        ],
    ),
    "coinbase": ExchangeProviderResponse(
        provider="coinbase",
        label="Coinbase Advanced",
        supports_testnet=False,
        requires_passphrase=False,
        recommended_permissions=["View", "Trade (optional)"],
        setup_steps=[
            "Open Coinbase Advanced API settings and create a dedicated key.",
            "Use a separate key per environment to keep production isolated.",
            "Start in read-only mode if you only want portfolio visibility.",
        ],
    ),
    "kraken": ExchangeProviderResponse(
        provider="kraken",
        label="Kraken",
        supports_testnet=False,
        requires_passphrase=False,
        recommended_permissions=["Query funds", "Query open orders", "Create orders (optional)"],
        setup_steps=[
            "Generate a new Kraken API key with funding query rights.",
            "Add trade rights only if you want live execution from the app.",
            "Store the secret once. Kraken will not show it again.",
        ],
    ),
    "bybit": ExchangeProviderResponse(
        provider="bybit",
        label="Bybit",
        supports_testnet=True,
        requires_passphrase=False,
        recommended_permissions=["Read-only", "Unified trading (optional)"],
        setup_steps=[
            "Create a dedicated API key in the Bybit API console.",
            "Pick read-only for portfolio sync, then upgrade to trading later if needed.",
            "Enable testnet when validating your setup without live funds.",
        ],
    ),
    "okx": ExchangeProviderResponse(
        provider="okx",
        label="OKX",
        supports_testnet=True,
        requires_passphrase=True,
        recommended_permissions=["Read", "Trade (optional)"],
        setup_steps=[
            "Create an API key in the OKX API section.",
            "Copy the API key, secret and passphrase immediately.",
            "Use passphrase exactly as created; it is required to reconnect later.",
        ],
    ),
}


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
            detail="Trop de tentatives. Reessayez dans quelques minutes.",
        )


def _normalise_provider(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


async def _list_connections_for_user(
    db: AsyncSession,
    user_id: UUID,
) -> list[ExchangeConnection]:
    result = await db.execute(
        select(ExchangeConnection)
        .where(ExchangeConnection.user_id == user_id)
        .order_by(ExchangeConnection.created_at.desc())
    )
    return result.scalars().all()


def _has_active_subscription(user: User) -> bool:
    return user.subscription_status in {"trial", "active"}


def _wallet_access_reason(user: User, connections: list[ExchangeConnection]) -> str:
    active_connections = [conn for conn in connections if conn.is_active]
    if user.accepted_terms_at is None:
        return "Accept the platform terms to unlock wallet features."
    if not _has_active_subscription(user):
        return "An active trial or subscription is required to unlock wallet features."
    if not active_connections:
        return "Add at least one exchange or wallet API connection in Settings."
    return "Wallet features unlocked."


async def _sync_user_access_state(
    user: User,
    db: AsyncSession,
    *,
    connections: list[ExchangeConnection] | None = None,
) -> tuple[list[ExchangeConnection], bool, str]:
    if connections is None:
        connections = await _list_connections_for_user(db, user.id)
    live_trading_enabled = any(
        connection.is_active and connection.can_trade for connection in connections
    )
    wallet_access_enabled = (
        user.accepted_terms_at is not None
        and _has_active_subscription(user)
        and any(connection.is_active for connection in connections)
    )
    user.wallet_access_enabled = wallet_access_enabled
    reason = _wallet_access_reason(user, connections)
    return connections, live_trading_enabled, reason


def _connection_response(connection: ExchangeConnection) -> ExchangeConnectionResponse:
    return ExchangeConnectionResponse(
        id=connection.id,
        provider=connection.provider,
        label=connection.label,
        api_key_hint=mask_api_key(decrypt_secret(connection.encrypted_api_key)),
        has_passphrase=bool(connection.encrypted_passphrase),
        sandbox_mode=connection.sandbox_mode,
        can_trade=connection.can_trade,
        is_active=connection.is_active,
        status=connection.status,
        last_error=connection.last_error,
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


def _normalize_preferences(value: object) -> dict:
    return value if isinstance(value, dict) else {}


async def _user_response(user: User, db: AsyncSession) -> UserResponse:
    connections, live_trading_enabled, reason = await _sync_user_access_state(user, db)
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        is_active=user.is_active,
        is_verified=user.is_verified,
        risk_profile=user.risk_profile,
        subscription_plan=user.subscription_plan,
        subscription_status=user.subscription_status,
        billing_cycle=user.billing_cycle,
        accepted_terms_at=user.accepted_terms_at,
        terms_version=user.terms_version,
        ai_behavior_style=user.ai_behavior_style,
        ai_assistant_tone=user.ai_assistant_tone,
        wallet_access_enabled=user.wallet_access_enabled,
        wallet_access_reason=reason,
        connected_exchanges_count=sum(1 for connection in connections if connection.is_active),
        live_trading_enabled=live_trading_enabled,
        preferences=_normalize_preferences(user.preferences),
        created_at=user.created_at,
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
    if not payload.accept_terms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous devez accepter les conditions pour creer un compte.",
        )

    # Validate password strength
    pwd = payload.password
    if len(pwd) < 8:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 8 caracteres.")
    if not any(c.isdigit() for c in pwd):
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins un chiffre.")
    if not any(c.isupper() for c in pwd):
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins une majuscule.")

    # Validate username
    if len(payload.username) < 3:
        raise HTTPException(status_code=400, detail="Le nom d'utilisateur doit contenir au moins 3 caracteres.")
    if not payload.username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Le nom d'utilisateur ne peut contenir que des lettres, chiffres, _ et -.")

    # Check for existing email
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse email est deja utilisee.",
        )

    # Check for existing username
    result = await db.execute(select(User).where(User.username == payload.username))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce nom d'utilisateur est deja pris.",
        )

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        subscription_plan=payload.subscription_plan,
        subscription_status="trial",
        billing_cycle=payload.billing_cycle,
        accepted_terms_at=datetime.now(timezone.utc),
        terms_version=payload.terms_version or settings.TERMS_VERSION,
        ai_behavior_style="balanced",
        ai_assistant_tone="analytical",
        wallet_access_enabled=False,
        preferences={},
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
            detail="Email ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte a ete desactive.",
        )

    # Auto-deactivate if not verified after 72h (RGPD: data minimization)
    if not user.is_verified and user.created_at:
        hours_since_creation = (datetime.now(timezone.utc) - user.created_at).total_seconds() / 3600
        if hours_since_creation > 72:
            user.is_active = False
            db.add(user)
            await db.flush()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Votre compte a ete desactive car l'email n'a pas ete verifie dans les 72h. Contactez support@gluetrade.com pour le reactiver.",
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
            detail="Session expiree. Veuillez vous reconnecter.",
        )

    from uuid import UUID

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte introuvable ou desactive.",
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
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's profile."""
    return await _user_response(current_user, db)


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
                detail="Ce nom d'utilisateur est deja pris.",
            )
        current_user.username = payload.username

    if payload.telegram_chat_id is not None:
        current_user.telegram_chat_id = payload.telegram_chat_id

    if payload.risk_profile is not None:
        current_user.risk_profile = payload.risk_profile

    if payload.subscription_plan is not None:
        current_user.subscription_plan = payload.subscription_plan

    if payload.billing_cycle is not None:
        current_user.billing_cycle = payload.billing_cycle

    if payload.ai_behavior_style is not None:
        current_user.ai_behavior_style = payload.ai_behavior_style

    if payload.ai_assistant_tone is not None:
        current_user.ai_assistant_tone = payload.ai_assistant_tone

    if payload.preferences is not None:
        current_user.preferences = _normalize_preferences(payload.preferences)

    db.add(current_user)
    await db.flush()
    await db.refresh(current_user)

    return await _user_response(current_user, db)


# ---------------------------------------------------------------------------
# POST /me/accept-terms
# ---------------------------------------------------------------------------


@router.post("/me/accept-terms", response_model=UserResponse)
async def accept_terms(
    payload: TermsAcceptance,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept or renew the current platform terms."""
    current_user.accepted_terms_at = datetime.now(timezone.utc)
    current_user.terms_version = payload.terms_version or settings.TERMS_VERSION
    db.add(current_user)
    await db.flush()
    await db.refresh(current_user)
    return await _user_response(current_user, db)


# ---------------------------------------------------------------------------
# DELETE /me  (RGPD: droit a l'effacement)
# ---------------------------------------------------------------------------


class DeleteAccountRequest(BaseModel):
    password: str = Field(..., description="Mot de passe pour confirmer la suppression")


@router.delete("/me", response_model=MessageResponse)
async def delete_account(
    payload: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Suppression definitive du compte et de toutes les donnees associees (RGPD Art. 17).

    Supprime : profil, exchange connections, preferences, tokens.
    Cette action est irreversible.
    """
    # Verify password
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mot de passe incorrect. Suppression refusee.",
        )

    # Invalidate all tokens in Redis
    try:
        r = await get_redis()
        # We can't enumerate all tokens, but blacklist current refresh
        await r.setex(f"deleted_user:{current_user.id}", 86400 * 30, "1")
    except Exception:
        pass

    # Delete user (cascade deletes exchange_connections via relationship)
    await db.delete(current_user)
    await db.flush()

    return MessageResponse(message="Votre compte et toutes vos donnees ont ete supprimes definitivement.")


# ---------------------------------------------------------------------------
# GET /me/data-export  (RGPD: droit a la portabilite)
# ---------------------------------------------------------------------------


@router.get("/me/data-export")
async def export_user_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Exporte toutes les donnees personnelles de l'utilisateur (RGPD Art. 20).

    Retourne un JSON contenant profil, preferences, et connexions.
    """
    connections = await _list_connections_for_user(db, current_user.id)

    return {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "username": current_user.username,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "is_verified": current_user.is_verified,
            "risk_profile": current_user.risk_profile,
            "subscription_plan": current_user.subscription_plan,
            "subscription_status": current_user.subscription_status,
            "billing_cycle": current_user.billing_cycle,
            "accepted_terms_at": current_user.accepted_terms_at.isoformat() if current_user.accepted_terms_at else None,
            "terms_version": current_user.terms_version,
            "ai_behavior_style": current_user.ai_behavior_style,
            "ai_assistant_tone": current_user.ai_assistant_tone,
        },
        "exchange_connections": [
            {
                "provider": c.provider,
                "label": c.label,
                "sandbox_mode": c.sandbox_mode,
                "can_trade": c.can_trade,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in connections
        ],
    }


# ---------------------------------------------------------------------------
# GET /exchange-providers
# ---------------------------------------------------------------------------


@router.get("/exchange-providers", response_model=list[ExchangeProviderResponse])
async def list_exchange_providers() -> list[ExchangeProviderResponse]:
    """Return supported provider metadata and setup guidance."""
    return list(EXCHANGE_PROVIDER_GUIDES.values())


# ---------------------------------------------------------------------------
# GET /me/exchange-connections
# ---------------------------------------------------------------------------


@router.get("/me/exchange-connections", response_model=list[ExchangeConnectionResponse])
async def list_exchange_connections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ExchangeConnectionResponse]:
    """Return the current user's configured exchange connections."""
    connections = await _list_connections_for_user(db, current_user.id)
    return [_connection_response(connection) for connection in connections]


# ---------------------------------------------------------------------------
# GET /me/exchange-connections/{provider}/credentials  (service-to-service)
# ---------------------------------------------------------------------------


@router.get(
    "/me/exchange-connections/{provider}/credentials",
    response_model=ExchangeCredentialsResponse,
)
async def get_exchange_credentials(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExchangeCredentialsResponse:
    """Return decrypted API credentials for the first active connection of *provider*.

    Intended for service-to-service calls (e.g. trading-engine fetching
    credentials on behalf of the authenticated user).  The caller must
    forward the user's JWT.
    """
    provider = _normalise_provider(provider)
    result = await db.execute(
        select(ExchangeConnection).where(
            ExchangeConnection.user_id == current_user.id,
            ExchangeConnection.provider == provider,
            ExchangeConnection.is_active == True,
        ).order_by(ExchangeConnection.created_at.desc())
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active {provider} connection found for this user",
        )

    return ExchangeCredentialsResponse(
        provider=connection.provider,
        api_key=decrypt_secret(connection.encrypted_api_key),
        api_secret=decrypt_secret(connection.encrypted_api_secret),
        passphrase=decrypt_secret(connection.encrypted_passphrase) if connection.encrypted_passphrase else None,
        sandbox_mode=connection.sandbox_mode,
    )


# ---------------------------------------------------------------------------
# POST /me/exchange-connections
# ---------------------------------------------------------------------------


@router.post(
    "/me/exchange-connections",
    response_model=ExchangeConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_exchange_connection(
    payload: ExchangeConnectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExchangeConnectionResponse:
    """Store encrypted API credentials for a user exchange connection."""
    provider = _normalise_provider(payload.provider)
    label = payload.label.strip() if payload.label else provider.upper()

    result = await db.execute(
        select(ExchangeConnection).where(
            ExchangeConnection.user_id == current_user.id,
            ExchangeConnection.provider == provider,
            ExchangeConnection.label == label,
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une connexion avec ce fournisseur existe deja.",
        )

    connection = ExchangeConnection(
        user_id=current_user.id,
        provider=provider,
        label=label,
        encrypted_api_key=encrypt_secret(payload.api_key),
        encrypted_api_secret=encrypt_secret(payload.api_secret),
        encrypted_passphrase=encrypt_secret(payload.passphrase) if payload.passphrase else None,
        sandbox_mode=payload.sandbox_mode,
        can_trade=payload.can_trade,
        is_active=True,
        status="configured",
    )
    db.add(connection)
    await db.flush()
    await _sync_user_access_state(current_user, db)
    db.add(current_user)
    await db.flush()
    await db.refresh(connection)
    return _connection_response(connection)


# ---------------------------------------------------------------------------
# DELETE /me/exchange-connections/{connection_id}
# ---------------------------------------------------------------------------


@router.delete("/me/exchange-connections/{connection_id}", response_model=MessageResponse)
async def delete_exchange_connection(
    connection_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete one stored exchange connection for the current user."""
    result = await db.execute(
        select(ExchangeConnection).where(
            ExchangeConnection.id == connection_id,
            ExchangeConnection.user_id == current_user.id,
        )
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=404, detail="Connexion exchange introuvable.")

    await db.delete(connection)
    await db.flush()
    await _sync_user_access_state(current_user, db)
    db.add(current_user)
    await db.flush()

    return MessageResponse(message="Exchange connection deleted")


# ---------------------------------------------------------------------------
# POST /verify-email
# ---------------------------------------------------------------------------


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    """Verify a user's email using the token sent via email."""
    r = await get_redis()
    user_id = await r.get(f"verify:{payload.token}")
    if not user_id:
        raise HTTPException(status_code=400, detail="Lien de verification invalide ou expire.")

    from uuid import UUID
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Compte introuvable.")

    user.is_verified = True
    db.add(user)
    await db.flush()
    await r.delete(f"verify:{payload.token}")

    return MessageResponse(message="Email verifie avec succes !")


# ---------------------------------------------------------------------------
# POST /resend-verification
# ---------------------------------------------------------------------------


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(current_user: User = Depends(get_current_user)):
    """Resend the email verification link."""
    if current_user.is_verified:
        return MessageResponse(message="Votre email est deja verifie.")

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

    return MessageResponse(message="Si cette adresse existe, un lien de reinitialisation a ete envoye.")


# ---------------------------------------------------------------------------
# POST /password-reset
# ---------------------------------------------------------------------------


@router.post("/password-reset", response_model=MessageResponse)
async def password_reset(payload: PasswordReset, db: AsyncSession = Depends(get_db)):
    """Reset password using a valid token."""
    r = await get_redis()
    user_id = await r.get(f"reset:{payload.token}")
    if not user_id:
        raise HTTPException(status_code=400, detail="Lien de reinitialisation invalide ou expire.")

    from uuid import UUID
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Compte introuvable.")

    user.hashed_password = hash_password(payload.new_password)
    db.add(user)
    await db.flush()
    await r.delete(f"reset:{payload.token}")

    return MessageResponse(message="Mot de passe reinitialise avec succes !")


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
