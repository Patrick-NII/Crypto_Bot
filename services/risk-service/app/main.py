from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI

from app.api.risk import router as risk_router
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Risk Service",
    description="Portfolio risk management, trade evaluation, and position sizing for the GlueTrade Trading Platform.",
    version="2.0.0",
)

app.include_router(risk_router)


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check exposing key risk configuration."""
    return {
        "status": "healthy",
        "service": "risk-service",
        "version": "2.0.0",
        "config": {
            "max_portfolio_drawdown": settings.MAX_PORTFOLIO_DRAWDOWN,
            "default_stop_loss_pct": settings.DEFAULT_STOP_LOSS_PCT,
            "default_take_profit_pct": settings.DEFAULT_TAKE_PROFIT_PCT,
            "max_position_size_pct": settings.MAX_POSITION_SIZE_PCT,
            "max_daily_trades": settings.MAX_DAILY_TRADES,
            "max_leverage": settings.MAX_LEVERAGE,
            "risk_per_trade_pct": settings.RISK_PER_TRADE_PCT,
            "var_confidence_level": settings.VAR_CONFIDENCE_LEVEL,
            "var_lookback_days": settings.VAR_LOOKBACK_DAYS,
            "market_data_service_url": settings.MARKET_DATA_SERVICE_URL,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8005, reload=True)
