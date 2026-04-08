"""Decision logger — persist every auto-trader decision with a feature snapshot.

Each cycle, every opportunity evaluated by the auto-trader (executed, rejected,
or hold) produces one row in ``auto_decisions``. The ``signals`` and
``context`` JSONB columns hold the full indicator + regime + scenario
snapshot exported by the ml-service — they become the feature store for
future retraining.

The table is tamper-evident: each row embeds ``prev_hash`` and
``entry_hash = sha256(prev_hash || canonical_json(row))``, forming a chain per
user. Any post-hoc modification of a row breaks the chain.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from app.repositories.auto_repository import auto_repository

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json_default(obj: Any) -> Any:
    """JSON serialiser that handles Decimal + datetime."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def _canonical_json(payload: Dict[str, Any]) -> str:
    """Deterministic JSON for hashing (sorted keys, no whitespace)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)


def _compute_hash(prev_hash: Optional[str], canonical: str) -> str:
    h = hashlib.sha256()
    if prev_hash:
        h.update(prev_hash.encode("utf-8"))
    h.update(canonical.encode("utf-8"))
    return h.hexdigest()


def serialize_ml_opportunity(opportunity: Dict[str, Any]) -> Dict[str, Any]:
    """Split an ml-service opportunity into (signals, context) for the decision log.

    The opportunity is expected to be the JSON dict returned by
    ``GET /api/v1/ml/signals`` — i.e. the result of ``asdict()`` on a
    ``RankedOpportunity`` with its nested dataclasses already flattened.
    """
    signals = {
        "strategy": opportunity.get("best_strategy") or {},
        "indicators": opportunity.get("indicators") or [],
        "direction": opportunity.get("direction"),
        "direction_label": opportunity.get("direction_label"),
        "confidence_score": opportunity.get("confidence_score"),
        "risk": opportunity.get("risk"),
        "setup_quality": opportunity.get("setup_quality"),
        "actionability": opportunity.get("actionability"),
        "action": opportunity.get("action"),
        "setup_type": opportunity.get("setup_type"),
        "horizon": opportunity.get("horizon"),
        "sub_scores": opportunity.get("sub_scores") or [],
        "key_reasons": opportunity.get("key_reasons") or [],
        "contradictions": opportunity.get("contradictions") or [],
        "notrade_reasons": opportunity.get("notrade_reasons") or [],
        "signal_trade_plan": opportunity.get("signal_trade_plan"),
    }
    context = {
        "market_regime": opportunity.get("market_regime"),
        "signal_context": opportunity.get("signal_context"),
        "regime": opportunity.get("regime"),
        "regime_fit": opportunity.get("regime_fit"),
        "confirmation_score": opportunity.get("confirmation_score"),
        "composite_score": opportunity.get("composite_score"),
        "reliability_score": opportunity.get("reliability_score"),
        "trend_context_score": opportunity.get("trend_context_score"),
        "trend_reliability_score": opportunity.get("trend_reliability_score"),
        "execution_risk": opportunity.get("execution_risk"),
        "liquidity_score": opportunity.get("liquidity_score"),
        "scenario": opportunity.get("scenario"),
        "scenario_probability": opportunity.get("scenario_probability"),
        "alternative_scenarios": opportunity.get("alternative_scenarios") or [],
        "global_score": opportunity.get("global_score"),
        "publication_score": opportunity.get("publication_score"),
        "freshness_ms": opportunity.get("freshness_ms"),
        "expected_holding_window": opportunity.get("expected_holding_window"),
    }
    return {"signals": signals, "context": context}


async def log_decision(
    *,
    user_id: str,
    cycle_id: str,
    portfolio_id: Optional[str],
    symbol: str,
    action: str,
    confidence: float,
    score: float,
    quantity: Optional[float],
    target_price: Optional[float],
    regime: Optional[str],
    scenario: Optional[str],
    signals: Dict[str, Any],
    context: Dict[str, Any],
    reasoning: str,
    outcome: str,
    outcome_reason: Optional[str] = None,
    execution_order_id: Optional[str] = None,
    trade_group_id: Optional[str] = None,
) -> str:
    """Persist a single decision row with audit chain.

    Returns the decision id. The chain hash is computed synchronously so
    that subsequent decisions can reference it.
    """
    decision_id = uuid.uuid4().hex
    prev_hash = await auto_repository.last_decision_hash(user_id)

    row: Dict[str, Any] = {
        "id": decision_id,
        "cycle_id": cycle_id,
        "user_id": user_id,
        "portfolio_id": portfolio_id,
        "decided_at": _now(),
        "symbol": symbol,
        "action": action.lower(),
        "quantity": Decimal(str(quantity)) if quantity is not None else None,
        "target_price": Decimal(str(target_price)) if target_price is not None else None,
        "confidence": Decimal(str(confidence)),
        "score": Decimal(str(score)),
        "regime": regime,
        "scenario": scenario,
        "signals": signals,
        "context": context,
        "reasoning": reasoning or "",
        "decision_outcome": outcome,
        "outcome_reason": outcome_reason,
        "execution_order_id": execution_order_id,
        "trade_group_id": trade_group_id,
        "prev_hash": prev_hash,
        "entry_hash": "",
    }

    # Compute the audit hash over the canonical JSON of the row (excluding
    # entry_hash itself, which we set right after).
    hashable = {k: v for k, v in row.items() if k != "entry_hash"}
    entry_hash = _compute_hash(prev_hash, _canonical_json(hashable))
    row["entry_hash"] = entry_hash

    await auto_repository.insert_decision(row)
    return decision_id
