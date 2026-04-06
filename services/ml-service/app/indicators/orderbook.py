"""Orderbook imbalance indicator.

Measures bid/ask pressure from Binance orderbook depth.
High bid imbalance → bullish pressure (more buyers).
High ask imbalance → bearish pressure (more sellers).
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.core.models import IndicatorSnapshot

logger = logging.getLogger(__name__)

_BINANCE_DEPTH_URL = "https://api.binance.com/api/v3/depth"


async def fetch_orderbook_imbalance(
    symbol: str,
    depth: int = 20,
) -> IndicatorSnapshot:
    """Fetch orderbook and compute bid/ask imbalance.

    Imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)
    Range: -1 (all sellers) to +1 (all buyers)
    """
    pair = symbol.replace("/", "").upper()
    if not pair.endswith("USDT") and not pair.endswith("EUR"):
        pair = f"{pair}USDT"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(_BINANCE_DEPTH_URL, params={"symbol": pair, "limit": depth})
            resp.raise_for_status()
            data = resp.json()

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        bid_vol = sum(float(b[1]) for b in bids)
        ask_vol = sum(float(a[1]) for a in asks)
        total = bid_vol + ask_vol

        if total <= 0:
            return IndicatorSnapshot("Orderbook", 0, 0, "Carnet d'ordres vide", weight=0.8, category="volume")

        imbalance = (bid_vol - ask_vol) / total  # -1 to +1

        if imbalance > 0.3:
            signal = min(imbalance * 0.8, 0.7)
            desc = f"Pression acheteuse forte ({imbalance:+.2f}) — bids dominent"
        elif imbalance > 0.1:
            signal = imbalance * 0.5
            desc = f"Leger biais acheteur ({imbalance:+.2f})"
        elif imbalance < -0.3:
            signal = max(imbalance * 0.8, -0.7)
            desc = f"Pression vendeuse forte ({imbalance:+.2f}) — asks dominent"
        elif imbalance < -0.1:
            signal = imbalance * 0.5
            desc = f"Leger biais vendeur ({imbalance:+.2f})"
        else:
            signal = 0.0
            desc = f"Carnet equilibre ({imbalance:+.2f})"

        return IndicatorSnapshot(
            "Orderbook", round(imbalance, 3), round(signal, 3), desc, weight=0.8, category="volume",
        )

    except Exception as exc:
        logger.debug("Orderbook fetch failed for %s: %s", symbol, exc)
        return IndicatorSnapshot("Orderbook", 0, 0, "Orderbook indisponible", weight=0.0, category="volume")
