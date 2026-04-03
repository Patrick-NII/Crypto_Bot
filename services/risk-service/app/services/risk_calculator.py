from __future__ import annotations

import logging
import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Quantisation helper -- round to 8 decimal places (standard for crypto)
_Q8 = Decimal("0.00000001")


def _d(value: Any) -> Decimal:
    """Coerce a value to Decimal safely."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class RiskCalculator:
    """Core risk calculation engine.

    All monetary values use ``Decimal`` to avoid floating-point errors.
    """

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_position_size(
        portfolio_value: Decimal,
        risk_per_trade_pct: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
    ) -> Decimal:
        """Kelly Criterion-inspired position sizing.

        risk_amount = portfolio_value * (risk_per_trade_pct / 100)
        position_size = risk_amount / abs(entry_price - stop_loss_price)

        Returns the number of units (shares / coins) to buy.
        """
        if portfolio_value <= 0:
            return Decimal("0")
        if entry_price <= 0 or stop_loss_price <= 0:
            return Decimal("0")

        price_diff = abs(entry_price - stop_loss_price)
        if price_diff == 0:
            logger.warning(
                "Entry price equals stop-loss price; cannot size position"
            )
            return Decimal("0")

        risk_amount = portfolio_value * (risk_per_trade_pct / Decimal("100"))
        position_size = (risk_amount / price_diff).quantize(
            _Q8, rounding=ROUND_HALF_UP
        )
        return max(position_size, Decimal("0"))

    # ------------------------------------------------------------------
    # Stop-loss (ATR-based)
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_stop_loss_atr(
        prices: List[Dict[str, Decimal]],
        multiplier: Decimal = Decimal("2.0"),
        period: int = 14,
    ) -> Decimal:
        """ATR-based stop loss.

        *prices* is a list of dicts with keys ``high``, ``low``, ``close``
        (OHLC candles in chronological order).

        ATR = simple moving average of True Range over *period*.
        stop_loss = last_close - (ATR * multiplier)

        Returns the recommended stop-loss price (floored at 0).
        """
        if not prices or len(prices) < 2:
            return Decimal("0")

        true_ranges: List[Decimal] = []
        for i in range(1, len(prices)):
            high = _d(prices[i].get("high", 0))
            low = _d(prices[i].get("low", 0))
            prev_close = _d(prices[i - 1].get("close", 0))

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )
            true_ranges.append(tr)

        # Use up to *period* most recent true ranges
        recent_tr = true_ranges[-period:]
        if not recent_tr:
            return Decimal("0")

        atr = sum(recent_tr) / Decimal(str(len(recent_tr)))
        last_close = _d(prices[-1].get("close", 0))
        stop_loss = last_close - (atr * multiplier)
        return max(stop_loss, Decimal("0")).quantize(_Q8, rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_atr(
        prices: List[Dict[str, Decimal]],
        period: int = 14,
    ) -> Decimal:
        """Return the ATR value itself (for reporting)."""
        if not prices or len(prices) < 2:
            return Decimal("0")

        true_ranges: List[Decimal] = []
        for i in range(1, len(prices)):
            high = _d(prices[i].get("high", 0))
            low = _d(prices[i].get("low", 0))
            prev_close = _d(prices[i - 1].get("close", 0))

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )
            true_ranges.append(tr)

        recent_tr = true_ranges[-period:]
        if not recent_tr:
            return Decimal("0")
        return (sum(recent_tr) / Decimal(str(len(recent_tr)))).quantize(
            _Q8, rounding=ROUND_HALF_UP
        )

    # ------------------------------------------------------------------
    # Value at Risk (historical)
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_var(
        returns: List[Decimal],
        confidence_level: float = 0.95,
        portfolio_value: Decimal = Decimal("0"),
    ) -> Tuple[Decimal, Decimal]:
        """Historical Value at Risk.

        Sorts daily returns, picks the percentile corresponding to
        ``1 - confidence_level``.

        Returns ``(var_amount, var_pct)``.  Both are expressed as
        *positive* numbers representing potential loss.
        """
        if not returns:
            return (Decimal("0"), Decimal("0"))

        sorted_returns = sorted(returns)
        index = int(math.floor((1.0 - confidence_level) * len(sorted_returns)))
        index = max(0, min(index, len(sorted_returns) - 1))

        var_pct = abs(sorted_returns[index])
        var_amount = (portfolio_value * var_pct).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        var_pct_rounded = var_pct.quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        return (var_amount, var_pct_rounded)

    # ------------------------------------------------------------------
    # Max drawdown
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_max_drawdown(
        equity_curve: List[Decimal],
    ) -> Tuple[Decimal, Decimal]:
        """Maximum drawdown from an equity curve.

        Returns ``(max_drawdown_amount, max_drawdown_pct)``.
        """
        if not equity_curve or len(equity_curve) < 2:
            return (Decimal("0"), Decimal("0"))

        peak = equity_curve[0]
        max_dd_amount = Decimal("0")
        max_dd_pct = Decimal("0")

        for value in equity_curve:
            if value > peak:
                peak = value
            if peak > 0:
                dd_amount = peak - value
                dd_pct = dd_amount / peak
                if dd_amount > max_dd_amount:
                    max_dd_amount = dd_amount
                if dd_pct > max_dd_pct:
                    max_dd_pct = dd_pct

        return (
            max_dd_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            max_dd_pct.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        )

    # ------------------------------------------------------------------
    # Sharpe ratio
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_sharpe_ratio(
        returns: List[Decimal],
        risk_free_rate: Decimal = Decimal("0.04"),
    ) -> Decimal:
        """Annualised Sharpe ratio.

        Sharpe = (mean_daily_return - daily_rf) / std_daily_return * sqrt(252)
        """
        if not returns or len(returns) < 2:
            return Decimal("0")

        n = len(returns)
        mean_return = sum(returns) / Decimal(str(n))

        # Daily risk-free rate (continuously compounded approximation)
        daily_rf = risk_free_rate / Decimal("252")

        variance = sum(
            (r - mean_return) ** 2 for r in returns
        ) / Decimal(str(n - 1))

        if variance <= 0:
            return Decimal("0")

        std_dev = variance.sqrt()
        if std_dev == 0:
            return Decimal("0")

        sharpe = ((mean_return - daily_rf) / std_dev) * Decimal(
            str(math.sqrt(252))
        )
        return sharpe.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    # ------------------------------------------------------------------
    # Volatility
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_volatility(returns: List[Decimal]) -> Decimal:
        """Annualised volatility: std(daily returns) * sqrt(252)."""
        if not returns or len(returns) < 2:
            return Decimal("0")

        n = len(returns)
        mean_return = sum(returns) / Decimal(str(n))
        variance = sum(
            (r - mean_return) ** 2 for r in returns
        ) / Decimal(str(n - 1))

        if variance <= 0:
            return Decimal("0")

        daily_vol = variance.sqrt()
        annual_vol = daily_vol * Decimal(str(math.sqrt(252)))
        return annual_vol.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    # ------------------------------------------------------------------
    # Trade evaluation
    # ------------------------------------------------------------------

    @staticmethod
    def evaluate_trade(
        trade: Dict[str, Any],
        profile: Dict[str, Any],
        portfolio_value: Decimal,
        current_positions: List[Dict[str, Any]],
        daily_trade_count: int,
    ) -> Dict[str, Any]:
        """Full trade evaluation against a risk profile.

        Checks:
        1. Position size vs max_position_size_pct
        2. Portfolio drawdown headroom
        3. Daily trade limit
        4. Concentration risk

        Returns a dict matching ``RiskEvaluationResult`` shape.
        """
        warnings: List[str] = []
        approved = True
        reason = None

        trade_quantity = _d(trade.get("quantity", 0))
        trade_price = _d(trade.get("price", 0))
        trade_value = trade_quantity * trade_price
        symbol = trade.get("symbol", "UNKNOWN")
        side = trade.get("side", "buy")

        max_pos_pct = _d(profile.get("max_position_size_pct", 10))
        max_dd_pct = _d(profile.get("max_portfolio_drawdown_pct", 15))
        max_daily = int(profile.get("max_daily_trades", 20))
        risk_per_trade = _d(profile.get("risk_per_trade_pct", 2))
        default_sl_pct = _d(profile.get("default_stop_loss_pct", 5))
        default_tp_pct = _d(profile.get("default_take_profit_pct", 15))

        # --- 1. Position size check ---
        position_size_ok = True
        recommended_quantity = trade_quantity

        if portfolio_value > 0:
            position_pct = (trade_value / portfolio_value) * Decimal("100")
            if position_pct > max_pos_pct:
                position_size_ok = False
                max_value = portfolio_value * max_pos_pct / Decimal("100")
                if trade_price > 0:
                    recommended_quantity = (max_value / trade_price).quantize(
                        _Q8, rounding=ROUND_HALF_UP
                    )
                warnings.append(
                    f"Position size {position_pct:.1f}% exceeds max "
                    f"{max_pos_pct}% of portfolio"
                )
        else:
            warnings.append("Portfolio value is zero or negative")

        # --- 2. Drawdown headroom ---
        drawdown_ok = True
        total_exposure = trade_value
        for pos in current_positions:
            pos_qty = _d(pos.get("quantity", 0))
            pos_price = _d(pos.get("current_price", pos.get("price", 0)))
            total_exposure += pos_qty * pos_price

        if portfolio_value > 0:
            exposure_pct = (total_exposure / portfolio_value) * Decimal("100")
            # If total exposure exceeds 100 + max_drawdown headroom,
            # we are at risk
            if exposure_pct > Decimal("100") + max_dd_pct:
                drawdown_ok = False
                warnings.append(
                    f"Total exposure {exposure_pct:.1f}% puts portfolio at "
                    f"drawdown risk (max {max_dd_pct}%)"
                )

        # --- 3. Daily trade limit ---
        daily_trades_ok = daily_trade_count < max_daily
        if not daily_trades_ok:
            warnings.append(
                f"Daily trade limit reached ({daily_trade_count}/{max_daily})"
            )

        # --- 4. Concentration risk ---
        same_symbol_exposure = Decimal("0")
        for pos in current_positions:
            if pos.get("symbol", "").upper() == symbol.upper():
                pos_qty = _d(pos.get("quantity", 0))
                pos_price = _d(
                    pos.get("current_price", pos.get("price", 0))
                )
                same_symbol_exposure += pos_qty * pos_price

        new_symbol_exposure = same_symbol_exposure + trade_value
        if portfolio_value > 0:
            concentration_pct = (
                new_symbol_exposure / portfolio_value
            ) * Decimal("100")
            if concentration_pct > max_pos_pct * Decimal("1.5"):
                warnings.append(
                    f"High concentration in {symbol}: "
                    f"{concentration_pct:.1f}% of portfolio"
                )

        # --- Risk score (0-1) ---
        risk_factors = Decimal("0")
        factor_count = Decimal("0")

        if portfolio_value > 0:
            size_risk = min(
                (trade_value / portfolio_value) / (max_pos_pct / Decimal("100")),
                Decimal("1"),
            )
            risk_factors += size_risk
            factor_count += 1

        if not daily_trades_ok:
            risk_factors += Decimal("1")
        else:
            risk_factors += Decimal(str(daily_trade_count)) / Decimal(
                str(max(max_daily, 1))
            )
        factor_count += 1

        if portfolio_value > 0:
            exp_risk = min(
                total_exposure / portfolio_value, Decimal("1")
            )
            risk_factors += exp_risk
            factor_count += 1

        risk_score = (
            (risk_factors / factor_count).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if factor_count > 0
            else Decimal("0.50")
        )
        risk_score = max(Decimal("0"), min(risk_score, Decimal("1")))

        # --- Stop loss / take profit recommendations ---
        if side == "buy":
            rec_sl = (trade_price * (Decimal("1") - default_sl_pct / Decimal("100"))).quantize(
                _Q8, rounding=ROUND_HALF_UP
            )
            rec_tp = (trade_price * (Decimal("1") + default_tp_pct / Decimal("100"))).quantize(
                _Q8, rounding=ROUND_HALF_UP
            )
        else:
            rec_sl = (trade_price * (Decimal("1") + default_sl_pct / Decimal("100"))).quantize(
                _Q8, rounding=ROUND_HALF_UP
            )
            rec_tp = (trade_price * (Decimal("1") - default_tp_pct / Decimal("100"))).quantize(
                _Q8, rounding=ROUND_HALF_UP
            )

        # --- Final approval ---
        if not position_size_ok or not drawdown_ok or not daily_trades_ok:
            approved = False
            reasons = []
            if not position_size_ok:
                reasons.append("position size exceeds limit")
            if not drawdown_ok:
                reasons.append("drawdown risk too high")
            if not daily_trades_ok:
                reasons.append("daily trade limit reached")
            reason = "Trade rejected: " + "; ".join(reasons)

        return {
            "approved": approved,
            "risk_score": risk_score,
            "position_size_ok": position_size_ok,
            "drawdown_ok": drawdown_ok,
            "daily_trades_ok": daily_trades_ok,
            "warnings": warnings,
            "recommended_stop_loss": rec_sl,
            "recommended_take_profit": rec_tp,
            "recommended_quantity": recommended_quantity,
            "reason": reason,
        }

    # ------------------------------------------------------------------
    # Take-profit levels
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_take_profit_levels(
        entry_price: Decimal,
        side: str,
        total_target_pct: Decimal = Decimal("15.0"),
    ) -> List[Dict[str, Any]]:
        """Multi-level take profit.

        Splits the target into three levels:
        - Level 1: 25% of position at target / 3
        - Level 2: 50% of position at target * 2 / 3
        - Level 3: 25% of position at full target

        Returns a list of level dicts.
        """
        if entry_price <= 0:
            return []

        fractions = [
            (1, Decimal("25"), Decimal("1") / Decimal("3")),
            (2, Decimal("50"), Decimal("2") / Decimal("3")),
            (3, Decimal("25"), Decimal("1")),
        ]

        levels: List[Dict[str, Any]] = []
        for level_num, pct_of_position, target_fraction in fractions:
            pct_from_entry = (total_target_pct * target_fraction).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if side == "buy":
                price = entry_price * (
                    Decimal("1") + pct_from_entry / Decimal("100")
                )
            else:
                price = entry_price * (
                    Decimal("1") - pct_from_entry / Decimal("100")
                )

            price = max(price, Decimal("0")).quantize(
                _Q8, rounding=ROUND_HALF_UP
            )

            levels.append(
                {
                    "level": level_num,
                    "price": price,
                    "pct_of_position": pct_of_position,
                    "pct_from_entry": pct_from_entry,
                }
            )

        return levels
