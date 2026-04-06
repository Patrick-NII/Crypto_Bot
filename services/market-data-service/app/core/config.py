"""Configuration settings for the GlueTrade Market Data Service."""

from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_NAME: str = "GlueTrade Market Data Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # CoinGecko
    COINGECKO_API_KEY: Optional[str] = None
    COINGECKO_BASE_URL: str = "https://api.coingecko.com/api/v3"

    # Binance (via CCXT)
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None

    # Price updates
    PRICE_UPDATE_INTERVAL_SECONDS: int = 10
    PRICE_CACHE_TTL_SECONDS: int = 10

    # Rate limiting
    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 1.0

    # Default symbols to track (top 50 by market cap)
    DEFAULT_SYMBOLS: List[str] = [
        "BTC", "ETH", "SOL", "BNB", "XRP",
        "ADA", "DOGE", "AVAX", "DOT", "MATIC",
        "LINK", "UNI", "ATOM", "LTC", "NEAR",
        "APT", "ARB", "OP", "FIL", "AAVE",
        "SHIB", "TRX", "TON", "SUI", "SEI",
        "PEPE", "WLD", "INJ", "TIA", "JUP",
        "ONDO", "RENDER", "FET", "STX", "IMX",
        "MKR", "GRT", "ALGO", "FTM", "SAND",
        "MANA", "AXS", "THETA", "EGLD", "FLOW",
        "XLM", "VET", "HBAR", "EOS", "CRO",
    ]

    # Redis channels
    REDIS_PRICE_CHANNEL: str = "price_updates"
    REDIS_PRICE_KEY_PREFIX: str = "market:price:"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
