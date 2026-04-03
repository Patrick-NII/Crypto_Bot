"""Background task that periodically fetches and broadcasts price updates.

Runs on a configurable interval (default 30s):
1. Fetches prices for default symbols via price_fetcher.
2. Stores results in Redis.
3. Publishes updates to the Redis pub/sub channel.
4. Broadcasts to all connected WebSocket clients.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.redis_client import publish_message
from app.services.price_fetcher import fetch_prices
from app.services.websocket_manager import manager
from typing import Optional

logger = logging.getLogger(__name__)

_running = False
_task: Optional[asyncio.Task] = None


async def _update_loop() -> None:
    """Main update loop. Runs until cancelled."""
    global _running
    _running = True
    logger.info(
        "Price updater started (interval=%ds, symbols=%d)",
        settings.PRICE_UPDATE_INTERVAL_SECONDS,
        len(settings.DEFAULT_SYMBOLS),
    )

    while _running:
        try:
            # Fetch latest prices (caching is handled inside fetch_prices)
            prices = await fetch_prices(settings.DEFAULT_SYMBOLS)

            if prices:
                # Serialize for broadcast / pub-sub
                serialized = {
                    symbol: pd.model_dump(mode="json")
                    for symbol, pd in prices.items()
                }

                # Publish to Redis channel for other services
                await publish_message(settings.REDIS_PRICE_CHANNEL, serialized)

                # Broadcast to WebSocket clients
                await manager.broadcast_price_update(serialized)

                logger.debug(
                    "Price update completed: %d symbols, %d WS clients",
                    len(prices),
                    manager.active_count,
                )
            else:
                logger.warning("Price update returned no data")

        except asyncio.CancelledError:
            logger.info("Price updater cancelled")
            break
        except Exception:
            logger.exception("Price update cycle failed")

        # Wait for the next interval
        try:
            await asyncio.sleep(settings.PRICE_UPDATE_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("Price updater sleep cancelled")
            break

    _running = False
    logger.info("Price updater stopped")


def start_updater() -> asyncio.Task:
    """Start the background price update loop.

    Returns:
        The asyncio Task running the update loop.
    """
    global _task
    if _task is not None and not _task.done():
        logger.warning("Price updater is already running")
        return _task

    _task = asyncio.create_task(_update_loop())
    return _task


async def stop_updater() -> None:
    """Stop the background price update loop gracefully."""
    global _running, _task
    _running = False

    if _task is not None and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
        logger.info("Price updater task cleaned up")


def is_running() -> bool:
    """Check whether the price updater is currently running."""
    return _running
