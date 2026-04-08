"""Outcome backfill — periodic job that fills ``max_drawdown_during_hold``.

For every closed trade_group with a missing ``max_drawdown_during_hold``, fetch
OHLCV between entry_time and exit_time from market-data-service, compute the
worst drawdown vs the entry price, and persist it.

Runs every 15 minutes via an asyncio background task started in ``main.py``.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.repositories.auto_repository import auto_repository

logger = logging.getLogger(__name__)

_INTERVAL_SECONDS = 15 * 60


async def _fetch_candles(
    client: httpx.AsyncClient,
    symbol: str,
    from_iso: str,
    to_iso: str,
) -> List[Dict[str, Any]]:
    """Fetch 1m OHLC between two timestamps from market-data-service."""
    try:
        resp = await client.get(
            f"{settings.MARKET_DATA_URL}/api/v1/prices/history/{symbol}",
            params={"interval": "1m", "from": from_iso, "to": to_iso},
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("candles") or data.get("data") or []
    except Exception as exc:
        logger.debug("Candles fetch failed for %s: %s", symbol, exc)
    return []


def _compute_max_drawdown(
    entry_price: Decimal,
    side: str,
    candles: List[Dict[str, Any]],
) -> Optional[Decimal]:
    if not candles or entry_price <= 0:
        return None
    worst = Decimal("0")
    for c in candles:
        low = c.get("low") or c.get("l")
        high = c.get("high") or c.get("h")
        try:
            low_d = Decimal(str(low)) if low is not None else entry_price
            high_d = Decimal(str(high)) if high is not None else entry_price
        except Exception:
            continue
        if side == "buy":
            # For long positions, worst drawdown is the lowest low
            move = (low_d - entry_price) / entry_price * Decimal("100")
            if move < worst:
                worst = move
        else:
            # For short positions (not really supported in spot), use the highest
            move = (entry_price - high_d) / entry_price * Decimal("100")
            if move < worst:
                worst = move
    return worst


async def backfill_once() -> int:
    """Backfill every eligible closed trade group. Returns how many were updated."""
    groups = await auto_repository.groups_needing_backfill(limit=50)
    if not groups:
        return 0
    updated = 0
    async with httpx.AsyncClient(timeout=10.0) as client:
        for group in groups:
            if group.entry_time is None or group.exit_time is None:
                continue
            candles = await _fetch_candles(
                client,
                group.symbol,
                group.entry_time.isoformat(),
                group.exit_time.isoformat(),
            )
            if not candles:
                continue
            drawdown = _compute_max_drawdown(
                Decimal(str(group.entry_price or 0)),
                group.side,
                candles,
            )
            if drawdown is None:
                continue
            await auto_repository.update_trade_group(
                group.id,
                {"max_drawdown_during_hold": drawdown},
            )
            updated += 1
    if updated:
        logger.info("Outcome backfill updated %d trade group(s)", updated)
    return updated


async def backfill_loop() -> None:
    """Background task: run backfill every 15 min until cancelled."""
    while True:
        try:
            await backfill_once()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("backfill_loop error: %s", exc)
        try:
            await asyncio.sleep(_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            return
