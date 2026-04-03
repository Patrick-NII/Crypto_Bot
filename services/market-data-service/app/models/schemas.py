"""Pydantic models for the Okamoey Market Data Service."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PriceData(BaseModel):
    """Full price data for a single asset."""

    symbol: str = Field(..., description="Asset symbol (e.g. BTC, ETH)")
    price: float = Field(..., description="Current price in USD")
    change_24h: float = Field(0.0, description="Absolute price change in 24h")
    change_pct_24h: float = Field(0.0, description="Percentage price change in 24h")
    volume_24h: float = Field(0.0, description="24h trading volume in USD")
    high_24h: float = Field(0.0, description="24h high price")
    low_24h: float = Field(0.0, description="24h low price")
    market_cap: float = Field(0.0, description="Market capitalization in USD")
    last_updated: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )


class PriceResponse(BaseModel):
    """Response for a single symbol price query."""

    success: bool = True
    data: PriceData


class MultiPriceResponse(BaseModel):
    """Response for multiple symbol price query."""

    success: bool = True
    data: dict[str, PriceData] = Field(
        default_factory=dict, description="Map of symbol -> PriceData"
    )


class OHLCVData(BaseModel):
    """Single OHLCV candlestick data point."""

    timestamp: int = Field(..., description="Unix timestamp in milliseconds")
    open: float
    high: float
    low: float
    close: float
    volume: float


class HistoryResponse(BaseModel):
    """Response for price history query."""

    success: bool = True
    symbol: str
    interval: str
    data: list[OHLCVData] = Field(default_factory=list)


class MarketOverview(BaseModel):
    """Market overview data for a coin."""

    symbol: str
    name: str
    price: float
    change_pct_24h: float = 0.0
    market_cap: float = 0.0
    volume_24h: float = 0.0
    rank: int = 0
    image_url: str = ""


class TopMarketsResponse(BaseModel):
    """Response for top markets query."""

    success: bool = True
    data: list[MarketOverview] = Field(default_factory=list)


class TrendingCoin(BaseModel):
    """Trending coin from CoinGecko."""

    symbol: str
    name: str
    market_cap_rank: int | None = None
    price_btc: float = 0.0
    score: int = 0


class TrendingResponse(BaseModel):
    """Response for trending coins query."""

    success: bool = True
    data: list[TrendingCoin] = Field(default_factory=list)


class FearGreedIndex(BaseModel):
    """Crypto Fear & Greed Index data."""

    value: int = Field(..., ge=0, le=100, description="Index value 0-100")
    classification: str = Field(
        ..., description="e.g. Extreme Fear, Fear, Neutral, Greed, Extreme Greed"
    )
    timestamp: datetime
    previous_close: int | None = None
    previous_classification: str | None = None


class FearGreedResponse(BaseModel):
    """Response for Fear & Greed Index query."""

    success: bool = True
    data: FearGreedIndex


class ExchangeInfo(BaseModel):
    """Exchange metadata."""

    id: str
    name: str
    url: str = ""
    has_ohlcv: bool = False
    has_ticker: bool = False


class ExchangesResponse(BaseModel):
    """Response for exchanges list query."""

    success: bool = True
    data: list[ExchangeInfo] = Field(default_factory=list)


class WebSocketMessage(BaseModel):
    """WebSocket message format."""

    type: str = Field(..., description="Message type: price_update, error, ping, pong")
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = False
    error: str
    detail: str | None = None
