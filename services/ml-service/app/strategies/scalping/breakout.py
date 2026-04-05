"""Scalping: Breakout strategy — Bollinger Band squeeze into expansion.

Detects compression (low bandwidth) followed by expansion with volume confirmation.
Primary TF: 1m. Confirmation TF: 5m for trend direction.
"""

from __future__ import annotations

from app.core.models import Candle, IndicatorSnapshot, StrategyResult
from app.indicators.bollinger import bollinger_raw, calc_bollinger
from app.indicators.ema_cross import calc_ema_cross
from app.indicators.volume import calc_volume_profile, volume_ratio
from app.indicators.atr import atr_raw
from app.settings.user_settings import UserSignalSettings

# BB bandwidth percentile thresholds
SQUEEZE_THRESHOLD = 0.015       # BW below this = compressed
EXPANSION_FACTOR = 1.8          # BW must grow this much from squeeze
MIN_VOLUME_SPIKE = 1.8          # Volume must be 1.8x avg during expansion
FAKE_BREAKOUT_CANDLES = 3       # Reject if price reverses within N candles


class BreakoutStrategy:
    name = "breakout"
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

        # 1. Compute rolling BB bandwidth over recent history
        bandwidths: list[float] = []
        period = settings.bb_period
        for i in range(period, len(closes)):
            window = closes[i - period : i + 1]
            _, mid, _, bw = bollinger_raw(window, period, settings.bb_std)
            bandwidths.append(bw)

        if len(bandwidths) < 10:
            return self._hold(symbol, settings, indicators, "Not enough bandwidth history")

        # 2. Detect squeeze: recent min bandwidth was very low
        recent_bw = bandwidths[-10:]
        min_bw = min(recent_bw)
        current_bw = bandwidths[-1]
        was_squeezed = min_bw < SQUEEZE_THRESHOLD

        # 3. Detect expansion from squeeze
        is_expanding = was_squeezed and current_bw > min_bw * EXPANSION_FACTOR

        bb_ind = calc_bollinger(closes, period, settings.bb_std)
        indicators.append(bb_ind)

        squeeze_ind = IndicatorSnapshot(
            "BB Squeeze", round(min_bw, 4),
            0.5 if was_squeezed else 0.0,
            f"Min BW {min_bw:.4f}, Current BW {current_bw:.4f}" + (" — SQUEEZED" if was_squeezed else ""),
            weight=1.0, category="volatility",
        )
        indicators.append(squeeze_ind)

        if not is_expanding:
            return self._hold(symbol, settings, indicators, "No breakout: BB not expanding from squeeze")

        # 4. Volume confirmation
        vol_ratio_val = volume_ratio(volumes, 20)
        vol_ind = calc_volume_profile(volumes)
        indicators.append(vol_ind)

        if vol_ratio_val < MIN_VOLUME_SPIKE:
            return self._hold(symbol, settings, indicators,
                              f"Volume too low ({vol_ratio_val:.1f}x) for breakout confirmation")

        # 5. Direction from confirmation timeframe (EMA cross) or primary
        conf_closes = [c.close for c in confirmation_candles] if confirmation_candles else closes
        ema_ind = calc_ema_cross(conf_closes, settings.ema_fast, settings.ema_slow)
        indicators.append(ema_ind)

        # Direction: positive EMA cross = bullish breakout, negative = bearish
        bullish = ema_ind.signal > 0
        bearish = ema_ind.signal < 0

        if not bullish and not bearish:
            return self._hold(symbol, settings, indicators, "No directional bias — EMA neutral")

        # 6. Fake breakout filter: check if last N candles reversed
        if len(primary_candles) >= FAKE_BREAKOUT_CANDLES + 1:
            recent = primary_candles[-FAKE_BREAKOUT_CANDLES:]
            if bullish:
                if all(recent[i].close < recent[i - 1].close for i in range(1, len(recent))):
                    return self._hold(symbol, settings, indicators, "Fake breakout filter: immediate reversal")
            elif bearish:
                if all(recent[i].close > recent[i - 1].close for i in range(1, len(recent))):
                    return self._hold(symbol, settings, indicators, "Fake breakout filter: immediate reversal")

        # 7. Compute entry, stop, TP
        entry = closes[-1]
        atr = atr_raw(primary_candles, settings.atr_period)
        stop_distance = max(atr * 1.5, entry * settings.default_stop_loss_pct / 100)

        if bullish:
            action = "BUY"
            stop_loss = entry - stop_distance
            take_profit = entry + stop_distance * settings.min_risk_reward
        else:
            action = "SELL"
            stop_loss = entry + stop_distance
            take_profit = entry - stop_distance * settings.min_risk_reward

        # Score: combine squeeze strength + volume + EMA alignment
        score = min(0.4 + abs(ema_ind.signal) * 0.3 + min(vol_ratio_val / 5, 0.3), 1.0)
        if bearish:
            score = -score
        confidence = min(abs(score), 1.0)

        reasoning = (
            f"BB squeeze ({min_bw:.4f}) → expansion ({current_bw:.4f}). "
            f"Volume {vol_ratio_val:.1f}x avg. "
            f"EMA {settings.ema_fast}/{settings.ema_slow} {'bullish' if bullish else 'bearish'}."
        )

        return StrategyResult(
            strategy_name=self.name,
            strategy_type=self.strategy_type,
            action=action,
            confidence=round(confidence, 2),
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
