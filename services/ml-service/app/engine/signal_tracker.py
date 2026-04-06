"""Signal Tracker — logs every emitted signal for future performance analysis.

Each signal is stored in Redis as a JSON entry with:
  - timestamp, symbol, action, direction, confidence, risk, regime, scenario
  - price_at_signal (entry price)

A background task can later compare with price_after_15m / price_after_1h
to measure accuracy and calibrate weights.

Keys: signal_log:{symbol}:{timestamp}  TTL: 7 days
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# TTL for signal log entries (7 days)
_LOG_TTL = 7 * 24 * 3600


async def log_signal(
    redis_client: Any,
    symbol: str,
    action: str,
    direction: int,
    confidence: int,
    risk: int,
    setup_quality: int,
    actionability: str,
    regime: str = "UNKNOWN",
    scenario: str = "",
    price: float = 0.0,
    score: float = 0.0,
) -> None:
    """Store a signal entry in Redis for later analysis."""
    if redis_client is None:
        return

    now = datetime.now(timezone.utc)
    key = f"signal_log:{symbol}:{now.strftime('%Y%m%d%H%M%S')}"

    entry = {
        "timestamp": now.isoformat(),
        "symbol": symbol,
        "action": action,
        "direction": direction,
        "confidence": confidence,
        "risk": risk,
        "setup_quality": setup_quality,
        "actionability": actionability,
        "regime": regime,
        "scenario": scenario,
        "price_at_signal": price,
        "score": score,
        # To be filled later by a background job:
        "price_after_15m": None,
        "price_after_1h": None,
        "price_after_4h": None,
        "outcome": None,  # "win" / "loss" / "neutral"
    }

    try:
        await redis_client.setex(key, _LOG_TTL, json.dumps(entry))
        logger.debug("Signal logged: %s %s %s dir=%d conf=%d", symbol, action, regime, direction, confidence)
    except Exception as exc:
        logger.warning("Failed to log signal: %s", exc)


async def get_recent_signals(
    redis_client: Any,
    symbol: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Retrieve recent signal logs from Redis."""
    if redis_client is None:
        return []

    try:
        pattern = f"signal_log:{symbol}:*" if symbol else "signal_log:*"
        keys = []
        async for key in redis_client.scan_iter(match=pattern, count=200):
            keys.append(key)
            if len(keys) >= limit * 2:  # over-fetch then sort
                break

        entries = []
        for key in keys:
            raw = await redis_client.get(key)
            if raw:
                try:
                    entries.append(json.loads(raw))
                except json.JSONDecodeError:
                    pass

        # Sort by timestamp descending
        entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return entries[:limit]
    except Exception as exc:
        logger.warning("Failed to read signal logs: %s", exc)
        return []


async def compute_signal_stats(
    redis_client: Any,
    symbol: Optional[str] = None,
) -> dict:
    """Compute basic performance stats from logged signals."""
    entries = await get_recent_signals(redis_client, symbol, limit=200)

    if not entries:
        return {"total": 0, "with_outcome": 0, "win_rate": None}

    with_outcome = [e for e in entries if e.get("outcome")]
    wins = sum(1 for e in with_outcome if e["outcome"] == "win")

    return {
        "total": len(entries),
        "with_outcome": len(with_outcome),
        "win_rate": round(wins / len(with_outcome) * 100, 1) if with_outcome else None,
        "avg_confidence": round(sum(e.get("confidence", 0) for e in entries) / len(entries), 1),
        "avg_risk": round(sum(e.get("risk", 0) for e in entries) / len(entries), 1),
        "regime_distribution": _count_field(entries, "regime"),
        "action_distribution": _count_field(entries, "action"),
    }


def _count_field(entries: list[dict], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in entries:
        val = str(e.get(field, "UNKNOWN"))
        counts[val] = counts.get(val, 0) + 1
    return counts
