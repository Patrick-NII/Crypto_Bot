from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "GlueTrade News Service"
    APP_VERSION: str = "1.0.0"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    OPENAI_API_KEY: str = ""
    CRYPTOCOMPARE_BASE: str = "https://min-api.cryptocompare.com/data/v2"
    COINGECKO_BASE: str = "https://api.coingecko.com/api/v3"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
