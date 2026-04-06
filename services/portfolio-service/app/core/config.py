"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """GlueTrade Portfolio Service configuration.

    Values are loaded from environment variables. A .env file in the project
    root is also read when present.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    APP_NAME: str = "GlueTrade Portfolio Service"

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/gluetrade_portfolio"
    )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # JWT (must match auth-service)
    JWT_SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"

    # Inter-service communication
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    MARKET_DATA_SERVICE_URL: str = "http://localhost:8003"
    TRADING_ENGINE_URL: str = "http://localhost:8004"
    RISK_SERVICE_URL: str = "http://localhost:8005"


settings = Settings()
