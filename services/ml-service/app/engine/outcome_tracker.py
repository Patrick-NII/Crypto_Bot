"""Outcome Tracker — background job that fills price_after_15m/1h/4h in signal logs.

Run periodically (every 5 min) to check old signals and record actual outcomes.
Also computes win/loss based on direction vs price movement.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_CHECK_INTERVALS = [
    ("price_after_15m", timedelta(minutes=15)),
    ("price_after_1h", timedelta(hours=1)),
    ("price_after_4h", timedelta(hours=4)),
]


async def _fetch_current_price(symbol: str) -> float:
    """Fetch latest price from market-data-service."""
    url = f"{settings.MARKET_DATA_SERVICE_URL}/api/v1/prices/{symbol}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("data", {}).get("price", 0) or data.get("price", 0) or 0)
    except Exception:
        return 0.0


def _determine_outcome(direction: int, price_at: float, price_after: float) -> str:
    """Determine win/loss/neutral based on direction prediction vs actual move."""
    if price_at <= 0 or price_after <= 0:
        return "unknown"

    pct_move = (price_after - price_at) / price_at * 100
    bullish_prediction = direction >= 55
    bearish_prediction = direction <= 45

    # Win = predicted direction matches actual move (> 0.1% threshold)
    if bullish_prediction and pct_move > 0.1:
        return "win"
    if bearish_prediction and pct_move < -0.1:
        return "win"
    if abs(pct_move) < 0.1:
        return "neutral"
    return "loss"


async def update_signal_outcomes(redis_client: Any) -> dict:
    """Scan recent signal logs and fill price outcomes where due.

    Returns stats: {checked, updated, errors}
    """
    if redis_client is None:
        return {"checked": 0, "updated": 0, "errors": 0}

    stats = {"checked": 0, "updated": 0, "errors": 0}
    now = datetime.now(timezone.utc)

    try:
        keys = []
        async for key in redis_client.scan_iter(match="signal_log:*", count=500):
            keys.append(key)
    except Exception as exc:
        logger.warning("Failed to scan signal logs: %s", exc)
        return stats

    for key in keys:
        stats["checked"] += 1
        try:
            raw = await redis_client.get(key)
            if not raw:
                continue

            entry = json.loads(raw)
            ts_str = entry.get("timestamp")
            if not ts_str:
                continue

            signal_time = datetime.fromisoformat(ts_str)
            age = now - signal_time
            price_at = float(entry.get("price_at_signal", 0) or 0)
            symbol = entry.get("symbol", "")
            updated = False

            if price_at <= 0 or not symbol:
                continue

            # Check each interval
            for field, interval in _CHECK_INTERVALS:
                if entry.get(field) is not None:
                    continue  # already filled
                if age < interval:
                    continue  # not yet due

                # Fetch current price (approximation — ideally we'd use historical)
                current_price = await _fetch_current_price(symbol)
                if current_price > 0:
                    entry[field] = current_price
                    updated = True

            # Determine outcome using 1h price (primary timeframe)
            if entry.get("outcome") is None and entry.get("price_after_1h") is not None:
                direction = int(entry.get("direction", 50))
                entry["outcome"] = _determine_outcome(direction, price_at, entry["price_after_1h"])
                updated = True

            if updated:
                ttl = await redis_client.ttl(key)
                if ttl > 0:
                    await redis_client.setex(key, ttl, json.dumps(entry))
                    stats["updated"] += 1

        except Exception as exc:
            stats["errors"] += 1
            logger.debug("Error processing signal log %s: %s", key, exc)

    if stats["updated"] > 0:
        logger.info("Signal outcomes updated: %s", stats)

    return stats
