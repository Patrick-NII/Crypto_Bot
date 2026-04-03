from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_bot"
    REDIS_HOST: str = "localhost"
    MARKET_DATA_SERVICE_URL: str = "http://localhost:8003"
    MODEL_RETRAIN_INTERVAL_HOURS: int = 24

    class Config:
        env_file = ".env"


settings = Settings()
