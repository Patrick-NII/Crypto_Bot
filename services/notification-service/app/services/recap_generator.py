"""Build the daily recap payload (portfolio + trades + LLM analysis)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_FR = (
    "Tu es un coach de trading crypto bienveillant et pédagogue. "
    "Tu rédiges en français un récap quotidien personnalisé pour le trader. "
    "Reste factuel, basé sur les chiffres fournis, sans jargon excessif. "
    "Ne donne JAMAIS de conseil financier garanti — seulement des observations et pistes."
)


def _build_user_message(stats: dict[str, Any]) -> str:
    """Construct the prompt that the LLM will see."""
    portfolio_value = stats.get("portfolio_value", "N/A")
    pnl_24h_pct = stats.get("pnl_24h_pct", 0)
    trades_count = stats.get("trades_count", 0)
    buys = stats.get("buys", 0)
    sells = stats.get("sells", 0)
    btc_change = stats.get("btc_change_pct", 0)
    eth_change = stats.get("eth_change_pct", 0)
    top_signal = stats.get("top_signal") or "Aucun signal fort"
    style = stats.get("ai_behavior_style", "balanced")

    return (
        f"Données du jour pour le récap utilisateur :\n"
        f"- Portefeuille total : {portfolio_value}\n"
        f"- Variation 24h : {pnl_24h_pct:+.2f}%\n"
        f"- Trades exécutés : {trades_count} ({buys} achats, {sells} ventes)\n"
        f"- Signal fort actif : {top_signal}\n"
        f"- Marché : BTC {btc_change:+.2f}%, ETH {eth_change:+.2f}%\n"
        f"- Style préféré : {style}\n\n"
        "Génère un récap structuré en deux sections :\n"
        "1) ANALYSE DU JOUR (2 phrases) : ce qui s'est passé sur le portefeuille et le marché.\n"
        "2) CONSEILS POUR DEMAIN (2 à 3 puces concises) : actions concrètes à envisager.\n\n"
        "Ton : adapté au style préféré. Maximum 150 mots au total. "
        "Sépare les deux sections par une ligne contenant exactement '---'."
    )


def _split_analysis(text: str) -> tuple[str, str]:
    """Split the LLM output into (summary, advice) on the '---' delimiter."""
    if "---" in text:
        parts = text.split("---", 1)
        return parts[0].strip(), parts[1].strip()
    return text.strip(), ""


async def _fetch_portfolio_snapshot(
    client: httpx.AsyncClient,
    auth_header: str | None,
) -> dict[str, Any]:
    """Best-effort portfolio snapshot. Returns {} on failure."""
    if not auth_header:
        return {}
    try:
        resp = await client.get(
            f"{settings.PORTFOLIO_SERVICE_URL}/api/v1/portfolio/snapshot",
            headers={"Authorization": auth_header},
            timeout=5.0,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as exc:
        logger.debug("Portfolio snapshot failed: %s", exc)
    return {}


async def _fetch_recent_trades(
    client: httpx.AsyncClient,
    auth_header: str | None,
) -> list[dict[str, Any]]:
    if not auth_header:
        return []
    try:
        resp = await client.get(
            f"{settings.TRADING_SERVICE_URL}/api/v1/orders/history",
            headers={"Authorization": auth_header},
            params={"limit": 20},
            timeout=5.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("orders", []) or data.get("items", [])
    except Exception as exc:
        logger.debug("Trades history failed: %s", exc)
    return []


async def _fetch_market_context(client: httpx.AsyncClient) -> dict[str, Any]:
    try:
        resp = await client.get(
            f"{settings.MARKET_DATA_SERVICE_URL}/api/v1/prices",
            params={"symbols": "BTC,ETH"},
            timeout=5.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data
            if isinstance(data, list):
                return {item.get("symbol", ""): item for item in data}
    except Exception as exc:
        logger.debug("Market context failed: %s", exc)
    return {}


def _extract_pnl_pct(snapshot: dict[str, Any]) -> float:
    for key in ("pnl_24h_pct", "change_24h_pct", "performance_24h_pct"):
        value = snapshot.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return 0.0


def _filter_today(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    out: list[dict[str, Any]] = []
    for trade in trades:
        ts = trade.get("created_at") or trade.get("timestamp") or trade.get("filled_at")
        if not ts:
            continue
        try:
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            elif isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            else:
                continue
            if dt >= cutoff:
                out.append(trade)
        except (ValueError, TypeError):
            continue
    return out


def _market_change_pct(market: dict[str, Any], symbol: str) -> float:
    entry = market.get(symbol) or market.get(f"{symbol}USDT") or {}
    for key in ("change_24h_pct", "change_pct", "percent_change_24h"):
        value = entry.get(key) if isinstance(entry, dict) else None
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return 0.0


async def _call_llm(stats: dict[str, Any]) -> tuple[str, str]:
    """Call the ai-agent-service /completion endpoint. Returns (summary, advice)."""
    user_message = _build_user_message(stats)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.AI_AGENT_SERVICE_URL}/api/v1/ai/completion",
                json={
                    "system_prompt": SYSTEM_PROMPT_FR,
                    "user_message": user_message,
                },
            )
            if resp.status_code == 200:
                text = resp.json().get("text", "")
                return _split_analysis(text)
            logger.warning("LLM completion HTTP %s: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("LLM call failed, using fallback summary: %s", exc)

    # Fallback (no LLM available)
    fallback = (
        f"Aujourd'hui, votre portefeuille est valorisé à {stats.get('portfolio_value', 'N/A')} "
        f"avec une variation de {stats.get('pnl_24h_pct', 0):+.2f}% sur 24h. "
        f"Vous avez exécuté {stats.get('trades_count', 0)} ordres."
    )
    advice = "Surveillez les niveaux clés de BTC/ETH et adaptez votre exposition au risque."
    return fallback, advice


async def generate_daily_recap(
    user: dict[str, Any],
    auth_header: str | None = None,
) -> dict[str, Any]:
    """Build the data dict that gets passed to the daily_recap.html template.

    `user` is expected to contain at minimum: id, email, username,
    ai_behavior_style, timezone.
    """
    async with httpx.AsyncClient() as client:
        snapshot = await _fetch_portfolio_snapshot(client, auth_header)
        trades = await _fetch_recent_trades(client, auth_header)
        market = await _fetch_market_context(client)

    today_trades = _filter_today(trades)
    buys = sum(1 for t in today_trades if str(t.get("side", "")).lower() == "buy")
    sells = sum(1 for t in today_trades if str(t.get("side", "")).lower() == "sell")

    pnl_pct = _extract_pnl_pct(snapshot)
    portfolio_value = snapshot.get("total_value")
    if portfolio_value is not None:
        try:
            portfolio_value = f"{float(portfolio_value):,.2f} USD"
        except (TypeError, ValueError):
            portfolio_value = str(portfolio_value)
    else:
        portfolio_value = "N/A"

    btc_change = _market_change_pct(market, "BTC")
    eth_change = _market_change_pct(market, "ETH")

    stats = {
        "portfolio_value": portfolio_value,
        "pnl_24h_pct": pnl_pct,
        "trades_count": len(today_trades),
        "buys": buys,
        "sells": sells,
        "btc_change_pct": btc_change,
        "eth_change_pct": eth_change,
        "top_signal": None,
        "ai_behavior_style": user.get("ai_behavior_style", "balanced"),
    }

    summary, advice = await _call_llm(stats)

    top_trades = [
        {
            "side": str(t.get("side", "")).lower(),
            "symbol": t.get("symbol", ""),
            "amount": str(t.get("filled_quantity") or t.get("quantity", "")),
        }
        for t in today_trades[:5]
    ]

    return {
        "username": user.get("username", "trader"),
        "recap_date": datetime.now(timezone.utc).strftime("%d/%m/%Y"),
        "portfolio_value": portfolio_value,
        "pnl_24h": f"{pnl_pct:+.2f}%",
        "pnl_color": "#06d6a0" if pnl_pct >= 0 else "#ef4444",
        "trades_count": len(today_trades),
        "buys": buys,
        "sells": sells,
        "top_trades": top_trades,
        "market_context": {
            "btc": f"{btc_change:+.2f}%",
            "eth": f"{eth_change:+.2f}%",
        },
        "btc_color": "#06d6a0" if btc_change >= 0 else "#ef4444",
        "eth_color": "#06d6a0" if eth_change >= 0 else "#ef4444",
        "ai_summary": summary,
        "ai_advice": advice,
        "dashboard_url": f"{settings.FRONTEND_URL}/portfolio",
        "settings_url": f"{settings.FRONTEND_URL}/settings",
    }
