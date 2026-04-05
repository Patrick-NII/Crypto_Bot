from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RiskProfile(BaseModel):
    """Defines risk tolerance parameters for portfolio management."""

    profile_id: str = Field(
        default="moderate",
        pattern="^(conservative|moderate|aggressive|custom)$",
    )
    max_position_size_pct: Decimal = Decimal("10.0")
    max_portfolio_drawdown_pct: Decimal = Decimal("15.0")
    default_stop_loss_pct: Decimal = Decimal("5.0")
    default_take_profit_pct: Decimal = Decimal("15.0")
    max_daily_trades: int = 20
    max_leverage: Decimal = Decimal("1.0")
    risk_per_trade_pct: Decimal = Decimal("2.0")

    class Config:
        json_encoders = {Decimal: str}

    @classmethod
    def conservative(cls) -> RiskProfile:
        """Conservative risk profile: tight stops, small positions."""
        return cls(
            profile_id="conservative",
            max_position_size_pct=Decimal("5.0"),
            max_portfolio_drawdown_pct=Decimal("8.0"),
            default_stop_loss_pct=Decimal("3.0"),
            default_take_profit_pct=Decimal("10.0"),
            max_daily_trades=10,
            max_leverage=Decimal("1.0"),
            risk_per_trade_pct=Decimal("1.0"),
        )

    @classmethod
    def moderate(cls) -> RiskProfile:
        """Moderate risk profile: balanced risk/reward."""
        return cls(
            profile_id="moderate",
            max_position_size_pct=Decimal("10.0"),
            max_portfolio_drawdown_pct=Decimal("15.0"),
            default_stop_loss_pct=Decimal("5.0"),
            default_take_profit_pct=Decimal("15.0"),
            max_daily_trades=20,
            max_leverage=Decimal("1.0"),
            risk_per_trade_pct=Decimal("2.0"),
        )

    @classmethod
    def aggressive(cls) -> RiskProfile:
        """Aggressive risk profile: wider stops, larger positions."""
        return cls(
            profile_id="aggressive",
            max_position_size_pct=Decimal("20.0"),
            max_portfolio_drawdown_pct=Decimal("25.0"),
            default_stop_loss_pct=Decimal("8.0"),
            default_take_profit_pct=Decimal("25.0"),
            max_daily_trades=40,
            max_leverage=Decimal("2.0"),
            risk_per_trade_pct=Decimal("4.0"),
        )


class TradeEvaluation(BaseModel):
    """A proposed trade to be evaluated against risk rules."""

    symbol: str
    side: str = Field(..., pattern="^(buy|sell)$")
    quantity: Decimal
    price: Decimal
    portfolio_value: Optional[Decimal] = None
    current_positions: Optional[List[Dict[str, Any]]] = None

    class Config:
        json_encoders = {Decimal: str}


class RiskEvaluationResult(BaseModel):
    """Result of evaluating a trade against the risk profile."""

    approved: bool
    risk_score: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    position_size_ok: bool
    drawdown_ok: bool
    daily_trades_ok: bool
    warnings: List[str] = Field(default_factory=list)
    recommended_stop_loss: Optional[Decimal] = None
    recommended_take_profit: Optional[Decimal] = None
    recommended_quantity: Optional[Decimal] = None
    reason: Optional[str] = None

    class Config:
        json_encoders = {Decimal: str}


class PositionRiskMetrics(BaseModel):
    """Risk contribution for a single portfolio line."""

    symbol: str
    value: Decimal
    weight: Decimal
    var_contribution: Decimal
    volatility: Decimal
    risk_score: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))

    class Config:
        json_encoders = {Decimal: str}


class PortfolioRiskMetrics(BaseModel):
    """Comprehensive portfolio risk assessment."""

    total_value: Decimal
    risk_score: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    daily_var: Decimal
    var_pct: Decimal
    max_drawdown: Decimal
    max_drawdown_pct: Decimal
    sharpe_ratio: Optional[Decimal] = None
    volatility: Decimal
    correlation_risk: str = Field(..., pattern="^(low|medium|high)$")
    risk_level: str = Field(
        ..., pattern="^(conservative|moderate|aggressive)$"
    )
    concentration_pct: Decimal = Decimal("0")
    cash_ratio: Decimal = Decimal("0")
    position_risk: List[PositionRiskMetrics] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    class Config:
        json_encoders = {Decimal: str}


class StopLossRecommendation(BaseModel):
    """Stop-loss recommendation for a given symbol."""

    symbol: str
    current_price: Decimal
    stop_loss_price: Decimal
    stop_loss_pct: Decimal
    method: str
    atr_value: Optional[Decimal] = None

    class Config:
        json_encoders = {Decimal: str}


class TakeProfitLevel(BaseModel):
    """A single take-profit target level."""

    level: int
    price: Decimal
    pct_of_position: Decimal
    pct_from_entry: Decimal

    class Config:
        json_encoders = {Decimal: str}


class TakeProfitRecommendation(BaseModel):
    """Multi-level take-profit recommendation."""

    symbol: str
    entry_price: Decimal
    side: str
    levels: List[TakeProfitLevel] = Field(default_factory=list)

    class Config:
        json_encoders = {Decimal: str}
