"""Multi-source price fetching service.

Priorities:
1. CCXT / Binance for lowest latency exchange data.
2. CoinGecko free API as fallback.

Results are cached in Redis with configurable TTL.
"""

import asyncio
import logging
from datetime import datetime, timezone

import ccxt.async_support as ccxt
import httpx

from app.core.config import settings
from app.core.redis_client import cache_get, cache_set
from app.models.schemas import OHLCVData, PriceData
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Mapping of common symbols to CoinGecko IDs
SYMBOL_TO_COINGECKO: Dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "LTC": "litecoin",
    "NEAR": "near",
    "APT": "aptos",
    "ARB": "arbitrum",
    "OP": "optimism",
    "FIL": "filecoin",
    "AAVE": "aave",
    "SHIB": "shiba-inu",
    "TRX": "tron",
    "TON": "the-open-network",
    "SUI": "sui",
    "SEI": "sei-network",
}

# Valid OHLCV intervals supported by most exchanges
VALID_INTERVALS = {
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
}


def _get_exchange() -> Optional[ccxt.Exchange]:
    """Create a CCXT Binance exchange instance if keys are available."""
    if settings.BINANCE_API_KEY and settings.BINANCE_API_SECRET:
        return ccxt.binance(
            {
                "apiKey": settings.BINANCE_API_KEY,
                "secret": settings.BINANCE_API_SECRET,
                "enableRateLimit": True,
            }
        )
    # Fall back to public (unauthenticated) Binance
    return ccxt.binance({"enableRateLimit": True})


async def _close_exchange(exchange: ccxt.Exchange) -> None:
    """Safely close an exchange connection."""
    try:
        await exchange.close()
    except Exception:
        pass


async def _fetch_via_ccxt(symbols: List[str]) -> Dict[str, PriceData]:
    """Fetch prices from Binance via CCXT.

    Args:
        symbols: List of asset symbols (e.g. ["BTC", "ETH"]).

    Returns:
        Dict mapping symbol -> PriceData for successfully fetched symbols.
    """
    exchange = _get_exchange()
    if exchange is None:
        return {}

    results: Dict[str, PriceData] = {}
    try:
        await exchange.load_markets()

        # Build CCXT trading pairs (symbol/USDT)
        pairs = {s: f"{s}/USDT" for s in symbols if f"{s}/USDT" in exchange.markets}

        if not pairs:
            return results

        # Fetch tickers in bulk when possible
        tickers = await exchange.fetch_tickers(list(pairs.values()))

        for symbol, pair in pairs.items():
            ticker = tickers.get(pair)
            if ticker is None:
                continue

            price = ticker.get("last") or ticker.get("close") or 0.0
            open_price = ticker.get("open", price)
            change_24h = (price - open_price) if open_price else 0.0
            change_pct = ((change_24h / open_price) * 100) if open_price else 0.0

            results[symbol] = PriceData(
                symbol=symbol,
                price=price,
                change_24h=round(change_24h, 8),
                change_pct_24h=round(change_pct, 4),
                volume_24h=ticker.get("quoteVolume", 0.0) or 0.0,
                high_24h=ticker.get("high", 0.0) or 0.0,
                low_24h=ticker.get("low", 0.0) or 0.0,
                market_cap=0.0,  # Not available from exchange ticker
                last_updated=datetime.now(timezone.utc),
            )

    except ccxt.RateLimitExceeded:
        logger.warning("CCXT rate limit hit, will retry on next cycle")
    except ccxt.NetworkError as exc:
        logger.warning("CCXT network error: %s", exc)
    except Exception:
        logger.exception("CCXT fetch failed")
    finally:
        await _close_exchange(exchange)

    return results


async def _fetch_via_coingecko(symbols: List[str]) -> Dict[str, PriceData]:
    """Fetch prices from the CoinGecko API.

    Args:
        symbols: List of asset symbols (e.g. ["BTC", "ETH"]).

    Returns:
        Dict mapping symbol -> PriceData for successfully fetched symbols.
    """
    # Map symbols to CoinGecko IDs
    id_to_symbol: Dict[str, str] = {}
    for s in symbols:
        cg_id = SYMBOL_TO_COINGECKO.get(s.upper())
        if cg_id:
            id_to_symbol[cg_id] = s.upper()

    if not id_to_symbol:
        return {}

    ids_param = ",".join(id_to_symbol.keys())
    url = f"{settings.COINGECKO_BASE_URL}/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": ids_param,
        "order": "market_cap_desc",
        "sparkline": "false",
        "price_change_percentage": "24h",
    }

    headers = {}
    if settings.COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = settings.COINGECKO_API_KEY

    results: Dict[str, PriceData] = {}

    retry_delay = settings.RETRY_BASE_DELAY
    for attempt in range(settings.MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params, headers=headers)

                if resp.status_code == 429:
                    logger.warning(
                        "CoinGecko rate limit (attempt %d/%d), backing off %.1fs",
                        attempt + 1,
                        settings.MAX_RETRIES,
                        retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue

                resp.raise_for_status()
                data = resp.json()

            for coin in data:
                cg_id = coin.get("id", "")
                symbol = id_to_symbol.get(cg_id)
                if symbol is None:
                    continue

                results[symbol] = PriceData(
                    symbol=symbol,
                    price=coin.get("current_price", 0.0) or 0.0,
                    change_24h=coin.get("price_change_24h", 0.0) or 0.0,
                    change_pct_24h=coin.get("price_change_percentage_24h", 0.0) or 0.0,
                    volume_24h=coin.get("total_volume", 0.0) or 0.0,
                    high_24h=coin.get("high_24h", 0.0) or 0.0,
                    low_24h=coin.get("low_24h", 0.0) or 0.0,
                    market_cap=coin.get("market_cap", 0.0) or 0.0,
                    last_updated=datetime.now(timezone.utc),
                )
            break  # Success

        except httpx.HTTPStatusError as exc:
            logger.warning("CoinGecko HTTP error: %s", exc)
            if attempt < settings.MAX_RETRIES - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
        except Exception:
            logger.exception("CoinGecko fetch failed (attempt %d)", attempt + 1)
            if attempt < settings.MAX_RETRIES - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2

    return results


async def fetch_prices(symbols: List[str]) -> Dict[str, PriceData]:
    """Fetch prices from the best available source.

    Strategy:
    1. Check Redis cache first.
    2. Try CCXT (Binance) for missing symbols.
    3. Fall back to CoinGecko for any still-missing symbols.
    4. Cache all results in Redis.

    Args:
        symbols: List of asset symbols (e.g. ["BTC", "ETH"]).

    Returns:
        Dict mapping symbol -> PriceData.
    """
    symbols = [s.upper() for s in symbols]
    results: Dict[str, PriceData] = {}
    uncached: List[str] = []

    # 1. Check Redis cache
    for s in symbols:
        cache_key = f"{settings.REDIS_PRICE_KEY_PREFIX}{s}"
        cached = await cache_get(cache_key)
        if cached is not None:
            try:
                results[s] = PriceData(**cached)
            except Exception:
                uncached.append(s)
        else:
            uncached.append(s)

    if not uncached:
        return results

    # 2. Try CCXT / Binance
    ccxt_data = await _fetch_via_ccxt(uncached)
    results.update(ccxt_data)
    still_missing = [s for s in uncached if s not in ccxt_data]

    # 3. Fall back to CoinGecko for remaining symbols
    if still_missing:
        cg_data = await _fetch_via_coingecko(still_missing)
        results.update(cg_data)

    # 4. Cache fetched results in Redis
    for symbol, price_data in results.items():
        if symbol in uncached:  # Only cache newly fetched
            cache_key = f"{settings.REDIS_PRICE_KEY_PREFIX}{symbol}"
            await cache_set(
                cache_key,
                price_data.model_dump(mode="json"),
                ttl=settings.PRICE_CACHE_TTL_SECONDS,
            )

    return results


async def fetch_ohlcv(
    symbol: str, interval: str = "1h", limit: int = 100
) -> List[OHLCVData]:
    """Fetch OHLCV candlestick data via CCXT.

    Args:
        symbol: Asset symbol (e.g. "BTC").
        interval: Candlestick interval (e.g. "1h", "1d").
        limit: Max number of candles.

    Returns:
        List of OHLCVData points.
    """
    if interval not in VALID_INTERVALS:
        interval = "1h"
    limit = min(limit, 1000)

    exchange = _get_exchange()
    if exchange is None:
        return []

    pair = f"{symbol.upper()}/USDT"
    candles: List[OHLCVData] = []

    try:
        await exchange.load_markets()
        if pair not in exchange.markets:
            return []

        raw = await exchange.fetch_ohlcv(pair, timeframe=interval, limit=limit)
        for entry in raw:
            candles.append(
                OHLCVData(
                    timestamp=entry[0],
                    open=entry[1],
                    high=entry[2],
                    low=entry[3],
                    close=entry[4],
                    volume=entry[5],
                )
            )
    except ccxt.RateLimitExceeded:
        logger.warning("CCXT rate limit hit during OHLCV fetch")
    except Exception:
        logger.exception("OHLCV fetch failed for %s", pair)
    finally:
        await _close_exchange(exchange)

    return candles


async def fetch_top_markets(limit: int = 20) -> List[dict]:
    """Fetch top cryptocurrencies by market cap from CoinGecko.

    Returns:
        List of market overview dicts.
    """
    cache_key = f"{settings.REDIS_PRICE_KEY_PREFIX}top_markets"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{settings.COINGECKO_BASE_URL}/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": str(limit),
        "page": "1",
        "sparkline": "false",
    }

    headers = {}
    if settings.COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = settings.COINGECKO_API_KEY

    retry_delay = settings.RETRY_BASE_DELAY
    for attempt in range(settings.MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 429:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                resp.raise_for_status()
                data = resp.json()

            markets = []
            for coin in data:
                markets.append(
                    {
                        "symbol": (coin.get("symbol") or "").upper(),
                        "name": coin.get("name", ""),
                        "price": coin.get("current_price", 0.0) or 0.0,
                        "change_pct_24h": coin.get("price_change_percentage_24h", 0.0) or 0.0,
                        "market_cap": coin.get("market_cap", 0.0) or 0.0,
                        "volume_24h": coin.get("total_volume", 0.0) or 0.0,
                        "rank": coin.get("market_cap_rank", 0) or 0,
                        "image_url": coin.get("image", ""),
                    }
                )

            await cache_set(cache_key, markets, ttl=60)
            return markets

        except Exception:
            logger.exception("Top markets fetch failed (attempt %d)", attempt + 1)
            if attempt < settings.MAX_RETRIES - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2

    return []


async def fetch_trending() -> List[dict]:
    """Fetch trending coins from CoinGecko.

    Returns:
        List of trending coin dicts.
    """
    cache_key = f"{settings.REDIS_PRICE_KEY_PREFIX}trending"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{settings.COINGECKO_BASE_URL}/search/trending"
    headers = {}
    if settings.COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = settings.COINGECKO_API_KEY

    retry_delay = settings.RETRY_BASE_DELAY
    for attempt in range(settings.MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 429:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                resp.raise_for_status()
                data = resp.json()

            coins = data.get("coins", [])
            trending = []
            for entry in coins:
                item = entry.get("item", {})
                trending.append(
                    {
                        "symbol": (item.get("symbol") or "").upper(),
                        "name": item.get("name", ""),
                        "market_cap_rank": item.get("market_cap_rank"),
                        "price_btc": item.get("price_btc", 0.0) or 0.0,
                        "score": item.get("score", 0),
                    }
                )

            await cache_set(cache_key, trending, ttl=300)
            return trending

        except Exception:
            logger.exception("Trending fetch failed (attempt %d)", attempt + 1)
            if attempt < settings.MAX_RETRIES - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2

    return []


async def fetch_fear_greed() -> Optional[dict]:
    """Fetch the Crypto Fear & Greed Index from alternative.me.

    Returns:
        FearGreedIndex dict or None on failure.
    """
    cache_key = f"{settings.REDIS_PRICE_KEY_PREFIX}fear_greed"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    url = "https://api.alternative.me/fng/"
    params = {"limit": "2", "format": "json"}

    retry_delay = settings.RETRY_BASE_DELAY
    for attempt in range(settings.MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 429:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                resp.raise_for_status()
                data = resp.json()

            entries = data.get("data", [])
            if not entries:
                return None

            current = entries[0]
            previous = entries[1] if len(entries) > 1 else None

            result = {
                "value": int(current.get("value", 0)),
                "classification": current.get("value_classification", "Unknown"),
                "timestamp": datetime.fromtimestamp(
                    int(current.get("timestamp", 0)), tz=timezone.utc
                ).isoformat(),
                "previous_close": int(previous["value"]) if previous else None,
                "previous_classification": (
                    previous.get("value_classification") if previous else None
                ),
            }

            await cache_set(cache_key, result, ttl=600)
            return result

        except Exception:
            logger.exception("Fear & Greed fetch failed (attempt %d)", attempt + 1)
            if attempt < settings.MAX_RETRIES - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2

    return None
