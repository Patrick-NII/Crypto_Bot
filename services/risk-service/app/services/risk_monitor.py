from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from app.models.risk import PortfolioRiskMetrics, RiskProfile
from app.services.risk_calculator import RiskCalculator

logger = logging.getLogger(__name__)


def _d(value: Any) -> Decimal:
    """Coerce a value to Decimal safely."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class RiskMonitor:
    """Monitors portfolio risk metrics and publishes alerts."""

    @staticmethod
    async def get_portfolio_metrics(
        positions: List[Dict[str, Any]],
        prices: Dict[str, Decimal],
        profile: RiskProfile,
        historical_returns: Optional[List[Decimal]] = None,
        equity_curve: Optional[List[Decimal]] = None,
    ) -> PortfolioRiskMetrics:
        """Calculate comprehensive portfolio risk metrics.

        Parameters
        ----------
        positions
            List of position dicts, each with at least ``symbol``,
            ``quantity``, and ``entry_price``.
        prices
            Mapping of symbol -> current price.
        profile
            The active risk profile.
        historical_returns
            Optional list of daily portfolio return decimals (e.g. 0.01
            for +1%).  If not supplied, a flat synthetic series is used
            so the service can still return structure.
        equity_curve
            Optional historical equity values for drawdown calculation.
        """
        # --- Total portfolio value ---
        total_value = Decimal("0")
        position_values: Dict[str, Decimal] = {}
        for pos in positions:
            symbol = pos.get("symbol", "UNKNOWN").upper()
            qty = _d(pos.get("quantity", 0))
            price = prices.get(symbol, _d(pos.get("current_price", pos.get("price", 0))))
            value = qty * price
            total_value += value
            position_values[symbol] = position_values.get(symbol, Decimal("0")) + value

        if total_value <= 0:
            return PortfolioRiskMetrics(
                total_value=Decimal("0"),
                daily_var=Decimal("0"),
                var_pct=Decimal("0"),
                max_drawdown=Decimal("0"),
                max_drawdown_pct=Decimal("0"),
                sharpe_ratio=None,
                volatility=Decimal("0"),
                correlation_risk="low",
                risk_level="conservative",
                warnings=["Portfolio value is zero or negative"],
            )

        # --- Daily returns ---
        if historical_returns and len(historical_returns) >= 2:
            returns = historical_returns
        else:
            # Synthetic flat returns so structure is valid
            returns = [Decimal("0")] * 30

        # --- VaR ---
        daily_var, var_pct = RiskCalculator.calculate_var(
            returns=returns,
            confidence_level=0.95,
            portfolio_value=total_value,
        )

        # --- Max drawdown ---
        if equity_curve and len(equity_curve) >= 2:
            max_dd, max_dd_pct = RiskCalculator.calculate_max_drawdown(equity_curve)
        else:
            max_dd = Decimal("0")
            max_dd_pct = Decimal("0")

        # --- Sharpe ---
        sharpe = None
        if historical_returns and len(historical_returns) >= 2:
            sharpe = RiskCalculator.calculate_sharpe_ratio(returns)

        # --- Volatility ---
        volatility = RiskCalculator.calculate_volatility(returns)

        # --- Correlation / concentration risk ---
        if len(position_values) == 0:
            correlation_risk = "low"
        elif len(position_values) == 1:
            correlation_risk = "high"
        else:
            max_weight = max(position_values.values()) / total_value
            if max_weight > Decimal("0.5"):
                correlation_risk = "high"
            elif max_weight > Decimal("0.25"):
                correlation_risk = "medium"
            else:
                correlation_risk = "low"

        # --- Overall risk level ---
        if var_pct > Decimal("0.05") or max_dd_pct > Decimal("0.20"):
            risk_level = "aggressive"
        elif var_pct > Decimal("0.02") or max_dd_pct > Decimal("0.10"):
            risk_level = "moderate"
        else:
            risk_level = "conservative"

        # --- Warnings ---
        warnings: List[str] = []

        if max_dd_pct > profile.max_portfolio_drawdown_pct / Decimal("100"):
            warnings.append(
                f"Max drawdown {max_dd_pct:.2%} exceeds profile limit "
                f"{profile.max_portfolio_drawdown_pct}%"
            )

        if correlation_risk == "high":
            warnings.append(
                "High concentration risk: portfolio dominated by a single asset"
            )

        if volatility > Decimal("0.50"):
            warnings.append(
                f"High annualized volatility: {volatility:.2%}"
            )

        return PortfolioRiskMetrics(
            total_value=total_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            daily_var=daily_var,
            var_pct=var_pct,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            sharpe_ratio=sharpe,
            volatility=volatility,
            correlation_risk=correlation_risk,
            risk_level=risk_level,
            warnings=warnings,
        )

    @staticmethod
    async def check_risk_alerts(
        metrics: PortfolioRiskMetrics,
        profile: RiskProfile,
    ) -> List[str]:
        """Check whether any risk thresholds are breached.

        Returns a list of human-readable alert strings.
        """
        alerts: List[str] = []

        # Drawdown alert
        dd_limit = profile.max_portfolio_drawdown_pct / Decimal("100")
        if metrics.max_drawdown_pct > dd_limit:
            alerts.append(
                f"ALERT: Max drawdown {metrics.max_drawdown_pct:.4f} "
                f"exceeds limit {dd_limit:.4f}"
            )

        # VaR alert -- warn if daily VaR exceeds 5% of portfolio
        if metrics.total_value > 0:
            var_ratio = metrics.daily_var / metrics.total_value
            if var_ratio > Decimal("0.05"):
                alerts.append(
                    f"ALERT: Daily VaR is {var_ratio:.2%} of portfolio value"
                )

        # Volatility alert
        if metrics.volatility > Decimal("0.60"):
            alerts.append(
                f"ALERT: Annualized volatility {metrics.volatility:.4f} "
                "is extremely high"
            )

        # Correlation alert
        if metrics.correlation_risk == "high":
            alerts.append(
                "ALERT: Portfolio has high concentration/correlation risk"
            )

        # Sharpe ratio alert
        if (
            metrics.sharpe_ratio is not None
            and metrics.sharpe_ratio < Decimal("-0.5")
        ):
            alerts.append(
                f"ALERT: Negative Sharpe ratio ({metrics.sharpe_ratio}) "
                "indicates poor risk-adjusted returns"
            )

        return alerts
