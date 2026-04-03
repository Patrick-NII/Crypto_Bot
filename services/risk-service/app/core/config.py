from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_bot"
    REDIS_HOST: str = "localhost"

    MAX_PORTFOLIO_DRAWDOWN: float = 0.15
    DEFAULT_STOP_LOSS_PCT: float = 0.05
    DEFAULT_TAKE_PROFIT_PCT: float = 0.15
    MAX_POSITION_SIZE_PCT: float = 0.10

    class Config:
        env_file = ".env"


settings = Settings()
