from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/api/v1/ml", tags=["ml"])


class MLSignal(BaseModel):
    symbol: str
    signal: str  # "buy", "sell", "hold"
    confidence: float
    model_id: str
    timestamp: str


class StrategyPerformance(BaseModel):
    strategy_name: str
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    period_days: int


class BacktestRequest(BaseModel):
    strategy: str = "momentum"
    symbol: str = "BTC/USDT"
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-31"


class BacktestResult(BaseModel):
    status: str
    message: str


class TrainedModel(BaseModel):
    model_id: str
    strategy: str
    trained_at: str
    accuracy: float
    status: str


@router.get("/signals", response_model=List[MLSignal])
async def get_ml_signals():
    """Get current ML signals (stub: returns empty list)."""
    return []


@router.get("/performance", response_model=List[StrategyPerformance])
async def get_strategy_performance():
    """Strategy performance (stub: returns mock data)."""
    return [
        StrategyPerformance(
            strategy_name="momentum",
            total_return_pct=12.5,
            sharpe_ratio=1.8,
            max_drawdown_pct=5.2,
            win_rate=0.62,
            total_trades=150,
            period_days=90,
        ),
        StrategyPerformance(
            strategy_name="mean_reversion",
            total_return_pct=8.3,
            sharpe_ratio=1.4,
            max_drawdown_pct=3.8,
            win_rate=0.58,
            total_trades=200,
            period_days=90,
        ),
    ]


@router.post("/backtest", response_model=BacktestResult)
async def run_backtest(request: BacktestRequest):
    """Run backtest (stub: Phase 5 - not yet implemented)."""
    return BacktestResult(
        status="not_implemented",
        message="Phase 5 - not yet implemented",
    )


@router.get("/models", response_model=List[TrainedModel])
async def list_models():
    """List trained models (stub: returns empty list)."""
    return []
