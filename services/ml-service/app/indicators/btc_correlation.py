"""BTC Correlation indicator.

Measures how strongly an altcoin follows BTC price movements.
High correlation + BTC dumping → altcoin will likely dump too.
Low correlation → altcoin moves independently (rare, useful for diversification).

Uses rolling 20-period Pearson correlation on returns.
"""

from __future__ import annotations

import logging
import math

from app.core.models import IndicatorSnapshot

logger = logging.getLogger(__name__)


def calc_btc_correlation(
    closes: list[float],
    btc_closes: list[float],
    period: int = 20,
) -> IndicatorSnapshot:
    """Compute rolling Pearson correlation between asset returns and BTC returns.

    Returns:
        IndicatorSnapshot with value = correlation (-1 to +1)
        Signal interpretation depends on BTC direction:
        - High corr + BTC falling → bearish signal for altcoin
        - High corr + BTC rising → bullish signal for altcoin
        - Low corr → neutral (independent movement)
    """
    if len(closes) < period + 1 or len(btc_closes) < period + 1:
        return IndicatorSnapshot(
            "BTC Corr", 0, 0, "Donnees insuffisantes pour la correlation BTC",
            weight=0.6, category="sentiment",
        )

    # Compute returns
    asset_returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1] > 0]
    btc_returns = [(btc_closes[i] - btc_closes[i - 1]) / btc_closes[i - 1] for i in range(1, len(btc_closes)) if btc_closes[i - 1] > 0]

    # Align lengths
    min_len = min(len(asset_returns), len(btc_returns), period)
    if min_len < 10:
        return IndicatorSnapshot("BTC Corr", 0, 0, "Pas assez de donnees", weight=0.0, category="sentiment")

    a = asset_returns[-min_len:]
    b = btc_returns[-min_len:]

    # Pearson correlation
    corr = _pearson(a, b)

    # BTC recent trend
    btc_trend = sum(btc_returns[-5:]) if len(btc_returns) >= 5 else 0.0
    btc_bullish = btc_trend > 0.005  # > 0.5% in last 5 periods
    btc_bearish = btc_trend < -0.005

    # Signal: correlation-weighted BTC direction
    if abs(corr) < 0.3:
        signal = 0.0
        desc = f"Faible correlation BTC ({corr:.2f}) — mouvement independant"
    elif corr > 0.6:
        if btc_bearish:
            signal = -0.4
            desc = f"Forte corr BTC ({corr:.2f}) + BTC baissier — risque de baisse"
        elif btc_bullish:
            signal = 0.3
            desc = f"Forte corr BTC ({corr:.2f}) + BTC haussier — soutien haussier"
        else:
            signal = 0.0
            desc = f"Forte corr BTC ({corr:.2f}) — BTC neutre"
    else:
        # Moderate correlation
        if btc_bearish:
            signal = -0.2
            desc = f"Corr moderee BTC ({corr:.2f}) + BTC baissier"
        elif btc_bullish:
            signal = 0.15
            desc = f"Corr moderee BTC ({corr:.2f}) + BTC haussier"
        else:
            signal = 0.0
            desc = f"Corr moderee BTC ({corr:.2f}) — BTC neutre"

    return IndicatorSnapshot(
        "BTC Corr", round(corr, 3), round(signal, 3), desc, weight=0.6, category="sentiment",
    )


def _pearson(x: list[float], y: list[float]) -> float:
    """Compute Pearson correlation coefficient."""
    n = len(x)
    if n < 2:
        return 0.0

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)

    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        return 0.0

    return cov / denom
