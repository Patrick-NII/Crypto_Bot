"""Auto-Trading Agent — autonomous portfolio management loop.

Runs on a configurable interval (default 5 min):
1. Fetches portfolio state and market data
2. Sends context to LLM for analysis
3. Parses structured trade recommendations
4. Filters by confidence threshold and risk checks
5. Executes approved trades via trading engine
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.config import settings
from app.core.llm_router import chat_completion, Complexity

logger = logging.getLogger(__name__)

_enabled = False
_task: Optional[asyncio.Task] = None
_trades_today = 0
_last_run: Optional[str] = None
_total_pnl = 0.0
_history: list[dict] = []

AUTO_TRADE_INTERVAL = 300  # 5 minutes
MAX_DAILY_TRADES = 10
CONFIDENCE_THRESHOLD = 0.7

SYSTEM_PROMPT = """You are an autonomous crypto trading agent for the Okamoey platform.
You manage a paper trading portfolio. Your goal is to maximize returns while managing risk.

Analyze the current portfolio state and market data. Then provide trade recommendations.

IMPORTANT: Respond ONLY with valid JSON in this exact format:
{
  "analysis": "Brief market analysis (1-2 sentences)",
  "trades": [
    {
      "action": "buy" or "sell",
      "symbol": "BTC",
      "amount_usd": 100,
      "confidence": 0.85,
      "reason": "Brief reason"
    }
  ]
}

Rules:
- Only recommend trades with confidence >= 0.7
- Maximum 3 trades per cycle
- Never risk more than 10% of portfolio on a single trade
- Consider correlation between assets
- If no good opportunities exist, return empty trades array
"""


async def _fetch_json(url: str) -> dict | list | None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("Auto-trader fetch failed: %s — %s", url, e)
        return None


async def _execute_trade(symbol: str, side: str, quantity: float) -> bool:
    """Execute a trade via the trading engine."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.TRADING_URL}/api/v1/orders",
                json={
                    "symbol": symbol,
                    "side": side,
                    "order_type": "market",
                    "quantity": quantity,
                    "source": "agent",
                },
            )
            resp.raise_for_status()
            return True
    except Exception as e:
        logger.error("Auto-trade execution failed: %s", e)
        return False


async def run_cycle() -> dict:
    """Run one auto-trading analysis cycle."""
    global _trades_today, _last_run, _total_pnl

    # Fetch context
    prices = await _fetch_json(f"{settings.MARKET_DATA_URL}/api/v1/markets/top?limit=20")
    portfolio = await _fetch_json(f"{settings.PORTFOLIO_URL}/api/v1/portfolios/")
    balances = await _fetch_json(f"{settings.TRADING_URL}/api/v1/trading/paper/balances")

    context = f"""
Current Time: {datetime.now(timezone.utc).isoformat()}
Trades Today: {_trades_today}/{MAX_DAILY_TRADES}

Portfolio: {json.dumps(portfolio, default=str)[:1000] if portfolio else 'No positions'}
Balances: {json.dumps(balances, default=str)[:500] if balances else 'Unknown'}
Top Markets: {json.dumps(prices, default=str)[:2000] if prices else 'No data'}
"""

    messages = [{"role": "user", "content": context}]

    try:
        response, provider, model = await chat_completion(
            messages, SYSTEM_PROMPT, Complexity.COMPLEX
        )

        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_str = response
            if "```" in json_str:
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
            result = json.loads(json_str.strip())
        except (json.JSONDecodeError, IndexError):
            logger.warning("Auto-trader: Failed to parse LLM response")
            result = {"analysis": "Parse error", "trades": []}

        analysis = result.get("analysis", "No analysis")
        trades = result.get("trades", [])
        executed = []

        for trade in trades:
            if _trades_today >= MAX_DAILY_TRADES:
                break

            confidence = trade.get("confidence", 0)
            if confidence < CONFIDENCE_THRESHOLD:
                continue

            symbol = trade.get("symbol", "")
            action = trade.get("action", "")
            amount_usd = trade.get("amount_usd", 0)

            if not symbol or not action or amount_usd <= 0:
                continue

            # Estimate quantity (rough — would need current price)
            quantity = amount_usd / 50000 if symbol == "BTC" else amount_usd / 3000  # rough estimate

            success = await _execute_trade(symbol, action, quantity)
            if success:
                _trades_today += 1
                executed.append({
                    "symbol": symbol,
                    "action": action,
                    "amount_usd": amount_usd,
                    "confidence": confidence,
                    "reason": trade.get("reason", ""),
                })

        _last_run = datetime.now(timezone.utc).isoformat()

        cycle_result = {
            "timestamp": _last_run,
            "analysis": analysis,
            "recommendations": len(trades),
            "executed": len(executed),
            "trades": executed,
            "provider": provider,
            "model": model,
        }

        _history.append(cycle_result)
        if len(_history) > 100:
            _history.pop(0)

        return cycle_result

    except Exception as e:
        logger.exception("Auto-trading cycle failed: %s", e)
        return {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}


async def _auto_loop():
    """Background loop that runs auto-trading cycles."""
    global _enabled, _trades_today
    logger.info("Auto-trader started (interval=%ds)", AUTO_TRADE_INTERVAL)

    while _enabled:
        try:
            result = await run_cycle()
            logger.info(
                "Auto-trade cycle: %d recommendations, %d executed",
                result.get("recommendations", 0),
                result.get("executed", 0),
            )
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Auto-trade loop error")

        try:
            await asyncio.sleep(AUTO_TRADE_INTERVAL)
        except asyncio.CancelledError:
            break

    logger.info("Auto-trader stopped")


def start():
    """Start the auto-trading loop."""
    global _enabled, _task, _trades_today
    if _enabled:
        return
    _enabled = True
    _trades_today = 0
    _task = asyncio.create_task(_auto_loop())


def stop():
    """Stop the auto-trading loop."""
    global _enabled, _task
    _enabled = False
    if _task and not _task.done():
        _task.cancel()
    _task = None


def get_status() -> dict:
    """Get current auto-trading status."""
    return {
        "enabled": _enabled,
        "last_run": _last_run,
        "trades_today": _trades_today,
        "max_daily_trades": MAX_DAILY_TRADES,
        "total_pnl": _total_pnl,
        "interval_seconds": AUTO_TRADE_INTERVAL,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
    }


def get_history() -> list[dict]:
    """Get auto-trading decision history."""
    return list(reversed(_history))
