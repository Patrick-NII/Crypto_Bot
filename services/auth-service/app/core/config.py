"""Application configuration using pydantic-settings."""

import base64
import hashlib

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """GlueTrade Auth Service configuration.

    Values are loaded from environment variables. A .env file in the project
    root is also read when present.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    APP_NAME: str = "GlueTrade Auth Service"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/gluetrade_auth"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # JWT
    JWT_SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Credentials encryption
    CREDENTIAL_ENCRYPTION_KEY: str | None = None

    # Product defaults
    TERMS_VERSION: str = "2026-04"

    # Email verification & password reset
    VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    RESET_TOKEN_EXPIRE_HOURS: int = 1
    FRONTEND_URL: str = "http://localhost:3000"

    # Mailing service
    MAILING_SERVICE_URL: str = "http://localhost:8009"

    # Rate limiting
    LOGIN_RATE_LIMIT: int = 5  # max attempts
    LOGIN_RATE_WINDOW: int = 300  # seconds (5 min)

    # Internal service-to-service token (used by notification-service for recap dispatch)
    INTERNAL_API_TOKEN: str = ""


settings = Settings()


if not settings.CREDENTIAL_ENCRYPTION_KEY:
    settings.CREDENTIAL_ENCRYPTION_KEY = base64.urlsafe_b64encode(
        hashlib.sha256(settings.JWT_SECRET_KEY.encode("utf-8")).digest()
    ).decode("utf-8")
