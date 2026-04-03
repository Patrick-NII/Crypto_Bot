"""Configuration settings for the Okamoey Market Data Service."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_NAME: str = "Okamoey Market Data Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    # CoinGecko
    COINGECKO_API_KEY: str | None = None
    COINGECKO_BASE_URL: str = "https://api.coingecko.com/api/v3"

    # Binance (via CCXT)
    BINANCE_API_KEY: str | None = None
    BINANCE_API_SECRET: str | None = None

    # Price updates
    PRICE_UPDATE_INTERVAL_SECONDS: int = 30
    PRICE_CACHE_TTL_SECONDS: int = 30

    # Rate limiting
    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 1.0

    # Default symbols to track
    DEFAULT_SYMBOLS: list[str] = [
        "BTC", "ETH", "SOL", "BNB", "XRP",
        "ADA", "DOGE", "AVAX", "DOT", "MATIC",
        "LINK", "UNI", "ATOM", "LTC", "NEAR",
        "APT", "ARB", "OP", "FIL", "AAVE",
    ]

    # Redis channels
    REDIS_PRICE_CHANNEL: str = "price_updates"
    REDIS_PRICE_KEY_PREFIX: str = "market:price:"

    model_config = {"env_prefix": "MARKET_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
