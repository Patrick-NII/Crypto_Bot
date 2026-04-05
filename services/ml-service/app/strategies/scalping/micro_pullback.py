"""Scalping: Micro Pullback — pullback to EMA on a micro-trend.

Identifies a strong micro-trend on confirmation TF (5m), then waits for a
pullback to the fast EMA on primary TF (1m) with volume dry-up during the
pullback and a spike on the bounce.
"""

from __future__ import annotations

from app.core.models import Candle, IndicatorSnapshot, StrategyResult
from app.indicators.math_utils import ema
from app.indicators.rsi import calc_rsi, rsi_raw
from app.indicators.ema_cross import calc_ema_cross
from app.indicators.volume import volume_ratio
from app.indicators.atr import atr_raw
from app.settings.user_settings import UserSignalSettings

# How close to EMA the price must get (as % of ATR)
PULLBACK_PROXIMITY_ATR = 0.8
# Volume must drop during pullback
PULLBACK_VOL_MAX = 0.8   # below 0.8x average during pullback
BOUNCE_VOL_MIN = 1.3      # above 1.3x on bounce candle


class MicroPullbackStrategy:
    name = "micro_pullback"
    strategy_type = "scalping"

    def generate(
        self,
        symbol: str,
        primary_candles: list[Candle],
        confirmation_candles: list[Candle] | None,
        settings: UserSignalSettings,
    ) -> StrategyResult:
        closes = [c.close for c in primary_candles]
        volumes = [c.volume for c in primary_candles]
        indicators: list[IndicatorSnapshot] = []

        if len(closes) < 30:
            return self._hold(symbol, settings, indicators, "Insufficient data")

        # 1. Identify micro-trend on confirmation TF
        conf_closes = [c.close for c in confirmation_candles] if confirmation_candles else closes
        if len(conf_closes) < 25:
            return self._hold(symbol, settings, indicators, "Insufficient confirmation data")

        ema_conf = calc_ema_cross(conf_closes, settings.ema_fast, settings.ema_slow)
        indicators.append(ema_conf)

        # Need a clear trend (not just marginally positive/negative)
        trend_up = ema_conf.signal >= 0.3
        trend_down = ema_conf.signal <= -0.3

        if not trend_up and not trend_down:
            return self._hold(symbol, settings, indicators,
                              f"No clear micro-trend on confirmation TF (signal={ema_conf.signal:.2f})")

        # 2. Check pullback to fast EMA on primary TF
        ema_fast_vals = ema(closes, settings.ema_fast)
        current_price = closes[-1]
        current_ema = ema_fast_vals[-1]
        atr_val = atr_raw(primary_candles, settings.atr_period)
        proximity = atr_val * PULLBACK_PROXIMITY_ATR if atr_val > 0 else current_price * 0.003

        ema_dist_ind = IndicatorSnapshot(
            "EMA Proximity", round(abs(current_price - current_ema), 4),
            0.5 if abs(current_price - current_ema) <= proximity else 0.0,
            f"Price {'near' if abs(current_price - current_ema) <= proximity else 'far from'} EMA{settings.ema_fast}",
            weight=0.8, category="trend",
        )
        indicators.append(ema_dist_ind)

        # In an uptrend, price should be near/touching EMA from above
        if trend_up and (current_price - current_ema) > proximity:
            return self._hold(symbol, settings, indicators,
                              "Price too far above EMA — not a pullback yet")
        if trend_up and current_price < current_ema - proximity:
            return self._hold(symbol, settings, indicators,
                              "Price broke below EMA — pullback too deep")

        if trend_down and (current_ema - current_price) > proximity:
            return self._hold(symbol, settings, indicators,
                              "Price too far below EMA — not a pullback yet")
        if trend_down and current_price > current_ema + proximity:
            return self._hold(symbol, settings, indicators,
                              "Price broke above EMA — pullback too deep")

        # 3. Volume pattern: dry-up during pullback, spike on bounce
        if len(volumes) < 10:
            return self._hold(symbol, settings, indicators, "Not enough volume data")

        avg_vol = sum(volumes[-20:]) / min(len(volumes), 20)
        # Check last 3-5 candles for volume dry-up
        pullback_vols = volumes[-5:-1]  # candles before the current one
        bounce_vol = volumes[-1]         # current candle

        avg_pullback_vol = sum(pullback_vols) / len(pullback_vols) if pullback_vols else avg_vol
        pullback_vol_ratio = avg_pullback_vol / avg_vol if avg_vol > 0 else 1.0
        bounce_vol_ratio = bounce_vol / avg_vol if avg_vol > 0 else 1.0

        vol_pattern_ind = IndicatorSnapshot(
            "Vol Pattern",
            round(bounce_vol_ratio, 2),
            0.4 if pullback_vol_ratio < PULLBACK_VOL_MAX and bounce_vol_ratio > BOUNCE_VOL_MIN else 0.0,
            f"Pullback vol {pullback_vol_ratio:.1f}x, Bounce vol {bounce_vol_ratio:.1f}x",
            weight=0.7, category="volume",
        )
        indicators.append(vol_pattern_ind)

        # Volume pattern is ideal but not mandatory — reduce confidence if missing
        vol_bonus = 0.15 if pullback_vol_ratio < PULLBACK_VOL_MAX and bounce_vol_ratio > BOUNCE_VOL_MIN else 0.0

        # 4. RSI should be in the 40-60 zone (not extreme)
        rsi_val = rsi_raw(closes, settings.rsi_period)
        rsi_ind = calc_rsi(closes, settings.rsi_period)
        indicators.append(rsi_ind)

        rsi_ok = (35 < rsi_val < 65)
        if not rsi_ok:
            return self._hold(symbol, settings, indicators,
                              f"RSI {rsi_val:.0f} outside pullback zone (35-65)")

        # 5. Fake breakout filter: last candle should move in trend direction
        if len(primary_candles) >= 2:
            last_candle = primary_candles[-1]
            if trend_up and last_candle.close < last_candle.open:
                return self._hold(symbol, settings, indicators,
                                  "Last candle bearish — bounce not confirmed")
            if trend_down and last_candle.close > last_candle.open:
                return self._hold(symbol, settings, indicators,
                                  "Last candle bullish — bounce not confirmed")

        # 6. Score and trade plan
        base_score = 0.35 + abs(ema_conf.signal) * 0.25 + vol_bonus
        score = min(base_score, 1.0)
        entry = current_price
        stop_dist = max(atr_val * 1.0, entry * settings.default_stop_loss_pct / 100)

        if trend_up:
            action = "BUY"
            stop_loss = entry - stop_dist
            take_profit = entry + stop_dist * settings.min_risk_reward
        else:
            action = "SELL"
            score = -score
            stop_loss = entry + stop_dist
            take_profit = entry - stop_dist * settings.min_risk_reward

        reasoning = (
            f"Micro-trend {'up' if trend_up else 'down'} on confirmation TF. "
            f"Price pulled back to EMA{settings.ema_fast}. "
            f"RSI {rsi_val:.0f} in neutral zone."
            + (f" Volume pattern confirmed." if vol_bonus > 0 else "")
        )

        return StrategyResult(
            strategy_name=self.name,
            strategy_type=self.strategy_type,
            action=action,
            confidence=round(abs(score), 2),
            score=round(score, 3),
            timeframe=settings.primary_timeframe,
            indicators=indicators,
            reasoning=reasoning,
            entry_price=round(entry, 4),
            stop_loss=round(stop_loss, 4),
            take_profit=round(take_profit, 4),
        )

    def _hold(
        self, symbol: str, settings: UserSignalSettings,
        indicators: list[IndicatorSnapshot], reason: str,
    ) -> StrategyResult:
        return StrategyResult(
            strategy_name=self.name,
            strategy_type=self.strategy_type,
            action="HOLD",
            confidence=0.0,
            score=0.0,
            timeframe=settings.primary_timeframe,
            indicators=indicators,
            reasoning=reason,
        )
