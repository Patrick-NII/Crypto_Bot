"""Configuration settings for the Trading Engine service."""

from __future__ import annotations

from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_NAME: str = "Trading Engine"
    APP_VERSION: str = "0.2.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/trading_engine"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Inter-service URLs
    MARKET_DATA_SERVICE_URL: str = "http://localhost:8003"
    RISK_SERVICE_URL: str = "http://localhost:8005"
    PORTFOLIO_SERVICE_URL: str = "http://localhost:8002"
    AUTH_SERVICE_URL: str = "http://localhost:8001"

    # JWT (must match auth-service / portfolio-service)
    JWT_SECRET_KEY: str = Field(
        default="CHANGE-ME-IN-PRODUCTION",
        validation_alias=AliasChoices("TRADING_JWT_SECRET_KEY", "JWT_SECRET_KEY"),
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        validation_alias=AliasChoices("TRADING_JWT_ALGORITHM", "JWT_ALGORITHM"),
    )

    # Trading
    TRADING_MODE: str = "paper"  # "paper" or "live"

    # Binance (via CCXT)
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None

    # Exchange
    DEFAULT_EXCHANGE: str = "binance"

    # Order execution
    ORDER_TIMEOUT_SECONDS: int = 30
    MAX_RETRIES: int = 3

    model_config = {"env_prefix": "TRADING_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
