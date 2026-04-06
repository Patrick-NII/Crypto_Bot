from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "GlueTrade Mailing Service"
    APP_VERSION: str = "1.0.0"

    # SMTP
    SMTP_HOST: str = "smtp.resend.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""  # Resend API key or SMTP password
    SMTP_USE_TLS: bool = True
    MAIL_FROM: str = "noreply@gluetrade.com"
    MAIL_FROM_NAME: str = "GlueTrade"

    # Redis (for async queue)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
