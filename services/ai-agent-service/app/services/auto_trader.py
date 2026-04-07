"""Auto-Trading Agent — deterministic signal selection, scoped per user."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Any, Optional

import httpx

from app.core.auth import DEFAULT_AI_USER_ID, get_auth_ttl_seconds
from app.core.config import settings
from app.core.llm_router import Complexity, chat_completion
from app.memory.redis_client import get_redis

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


def _serializable_session(session: AutoTradingSession) -> dict[str, Any]:
    return {
        "enabled": session.enabled,
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
        trades_today=int(payload.get("trades_today", 0) or 0),
        last_run=payload.get("last_run"),
        last_regime=payload.get("last_regime"),
        total_pnl=float(payload.get("total_pnl", 0) or 0),
        history=history if isinstance(history, list) else [],
        auth_header=auth_header,
        last_error=payload.get("last_error"),
        trade_day=payload.get("trade_day"),
    )
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
) -> bool:
    """Execute a trade with mandatory preflight + retry + auto-conversion.

    Uses /orders/execute-with-conversion which:
    - Preflights the order
    - Handles conversion chains (e.g. EUR → USDT → BTC)
    - Retries with exponential backoff on rate limit / timeout
    """
    if quantity <= 0:
        return False

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
        return False

    status = response.get("status")
    steps = response.get("steps", [])

    if status == "filled":
        conversion_count = sum(1 for s in steps if s.get("note") == "conversion step")
        if conversion_count > 0:
            logger.info(
                "Auto-trade filled with %d conversion step(s): %s %s qty=%s",
                conversion_count, side, symbol, quantity,
            )
        else:
            logger.info("Auto-trade filled: %s %s qty=%s", side, symbol, quantity)
        return True

    error = response.get("error", {})
    logger.error(
        "Auto-trade failed: %s %s qty=%s strategy=%s code=%s reason=%s steps=%d",
        side, symbol, quantity, strategy,
        error.get("code", "UNKNOWN"),
        error.get("user_message", "unknown error"),
        len(steps),
    )
    return False


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


async def run_cycle(
    user_id: str,
    auth_header: Optional[str],
    trades_today: int,
) -> dict:
    """Run one auto-trading analysis cycle for a specific user."""
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

    executed: list[dict] = []
    for trade in cycle_trades:
        success = await _execute_trade(
            trade["symbol"],
            trade["action"],
            trade["quantity"],
            trade["strategy"],
            auth_header=auth_header,
        )
        if success:
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

    return {
        "user_id": user_id,
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
    logger.info("Auto-trader started for user=%s (interval=%ds)", user_id, AUTO_TRADE_INTERVAL)

    while session.enabled:
        try:
            _sync_daily_counter(session)
            if user_id != DEFAULT_AI_USER_ID and not session.auth_header:
                raise AutoTradingAuthError(
                    "Missing authorization for user-scoped auto-trading"
                )

            result = await run_cycle(user_id, session.auth_header, session.trades_today)
            session.last_run = result.get("timestamp")
            session.last_regime = result.get("regime")
            session.trades_today = min(
                MAX_DAILY_TRADES,
                session.trades_today + int(result.get("executed", 0)),
            )
            session.history.append(result)
            session.history = session.history[-AUTO_TRADING_HISTORY_LIMIT:]
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
            await asyncio.sleep(AUTO_TRADE_INTERVAL)
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
) -> None:
    """Start the auto-trading loop for a specific user."""
    session = _session(user_id)
    if auth_header:
        session.auth_header = auth_header
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
        "last_run": session.last_run,
        "last_regime": session.last_regime,
        "trades_today": session.trades_today,
        "max_daily_trades": MAX_DAILY_TRADES,
        "total_pnl": session.total_pnl,
        "interval_seconds": AUTO_TRADE_INTERVAL,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "last_error": session.last_error,
    }


def get_history(user_id: str) -> list[dict]:
    """Get auto-trading decision history for one user."""
    session = _session(user_id)
    _sync_daily_counter(session)
    return list(reversed(session.history))
