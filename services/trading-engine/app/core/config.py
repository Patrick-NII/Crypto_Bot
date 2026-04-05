"""Configuration settings for the Trading Engine service."""

from __future__ import annotations

from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Trading Engine"
    APP_VERSION: str = "0.2.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/trading_engine",
        validation_alias=AliasChoices("DATABASE_URL", "TRADING_DATABASE_URL"),
    )

    # Redis
    REDIS_HOST: str = Field(
        default="localhost",
        validation_alias=AliasChoices("REDIS_HOST", "TRADING_REDIS_HOST"),
    )
    REDIS_PORT: int = Field(
        default=6379,
        validation_alias=AliasChoices("REDIS_PORT", "TRADING_REDIS_PORT"),
    )

    # Inter-service URLs
    MARKET_DATA_SERVICE_URL: str = Field(
        default="http://localhost:8003",
        validation_alias=AliasChoices(
            "MARKET_DATA_SERVICE_URL",
            "TRADING_MARKET_DATA_SERVICE_URL",
        ),
    )
    RISK_SERVICE_URL: str = Field(
        default="http://localhost:8005",
        validation_alias=AliasChoices("RISK_SERVICE_URL", "TRADING_RISK_SERVICE_URL"),
    )
    PORTFOLIO_SERVICE_URL: str = Field(
        default="http://localhost:8002",
        validation_alias=AliasChoices(
            "PORTFOLIO_SERVICE_URL",
            "TRADING_PORTFOLIO_SERVICE_URL",
        ),
    )
    AUTH_SERVICE_URL: str = Field(
        default="http://localhost:8001",
        validation_alias=AliasChoices("AUTH_SERVICE_URL", "TRADING_AUTH_SERVICE_URL"),
    )

    # JWT (must match auth-service / portfolio-service)
    JWT_SECRET_KEY: str = Field(
        default="CHANGE-ME-IN-PRODUCTION",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "TRADING_JWT_SECRET_KEY"),
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        validation_alias=AliasChoices("JWT_ALGORITHM", "TRADING_JWT_ALGORITHM"),
    )

    # Trading
    TRADING_MODE: str = Field(
        default="paper",
        validation_alias=AliasChoices("TRADING_MODE"),
    )  # "paper" or "live"

    # Binance (via CCXT)
    BINANCE_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("BINANCE_API_KEY", "TRADING_BINANCE_API_KEY"),
    )
    BINANCE_API_SECRET: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("BINANCE_API_SECRET", "TRADING_BINANCE_API_SECRET"),
    )

    # Exchange
    DEFAULT_EXCHANGE: str = Field(
        default="binance",
        validation_alias=AliasChoices("DEFAULT_EXCHANGE", "TRADING_DEFAULT_EXCHANGE"),
    )

    # Order execution
    ORDER_TIMEOUT_SECONDS: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "ORDER_TIMEOUT_SECONDS",
            "TRADING_ORDER_TIMEOUT_SECONDS",
        ),
    )
    MAX_RETRIES: int = Field(
        default=3,
        validation_alias=AliasChoices("MAX_RETRIES", "TRADING_MAX_RETRIES"),
    )


settings = Settings()
