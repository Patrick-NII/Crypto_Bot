from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


class RiskProfile(BaseModel):
    risk_tolerance: str = "moderate"
    max_portfolio_drawdown: float = 0.15
    default_stop_loss_pct: float = 0.05
    default_take_profit_pct: float = 0.15
    max_position_size_pct: float = 0.10


class TradeEvaluation(BaseModel):
    symbol: str
    side: str = "buy"
    quantity: float = 0.0
    price: float = 0.0


class TradeEvaluationResult(BaseModel):
    approved: bool = True
    risk_score: float = 0.5
    warnings: List[str] = []


class PortfolioRiskMetrics(BaseModel):
    value_at_risk_1d: float = 0.0
    value_at_risk_7d: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    portfolio_beta: float = 1.0
    correlation_to_btc: float = 0.0


@router.get("/profile", response_model=RiskProfile)
async def get_risk_profile():
    """Get user risk profile (stub: returns default moderate profile)."""
    return RiskProfile()


@router.put("/profile", response_model=RiskProfile)
async def update_risk_profile(profile: RiskProfile):
    """Update risk profile (stub: accepts and returns)."""
    return profile


@router.post("/evaluate", response_model=TradeEvaluationResult)
async def evaluate_trade(trade: TradeEvaluation):
    """Evaluate trade risk (stub: returns approved with moderate risk score)."""
    return TradeEvaluationResult(approved=True, risk_score=0.5, warnings=[])


@router.get("/metrics", response_model=PortfolioRiskMetrics)
async def get_risk_metrics():
    """Portfolio risk metrics (stub: returns mock VaR, drawdown, etc.)."""
    return PortfolioRiskMetrics(
        value_at_risk_1d=150.25,
        value_at_risk_7d=420.80,
        max_drawdown=0.08,
        current_drawdown=0.03,
        sharpe_ratio=1.45,
        portfolio_beta=1.12,
        correlation_to_btc=0.85,
    )
