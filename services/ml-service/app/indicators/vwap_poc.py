"""Volume-Weighted Average Price (VWAP) + Point of Control (POC).

VWAP: fair value based on volume-weighted price. Price above VWAP = bullish.
POC: price level with highest traded volume. Acts as magnet / S&R level.

These provide volume-based support/resistance levels, much more reliable
than simple MA-based levels.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from app.core.models import Candle, IndicatorSnapshot

logger = logging.getLogger(__name__)


def calc_vwap(candles: list[Candle]) -> IndicatorSnapshot:
    """Compute VWAP from intraday candles.

    VWAP = cumulative(typical_price * volume) / cumulative(volume)
    Signal: price vs VWAP position.
    """
    if len(candles) < 5:
        return IndicatorSnapshot("VWAP", 0, 0, "Donnees insuffisantes", weight=0.5, category="volume")

    cum_tpv = 0.0
    cum_vol = 0.0

    for c in candles:
        typical_price = (c.high + c.low + c.close) / 3
        cum_tpv += typical_price * c.volume
        cum_vol += c.volume

    if cum_vol <= 0:
        return IndicatorSnapshot("VWAP", 0, 0, "Volume nul", weight=0.0, category="volume")

    vwap = cum_tpv / cum_vol
    current_price = candles[-1].close
    deviation_pct = (current_price - vwap) / vwap * 100 if vwap > 0 else 0

    if deviation_pct > 1.5:
        signal = -0.3
        desc = f"Prix au-dessus du VWAP ({deviation_pct:+.1f}%) — surachat potentiel"
    elif deviation_pct > 0.5:
        signal = 0.1
        desc = f"Prix legerement au-dessus du VWAP ({deviation_pct:+.1f}%) — biais haussier"
    elif deviation_pct < -1.5:
        signal = 0.3
        desc = f"Prix sous le VWAP ({deviation_pct:+.1f}%) — survente potentielle"
    elif deviation_pct < -0.5:
        signal = -0.1
        desc = f"Prix legerement sous le VWAP ({deviation_pct:+.1f}%) — biais baissier"
    else:
        signal = 0.0
        desc = f"Prix proche du VWAP ({deviation_pct:+.1f}%) — fair value"

    return IndicatorSnapshot(
        "VWAP", round(vwap, 4), round(signal, 3), desc, weight=0.5, category="volume",
    )


def calc_poc(candles: list[Candle], bins: int = 50) -> IndicatorSnapshot:
    """Compute Point of Control (POC) — price level with highest volume.

    Discretizes the price range into bins and finds the one with most volume.
    POC acts as a magnet: price tends to gravitate toward it.
    """
    if len(candles) < 10:
        return IndicatorSnapshot("POC", 0, 0, "Donnees insuffisantes", weight=0.4, category="volume")

    all_prices = [(c.high + c.low + c.close) / 3 for c in candles]
    price_min = min(all_prices)
    price_max = max(all_prices)
    price_range = price_max - price_min

    if price_range <= 0:
        return IndicatorSnapshot("POC", 0, 0, "Range de prix nul", weight=0.0, category="volume")

    bin_size = price_range / bins
    volume_at_price: defaultdict[int, float] = defaultdict(float)

    for c in candles:
        typical = (c.high + c.low + c.close) / 3
        bin_idx = min(int((typical - price_min) / bin_size), bins - 1)
        volume_at_price[bin_idx] += c.volume

    # Find bin with max volume
    poc_bin = max(volume_at_price, key=lambda k: volume_at_price[k])
    poc_price = price_min + (poc_bin + 0.5) * bin_size

    current_price = candles[-1].close
    distance_pct = (current_price - poc_price) / poc_price * 100 if poc_price > 0 else 0

    if abs(distance_pct) < 0.5:
        signal = 0.0
        desc = f"Prix au POC ({poc_price:.2f}) — zone de forte activite, equilibre"
    elif distance_pct > 2:
        signal = -0.2
        desc = f"Prix {distance_pct:.1f}% au-dessus du POC ({poc_price:.2f}) — risque de retour"
    elif distance_pct > 0.5:
        signal = 0.1
        desc = f"Prix legerement au-dessus du POC ({poc_price:.2f})"
    elif distance_pct < -2:
        signal = 0.2
        desc = f"Prix {abs(distance_pct):.1f}% sous le POC ({poc_price:.2f}) — potentiel rebond"
    else:
        signal = -0.1
        desc = f"Prix legerement sous le POC ({poc_price:.2f})"

    return IndicatorSnapshot(
        "POC", round(poc_price, 4), round(signal, 3), desc, weight=0.4, category="volume",
    )
