"""Builds context data for each agent by fetching from other microservices."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_http: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=10.0)
    return _http


async def _get(url: str, auth_header: Optional[str] = None) -> Any:
    try:
        headers = {"Authorization": auth_header} if auth_header else None
        resp = await _client().get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning("Context fetch failed: %s — %s", url, e)
        return None


async def get_dashboard_context(user_id: str, auth_header: Optional[str] = None) -> dict:
    """Fetch data relevant to the dashboard agent."""
    market = await _get(f"{settings.MARKET_DATA_URL}/api/v1/markets/top?limit=10")
    fear = await _get(f"{settings.MARKET_DATA_URL}/api/v1/markets/fear-greed")
    portfolio = await _get(f"{settings.PORTFOLIO_URL}/api/v1/portfolios/snapshot", auth_header)
    user_profile = await _get(f"{settings.AUTH_URL}/api/v1/auth/me", auth_header) if auth_header else None
    return {
        "user_profile": user_profile,
        "top_market": market,
        "fear_greed": fear,
        "portfolio_snapshot": portfolio,
    }


async def get_portfolio_context(user_id: str, auth_header: Optional[str] = None) -> dict:
    """Fetch data relevant to the portfolio agent."""
    snapshot = await _get(f"{settings.PORTFOLIO_URL}/api/v1/portfolios/snapshot", auth_header)
    user_profile = await _get(f"{settings.AUTH_URL}/api/v1/auth/me", auth_header) if auth_header else None
    return {
        "user_profile": user_profile,
        "portfolio_snapshot": snapshot,
    }


async def get_trading_context(user_id: str, auth_header: Optional[str] = None) -> dict:
    """Fetch data relevant to the trading agent."""
    snapshot = await _get(f"{settings.PORTFOLIO_URL}/api/v1/portfolios/snapshot", auth_header)
    orders = await _get(f"{settings.TRADING_URL}/api/v1/orders?limit=20", auth_header)
    user_profile = await _get(f"{settings.AUTH_URL}/api/v1/auth/me", auth_header) if auth_header else None
    return {
        "user_profile": user_profile,
        "portfolio_snapshot": snapshot,
        "recent_orders": orders,
    }


async def get_strategy_context(user_id: str, auth_header: Optional[str] = None) -> dict:
    """Fetch data relevant to the strategy agent."""
    strategies = await _get(f"{settings.TRADING_URL}/api/v1/strategies")
    signal_universe = await _get(f"{settings.STRATEGY_URL}/api/v1/ml/signals?limit=8")
    user_profile = await _get(f"{settings.AUTH_URL}/api/v1/auth/me", auth_header) if auth_header else None
    return {
        "user_profile": user_profile,
        "strategies": strategies,
        "signal_universe": signal_universe,
    }


async def get_risk_context(user_id: str, auth_header: Optional[str] = None) -> dict:
    """Fetch data relevant to the risk agent."""
    risk_profile = await _get(f"{settings.RISK_URL}/api/v1/risk/profile", auth_header)
    risk_metrics = await _get(f"{settings.RISK_URL}/api/v1/risk/metrics", auth_header)
    user_profile = await _get(f"{settings.AUTH_URL}/api/v1/auth/me", auth_header) if auth_header else None
    return {
        "user_profile": user_profile,
        "risk_profile": risk_profile,
        "risk_metrics": risk_metrics,
    }


async def get_analytics_context(user_id: str, auth_header: Optional[str] = None) -> dict:
    """Fetch data relevant to the analytics agent."""
    metrics = await _get(f"{settings.RISK_URL}/api/v1/risk/metrics", auth_header)
    user_profile = await _get(f"{settings.AUTH_URL}/api/v1/auth/me", auth_header) if auth_header else None
    return {
        "user_profile": user_profile,
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


async def build_context(agent_type: str, user_id: str, auth_header: Optional[str] = None) -> str:
    """Build a context string for the given agent type."""
    builder = CONTEXT_BUILDERS.get(agent_type)
    if not builder:
        return ""

    data = await builder(user_id, auth_header)
    if not data:
        return ""

    parts = []
    for key, value in data.items():
        if value is not None:
            parts.append(f"[{key}]: {value}")
    return "\n".join(parts)
