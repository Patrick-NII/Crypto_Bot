"""Configuration settings for the Trading Engine service."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_NAME: str = "Trading Engine"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/trading_engine"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Inter-service URLs
    MARKET_DATA_SERVICE_URL: str = "http://localhost:8003"
    RISK_SERVICE_URL: str = "http://localhost:8005"
    PORTFOLIO_SERVICE_URL: str = "http://localhost:8006"

    # Trading
    TRADING_MODE: str = "paper"  # "paper" or "live"

    # Binance (via CCXT)
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None

    model_config = {"env_prefix": "TRADING_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
