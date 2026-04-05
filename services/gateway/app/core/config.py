from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Service URLs
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    PORTFOLIO_SERVICE_URL: str = "http://localhost:8002"
    MARKET_DATA_SERVICE_URL: str = "http://localhost:8003"
    TRADING_ENGINE_URL: str = "http://localhost:8004"
    RISK_SERVICE_URL: str = "http://localhost:8005"
    ML_SERVICE_URL: str = "http://localhost:8006"
    NOTIFICATION_SERVICE_URL: str = "http://localhost:8007"
    NEWS_SERVICE_URL: str = "http://localhost:8011"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Auth
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"

    # Rate limiting (300/min to handle sparklines burst on page load)
    RATE_LIMIT_PER_MINUTE: int = 300

    # Proxy
    PROXY_TIMEOUT: float = 15.0

    model_config = {"case_sensitive": True}


settings = Settings()
