"""Price API router - /api/v1/prices

Endpoints:
- GET /              Get prices for multiple symbols
- GET /search        Search crypto assets by name or symbol
- GET /{symbol}      Get single symbol price with full data
- GET /history/{symbol}  Get OHLCV price history
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    AssetSearchResult,
    ErrorResponse,
    HistoryResponse,
    MultiPriceResponse,
    OHLCVData,
    PriceData,
    PriceResponse,
    SearchResponse,
)
from app.services.price_fetcher import fetch_ohlcv, fetch_prices, search_assets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/prices", tags=["prices"])


@router.get(
    "/",
    response_model=MultiPriceResponse,
    summary="Get prices for multiple symbols",
    responses={400: {"model": ErrorResponse}},
)
async def get_prices(
    symbols: str = Query(
        "BTC,ETH,SOL",
        description="Comma-separated list of symbols (e.g. BTC,ETH,SOL)",
    ),
) -> MultiPriceResponse:
    """Fetch current prices for the requested symbols.

    Returns cached data when available (30s TTL), otherwise fetches fresh data
    from Binance (CCXT) with CoinGecko fallback.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    if not symbol_list:
        raise HTTPException(status_code=400, detail="No valid symbols provided")

    if len(symbol_list) > 50:
        raise HTTPException(
            status_code=400, detail="Maximum 50 symbols per request"
        )

    prices = await fetch_prices(symbol_list)
    return MultiPriceResponse(success=True, data=prices)


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search crypto assets by name or symbol",
)
async def search_crypto_assets(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, le=100, description="Maximum results to return"),
) -> SearchResponse:
    """Search crypto assets by name or symbol.

    Uses CoinGecko /search endpoint with Redis cache (5 min).
    Returns list of matching assets with id, symbol, name, market_cap_rank, thumb.
    """
    raw = await search_assets(q, limit=limit)
    results = [AssetSearchResult(**item) for item in raw]
    return SearchResponse(
        success=True,
        query=q,
        results=results,
        total=len(results),
    )


@router.get(
    "/history/{symbol}",
    response_model=HistoryResponse,
    summary="Get OHLCV price history",
    responses={404: {"model": ErrorResponse}},
)
async def get_price_history(
    symbol: str,
    interval: str = Query("1h", description="Candlestick interval (e.g. 1m, 5m, 1h, 1d)"),
    limit: int = Query(100, ge=1, le=1000, description="Number of candles"),
) -> HistoryResponse:
    """Fetch OHLCV candlestick data from the exchange via CCXT.

    Supported intervals: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
    """
    candles = await fetch_ohlcv(symbol.upper(), interval=interval, limit=limit)

    if not candles:
        raise HTTPException(
            status_code=404,
            detail=f"No OHLCV data found for {symbol.upper()}/USDT with interval {interval}",
        )

    return HistoryResponse(
        success=True,
        symbol=symbol.upper(),
        interval=interval,
        data=candles,
    )


@router.get(
    "/{symbol}",
    response_model=PriceResponse,
    summary="Get single symbol price",
    responses={404: {"model": ErrorResponse}},
)
async def get_single_price(symbol: str) -> PriceResponse:
    """Fetch current price and full market data for a single symbol."""
    prices = await fetch_prices([symbol.upper()])

    if symbol.upper() not in prices:
        raise HTTPException(
            status_code=404,
            detail=f"Price data not found for {symbol.upper()}",
        )

    return PriceResponse(success=True, data=prices[symbol.upper()])
