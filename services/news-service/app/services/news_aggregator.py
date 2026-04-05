"""Aggregates news from RSS feeds (Cointelegraph, CoinDesk) and trending from CoinGecko."""

from __future__ import annotations

import hashlib
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---- RSS Sources (no API key required) ----

RSS_FEEDS = [
    {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss"},
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "Bitcoin Magazine", "url": "https://bitcoinmagazine.com/feed"},
]

SENTIMENT_KEYWORDS_POS = {"bullish", "surge", "rally", "breakout", "all-time high", "adoption",
                          "partnership", "approved", "upgrade", "gains", "soars", "milestone", "record"}
SENTIMENT_KEYWORDS_NEG = {"bearish", "crash", "dump", "hack", "scam", "ban", "lawsuit", "sec",
                          "fraud", "exploit", "plunge", "drops", "warning", "risk", "collapse"}


def _score_sentiment(title: str, body: str) -> float:
    text = (title + " " + body).lower()
    pos = sum(1 for kw in SENTIMENT_KEYWORDS_POS if kw in text)
    neg = sum(1 for kw in SENTIMENT_KEYWORDS_NEG if kw in text)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 2)


def _estimate_impact(sentiment: float, title: str) -> str:
    title_lower = title.lower()
    if abs(sentiment) > 0.6 or any(kw in title_lower for kw in ["sec", "regulation", "ban", "hack"]):
        return "high"
    if abs(sentiment) > 0.3 or any(kw in title_lower for kw in ["bitcoin", "ethereum", "btc", "eth"]):
        return "medium"
    return "low"


def _extract_categories(title: str) -> list[str]:
    """Extract crypto symbols and topics from title."""
    KNOWN = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "MATIC",
             "LINK", "UNI", "ATOM", "LTC", "NEAR", "APT", "ARB", "OP", "PEPE", "SHIB",
             "RENDER", "FET", "SUI", "TIA", "TON", "SEI", "ALGO"}
    words = title.upper().replace(",", " ").replace(".", " ").split()
    found = [w for w in words if w in KNOWN]

    # Also detect full names
    title_upper = title.upper()
    NAME_MAP = {"BITCOIN": "BTC", "ETHEREUM": "ETH", "SOLANA": "SOL", "RIPPLE": "XRP",
                "CARDANO": "ADA", "DOGECOIN": "DOGE", "POLKADOT": "DOT"}
    for name, sym in NAME_MAP.items():
        if name in title_upper and sym not in found:
            found.append(sym)

    return list(set(found)) if found else ["Crypto"]


def _parse_rss_date(date_str: str) -> str:
    """Parse RSS date string to ISO format."""
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


async def _fetch_single_rss(source_name: str, url: str, limit: int) -> list[dict[str, Any]]:
    """Fetch and parse a single RSS feed."""
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "OkamoeyBot/1.0"})
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        items = root.findall(".//item")
        articles = []

        for item in items[:limit]:
            title = (item.findtext("title") or "").strip()
            if not title:
                continue

            body = (item.findtext("description") or "")[:300].strip()
            # Strip HTML tags from body
            import re
            body = re.sub(r"<[^>]+>", "", body).strip()

            link = (item.findtext("link") or "").strip()
            pub_date = item.findtext("pubDate") or ""
            image = ""

            # Try to extract image from media:content or enclosure
            for child in item:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag in ("content", "thumbnail") and child.get("url"):
                    image = child.get("url", "")
                    break
                if tag == "enclosure" and child.get("type", "").startswith("image"):
                    image = child.get("url", "")
                    break

            sentiment = _score_sentiment(title, body)
            article_id = hashlib.md5(f"{source_name}:{title}".encode()).hexdigest()[:12]

            articles.append({
                "id": article_id,
                "title": title,
                "body": body,
                "source": source_name,
                "url": link,
                "image": image,
                "published_at": _parse_rss_date(pub_date),
                "categories": _extract_categories(title),
                "sentiment": sentiment,
                "impact": _estimate_impact(sentiment, title),
            })

        return articles

    except Exception as e:
        logger.error("RSS fetch failed for %s: %s", source_name, e)
        return []


async def fetch_news(limit: int = 20, symbol: str | None = None) -> list[dict[str, Any]]:
    """Fetch news from all RSS sources, merge and sort by date."""
    all_articles: list[dict[str, Any]] = []

    # Fetch all feeds in parallel
    import asyncio
    per_feed_limit = max(limit, 15)  # fetch more per feed to have enough after filtering
    tasks = [_fetch_single_rss(feed["name"], feed["url"], per_feed_limit) for feed in RSS_FEEDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, list):
            all_articles.extend(result)

    # Deduplicate by title similarity
    seen_titles: set[str] = set()
    unique: list[dict[str, Any]] = []
    for article in all_articles:
        key = article["title"][:40].lower()
        if key not in seen_titles:
            seen_titles.add(key)
            unique.append(article)

    # Filter by symbol if specified
    if symbol:
        sym_upper = symbol.upper()
        unique = [a for a in unique if sym_upper in a.get("title", "").upper() or sym_upper in a.get("categories", [])]

    # Sort by published date (newest first)
    unique.sort(key=lambda a: a.get("published_at", ""), reverse=True)

    return unique[:limit]


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
    """Aggregate market sentiment from Fear & Greed + news."""
    fg = {"value": 50, "label": "Neutral"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.alternative.me/fng/?limit=1&format=json")
            data = resp.json()
            entry = data.get("data", [{}])[0]
            fg = {"value": int(entry.get("value", 50)), "label": entry.get("value_classification", "Neutral")}
    except Exception:
        pass

    news = await fetch_news(limit=15)
    avg_sentiment = 0.0
    if news:
        avg_sentiment = round(sum(a["sentiment"] for a in news) / len(news), 2)

    return {
        "fear_greed": fg,
        "news_sentiment": avg_sentiment,
        "news_count": len(news),
        "overall": "bullish" if avg_sentiment > 0.15 else "bearish" if avg_sentiment < -0.15 else "neutral",
    }
