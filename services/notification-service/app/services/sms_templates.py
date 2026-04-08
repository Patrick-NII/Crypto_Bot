"""Short SMS templates — one per event type (<= 160 chars each)."""

from __future__ import annotations

from typing import Any, Dict

# Templates rendered with .format(**payload). Missing keys fall back to
# the default value defined in ``_DEFAULTS``.
TEMPLATES: Dict[str, str] = {
    "trade_buy": "[GlueTrade] BUY {symbol} qty={quantity} @ {price}. Tx #{trade_short}",
    "trade_sell": "[GlueTrade] SELL {symbol} qty={quantity} @ {price}. P&L {pnl_sign}{pnl}. Tx #{trade_short}",
    "trade_failed": "[GlueTrade] Trade {side} {symbol} FAILED: {reason}",
    "stop_loss_hit": "[GlueTrade] Stop-loss declenche sur {symbol}. Perte: {loss_pct}%. Tx #{trade_short}",
    "take_profit_hit": "[GlueTrade] Take-profit atteint sur {symbol}. Gain: {gain_pct}%. Tx #{trade_short}",
    "circuit_breaker": "[GlueTrade] ALERTE: Auto-trading arrete. Raison: {reason}. Verifiez le compte.",
    "emergency_halt": "[GlueTrade] URGENT: arret d'urgence. {reason}. {cancelled} ordres annules.",
    "daily_recap": "[GlueTrade] Recap {date}: {trades_count} trades, P&L {pnl_sign}{pnl}.",
    "position_opened_large": "[GlueTrade] Position importante ouverte: {symbol} {pct_portfolio}% du portfolio.",
    "pnl_milestone": "[GlueTrade] Seuil P&L franchi: {pnl_sign}{pnl_pct}% aujourd'hui.",
    "auto_armed": "[GlueTrade] Auto-trading active ({mode}). Cycle: {interval_min}min.",
    "auto_disarmed": "[GlueTrade] Auto-trading desactive.",
    "heartbeat_miss": "[GlueTrade] Auto-trader ne repond plus (>{miss_min}min). Verifiez la connexion.",
    "new_login_unknown": "[GlueTrade] Connexion depuis une nouvelle IP: {ip} ({location}).",
    "api_key_error": "[GlueTrade] Cle API Binance invalide ou expiree. Verifiez les permissions.",
}


_DEFAULTS: Dict[str, Any] = {
    "symbol": "?",
    "side": "?",
    "quantity": "?",
    "price": "?",
    "pnl": "0",
    "pnl_sign": "",
    "pnl_pct": "0",
    "trade_short": "------",
    "reason": "inconnue",
    "loss_pct": "?",
    "gain_pct": "?",
    "cancelled": 0,
    "date": "",
    "trades_count": 0,
    "pct_portfolio": "?",
    "mode": "paper",
    "interval_min": 5,
    "miss_min": 10,
    "ip": "?",
    "location": "?",
}


class _SafeDict(dict):
    def __missing__(self, key):
        return _DEFAULTS.get(key, f"{{{key}}}")


def render(event_type: str, payload: Dict[str, Any]) -> str | None:
    """Render the SMS body for an event, or ``None`` if unknown."""
    template = TEMPLATES.get(event_type)
    if not template:
        return None

    merged: Dict[str, Any] = {**_DEFAULTS, **(payload or {})}
    # Convenience transforms
    if "pnl" in merged and "pnl_sign" not in (payload or {}):
        try:
            pnl_f = float(merged["pnl"])
            merged["pnl_sign"] = "+" if pnl_f >= 0 else ""
        except (TypeError, ValueError):
            merged["pnl_sign"] = ""
    # Trade group short id
    if "trade_group_id" in merged and merged.get("trade_group_id"):
        merged["trade_short"] = str(merged["trade_group_id"])[:6]

    try:
        return template.format_map(_SafeDict(merged))[:320]
    except Exception:
        return template[:320]
