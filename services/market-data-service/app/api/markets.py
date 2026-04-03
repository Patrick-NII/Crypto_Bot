"""Market API router - /api/v1/markets

Endpoints:
- GET /top         Top cryptocurrencies by market cap
- GET /trending    Trending coins (CoinGecko)
- GET /fear-greed  Crypto Fear & Greed Index
- GET /exchanges   List supported exchanges
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    ErrorResponse,
    ExchangeInfo,
    ExchangesResponse,
    FearGreedIndex,
    FearGreedResponse,
    MarketOverview,
    TopMarketsResponse,
    TrendingCoin,
    TrendingResponse,
)
from app.services.price_fetcher import fetch_fear_greed, fetch_top_markets, fetch_trending

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/markets", tags=["markets"])

# Supported exchanges and their metadata
SUPPORTED_EXCHANGES = [
    ExchangeInfo(
        id="binance",
        name="Binance",
        url="https://www.binance.com",
        has_ohlcv=True,
        has_ticker=True,
    ),
    ExchangeInfo(
        id="coinbase",
        name="Coinbase",
        url="https://www.coinbase.com",
        has_ohlcv=True,
        has_ticker=True,
    ),
    ExchangeInfo(
        id="kraken",
        name="Kraken",
        url="https://www.kraken.com",
        has_ohlcv=True,
        has_ticker=True,
    ),
    ExchangeInfo(
        id="bybit",
        name="Bybit",
        url="https://www.bybit.com",
        has_ohlcv=True,
        has_ticker=True,
    ),
    ExchangeInfo(
        id="okx",
        name="OKX",
        url="https://www.okx.com",
        has_ohlcv=True,
        has_ticker=True,
    ),
    ExchangeInfo(
        id="kucoin",
        name="KuCoin",
        url="https://www.kucoin.com",
        has_ohlcv=True,
        has_ticker=True,
    ),
]


@router.get(
    "/top",
    response_model=TopMarketsResponse,
    summary="Top cryptocurrencies by market cap",
)
async def get_top_markets(
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
) -> TopMarketsResponse:
    """Fetch the top cryptocurrencies ranked by market capitalization.

    Data sourced from CoinGecko with 60s cache.
    """
    raw = await fetch_top_markets(limit=limit)

    markets = [MarketOverview(**m) for m in raw]
    return TopMarketsResponse(success=True, data=markets)


@router.get(
    "/trending",
    response_model=TrendingResponse,
    summary="Trending coins",
)
async def get_trending() -> TrendingResponse:
    """Fetch currently trending cryptocurrencies from CoinGecko.

    Results are cached for 5 minutes.
    """
    raw = await fetch_trending()

    coins = [TrendingCoin(**c) for c in raw]
    return TrendingResponse(success=True, data=coins)


@router.get(
    "/fear-greed",
    response_model=FearGreedResponse,
    summary="Crypto Fear & Greed Index",
    responses={503: {"model": ErrorResponse}},
)
async def get_fear_greed() -> FearGreedResponse:
    """Fetch the Crypto Fear & Greed Index from alternative.me.

    Values range from 0 (Extreme Fear) to 100 (Extreme Greed).
    Cached for 10 minutes.
    """
    data = await fetch_fear_greed()

    if data is None:
        raise HTTPException(
            status_code=503,
            detail="Fear & Greed Index is temporarily unavailable",
        )

    return FearGreedResponse(success=True, data=FearGreedIndex(**data))


@router.get(
    "/exchanges",
    response_model=ExchangesResponse,
    summary="List supported exchanges",
)
async def get_exchanges() -> ExchangesResponse:
    """List all exchanges supported by the Okamoey market data service."""
    return ExchangesResponse(success=True, data=SUPPORTED_EXCHANGES)
