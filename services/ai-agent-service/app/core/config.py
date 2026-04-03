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

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://okamoey:okamoey@localhost:5433/okamoey"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Internal service URLs
    MARKET_DATA_URL: str = "http://localhost:8003"
    PORTFOLIO_URL: str = "http://localhost:8002"
    TRADING_URL: str = "http://localhost:8004"
    RISK_URL: str = "http://localhost:8005"
    STRATEGY_URL: str = "http://localhost:8006"

    # Conversation
    MAX_CONVERSATION_HISTORY: int = 50
    CONVERSATION_TTL_HOURS: int = 24

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
