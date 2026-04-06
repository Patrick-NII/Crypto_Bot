from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "GlueTrade Mailing Service"
    APP_VERSION: str = "1.0.0"

    # SMTP (Hostinger)
    SMTP_HOST: str = "smtp.hostinger.com"
    SMTP_PORT: int = 465
    SMTP_USE_SSL: bool = True  # SSL on port 465 (not STARTTLS)

    # ── Mailbox: hello@ (communication: welcome, alerts, newsletters) ──
    SMTP_HELLO_USER: str = ""
    SMTP_HELLO_PASSWORD: str = ""
    MAIL_FROM_HELLO: str = "hello@gluetrade.com"
    MAIL_FROM_HELLO_NAME: str = "GlueTrade"

    # ── Mailbox: support@ (transactional: verify, reset, security) ──
    SMTP_SUPPORT_USER: str = ""
    SMTP_SUPPORT_PASSWORD: str = ""
    MAIL_FROM_SUPPORT: str = "support@gluetrade.com"
    MAIL_FROM_SUPPORT_NAME: str = "GlueTrade Security"

    # Redis (for future async queue)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
