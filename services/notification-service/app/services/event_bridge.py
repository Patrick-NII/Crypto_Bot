"""Map Redis events to email templates and template data.

Each event coming from a producing service is normalised into a tuple
``(template_name, template_data, preference_key)`` so that the email dispatcher
can decide whether to send and what to render.

Producers are expected to enrich payloads with at least:
  - user_id      (uuid string)
  - user_email   (the recipient)
  - username     (display name)
  - user_timezone (optional, for date formatting)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Mapping of (channel, event_type) -> (template, preference_key)
_ROUTING: dict[tuple[str, str], tuple[str, str]] = {
    # Trading orders
    ("trading:user-orders", "order_filled_buy"): ("trade_buy_confirmation", "email_trades"),
    ("trading:user-orders", "order_filled_sell"): ("trade_sell_confirmation", "email_trades"),
    # Deposits / withdrawals
    ("trading:user-deposits", "deposit"): ("deposit_confirmation", "email_deposits"),
    ("trading:user-deposits", "withdrawal"): ("withdrawal_confirmation", "email_deposits"),
    # Security
    ("auth:security", "login"): ("login_notification", "email_security"),
    ("auth:security", "password_changed"): ("security_alert", "email_security"),
}


def classify_event(channel: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return event metadata or None if event is not handled."""
    event_type = payload.get("event_type") or payload.get("type")
    if not event_type:
        return None

    routing = _ROUTING.get((channel, event_type))
    if routing is None:
        return None

    template, pref_key = routing
    return {
        "template": template,
        "preference_key": pref_key,
        "user_id": payload.get("user_id"),
        "user_email": payload.get("user_email"),
        "username": payload.get("username") or payload.get("user_email", "trader"),
    }


def _fmt_money(value: Any, currency: str = "USDT") -> str:
    try:
        return f"{float(value):,.2f} {currency}"
    except (TypeError, ValueError):
        return f"{value} {currency}"


def _fmt_amount(value: Any, decimals: int = 6) -> str:
    try:
        return f"{float(value):,.{decimals}f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


def _fmt_datetime(value: Any, tz_name: str | None = None) -> str:
    if value is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    elif isinstance(value, datetime):
        dt = value
    else:
        return str(value)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def build_template_payload(template: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Transform a Redis event payload into the data dict for the Jinja template."""
    base = {
        "username": payload.get("username") or "trader",
        "exchange": payload.get("exchange") or "Binance",
    }

    if template in ("trade_buy_confirmation", "trade_sell_confirmation"):
        symbol = payload.get("symbol") or payload.get("pair") or ""
        quote = payload.get("quote_currency") or "USDT"
        quantity = payload.get("filled_quantity") or payload.get("quantity") or 0
        price = payload.get("avg_price") or payload.get("price") or 0
        try:
            total_val = float(quantity) * float(price)
        except (TypeError, ValueError):
            total_val = 0.0
        base.update(
            {
                "symbol": symbol,
                "quantity": _fmt_amount(quantity),
                "price": _fmt_money(price, quote),
                "total": _fmt_money(total_val, quote),
                "fee": _fmt_money(payload["fee"], quote) if payload.get("fee") else "",
                "order_id": payload.get("order_id") or payload.get("id") or "",
            }
        )
        if template == "trade_sell_confirmation" and payload.get("realized_pnl") is not None:
            try:
                pnl_val = float(payload["realized_pnl"])
                base["pnl"] = _fmt_money(pnl_val, quote)
                base["pnl_color"] = "#06d6a0" if pnl_val >= 0 else "#ef4444"
            except (TypeError, ValueError):
                pass

    elif template == "deposit_confirmation":
        base.update(
            {
                "asset": payload.get("asset") or "USDT",
                "amount": _fmt_amount(payload.get("amount", 0)),
                "value_usd": _fmt_money(payload["value_usd"], "USD") if payload.get("value_usd") else "",
                "deposit_time": _fmt_datetime(payload.get("timestamp")),
                "tx_id": payload.get("tx_id", ""),
            }
        )

    elif template == "withdrawal_confirmation":
        base.update(
            {
                "asset": payload.get("asset") or "USDT",
                "amount": _fmt_amount(payload.get("amount", 0)),
                "value_usd": _fmt_money(payload["value_usd"], "USD") if payload.get("value_usd") else "",
                "withdrawal_time": _fmt_datetime(payload.get("timestamp")),
                "destination": payload.get("destination", ""),
                "tx_id": payload.get("tx_id", ""),
            }
        )

    elif template == "login_notification":
        base.update(
            {
                "login_time": _fmt_datetime(payload.get("timestamp")),
                "ip_address": payload.get("ip_address") or payload.get("ip") or "unknown",
                "location": payload.get("location", ""),
                "user_agent": payload.get("user_agent", ""),
                "security_url": payload.get("security_url", ""),
            }
        )

    elif template == "security_alert":
        base.update(
            {
                "event": payload.get("subject") or "Security event",
                "details": payload.get("details") or "",
            }
        )

    return base
