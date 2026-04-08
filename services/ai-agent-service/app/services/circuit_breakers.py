"""Circuit breakers for the auto-trader.

Four layers of protection (all enabled by default, each configurable):

1. **Max daily loss** — stops the auto if realized P&L today falls below a
   % of the portfolio value at start of day.
2. **Max consecutive losses** — stops after N losing trades in a row.
3. **Symbol cooldown** — after a stop-loss hit, blocks re-entry on the same
   symbol for N minutes.
4. **Heartbeat dead-man switch** — if the cycle has not produced a
   ``heartbeat_at`` update for more than ``max_heartbeat_miss_seconds``,
   surface a warning (no auto-stop — the loop is already dead, we just
   notify).

The breakers are applied at the start of every cycle via
``check_all(session_state)``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Default thresholds — overridable via ``AutoSession.config`` per user
DEFAULTS: Dict[str, Any] = {
    "max_daily_loss_pct": 5.0,       # stop if loss > 5% of opening value
    "max_consecutive_losses": 3,
    "symbol_cooldown_minutes": 30,   # after SL hit
    "heartbeat_max_miss_seconds": 900,  # 3 × default interval (5 min)
}


@dataclass
class BreakerResult:
    ok: bool
    reason: Optional[str] = None
    action: Optional[str] = None  # "stop" | "warn"


def _config_value(config: Optional[Dict[str, Any]], key: str) -> Any:
    if config and key in config:
        return config[key]
    return DEFAULTS[key]


def check_max_daily_loss(session_state: Dict[str, Any]) -> BreakerResult:
    start_value = session_state.get("portfolio_value_start_of_day")
    realized = session_state.get("realized_pnl_today", Decimal("0"))
    if start_value is None:
        return BreakerResult(ok=True)
    try:
        start_d = Decimal(str(start_value))
        pnl_d = Decimal(str(realized))
    except Exception:
        return BreakerResult(ok=True)
    if start_d <= 0:
        return BreakerResult(ok=True)
    max_loss_pct = Decimal(str(_config_value(session_state.get("config"), "max_daily_loss_pct")))
    loss_pct = (pnl_d / start_d) * Decimal("100")
    if loss_pct <= -max_loss_pct:
        return BreakerResult(
            ok=False,
            reason=f"Max daily loss reached: {loss_pct:.2f}% <= -{max_loss_pct}%",
            action="stop",
        )
    return BreakerResult(ok=True)


def check_consecutive_losses(session_state: Dict[str, Any]) -> BreakerResult:
    count = int(session_state.get("consecutive_losses", 0))
    max_count = int(_config_value(session_state.get("config"), "max_consecutive_losses"))
    if count >= max_count:
        return BreakerResult(
            ok=False,
            reason=f"Max consecutive losses reached: {count}/{max_count}",
            action="stop",
        )
    return BreakerResult(ok=True)


def check_heartbeat(session_state: Dict[str, Any]) -> BreakerResult:
    heartbeat = session_state.get("heartbeat_at")
    if heartbeat is None:
        return BreakerResult(ok=True)  # First cycle — no prior heartbeat
    max_miss_s = int(_config_value(session_state.get("config"), "heartbeat_max_miss_seconds"))
    try:
        last_beat: datetime = heartbeat if isinstance(heartbeat, datetime) else datetime.fromisoformat(str(heartbeat))
        if last_beat.tzinfo is None:
            last_beat = last_beat.replace(tzinfo=timezone.utc)
    except Exception:
        return BreakerResult(ok=True)
    delta = (datetime.now(timezone.utc) - last_beat).total_seconds()
    if delta > max_miss_s:
        return BreakerResult(
            ok=False,
            reason=f"Heartbeat dead-man: last beat {int(delta)}s ago (max {max_miss_s}s)",
            action="warn",
        )
    return BreakerResult(ok=True)


def is_symbol_in_cooldown(session_state: Dict[str, Any], symbol: str) -> bool:
    cooldowns = session_state.get("cooldown_symbols") or {}
    expires = cooldowns.get(symbol.upper())
    if not expires:
        return False
    try:
        expires_at = expires if isinstance(expires, datetime) else datetime.fromisoformat(str(expires))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
    except Exception:
        return False
    return datetime.now(timezone.utc) < expires_at


def add_symbol_cooldown(
    session_state: Dict[str, Any],
    symbol: str,
    minutes: Optional[int] = None,
) -> None:
    if minutes is None:
        minutes = int(_config_value(session_state.get("config"), "symbol_cooldown_minutes"))
    cooldowns = dict(session_state.get("cooldown_symbols") or {})
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    cooldowns[symbol.upper()] = expires_at.isoformat()
    session_state["cooldown_symbols"] = cooldowns
    logger.info(
        "Cooldown added: %s until %s (%d min)", symbol, expires_at.isoformat(), minutes
    )


def register_trade_outcome(
    session_state: Dict[str, Any],
    *,
    pnl: float,
    symbol: Optional[str] = None,
    was_stop_loss: bool = False,
) -> None:
    """Update session counters after a trade closes.

    - Increments ``consecutive_losses`` if pnl < 0; resets to 0 if pnl >= 0.
    - Adds realized pnl to ``realized_pnl_today``.
    - If the trade closed via stop-loss, arm a cooldown on the symbol.
    """
    pnl_d = Decimal(str(pnl))
    current_total = Decimal(str(session_state.get("realized_pnl_today") or 0))
    session_state["realized_pnl_today"] = current_total + pnl_d

    if pnl_d < 0:
        session_state["consecutive_losses"] = int(session_state.get("consecutive_losses", 0)) + 1
    else:
        session_state["consecutive_losses"] = 0

    if was_stop_loss and symbol:
        add_symbol_cooldown(session_state, symbol)


def check_all(session_state: Dict[str, Any]) -> BreakerResult:
    """Run all breakers in order — returns the first one that trips."""
    for check in (check_max_daily_loss, check_consecutive_losses, check_heartbeat):
        result = check(session_state)
        if not result.ok:
            return result
    return BreakerResult(ok=True)
