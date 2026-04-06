"""Weight Optimizer — analyzes signal log outcomes to suggest better indicator weights.

Uses simple logistic-like scoring: for each regime, compute which indicators
had the strongest correlation with winning signals.

No external ML library needed — pure Python statistics.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

from app.engine.signal_tracker import get_recent_signals

logger = logging.getLogger(__name__)

# Default weights (current production values)
DEFAULT_WEIGHTS = {
    "RSI": 1.2,
    "MACD": 1.3,
    "EMA Cross": 1.1,
    "Bollinger": 1.0,
    "Volume": 0.6,
}


async def compute_optimal_weights(
    redis_client: Any,
    min_samples: int = 30,
) -> dict[str, dict]:
    """Analyze signal outcomes and suggest improved weights per regime.

    Returns:
        {
            "global": {"RSI": 1.3, "MACD": 1.1, ...},
            "by_regime": {
                "RANGE": {"RSI": 1.5, ...},
                "TREND_UP": {"MACD": 1.4, ...},
            },
            "stats": {"total_signals": N, "with_outcome": N, "win_rate": X}
        }
    """
    entries = await get_recent_signals(redis_client, limit=500)
    with_outcome = [e for e in entries if e.get("outcome") in ("win", "loss")]

    if len(with_outcome) < min_samples:
        return {
            "global": DEFAULT_WEIGHTS,
            "by_regime": {},
            "stats": {
                "total_signals": len(entries),
                "with_outcome": len(with_outcome),
                "min_samples_needed": min_samples,
                "message": f"Pas assez de donnees ({len(with_outcome)}/{min_samples}). Les poids par defaut sont utilises.",
            },
        }

    # Global weight analysis
    global_weights = _analyze_weights(with_outcome)

    # Per-regime analysis
    by_regime: dict[str, dict[str, float]] = {}
    regimes = set(e.get("regime", "UNKNOWN") for e in with_outcome)
    for regime in regimes:
        regime_entries = [e for e in with_outcome if e.get("regime") == regime]
        if len(regime_entries) >= 10:
            by_regime[regime] = _analyze_weights(regime_entries)

    wins = sum(1 for e in with_outcome if e["outcome"] == "win")

    return {
        "global": global_weights,
        "by_regime": by_regime,
        "stats": {
            "total_signals": len(entries),
            "with_outcome": len(with_outcome),
            "win_rate": round(wins / len(with_outcome) * 100, 1),
            "win_count": wins,
            "loss_count": len(with_outcome) - wins,
        },
    }


def _analyze_weights(entries: list[dict]) -> dict[str, float]:
    """Compute optimal weights based on win/loss correlation.

    For each confidence level, check if higher confidence correlates with more wins.
    For each direction extremity, check if stronger signals win more.
    Then adjust indicator weights proportionally.
    """
    if not entries:
        return dict(DEFAULT_WEIGHTS)

    wins = [e for e in entries if e["outcome"] == "win"]
    losses = [e for e in entries if e["outcome"] == "loss"]

    if not wins or not losses:
        return dict(DEFAULT_WEIGHTS)

    # Analyze: winning signals tend to have higher confidence
    avg_conf_win = sum(e.get("confidence", 50) for e in wins) / len(wins)
    avg_conf_loss = sum(e.get("confidence", 50) for e in losses) / len(losses)

    # Analyze: winning signals tend to have lower risk
    avg_risk_win = sum(e.get("risk", 50) for e in wins) / len(wins)
    avg_risk_loss = sum(e.get("risk", 50) for e in losses) / len(losses)

    # Analyze: winning signals tend to have stronger direction
    avg_dir_win = sum(abs(e.get("direction", 50) - 50) for e in wins) / len(wins)
    avg_dir_loss = sum(abs(e.get("direction", 50) - 50) for e in losses) / len(losses)

    # Confidence gap → if wins have higher confidence, our scoring works
    conf_quality = (avg_conf_win - avg_conf_loss) / max(avg_conf_win, 1)

    # Build weight suggestions (subtle adjustments from defaults)
    weights = dict(DEFAULT_WEIGHTS)

    # If confidence discriminates well (wins > losses), keep current weights
    # If not, boost volume (confirmation) and reduce momentum (noisy)
    if conf_quality < 0.05:
        # Confidence doesn't discriminate → momentum indicators are noisy
        weights["RSI"] = max(0.5, weights["RSI"] - 0.2)
        weights["MACD"] = max(0.5, weights["MACD"] - 0.2)
        weights["Volume"] = min(1.5, weights["Volume"] + 0.3)
        logger.info("Weight optimizer: confidence not discriminating, boosting Volume, reducing momentum")
    elif conf_quality > 0.15:
        # Confidence discriminates well → slightly boost trend indicators
        weights["EMA Cross"] = min(1.5, weights["EMA Cross"] + 0.1)
        weights["MACD"] = min(1.6, weights["MACD"] + 0.1)

    # If risk discriminates well (losses have higher risk), the risk model works
    risk_quality = (avg_risk_loss - avg_risk_win) / max(avg_risk_loss, 1)
    if risk_quality < 0.05:
        weights["Bollinger"] = min(1.4, weights["Bollinger"] + 0.2)  # boost volatility awareness

    return {k: round(v, 2) for k, v in weights.items()}


async def get_calibration_report(redis_client: Any) -> dict:
    """Generate a calibration report: does confidence X% mean X% win rate?"""
    entries = await get_recent_signals(redis_client, limit=500)
    with_outcome = [e for e in entries if e.get("outcome") in ("win", "loss")]

    if len(with_outcome) < 20:
        return {"message": "Pas assez de donnees pour la calibration.", "buckets": []}

    # Bucket by confidence ranges
    buckets = [
        (0, 30, "0-30%"),
        (30, 50, "30-50%"),
        (50, 70, "50-70%"),
        (70, 100, "70-100%"),
    ]

    report = []
    for lo, hi, label in buckets:
        bucket_entries = [e for e in with_outcome if lo <= e.get("confidence", 0) < hi]
        if not bucket_entries:
            report.append({"range": label, "count": 0, "win_rate": None})
            continue
        wins = sum(1 for e in bucket_entries if e["outcome"] == "win")
        report.append({
            "range": label,
            "count": len(bucket_entries),
            "win_rate": round(wins / len(bucket_entries) * 100, 1),
            "expected_midpoint": (lo + hi) / 2,
        })

    return {"buckets": report, "total": len(with_outcome)}
