from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AI Agent Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # LLM API Keys
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Default models per tier
    MODEL_FAST: str = "gpt-4o-mini"
    MODEL_MEDIUM: str = "gpt-4o"
    MODEL_COMPLEX: str = "claude-sonnet-4-20250514"

    # Database — shared with trading-engine (gluetrade_trading)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@postgres:5432/gluetrade_trading",
        validation_alias=AliasChoices("DATABASE_URL", "AI_DATABASE_URL"),
    )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # JWT (must match auth-service)
    JWT_SECRET_KEY: str = Field(
        default="CHANGE-ME-IN-PRODUCTION",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "AI_JWT_SECRET_KEY"),
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        validation_alias=AliasChoices("JWT_ALGORITHM", "AI_JWT_ALGORITHM"),
    )

    # Internal service URLs
    MARKET_DATA_URL: str = "http://localhost:8003"
    PORTFOLIO_URL: str = "http://localhost:8002"
    TRADING_URL: str = "http://localhost:8004"
    RISK_URL: str = "http://localhost:8005"
    STRATEGY_URL: str = "http://localhost:8006"
    AUTH_URL: str = "http://localhost:8001"

    # Conversation
    MAX_CONVERSATION_HISTORY: int = 50
    CONVERSATION_TTL_HOURS: int = 24

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
