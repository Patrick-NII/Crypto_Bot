"""Aggregates news from CryptoCompare and trending from CoinGecko."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SENTIMENT_KEYWORDS_POS = {"bullish", "surge", "rally", "breakout", "all-time high", "adoption", "partnership", "approved", "upgrade"}
SENTIMENT_KEYWORDS_NEG = {"bearish", "crash", "dump", "hack", "scam", "ban", "lawsuit", "sec", "fraud", "exploit"}


def _score_sentiment(title: str, body: str) -> float:
    text = (title + " " + body).lower()
    pos = sum(1 for kw in SENTIMENT_KEYWORDS_POS if kw in text)
    neg = sum(1 for kw in SENTIMENT_KEYWORDS_NEG if kw in text)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 2)


def _estimate_impact(sentiment: float, categories: str) -> str:
    if abs(sentiment) > 0.6:
        return "high"
    if abs(sentiment) > 0.3 or "regulation" in categories.lower():
        return "medium"
    return "low"


async def fetch_news(limit: int = 20, symbol: str | None = None) -> list[dict[str, Any]]:
    """Fetch news from CryptoCompare."""
    url = f"{settings.CRYPTOCOMPARE_BASE}/news/"
    params: dict[str, str] = {"lang": "EN", "sortOrder": "latest"}
    if symbol:
        params["categories"] = symbol.upper()

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        articles = []
        for item in (data.get("Data") or [])[:limit]:
            title = item.get("title", "")
            body = item.get("body", "")[:300]
            categories = item.get("categories", "")
            sentiment = _score_sentiment(title, body)

            articles.append({
                "id": str(item.get("id", "")),
                "title": title,
                "body": body,
                "source": item.get("source_info", {}).get("name", item.get("source", "")),
                "url": item.get("url", ""),
                "image": item.get("imageurl", ""),
                "published_at": datetime.fromtimestamp(item.get("published_on", 0), tz=timezone.utc).isoformat(),
                "categories": [c.strip() for c in categories.split("|") if c.strip()],
                "sentiment": sentiment,
                "impact": _estimate_impact(sentiment, categories),
            })
        return articles

    except Exception as e:
        logger.error("CryptoCompare news fetch failed: %s", e)
        return []


async def fetch_trending() -> list[dict[str, Any]]:
    """Fetch trending coins from CoinGecko."""
    url = f"{settings.COINGECKO_BASE}/search/trending"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        coins = []
        for entry in data.get("coins", []):
            item = entry.get("item", {})
            coins.append({
                "symbol": (item.get("symbol") or "").upper(),
                "name": item.get("name", ""),
                "rank": item.get("market_cap_rank"),
                "thumb": item.get("thumb", ""),
                "score": item.get("score", 0),
                "price_btc": item.get("price_btc", 0),
            })
        return coins

    except Exception as e:
        logger.error("Trending fetch failed: %s", e)
        return []


async def fetch_market_sentiment() -> dict[str, Any]:
    """Aggregate market sentiment from Fear & Greed + news + trending."""
    # Fear & Greed
    fg = {"value": 50, "label": "Neutral"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.alternative.me/fng/?limit=1&format=json")
            data = resp.json()
            entry = data.get("data", [{}])[0]
            fg = {"value": int(entry.get("value", 50)), "label": entry.get("value_classification", "Neutral")}
    except Exception:
        pass

    # Recent news sentiment
    news = await fetch_news(limit=10)
    avg_sentiment = 0.0
    if news:
        avg_sentiment = round(sum(a["sentiment"] for a in news) / len(news), 2)

    return {
        "fear_greed": fg,
        "news_sentiment": avg_sentiment,
        "news_count": len(news),
        "overall": "bullish" if avg_sentiment > 0.15 else "bearish" if avg_sentiment < -0.15 else "neutral",
    }
