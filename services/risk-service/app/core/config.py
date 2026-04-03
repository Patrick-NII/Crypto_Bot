from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Risk service configuration."""

    # Infrastructure
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_bot"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Inter-service communication
    MARKET_DATA_SERVICE_URL: str = "http://localhost:8003"

    # Risk thresholds
    MAX_PORTFOLIO_DRAWDOWN: float = 0.15
    DEFAULT_STOP_LOSS_PCT: float = 0.05
    DEFAULT_TAKE_PROFIT_PCT: float = 0.15
    MAX_POSITION_SIZE_PCT: float = 0.10
    MAX_DAILY_TRADES: int = 20
    MAX_LEVERAGE: float = 1.0
    RISK_PER_TRADE_PCT: float = 0.02

    # VaR parameters
    VAR_CONFIDENCE_LEVEL: float = 0.95
    VAR_LOOKBACK_DAYS: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
