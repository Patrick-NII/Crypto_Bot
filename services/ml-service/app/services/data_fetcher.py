"""Data fetcher — OHLCV retrieval from market-data-service with CoinGecko fallback.

Extracted from api/ml.py _fetch_market_history / _fetch_top_symbols.
Adds fetch_multi_timeframe() for parallel multi-TF fetching.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.core.config import settings
from app.core.models import Candle

logger = logging.getLogger(__name__)

CG_BASE = "https://api.coingecko.com/api/v3"

SYM_TO_CG = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
    "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin", "AVAX": "avalanche-2",
    "DOT": "polkadot", "LINK": "chainlink", "UNI": "uniswap", "ATOM": "cosmos",
    "LTC": "litecoin", "NEAR": "near", "APT": "aptos", "ARB": "arbitrum",
    "OP": "optimism", "FIL": "filecoin", "AAVE": "aave", "SHIB": "shiba-inu",
    "MATIC": "matic-network", "TRX": "tron", "TON": "the-open-network",
    "SUI": "sui", "SEI": "sei-network", "PEPE": "pepe", "ALGO": "algorand",
    "FTM": "fantom", "XLM": "stellar", "HBAR": "hedera-hashgraph",
}


async def fetch_candles(
    symbol: str,
    interval: str = "1h",
    limit: int = 120,
) -> tuple[list[Candle], str]:
    """Fetch OHLCV candles. Returns (candles, source)."""
    candles, source = await _fetch_from_market_service(symbol, interval, limit)
    if candles:
        return candles, source

    candles, source = await _fetch_from_coingecko(symbol, limit)
    return candles, source


async def fetch_closes_and_volumes(
    symbol: str,
    interval: str = "1h",
    limit: int = 120,
) -> tuple[list[float], list[float], str]:
    """Convenience: returns (closes, volumes, source)."""
    candles, source = await fetch_candles(symbol, interval, limit)
    closes = [c.close for c in candles]
    volumes = [c.volume for c in candles]
    return closes, volumes, source


async def fetch_multi_timeframe(
    symbol: str,
    timeframes: dict[str, int],
) -> dict[str, list[Candle]]:
    """Fetch candles for multiple timeframes in parallel.

    Args:
        timeframes: {"1m": 120, "5m": 60, "15m": 48}

    Returns:
        {"1m": [Candle, ...], "5m": [...], ...}
    """
    async def _fetch_one(tf: str, lim: int) -> tuple[str, list[Candle]]:
        candles, _ = await fetch_candles(symbol, tf, lim)
        return tf, candles

    tasks = [_fetch_one(tf, lim) for tf, lim in timeframes.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    out: dict[str, list[Candle]] = {}
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Multi-TF fetch error: %s", result)
            continue
        tf, candles = result
        out[tf] = candles
    return out


async def fetch_top_symbols(limit: int = 10) -> list[str]:
    """Fetch top symbols by market cap from market-data-service."""
    url = f"{settings.MARKET_DATA_SERVICE_URL}/api/v1/markets/top"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"limit": limit})
            resp.raise_for_status()
            payload = resp.json()
            rows = payload.get("data", payload)
            symbols = [str(row.get("symbol", "")).upper() for row in rows if row.get("symbol")]
            if symbols:
                return symbols[:limit]
    except Exception:
        pass
    return list(SYM_TO_CG.keys())[:limit]


# ── Internal helpers ──

async def _fetch_from_market_service(
    symbol: str, interval: str, limit: int,
) -> tuple[list[Candle], str]:
    url = f"{settings.MARKET_DATA_SERVICE_URL}/api/v1/prices/history/{symbol.upper()}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params={"interval": interval, "limit": limit})
            resp.raise_for_status()
            payload = resp.json()
            raw_candles = payload.get("data", payload)
            candles = [
                Candle(
                    time=int(c.get("time", c.get("timestamp", 0))),
                    open=float(c.get("open", 0)),
                    high=float(c.get("high", 0)),
                    low=float(c.get("low", 0)),
                    close=float(c.get("close", 0)),
                    volume=float(c.get("volume", 0)),
                )
                for c in raw_candles
                if c.get("close") is not None
            ]
            if candles:
                return candles, "market-data-service"
    except Exception:
        pass
    return [], "unavailable"


async def _fetch_from_coingecko(symbol: str, limit: int) -> tuple[list[Candle], str]:
    cg_id = SYM_TO_CG.get(symbol.upper())
    if not cg_id:
        return [], "unavailable"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{CG_BASE}/coins/{cg_id}/market_chart",
                params={"vs_currency": "usd", "days": "30", "interval": "hourly"},
            )
            if resp.status_code == 200:
                payload = resp.json()
                prices = payload.get("prices", [])
                volumes = payload.get("total_volumes", [])
                candles = []
                for i, price_row in enumerate(prices[-limit:]):
                    vol = volumes[len(volumes) - limit + i][1] if i < len(volumes) else 0
                    p = float(price_row[1])
                    candles.append(Candle(
                        time=int(price_row[0] / 1000),
                        open=p, high=p, low=p, close=p,
                        volume=float(vol),
                    ))
                return candles, "coingecko"
    except Exception:
        pass
    return [], "unavailable"
