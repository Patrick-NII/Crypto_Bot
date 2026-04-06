"""Funding rate indicator.

Fetches the current funding rate from Binance Futures.
Positive funding → longs pay shorts → market overleveraged long → bearish signal.
Negative funding → shorts pay longs → market overleveraged short → bullish signal.
Extreme funding rates often precede reversals.
"""

from __future__ import annotations

import logging

import httpx

from app.core.models import IndicatorSnapshot

logger = logging.getLogger(__name__)

_BINANCE_FUNDING_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"


async def fetch_funding_rate(symbol: str) -> IndicatorSnapshot:
    """Fetch current funding rate from Binance Futures.

    Typical range: -0.01% to +0.05% per 8h funding interval.
    Extreme: > 0.1% or < -0.05%
    """
    pair = symbol.replace("/", "").upper()
    if not pair.endswith("USDT"):
        pair = f"{pair}USDT"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(_BINANCE_FUNDING_URL, params={"symbol": pair})
            resp.raise_for_status()
            data = resp.json()

        rate = float(data.get("lastFundingRate", 0))
        rate_pct = rate * 100  # convert to percentage

        # Interpret: positive funding = bearish (longs overleveraged)
        if rate_pct > 0.08:
            signal = -0.5
            desc = f"Funding eleve ({rate_pct:+.4f}%) — longs surexposes, risque de squeeze baissier"
        elif rate_pct > 0.03:
            signal = -0.2
            desc = f"Funding positif ({rate_pct:+.4f}%) — leger biais vendeur"
        elif rate_pct < -0.03:
            signal = 0.3
            desc = f"Funding negatif ({rate_pct:+.4f}%) — shorts surexposes, potentiel squeeze haussier"
        elif rate_pct < -0.01:
            signal = 0.1
            desc = f"Funding legerement negatif ({rate_pct:+.4f}%)"
        else:
            signal = 0.0
            desc = f"Funding neutre ({rate_pct:+.4f}%)"

        return IndicatorSnapshot(
            "Funding Rate", round(rate_pct, 4), round(signal, 3), desc, weight=0.7, category="sentiment",
        )

    except Exception as exc:
        logger.debug("Funding rate fetch failed for %s: %s", symbol, exc)
        return IndicatorSnapshot("Funding Rate", 0, 0, "Funding rate indisponible", weight=0.0, category="sentiment")
