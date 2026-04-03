from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REDIS_HOST: str = "localhost"
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
