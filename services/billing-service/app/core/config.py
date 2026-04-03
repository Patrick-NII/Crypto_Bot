from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Okamoey Billing Service"
    APP_VERSION: str = "1.0.0"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_PRO: str = ""  # Stripe Price ID for Pro plan
    STRIPE_PRICE_ENTERPRISE: str = ""  # Stripe Price ID for Enterprise plan

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://okamoey:okamoey@localhost:5433/okamoey"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
