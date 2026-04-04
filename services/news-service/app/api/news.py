"""News API endpoints."""

from fastapi import APIRouter, Query

from app.services.news_aggregator import fetch_news, fetch_trending, fetch_market_sentiment

router = APIRouter(prefix="/api/v1/news", tags=["news"])


@router.get("/feed")
async def get_news_feed(limit: int = Query(20, le=50), symbol: str | None = None):
    return await fetch_news(limit=limit, symbol=symbol)


@router.get("/feed/{symbol}")
async def get_news_by_symbol(symbol: str, limit: int = Query(20, le=50)):
    return await fetch_news(limit=limit, symbol=symbol)


@router.get("/trending")
async def get_trending():
    return await fetch_trending()


@router.get("/sentiment")
async def get_sentiment():
    return await fetch_market_sentiment()
