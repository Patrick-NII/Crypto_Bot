"""Telegram message templates — one per event type, HTML-formatted.

Telegram supports HTML and Markdown. We use HTML for safer escaping. Each
template fits the same event taxonomy as the SMS templates so the
auto-trader can publish a single event and both dispatchers consume it.
"""

from __future__ import annotations

from typing import Any, Dict

# HTML templates rendered with .format(**payload) via SafeDict.
TEMPLATES: Dict[str, str] = {
    "trade_buy": (
        "<b>BUY {symbol}</b>\n"
        "Quantite: <code>{quantity}</code>\n"
        "Prix: <code>{price}</code>\n"
        "Tx: <code>#{trade_short}</code>"
    ),
    "trade_sell": (
        "<b>SELL {symbol}</b>\n"
        "Quantite: <code>{quantity}</code>\n"
        "Prix: <code>{price}</code>\n"
        "P&L: <b>{pnl_sign}{pnl}</b>\n"
        "Tx: <code>#{trade_short}</code>"
    ),
    "trade_failed": (
        "<b>Trade ECHEC</b>\n"
        "Symbol: <code>{symbol}</code>\n"
        "Side: {side}\n"
        "Raison: {reason}"
    ),
    "stop_loss_hit": (
        "<b>Stop-Loss declenche</b>\n"
        "Symbol: <code>{symbol}</code>\n"
        "Perte: {loss_pct}%\n"
        "Tx: <code>#{trade_short}</code>"
    ),
    "take_profit_hit": (
        "<b>Take-Profit atteint</b>\n"
        "Symbol: <code>{symbol}</code>\n"
        "Gain: {gain_pct}%\n"
        "Tx: <code>#{trade_short}</code>"
    ),
    "circuit_breaker": (
        "<b>ALERTE: Auto-trading arrete</b>\n"
        "Raison: {reason}\n"
        "Verifiez votre compte."
    ),
    "emergency_halt": (
        "<b>URGENT: Arret d'urgence</b>\n"
        "Raison: {reason}\n"
        "Ordres annules: <code>{cancelled}</code>"
    ),
    "daily_recap": (
        "<b>Recap {date}</b>\n"
        "Trades: <code>{trades_count}</code>\n"
        "P&L: <b>{pnl_sign}{pnl}</b>"
    ),
    "position_opened_large": (
        "<b>Position importante ouverte</b>\n"
        "Symbol: <code>{symbol}</code>\n"
        "Pourcentage: {pct_portfolio}%"
    ),
    "pnl_milestone": (
        "<b>Seuil P&amp;L franchi</b>\n"
        "Variation: <b>{pnl_sign}{pnl_pct}%</b>"
    ),
    "auto_armed": (
        "<b>Auto-trading active</b>\n"
        "Mode: <code>{mode}</code>\n"
        "Cycle: {interval_min} min"
    ),
    "auto_disarmed": "<b>Auto-trading desactive</b>",
    "heartbeat_miss": (
        "<b>Auto-trader: heartbeat manquant</b>\n"
        "Aucun signe de vie depuis {miss_min} minutes.\n"
        "Verifiez la connexion."
    ),
    "new_login_unknown": (
        "<b>Nouvelle connexion</b>\n"
        "IP: <code>{ip}</code>\n"
        "Localisation: {location}"
    ),
    "api_key_error": (
        "<b>Cle API Binance invalide</b>\n"
        "Verifiez les permissions dans Settings."
    ),
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
    """Render the Telegram message body for an event, or None if unknown."""
    template = TEMPLATES.get(event_type)
    if not template:
        return None

    merged: Dict[str, Any] = {**_DEFAULTS, **(payload or {})}
    if "pnl" in merged and "pnl_sign" not in (payload or {}):
        try:
            pnl_f = float(merged["pnl"])
            merged["pnl_sign"] = "+" if pnl_f >= 0 else ""
        except (TypeError, ValueError):
            merged["pnl_sign"] = ""
    if merged.get("trade_group_id"):
        merged["trade_short"] = str(merged["trade_group_id"])[:6]

    try:
        return template.format_map(_SafeDict(merged))[:4000]
    except Exception:
        return template[:4000]
