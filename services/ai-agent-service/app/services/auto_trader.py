"""Auto-Trading Agent — deterministic signal selection, scoped per user.

Refactored in the "auto-trading complet" phase to:
    - Persist every decision in ``auto_decisions`` (Postgres) with a feature
      snapshot and an audit hash chain.
    - Link each BUY to its eventual SELL via ``trade_groups`` (FIFO).
    - Enforce circuit breakers (daily loss, consecutive losses, heartbeat,
      symbol cooldown after stop-loss).
    - Publish SMS events on ``sms:events`` for the notification-service.
    - Support three modes: ``paper`` (simulated fills), ``live`` (real
      Binance), ``dry_run`` (decisions logged but no orders sent).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, Optional

import httpx

from app.core.auth import DEFAULT_AI_USER_ID, get_auth_ttl_seconds
from app.core.config import settings
from app.core.llm_router import Complexity, chat_completion
from app.memory.redis_client import get_redis
from app.repositories.auto_repository import auto_repository
from app.services import circuit_breakers
from app.services.decision_logger import log_decision, serialize_ml_opportunity
from app.services.sms_events import publish_event as publish_sms_event
from app.services.trade_group_tracker import close_trade_group, open_trade_group

logger = logging.getLogger(__name__)

AUTO_TRADE_INTERVAL = 300  # 5 minutes
MAX_DAILY_TRADES = 10
CONFIDENCE_THRESHOLD = 0.68
MAX_TRADES_PER_CYCLE = 3
MAX_BUY_ALLOCATION_PCT = Decimal("0.12")
MIN_ORDER_USD = Decimal("25")
STABLES = {"USDT", "USDC", "BUSD", "FDUSD", "USD", "DAI", "TUSD"}
AUTO_TRADING_HISTORY_LIMIT = 100
AUTO_TRADING_STATE_TTL_SECONDS = 30 * 24 * 3600

SUMMARY_PROMPT = """You are the execution analyst for an automated crypto desk.
Write a brief, factual summary of the current cycle in 2 short paragraphs.
Mention the detected market regime, the strongest opportunities, and the key risk constraint.
Do not invent trades not present in the provided context."""


class AutoTradingAuthError(RuntimeError):
    """Raised when a user-scoped auto-trading session loses authorization."""


@dataclass
class AutoTradingSession:
    """In-memory auto-trading state for a single user."""

    enabled: bool = False
    task: Optional[asyncio.Task[Any]] = None
    trades_today: int = 0
    last_run: Optional[str] = None
    last_regime: Optional[str] = None
    total_pnl: float = 0.0
    history: list[dict] = field(default_factory=list)
    auth_header: Optional[str] = None
    last_error: Optional[str] = None
    trade_day: Optional[str] = None

    # Extended auto-trading fields (auto-trading complet phase)
    mode: str = "paper"  # paper | live | dry_run
    portfolio_id: Optional[str] = None
    interval_seconds: int = 300
    cycle_id: Optional[str] = None
    cooldown_symbols: Dict[str, str] = field(default_factory=dict)
    consecutive_losses: int = 0
    realized_pnl_today: Decimal = Decimal("0")
    portfolio_value_start_of_day: Optional[Decimal] = None
    heartbeat_at: Optional[datetime] = None
    next_cycle_at: Optional[datetime] = None
    config: Dict[str, Any] = field(default_factory=dict)


_sessions: dict[str, AutoTradingSession] = {}


def _session(user_id: str) -> AutoTradingSession:
    session = _sessions.get(user_id)
    if session is None:
        session = AutoTradingSession()
        _sessions[user_id] = session
    return session


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _users_key() -> str:
    return "ai:auto_trading:users"


def _state_key(user_id: str) -> str:
    return f"ai:auto_trading:{user_id}:state"


def _auth_key(user_id: str) -> str:
    return f"ai:auto_trading:{user_id}:auth"


def _sync_daily_counter(session: AutoTradingSession) -> None:
    today = _today_utc()
    if session.trade_day != today:
        session.trades_today = 0
        session.trade_day = today


def _session_state_for_breakers(session: AutoTradingSession) -> Dict[str, Any]:
    """Snapshot used by circuit_breakers.check_all().

    Intentionally minimal — just what the breakers need. Kept in sync with
    the dataclass on purpose (no generic dict dump).
    """
    return {
        "config": dict(session.config),
        "cooldown_symbols": dict(session.cooldown_symbols),
        "consecutive_losses": session.consecutive_losses,
        "realized_pnl_today": session.realized_pnl_today,
        "portfolio_value_start_of_day": session.portfolio_value_start_of_day,
        "heartbeat_at": session.heartbeat_at,
    }


def _serializable_session(session: AutoTradingSession) -> dict[str, Any]:
    return {
        "enabled": session.enabled,
        "mode": session.mode,
        "portfolio_id": session.portfolio_id,
        "interval_seconds": session.interval_seconds,
        "cycle_id": session.cycle_id,
        "cooldown_symbols": session.cooldown_symbols,
        "consecutive_losses": session.consecutive_losses,
        "realized_pnl_today": str(session.realized_pnl_today),
        "portfolio_value_start_of_day": (
            str(session.portfolio_value_start_of_day)
            if session.portfolio_value_start_of_day is not None
            else None
        ),
        "heartbeat_at": session.heartbeat_at.isoformat() if session.heartbeat_at else None,
        "next_cycle_at": session.next_cycle_at.isoformat() if session.next_cycle_at else None,
        "config": session.config,
        "trades_today": session.trades_today,
        "last_run": session.last_run,
        "last_regime": session.last_regime,
        "total_pnl": session.total_pnl,
        "history": session.history[-AUTO_TRADING_HISTORY_LIMIT:],
        "last_error": session.last_error,
        "trade_day": session.trade_day,
    }


async def _persist_session(user_id: str) -> None:
    session = _sessions.get(user_id)
    if session is None:
        return

    try:
        redis = await get_redis()
        await redis.sadd(_users_key(), user_id)
        await redis.setex(
            _state_key(user_id),
            AUTO_TRADING_STATE_TTL_SECONDS,
            json.dumps(_serializable_session(session)),
        )

        if session.auth_header:
            try:
                ttl = get_auth_ttl_seconds(session.auth_header)
            except Exception:
                ttl = None
            if ttl and ttl > 0:
                await redis.setex(_auth_key(user_id), ttl, session.auth_header)
            elif user_id != DEFAULT_AI_USER_ID:
                await redis.delete(_auth_key(user_id))
        else:
            await redis.delete(_auth_key(user_id))
    except Exception as exc:
        logger.warning("Auto-trader state persistence failed for user=%s: %s", user_id, exc)


async def _restore_session(user_id: str) -> AutoTradingSession | None:
    try:
        redis = await get_redis()
        raw_state = await redis.get(_state_key(user_id))
        if not raw_state:
            await redis.srem(_users_key(), user_id)
            await redis.delete(_auth_key(user_id))
            return None

        payload = json.loads(raw_state)
        history = payload.get("history")
        auth_header = await redis.get(_auth_key(user_id))
    except Exception as exc:
        logger.warning("Auto-trader state restore failed for user=%s: %s", user_id, exc)
        return None

    session = AutoTradingSession(
        enabled=bool(payload.get("enabled", False)),
        mode=str(payload.get("mode", "paper") or "paper"),
        portfolio_id=payload.get("portfolio_id"),
        interval_seconds=int(payload.get("interval_seconds", AUTO_TRADE_INTERVAL) or AUTO_TRADE_INTERVAL),
        cycle_id=payload.get("cycle_id"),
        cooldown_symbols=payload.get("cooldown_symbols") or {},
        consecutive_losses=int(payload.get("consecutive_losses", 0) or 0),
        realized_pnl_today=Decimal(str(payload.get("realized_pnl_today") or "0")),
        portfolio_value_start_of_day=(
            Decimal(str(payload["portfolio_value_start_of_day"]))
            if payload.get("portfolio_value_start_of_day") is not None
            else None
        ),
        config=payload.get("config") or {},
        trades_today=int(payload.get("trades_today", 0) or 0),
        last_run=payload.get("last_run"),
        last_regime=payload.get("last_regime"),
        total_pnl=float(payload.get("total_pnl", 0) or 0),
        history=history if isinstance(history, list) else [],
        auth_header=auth_header,
        last_error=payload.get("last_error"),
        trade_day=payload.get("trade_day"),
    )
    # Parse datetime fields
    for attr in ("heartbeat_at", "next_cycle_at"):
        raw = payload.get(attr)
        if isinstance(raw, str) and raw:
            try:
                parsed = datetime.fromisoformat(raw)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                setattr(session, attr, parsed)
            except ValueError:
                pass
    session.history = session.history[-AUTO_TRADING_HISTORY_LIMIT:]
    _sessions[user_id] = session
    return session


async def restore_sessions() -> None:
    """Restore persisted user sessions and resume authorized loops."""
    try:
        redis = await get_redis()
        user_ids = await redis.smembers(_users_key())
    except Exception as exc:
        logger.warning("Auto-trader session discovery failed: %s", exc)
        return

    for user_id in sorted(user_ids):
        session = await _restore_session(user_id)
        if session is None:
            continue

        _sync_daily_counter(session)

        if not session.enabled:
            continue

        if user_id == DEFAULT_AI_USER_ID or session.auth_header:
            await start(user_id, session.auth_header, restore=True)
            continue

        session.enabled = False
        session.last_error = "Authorization expired after service restart"
        await _persist_session(user_id)


async def remember_auth(user_id: str, auth_header: Optional[str]) -> None:
    """Refresh the stored auth header for a user session when a token is present."""
    if not auth_header:
        return
    session = _session(user_id)
    session.auth_header = auth_header
    if (
        session.enabled
        or session.history
        or session.last_run is not None
        or session.last_error is not None
        or session.trades_today > 0
    ):
        await _persist_session(user_id)


async def _fetch_json(
    url: str,
    auth_header: Optional[str] = None,
    params: dict | None = None,
) -> dict | list | None:
    try:
        headers = {"Authorization": auth_header} if auth_header else None
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            if auth_header and resp.status_code in {401, 403}:
                raise AutoTradingAuthError("Auto-trading session lost authorization")
            resp.raise_for_status()
            return resp.json()
    except AutoTradingAuthError:
        raise
    except Exception as exc:
        logger.warning("Auto-trader fetch failed: %s — %s", url, exc)
        return None


async def _post_json(
    url: str,
    payload: dict[str, Any],
    auth_header: Optional[str] = None,
) -> dict | None:
    try:
        headers = {"Authorization": auth_header} if auth_header else None
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if auth_header and resp.status_code in {401, 403}:
                raise AutoTradingAuthError("Auto-trading session lost authorization")
            resp.raise_for_status()
            return resp.json()
    except AutoTradingAuthError:
        raise
    except Exception as exc:
        logger.error("Auto-trader post failed: %s — %s", url, exc)
        return None


def _as_decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _signal_side(action: str) -> str:
    upper = action.upper()
    if upper in {"BUY", "STRONG_BUY", "ACCUMULATE"}:
        return "buy"
    if upper in {"SELL", "STRONG_SELL", "REDUCE"}:
        return "sell"
    return "hold"


def _available_cash(balances: dict[str, Any]) -> Decimal:
    return sum(
        _as_decimal(amount)
        for asset, amount in balances.items()
        if asset.upper() in STABLES
    )


def _holding_quantity(balances: dict[str, Any], symbol: str) -> Decimal:
    return _as_decimal(balances.get(symbol.upper(), 0))


def _build_fallback_analysis(
    regime: str,
    signals: list[dict],
    executed: list[dict],
) -> str:
    if not signals:
        return "No signal universe available this cycle."

    top = signals[0]
    if not executed:
        return (
            f"Regime {regime}. Best setup was {top['symbol']} with {top['action']} "
            f"at {round(top['confidence'] * 100)}% confidence, but no trade cleared execution filters."
        )

    actions = ", ".join(
        f"{trade['symbol']} {trade['action']} ${trade['amount_usd']:.0f}"
        for trade in executed
    )
    return (
        f"Regime {regime}. Executed {len(executed)} trade(s): {actions}. "
        f"Top conviction remained {top['symbol']} at {round(top['confidence'] * 100)}% confidence."
    )


async def _execute_trade(
    symbol: str,
    side: str,
    quantity: Decimal,
    strategy: str,
    auth_header: Optional[str],
) -> Dict[str, Any]:
    """Execute a trade with mandatory preflight + retry + auto-conversion.

    Uses /orders/execute-with-conversion which:
    - Preflights the order
    - Handles conversion chains (e.g. EUR → USDT → BTC)
    - Retries with exponential backoff on rate limit / timeout

    Returns a result dict:
        {
            "success": bool,
            "order_id": Optional[str],        # ID of the primary fill order
            "filled_price": Optional[float],
            "filled_quantity": Optional[float],
            "fee": float,
            "steps": list[dict],
            "error_code": Optional[str],
            "error_message": Optional[str],
        }
    """
    if quantity <= 0:
        return {"success": False, "order_id": None, "error_message": "quantity_zero"}

    payload = {
        "symbol": symbol,
        "side": side,
        "quantity": float(quantity),
        "max_retries": 3,
    }
    response = await _post_json(
        f"{settings.TRADING_URL}/api/v1/orders/execute-with-conversion",
        payload,
        auth_header=auth_header,
    )

    if response is None:
        logger.error(
            "Auto-trade failed: %s %s qty=%s strategy=%s — no response",
            side, symbol, quantity, strategy,
        )
        return {"success": False, "order_id": None, "error_message": "no_response", "steps": []}

    status = response.get("status")
    steps = response.get("steps", []) or []

    if status == "filled":
        # The primary (last) step is the actual target trade; earlier steps are conversions
        primary = steps[-1] if steps else {}
        conversion_count = sum(1 for s in steps if s.get("note") == "conversion step")
        if conversion_count > 0:
            logger.info(
                "Auto-trade filled with %d conversion step(s): %s %s qty=%s",
                conversion_count, side, symbol, quantity,
            )
        else:
            logger.info("Auto-trade filled: %s %s qty=%s", side, symbol, quantity)
        return {
            "success": True,
            "order_id": primary.get("order_id"),
            "filled_price": primary.get("filled_price") or primary.get("avg_price"),
            "filled_quantity": primary.get("filled_quantity") or float(quantity),
            "fee": float(primary.get("fee") or 0),
            "steps": steps,
            "error_code": None,
            "error_message": None,
        }

    error = response.get("error", {}) or {}
    logger.error(
        "Auto-trade failed: %s %s qty=%s strategy=%s code=%s reason=%s steps=%d",
        side, symbol, quantity, strategy,
        error.get("code", "UNKNOWN"),
        error.get("user_message", "unknown error"),
        len(steps),
    )
    return {
        "success": False,
        "order_id": None,
        "steps": steps,
        "error_code": error.get("code", "UNKNOWN"),
        "error_message": error.get("user_message") or "execution_failed",
    }


def _rank_signals(signals: list[dict]) -> list[dict]:
    scored = []
    for signal in signals:
        action = str(signal.get("action", "HOLD")).upper()
        if action == "HOLD":
            continue
        confidence = float(signal.get("confidence", 0))
        score = abs(float(signal.get("score", 0)))
        price = _as_decimal(signal.get("price", 0))
        if price <= 0 or confidence < CONFIDENCE_THRESHOLD:
            continue
        scored.append(
            {
                **signal,
                "confidence": confidence,
                "score": score,
                "price_decimal": price,
                "priority": confidence * 0.75 + score * 0.25,
            }
        )
    return sorted(scored, key=lambda item: item["priority"], reverse=True)


def _select_trades(
    signals: list[dict],
    balances: dict[str, Any],
    remaining_trade_budget: int,
) -> list[dict]:
    available_cash = _available_cash(balances)
    remaining_cash = available_cash
    executed: list[dict] = []

    for signal in _rank_signals(signals):
        if len(executed) >= min(MAX_TRADES_PER_CYCLE, remaining_trade_budget):
            break

        side = _signal_side(str(signal["action"]))
        symbol = str(signal["symbol"]).upper()
        price = signal["price_decimal"]
        confidence = Decimal(str(signal["confidence"]))
        regime = str(signal.get("regime", "unknown"))
        reasoning = str(signal.get("reasoning", ""))

        if side == "buy":
            if remaining_cash < MIN_ORDER_USD:
                continue
            allocation = remaining_cash * MAX_BUY_ALLOCATION_PCT * (
                Decimal("0.6") + confidence * Decimal("0.8")
            )
            amount_usd = min(allocation, remaining_cash * Decimal("0.4"))
        elif side == "sell":
            held_qty = _holding_quantity(balances, symbol)
            if held_qty <= 0:
                continue
            held_value = held_qty * price
            amount_usd = min(
                held_value * (Decimal("0.25") + confidence * Decimal("0.5")),
                held_value,
            )
        else:
            continue

        amount_usd = amount_usd.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        if amount_usd < MIN_ORDER_USD or price <= 0:
            continue

        quantity = (amount_usd / price).quantize(
            Decimal("0.00000001"),
            rounding=ROUND_DOWN,
        )
        if quantity <= 0:
            continue

        executed.append(
            {
                "symbol": symbol,
                "action": side,
                "amount_usd": float(amount_usd),
                "quantity": quantity,
                "confidence": float(confidence),
                "reason": reasoning,
                "regime": regime,
                "strategy": "ml_signal_engine",
                "price": float(price),
            }
        )

        if side == "buy":
            remaining_cash = max(Decimal("0"), remaining_cash - amount_usd)

    return executed


async def _build_cycle_analysis(
    regime: str,
    signals: list[dict],
    executed: list[dict],
) -> tuple[str, str | None, str | None]:
    context = {
        "regime": regime,
        "signals": signals[:5],
        "executed": executed,
        "trade_count": len(executed),
    }

    try:
        reply, provider, model = await chat_completion(
            messages=[{"role": "user", "content": str(context)}],
            system_prompt=SUMMARY_PROMPT,
            complexity=Complexity.MEDIUM,
        )
        return reply, provider, model
    except Exception as exc:
        logger.warning("Auto-trader AI summary unavailable: %s", exc)
        return _build_fallback_analysis(regime, signals, executed), None, None


async def _handle_execution_result(
    *,
    user_id: str,
    session: AutoTradingSession,
    decision_id: str,
    trade: Dict[str, Any],
    result: Dict[str, Any],
    redis,
) -> None:
    """After an order execution, link it to a trade_group and notify SMS.

    - BUY → open new trade_group (or extend the existing open one).
    - SELL → close the oldest open trade_group for the symbol.
    - Publish the appropriate sms:events payload.
    """
    symbol = str(trade["symbol"]).upper()
    side = str(trade["action"]).lower()
    success = bool(result.get("success"))

    if not success:
        await auto_repository.update_decision(
            decision_id,
            outcome="rejected_filter",
            outcome_reason=result.get("error_message") or "execution_failed",
        )
        await publish_sms_event(
            redis,
            user_id,
            "trade_failed",
            {
                "symbol": symbol,
                "side": side,
                "reason": result.get("error_message"),
                "code": result.get("error_code"),
            },
        )
        return

    order_id = result.get("order_id")
    filled_price = float(result.get("filled_price") or trade.get("price") or 0)
    filled_qty = float(result.get("filled_quantity") or trade.get("quantity") or 0)
    fee = float(result.get("fee") or 0)

    trade_group_id: Optional[str] = None
    if side == "buy":
        trade_group_id = await open_trade_group(
            user_id=user_id,
            portfolio_id=session.portfolio_id,
            symbol=symbol,
            side="buy",
            entry_decision_id=decision_id,
            entry_order_id=order_id,
            entry_quantity=filled_qty,
            entry_price=filled_price,
            entry_fee=fee,
            entry_reason=str(trade.get("reason") or ""),
        )
    elif side == "sell":
        trade_group_id = await close_trade_group(
            user_id=user_id,
            symbol=symbol,
            exit_decision_id=decision_id,
            exit_order_id=order_id,
            exit_quantity=filled_qty,
            exit_price=filled_price,
            exit_fee=fee,
            exit_reason=str(trade.get("reason") or ""),
            side="buy",  # match the long open group
        )
        # Register outcome for the circuit breakers
        if trade_group_id:
            group = await auto_repository.get_trade_group(trade_group_id)
            if group is not None and group.realized_pnl is not None:
                pnl_float = float(group.realized_pnl)
                breaker_state = _session_state_for_breakers(session)
                circuit_breakers.register_trade_outcome(
                    breaker_state,
                    pnl=pnl_float,
                    symbol=symbol,
                    was_stop_loss=pnl_float < 0,  # paper approximation
                )
                session.realized_pnl_today = breaker_state["realized_pnl_today"]
                session.consecutive_losses = breaker_state["consecutive_losses"]
                session.cooldown_symbols = breaker_state["cooldown_symbols"]
                session.total_pnl = float(session.realized_pnl_today)

    await auto_repository.update_decision(
        decision_id,
        outcome="executed",
        execution_order_id=order_id,
        trade_group_id=trade_group_id,
    )

    # SMS event per side
    sms_event_type = "trade_buy" if side == "buy" else "trade_sell"
    await publish_sms_event(
        redis,
        user_id,
        sms_event_type,
        {
            "symbol": symbol,
            "side": side,
            "quantity": filled_qty,
            "price": filled_price,
            "trade_group_id": trade_group_id,
            "portfolio_id": session.portfolio_id,
            "reason": trade.get("reason"),
        },
    )


async def run_cycle(
    user_id: str,
    auth_header: Optional[str],
    trades_today: int,
    *,
    session: Optional[AutoTradingSession] = None,
) -> dict:
    """Run one auto-trading analysis cycle for a specific user.

    When ``session`` is provided, the cycle:
        - Checks circuit breakers at start (and short-circuits if tripped)
        - Persists every evaluated opportunity to ``auto_decisions``
        - Links fills to ``trade_groups`` and updates P&L counters
        - Publishes SMS events for fills / failures
    """
    session = session if session is not None else _session(user_id)
    cycle_id = uuid.uuid4().hex
    session.cycle_id = cycle_id
    redis = None
    try:
        redis = await get_redis()
    except Exception:
        redis = None

    # ------------------------------------------------------------------
    # Circuit breakers — short-circuit if tripped
    # ------------------------------------------------------------------
    breaker_state = _session_state_for_breakers(session)
    breaker_result = circuit_breakers.check_all(breaker_state)
    if not breaker_result.ok:
        logger.warning(
            "Auto-trader breaker tripped user=%s reason=%s action=%s",
            user_id,
            breaker_result.reason,
            breaker_result.action,
        )
        session.last_error = breaker_result.reason
        await publish_sms_event(
            redis,
            user_id,
            "circuit_breaker",
            {
                "reason": breaker_result.reason,
                "action": breaker_result.action,
                "cycle_id": cycle_id,
            },
        )
        if breaker_result.action == "stop":
            session.enabled = False
        # Return an early cycle result so the loop can persist state cleanly
        return {
            "user_id": user_id,
            "timestamp": _now(),
            "cycle_id": cycle_id,
            "analysis": f"Breaker tripped: {breaker_result.reason}",
            "recommendations": 0,
            "executed": 0,
            "trades": [],
            "provider": None,
            "model": None,
            "regime": "breaker",
            "signals_scanned": 0,
            "candidates": [],
            "breaker_reason": breaker_result.reason,
        }

    # ------------------------------------------------------------------
    # Fetch data
    # ------------------------------------------------------------------
    markets = await _fetch_json(
        f"{settings.MARKET_DATA_URL}/api/v1/markets/top",
        params={"limit": 12},
    )
    balances = await _fetch_json(
        f"{settings.TRADING_URL}/api/v1/orders/balance",
        auth_header=auth_header,
    )

    market_rows = (markets or {}).get("data", []) if isinstance(markets, dict) else []
    symbols = [
        str(row.get("symbol", "")).upper()
        for row in market_rows
        if row.get("symbol")
    ]
    signal_payload = await _fetch_json(
        f"{settings.STRATEGY_URL}/api/v1/ml/signals",
        params={
            "symbols": ",".join(symbols),
            "limit": min(len(symbols), 12),
            "interval": "1h",
            "lookback": 120,
        },
    )

    if not isinstance(balances, dict):
        balances = {}

    raw_signals = []
    if isinstance(signal_payload, dict):
        raw_signals = signal_payload.get("signals", []) or []

    ranked_signals = _rank_signals(raw_signals)
    remaining_trade_budget = max(0, MAX_DAILY_TRADES - trades_today)
    cycle_trades = _select_trades(ranked_signals, balances, remaining_trade_budget)

    # ------------------------------------------------------------------
    # Persist every evaluated opportunity (executed + rejected + watch)
    # ------------------------------------------------------------------
    decision_id_by_symbol: Dict[str, str] = {}
    selected_symbols = {str(t["symbol"]).upper() for t in cycle_trades}

    for opp in ranked_signals:
        symbol = str(opp.get("symbol", "")).upper()
        if not symbol:
            continue
        action = str(opp.get("action", "hold")).lower()
        feature_payload = serialize_ml_opportunity(opp)

        in_cooldown = circuit_breakers.is_symbol_in_cooldown(breaker_state, symbol)
        will_execute = symbol in selected_symbols and not in_cooldown
        pre_outcome = "pending" if will_execute else (
            "rejected_risk" if in_cooldown else "rejected_filter"
        )
        pre_reason = (
            "symbol_cooldown" if in_cooldown
            else ("selected_for_execution" if will_execute else "not_selected_by_ranker")
        )

        decision_id = await log_decision(
            user_id=user_id,
            cycle_id=cycle_id,
            portfolio_id=session.portfolio_id,
            symbol=symbol,
            action=action,
            confidence=float(opp.get("confidence") or 0),
            score=float(opp.get("score") or 0),
            quantity=None,
            target_price=float(opp.get("price") or 0) or None,
            regime=str(opp.get("regime") or "") or None,
            scenario=str(opp.get("scenario") or "") or None,
            signals=feature_payload["signals"],
            context=feature_payload["context"],
            reasoning=str(opp.get("reasoning") or ""),
            outcome=pre_outcome,
            outcome_reason=pre_reason,
        )
        decision_id_by_symbol[symbol] = decision_id

    # ------------------------------------------------------------------
    # Execute selected trades (dry-run skips the actual POST)
    # ------------------------------------------------------------------
    executed: list[dict] = []
    for trade in cycle_trades:
        symbol = str(trade["symbol"]).upper()
        decision_id = decision_id_by_symbol.get(symbol)
        if decision_id is None:
            # Shouldn't happen, but stay defensive
            continue

        if session.mode == "dry_run":
            await auto_repository.update_decision(
                decision_id,
                outcome="dry_run",
                outcome_reason="dry_run_mode",
            )
            executed.append(
                {
                    **{k: trade[k] for k in ("symbol", "action", "amount_usd",
                                              "confidence", "reason", "regime",
                                              "strategy", "price")},
                    "dry_run": True,
                    "decision_id": decision_id,
                }
            )
            continue

        result = await _execute_trade(
            trade["symbol"],
            trade["action"],
            trade["quantity"],
            trade["strategy"],
            auth_header=auth_header,
        )

        await _handle_execution_result(
            user_id=user_id,
            session=session,
            decision_id=decision_id,
            trade=trade,
            result=result,
            redis=redis,
        )

        if result.get("success"):
            executed.append(
                {
                    "symbol": trade["symbol"],
                    "action": trade["action"],
                    "amount_usd": trade["amount_usd"],
                    "confidence": trade["confidence"],
                    "reason": trade["reason"],
                    "regime": trade["regime"],
                    "strategy": trade["strategy"],
                    "price": trade["price"],
                    "decision_id": decision_id,
                    "trade_group_id": None,  # filled by handler via DB
                }
            )

    dominant_regime = (
        ranked_signals[0].get("regime", "unknown")
        if ranked_signals
        else "unknown"
    )
    analysis, provider, model = await _build_cycle_analysis(
        str(dominant_regime),
        ranked_signals,
        executed,
    )
    timestamp = _now()

    # Update heartbeat and next_cycle_at for the dead-man switch + UI countdown
    session.heartbeat_at = timestamp
    from datetime import timedelta as _timedelta
    session.next_cycle_at = timestamp + _timedelta(seconds=session.interval_seconds)

    return {
        "user_id": user_id,
        "cycle_id": cycle_id,
        "timestamp": timestamp,
        "analysis": analysis,
        "recommendations": len(ranked_signals),
        "executed": len(executed),
        "trades": executed,
        "provider": provider,
        "model": model,
        "regime": dominant_regime,
        "signals_scanned": len(raw_signals),
        "candidates": [
            {
                "symbol": signal["symbol"],
                "action": signal["action"],
                "confidence": signal["confidence"],
                "regime": signal.get("regime"),
                "price": signal.get("price"),
            }
            for signal in ranked_signals[:5]
        ],
    }


async def _auto_loop(user_id: str) -> None:
    """Background loop that runs auto-trading cycles for one user."""
    session = _session(user_id)
    logger.info(
        "Auto-trader started for user=%s (mode=%s interval=%ds)",
        user_id, session.mode, session.interval_seconds,
    )

    while session.enabled:
        try:
            _sync_daily_counter(session)
            if user_id != DEFAULT_AI_USER_ID and not session.auth_header:
                raise AutoTradingAuthError(
                    "Missing authorization for user-scoped auto-trading"
                )

            result = await run_cycle(
                user_id, session.auth_header, session.trades_today, session=session
            )
            session.last_run = result.get("timestamp")
            session.last_regime = result.get("regime")
            session.trades_today = min(
                MAX_DAILY_TRADES,
                session.trades_today + int(result.get("executed", 0)),
            )
            session.history.append(result)
            session.history = session.history[-AUTO_TRADING_HISTORY_LIMIT:]

            # Persist session snapshot to gluetrade_trading DB (in addition
            # to the existing Redis mirror)
            try:
                await auto_repository.upsert_session(
                    {
                        "user_id": user_id,
                        "portfolio_id": session.portfolio_id,
                        "enabled": session.enabled,
                        "mode": session.mode,
                        "interval_seconds": session.interval_seconds,
                        "last_cycle_at": session.heartbeat_at,
                        "next_cycle_at": session.next_cycle_at,
                        "heartbeat_at": session.heartbeat_at,
                        "cycles_today": int(session.trades_today),
                        "trades_today": int(session.trades_today),
                        "realized_pnl_today": Decimal(str(session.realized_pnl_today)),
                        "consecutive_losses": int(session.consecutive_losses),
                        "portfolio_value_start_of_day": session.portfolio_value_start_of_day,
                        "cooldown_symbols": dict(session.cooldown_symbols),
                        "config": dict(session.config),
                        "last_error": session.last_error,
                        "trade_day": session.trade_day,
                    }
                )
            except Exception as exc:
                logger.debug("auto_repository upsert_session failed: %s", exc)

            if not session.enabled:
                # Breaker tripped during run_cycle — exit the loop cleanly
                session.last_error = session.last_error or "Auto-trader disabled by circuit breaker"
                await _persist_session(user_id)
                logger.warning(
                    "Auto-trader disabled by breaker user=%s: %s",
                    user_id,
                    session.last_error,
                )
                break

            session.last_error = None
            await _persist_session(user_id)

            logger.info(
                "Auto-trade cycle user=%s: %d candidates, %d executed",
                user_id,
                result.get("recommendations", 0),
                result.get("executed", 0),
            )
        except AutoTradingAuthError as exc:
            session.last_error = str(exc)
            session.enabled = False
            await _persist_session(user_id)
            logger.warning("Auto-trader stopped for user=%s: %s", user_id, exc)
            break
        except asyncio.CancelledError:
            break
        except Exception:
            session.last_error = "Auto-trade loop error"
            await _persist_session(user_id)
            logger.exception("Auto-trade loop error for user=%s", user_id)

        try:
            await asyncio.sleep(session.interval_seconds or AUTO_TRADE_INTERVAL)
        except asyncio.CancelledError:
            break

    session.task = None
    await _persist_session(user_id)
    logger.info("Auto-trader stopped for user=%s", user_id)


async def start(
    user_id: str,
    auth_header: Optional[str] = None,
    *,
    restore: bool = False,
    mode: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """Start the auto-trading loop for a specific user.

    Extra params:
        mode: "paper" | "live" | "dry_run"
        portfolio_id: which portfolio the auto-trader operates on
        interval_seconds: cycle interval (overrides AUTO_TRADE_INTERVAL)
        config: per-user circuit-breaker overrides
    """
    session = _session(user_id)
    if auth_header:
        session.auth_header = auth_header
    if mode:
        session.mode = mode
    if portfolio_id is not None:
        session.portfolio_id = portfolio_id
    if interval_seconds:
        session.interval_seconds = max(60, min(int(interval_seconds), 3600))
    if config:
        merged = dict(session.config or {})
        merged.update(config)
        session.config = merged

    _sync_daily_counter(session)
    if session.enabled and session.task and not session.task.done():
        await _persist_session(user_id)
        return
    session.enabled = True
    if not restore and session.trade_day is None:
        session.trade_day = _today_utc()
    session.last_error = None
    session.task = asyncio.create_task(_auto_loop(user_id))
    await _persist_session(user_id)
    try:
        redis = await get_redis()
        await publish_sms_event(
            redis,
            user_id,
            "auto_armed",
            {
                "mode": session.mode,
                "interval_seconds": session.interval_seconds,
                "portfolio_id": session.portfolio_id,
            },
        )
    except Exception:
        pass


async def emergency_stop(user_id: str, *, reason: str = "user_initiated") -> Dict[str, Any]:
    """Cancel every open order + disable the session + publish SMS alert.

    Returns a summary ``{cancelled: N, errors: [...]}``.
    """
    session = _sessions.get(user_id)
    summary: Dict[str, Any] = {"cancelled": 0, "errors": []}

    # Disable the loop first so a new cycle doesn't race with the cancels.
    if session is not None:
        session.enabled = False
        task = session.task
        session.task = None
        if task and not task.done():
            task.cancel()
            try:
                await asyncio.gather(task, return_exceptions=True)
            except Exception:
                pass
        session.last_error = f"Emergency stop: {reason}"

    # Try to fetch open orders from trading-engine and cancel each
    auth_header = session.auth_header if session else None
    if auth_header:
        open_orders = await _fetch_json(
            f"{settings.TRADING_URL}/api/v1/orders/open",
            auth_header=auth_header,
        )
        if isinstance(open_orders, dict):
            order_list = open_orders.get("orders", []) or []
            async with httpx.AsyncClient(timeout=10.0) as client:
                for order in order_list:
                    order_id = order.get("id")
                    if not order_id:
                        continue
                    try:
                        resp = await client.delete(
                            f"{settings.TRADING_URL}/api/v1/orders/{order_id}",
                            headers={"Authorization": auth_header},
                        )
                        if resp.status_code < 400:
                            summary["cancelled"] = int(summary["cancelled"]) + 1
                        else:
                            summary["errors"].append(
                                f"{order_id}: HTTP {resp.status_code}"
                            )
                    except Exception as exc:
                        summary["errors"].append(f"{order_id}: {exc}")

    if session is not None:
        await _persist_session(user_id)

    try:
        redis = await get_redis()
        await publish_sms_event(
            redis,
            user_id,
            "emergency_halt",
            {"reason": reason, "cancelled": summary["cancelled"]},
        )
    except Exception:
        pass

    logger.warning(
        "Emergency stop user=%s reason=%s cancelled=%d errors=%d",
        user_id,
        reason,
        summary["cancelled"],
        len(summary["errors"]),
    )
    return summary


async def stop(user_id: str) -> None:
    """Stop the auto-trading loop for a specific user."""
    session = _sessions.get(user_id)
    if session is None:
        return
    session.enabled = False
    session.last_error = None
    task = session.task
    session.task = None
    if task and not task.done():
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    await _persist_session(user_id)
    try:
        redis = await get_redis()
        await publish_sms_event(redis, user_id, "auto_disarmed", {})
    except Exception:
        pass


async def update_config(
    user_id: str,
    *,
    mode: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    portfolio_id: Optional[str] = None,
    breakers: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Update auto-trader per-user config without stopping the loop."""
    session = _session(user_id)
    if mode is not None:
        session.mode = mode
    if interval_seconds is not None:
        session.interval_seconds = max(60, min(int(interval_seconds), 3600))
    if portfolio_id is not None:
        session.portfolio_id = portfolio_id
    if breakers:
        merged = dict(session.config or {})
        merged.update(breakers)
        session.config = merged
    await _persist_session(user_id)
    return {
        "mode": session.mode,
        "interval_seconds": session.interval_seconds,
        "portfolio_id": session.portfolio_id,
        "config": session.config,
    }


async def shutdown() -> None:
    """Stop all user sessions during service shutdown."""
    tasks: list[asyncio.Task[Any]] = []
    for user_id, session in _sessions.items():
        session.enabled = False
        if session.task and not session.task.done():
            session.task.cancel()
            tasks.append(session.task)
        session.task = None
        await _persist_session(user_id)

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def get_status(user_id: str) -> dict:
    """Get current auto-trading status for one user."""
    session = _session(user_id)
    _sync_daily_counter(session)
    return {
        "enabled": session.enabled,
        "mode": session.mode,
        "portfolio_id": session.portfolio_id,
        "cycle_id": session.cycle_id,
        "last_run": session.last_run,
        "last_regime": session.last_regime,
        "trades_today": session.trades_today,
        "max_daily_trades": MAX_DAILY_TRADES,
        "total_pnl": session.total_pnl,
        "realized_pnl_today": str(session.realized_pnl_today),
        "consecutive_losses": session.consecutive_losses,
        "cooldown_symbols": session.cooldown_symbols,
        "heartbeat_at": session.heartbeat_at.isoformat() if session.heartbeat_at else None,
        "next_cycle_at": session.next_cycle_at.isoformat() if session.next_cycle_at else None,
        "interval_seconds": session.interval_seconds or AUTO_TRADE_INTERVAL,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "config": session.config,
        "last_error": session.last_error,
    }


def get_history(user_id: str) -> list[dict]:
    """Get auto-trading decision history for one user."""
    session = _session(user_id)
    _sync_daily_counter(session)
    return list(reversed(session.history))
