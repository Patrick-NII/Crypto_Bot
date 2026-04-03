"""Builds context data for each agent by fetching from other microservices."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_http: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=10.0)
    return _http


async def _get(url: str) -> Any:
    try:
        resp = await _client().get(url)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning("Context fetch failed: %s — %s", url, e)
        return None


async def get_dashboard_context(user_id: str) -> dict:
    """Fetch data relevant to the dashboard agent."""
    market = await _get(f"{settings.MARKET_DATA_URL}/api/v1/markets/top?limit=10")
    fear = await _get(f"{settings.MARKET_DATA_URL}/api/v1/markets/fear-greed")
    portfolio = await _get(f"{settings.PORTFOLIO_URL}/api/v1/portfolios/")
    return {
        "top_market": market,
        "fear_greed": fear,
        "portfolios": portfolio,
    }


async def get_portfolio_context(user_id: str) -> dict:
    """Fetch data relevant to the portfolio agent."""
    portfolios = await _get(f"{settings.PORTFOLIO_URL}/api/v1/portfolios/")
    positions = None
    if portfolios and isinstance(portfolios, list) and len(portfolios) > 0:
        pid = portfolios[0].get("id")
        if pid:
            positions = await _get(f"{settings.PORTFOLIO_URL}/api/v1/portfolios/{pid}/positions")
    return {
        "portfolios": portfolios,
        "positions": positions,
    }


async def get_trading_context(user_id: str) -> dict:
    """Fetch data relevant to the trading agent."""
    balances = await _get(f"{settings.TRADING_URL}/api/v1/trading/paper/balances")
    orders = await _get(f"{settings.TRADING_URL}/api/v1/trading/orders")
    return {
        "balances": balances,
        "recent_orders": orders,
    }


async def get_strategy_context(user_id: str) -> dict:
    """Fetch data relevant to the strategy agent."""
    strategies = await _get(f"{settings.STRATEGY_URL}/api/v1/ml/strategies")
    return {
        "strategies": strategies,
    }


async def get_risk_context(user_id: str) -> dict:
    """Fetch data relevant to the risk agent."""
    risk = await _get(f"{settings.RISK_URL}/api/v1/risk/portfolio")
    return {
        "risk_assessment": risk,
    }


async def get_analytics_context(user_id: str) -> dict:
    """Fetch data relevant to the analytics agent."""
    metrics = await _get(f"{settings.RISK_URL}/api/v1/risk/metrics")
    return {
        "metrics": metrics,
    }


CONTEXT_BUILDERS = {
    "dashboard": get_dashboard_context,
    "portfolio": get_portfolio_context,
    "trading": get_trading_context,
    "strategy": get_strategy_context,
    "risk": get_risk_context,
    "analytics": get_analytics_context,
}


async def build_context(agent_type: str, user_id: str) -> str:
    """Build a context string for the given agent type."""
    builder = CONTEXT_BUILDERS.get(agent_type)
    if not builder:
        return ""

    data = await builder(user_id)
    if not data:
        return ""

    parts = []
    for key, value in data.items():
        if value is not None:
            parts.append(f"[{key}]: {value}")
    return "\n".join(parts)
