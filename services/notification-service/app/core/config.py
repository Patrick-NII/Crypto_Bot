from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REDIS_HOST: str = "localhost"
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_BOT_USERNAME: str = ""  # e.g. "GlueTradeBot" — exposed to UI for the t.me/ link

    # Service URLs (used by EmailDispatcher and recap generator)
    MAILING_SERVICE_URL: str = "http://gluetrade-mailing:8009"
    AUTH_SERVICE_URL: str = "http://gluetrade-auth:8001"
    PORTFOLIO_SERVICE_URL: str = "http://gluetrade-portfolio:8003"
    TRADING_SERVICE_URL: str = "http://gluetrade-trading:8004"
    ML_SERVICE_URL: str = "http://gluetrade-ml:8006"
    AI_AGENT_SERVICE_URL: str = "http://gluetrade-ai-agent:8008"
    MARKET_DATA_SERVICE_URL: str = "http://gluetrade-market-data:8002"

    FRONTEND_URL: str = "http://localhost:3000"

    # Internal service-to-service token (signed by auth-service) for fetching user lists
    INTERNAL_API_TOKEN: str = ""

    # Email dispatcher throttling (per user, per minute)
    EMAIL_THROTTLE_MAX_PER_MIN: int = 5

    # SMS throttling (per user, per minute)
    SMS_THROTTLE_MAX_PER_MIN: int = 5

    # Telegram throttling (per user, per minute)
    TELEGRAM_THROTTLE_MAX_PER_MIN: int = 10

    # Twilio credentials
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""  # E.164 sender number
    TWILIO_MESSAGING_SERVICE_SID: str = ""  # alternative to TWILIO_PHONE_NUMBER
    TWILIO_VERIFY_SERVICE_SID: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
