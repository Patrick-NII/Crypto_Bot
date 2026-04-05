"""Scalping: Momentum Burst — RSI mid-cross + MACD histogram acceleration.

Detects sharp momentum shifts: RSI crossing 50 (direction) combined with
rapidly increasing MACD histogram (acceleration) and volume spike.
Primary TF: 1m. Confirmation TF: 5m for trend context.
"""

from __future__ import annotations

from app.core.models import Candle, IndicatorSnapshot, StrategyResult
from app.indicators.rsi import calc_rsi, rsi_raw
from app.indicators.macd import calc_macd, macd_raw
from app.indicators.volume import calc_volume_profile, volume_ratio
from app.indicators.atr import atr_raw
from app.indicators.ema_cross import calc_ema_cross
from app.settings.user_settings import UserSignalSettings

MACD_ACCEL_THRESHOLD = 1.5   # histogram must grow 1.5x vs previous bar
MIN_VOLUME_SPIKE = 1.5


class MomentumBurstStrategy:
    name = "momentum_burst"
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

        if len(closes) < 35:
            return self._hold(symbol, settings, indicators, "Insufficient data")

        # 1. RSI — detect crossing 50 (momentum shift)
        rsi_val = rsi_raw(closes, settings.rsi_period)
        prev_closes = closes[:-1]
        rsi_prev = rsi_raw(prev_closes, settings.rsi_period) if len(prev_closes) >= settings.rsi_period + 1 else 50

        rsi_crossed_up = rsi_prev < 50 <= rsi_val
        rsi_crossed_down = rsi_prev > 50 >= rsi_val
        rsi_ind = calc_rsi(closes, settings.rsi_period)
        indicators.append(rsi_ind)

        if not rsi_crossed_up and not rsi_crossed_down:
            return self._hold(symbol, settings, indicators, f"RSI {rsi_val:.0f} — no mid-cross")

        # 2. MACD histogram acceleration
        macd_val, signal_val, hist = macd_raw(closes, settings.macd_fast, settings.macd_slow, settings.macd_signal)
        prev_macd, prev_sig, prev_hist = macd_raw(prev_closes, settings.macd_fast, settings.macd_slow, settings.macd_signal)

        macd_ind = calc_macd(closes, settings.macd_fast, settings.macd_slow, settings.macd_signal)
        indicators.append(macd_ind)

        # Check acceleration: histogram growing faster
        hist_accel = abs(hist) / (abs(prev_hist) + 1e-10)
        accel_ind = IndicatorSnapshot(
            "MACD Accel", round(hist_accel, 2),
            0.5 if hist_accel > MACD_ACCEL_THRESHOLD else 0.0,
            f"Histogram acceleration {hist_accel:.1f}x",
            weight=1.0, category="momentum",
        )
        indicators.append(accel_ind)

        if hist_accel < MACD_ACCEL_THRESHOLD:
            return self._hold(symbol, settings, indicators,
                              f"MACD acceleration too weak ({hist_accel:.1f}x < {MACD_ACCEL_THRESHOLD}x)")

        # 3. Volume confirmation
        vol_ratio_val = volume_ratio(volumes, 20)
        vol_ind = calc_volume_profile(volumes)
        indicators.append(vol_ind)

        if vol_ratio_val < MIN_VOLUME_SPIKE:
            return self._hold(symbol, settings, indicators,
                              f"Volume too low ({vol_ratio_val:.1f}x) for momentum burst")

        # 4. Confirmation TF trend alignment (optional but strengthens signal)
        conf_bonus = 0.0
        if confirmation_candles and len(confirmation_candles) > 25:
            conf_closes = [c.close for c in confirmation_candles]
            ema_conf = calc_ema_cross(conf_closes, settings.ema_fast, settings.ema_slow)
            indicators.append(ema_conf)
            # Boost if confirmation aligns with primary direction
            if rsi_crossed_up and ema_conf.signal > 0:
                conf_bonus = 0.15
            elif rsi_crossed_down and ema_conf.signal < 0:
                conf_bonus = 0.15

        # 5. Direction and scoring
        bullish = rsi_crossed_up and hist > 0
        bearish = rsi_crossed_down and hist < 0

        if not bullish and not bearish:
            return self._hold(symbol, settings, indicators,
                              "RSI and MACD directions disagree")

        # Score: RSI cross strength + MACD accel + volume + confirmation
        base_score = 0.35 + min(hist_accel / 6, 0.25) + min(vol_ratio_val / 8, 0.2) + conf_bonus
        score = min(base_score, 1.0)
        if bearish:
            score = -score

        entry = closes[-1]
        atr = atr_raw(primary_candles, settings.atr_period)
        stop_dist = max(atr * 1.2, entry * settings.default_stop_loss_pct / 100)

        if bullish:
            action = "BUY"
            stop_loss = entry - stop_dist
            take_profit = entry + stop_dist * settings.min_risk_reward
        else:
            action = "SELL"
            stop_loss = entry + stop_dist
            take_profit = entry - stop_dist * settings.min_risk_reward

        reasoning = (
            f"RSI crossed {'above' if bullish else 'below'} 50 ({rsi_prev:.0f}→{rsi_val:.0f}). "
            f"MACD histogram acceleration {hist_accel:.1f}x. "
            f"Volume {vol_ratio_val:.1f}x average."
            + (f" Confirmation TF aligned (+{conf_bonus:.0%})." if conf_bonus > 0 else "")
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
