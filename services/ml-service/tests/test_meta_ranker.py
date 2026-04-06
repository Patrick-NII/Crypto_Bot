from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.models import Candle, IndicatorSnapshot, MarketContext, RegimeInfo, Scenario, StrategyResult
from app.engine.enhanced_scoring import EnhancedScore, Contradiction
from app.engine.meta_ranker import ScannerContext, build_notrade_reasons, build_scanner_context
from app.settings.user_settings import scalping_preset


def build_candles_from_closes(closes: list[float], step_seconds: int, volume_base: float = 1_000.0) -> list[Candle]:
    candles: list[Candle] = []
    previous = closes[0]
    start = 1_710_000_000
    for index, close in enumerate(closes):
        open_price = previous if index > 0 else close * 0.997
        high = max(open_price, close) * 1.006
        low = min(open_price, close) * 0.994
        candles.append(
            Candle(
                time=start + index * step_seconds,
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume_base + index * 45,
            )
        )
        previous = close
    return candles


class MetaRankerTests(unittest.TestCase):
    def test_build_scanner_context_for_breakout_scalping(self) -> None:
        settings = scalping_preset()
        candles = [
            Candle(time=1_710_000_000 + i * 60, open=100 + i, high=101 + i, low=99 + i, close=100.4 + i, volume=1200 + i * 50)
            for i in range(40)
        ]
        confirmation = [
            Candle(time=1_710_000_000 + i * 300, open=100 + i * 0.6, high=101 + i * 0.6, low=99 + i * 0.6, close=100.5 + i * 0.6, volume=2400 + i * 80)
            for i in range(40)
        ]
        anchor = [
            Candle(time=1_710_000_000 + i * 3600, open=100 + i * 1.2, high=101 + i * 1.2, low=99 + i * 1.2, close=100.8 + i * 1.2, volume=18_000 + i * 300)
            for i in range(40)
        ]

        result = StrategyResult(
            strategy_name="breakout",
            strategy_type="scalping",
            action="BUY",
            confidence=0.81,
            score=0.72,
            timeframe="1m",
            indicators=[
                IndicatorSnapshot("RSI", 63, 0.4, "Momentum rising", category="momentum"),
                IndicatorSnapshot("EMA Cross", 1.5, 0.6, "Bullish alignment", category="trend"),
                IndicatorSnapshot("Volume", 2.1, 0.7, "Volume spike", category="volume"),
            ],
            reasoning="Breakout continuation with volume confirmation",
            entry_price=140.0,
            stop_loss=137.5,
            take_profit=145.5,
        )
        enhanced = EnhancedScore(
            direction=82,
            direction_label="Forte impulsion acheteuse",
            confidence=78,
            risk=38,
            setup_quality=74,
            actionability="HIGH_CONVICTION",
            action="STRONG_BUY",
            market_regime="EXPANDING",
            signal_context="trend_aligned",
        )
        market_context = MarketContext(regime="high_volatility", btc_trend="bullish", volatility_percentile=74, volume_ratio=2.0, atr=1.2)
        regime = RegimeInfo(regime="BREAKOUT", confidence=0.82, volatility_state="expanding", momentum_state="accelerating")
        scenario = Scenario(name="CONTINUATION", direction="bullish", probability=0.71, reasoning="Breakout holds above range")

        context = build_scanner_context(
            result=result,
            market_context=market_context,
            regime=regime,
            scenario=scenario,
            enhanced=enhanced,
            primary_candles=candles,
            confirmation_candles=confirmation,
            anchor_candles=anchor,
            context_candles_by_tf={
                "2h": anchor,
                "4h": anchor,
                "6h": anchor,
            },
            btc_closes=[c.close for c in confirmation],
            settings=settings,
            now_ms=int((candles[-1].time + 30) * 1000),
        )

        self.assertEqual(context.setup_type, "breakout_continuation")
        self.assertEqual(context.regime, "BREAKOUT")
        self.assertIn("Scalp 1m/5m/15m/1h", context.horizon)
        self.assertGreaterEqual(context.regime_fit, 70)
        self.assertGreaterEqual(context.confirmation_score, 60)
        self.assertGreaterEqual(context.composite_score, 65)
        self.assertGreaterEqual(context.reliability_score, 58)
        self.assertGreaterEqual(context.trend_context_score, 60)
        self.assertGreaterEqual(context.trend_reliability_score, 50)
        self.assertLessEqual(context.execution_risk, 55)
        self.assertGreater(context.meta_score, 60)

    def test_build_nottrade_reasons_blocks_weak_setups(self) -> None:
        settings = scalping_preset()
        context = ScannerContext(
            horizon="Scalp 1m/5m/15m/1h",
            setup_type="contextual_setup",
            regime="RANGE",
            regime_fit=42,
            confirmation_score=48,
            composite_score=37,
            reliability_score=44,
            trend_context_score=34,
            trend_reliability_score=74,
            execution_risk=72,
            liquidity_score=35,
            expected_holding_window="5-30 min",
            freshness_ms=10_000,
            meta_score=31.5,
        )
        enhanced = EnhancedScore(
            direction=39,
            direction_label="Leger biais baissier",
            confidence=32,
            risk=69,
            setup_quality=40,
            actionability="WATCH",
            action="REDUCE",
            market_regime="RANGING",
            signal_context="mixed",
            contradictions=[Contradiction("Momentum et tendance en desaccord", "strong")],
        )

        reasons = build_notrade_reasons(context, enhanced, settings)

        self.assertTrue(any("Regime fit" in reason for reason in reasons))
        self.assertTrue(any("Setup" in reason for reason in reasons))
        self.assertTrue(any("Confirmation" in reason for reason in reasons))
        self.assertTrue(any("Fiabilite" in reason for reason in reasons))
        self.assertTrue(any("Risque d'execution" in reason for reason in reasons))
        self.assertIn("Contradiction forte detectee", reasons)

    def test_curve_analysis_rewards_stabilized_impulse_over_rejected_pump(self) -> None:
        settings = scalping_preset()
        stable_primary = build_candles_from_closes(
            [
                100.0, 100.3, 100.5, 100.8, 101.0, 101.2, 101.5, 101.9, 102.4, 102.9,
                103.5, 104.2, 105.1, 106.5, 108.6, 111.9, 113.4, 114.1, 114.5, 114.8,
                115.0, 115.2, 115.4, 115.6, 115.8, 116.0, 116.2, 116.4, 116.7, 117.0,
            ],
            60,
            1_400.0,
        )
        unstable_primary = build_candles_from_closes(
            [
                100.0, 100.3, 100.5, 100.8, 101.0, 101.2, 101.5, 101.9, 102.4, 102.9,
                103.5, 104.2, 105.1, 106.5, 108.6, 111.9, 113.8, 111.2, 109.0, 110.8,
                108.3, 110.1, 107.8, 109.4, 107.1, 108.0, 106.8, 107.7, 106.3, 105.9,
            ],
            60,
            1_400.0,
        )
        stable_confirmation = build_candles_from_closes(
            [100, 100.8, 101.5, 102.2, 103.0, 103.7, 104.5, 106.0, 108.8, 111.1, 112.5, 113.3, 114.0, 114.4, 114.8, 115.1, 115.4, 115.8, 116.2, 116.7],
            300,
            2_800.0,
        )
        unstable_confirmation = build_candles_from_closes(
            [100, 100.8, 101.5, 102.2, 103.0, 103.7, 104.5, 106.0, 108.8, 111.1, 112.9, 110.2, 108.1, 109.8, 107.7, 108.9, 107.0, 107.8, 106.5, 105.9],
            300,
            2_800.0,
        )
        stable_anchor = build_candles_from_closes(
            [92, 93, 94.5, 96, 97, 98.2, 99.5, 101.0, 103.2, 105.4, 107.1, 108.8, 110.2, 111.0, 112.4, 113.5, 114.2, 115.0, 116.1, 117.0],
            3600,
            18_000.0,
        )
        unstable_anchor = build_candles_from_closes(
            [92, 93, 94.5, 96, 97, 98.2, 99.5, 101.0, 103.2, 105.4, 107.1, 108.8, 110.2, 111.0, 112.4, 110.0, 108.1, 109.0, 107.2, 105.8],
            3600,
            18_000.0,
        )

        result = StrategyResult(
            strategy_name="momentum_burst",
            strategy_type="scalping",
            action="BUY",
            confidence=0.74,
            score=0.64,
            timeframe="1m",
            indicators=[
                IndicatorSnapshot("RSI", 67, 0.45, "Momentum rising", category="momentum"),
                IndicatorSnapshot("EMA Cross", 1.2, 0.52, "Bullish alignment", category="trend"),
                IndicatorSnapshot("Volume", 1.8, 0.38, "Participation improving", category="volume"),
            ],
            reasoning="Up impulse with continuation potential",
            entry_price=117.2,
            stop_loss=114.8,
            take_profit=121.9,
        )
        enhanced = EnhancedScore(
            direction=76,
            direction_label="Biais acheteur",
            confidence=71,
            risk=42,
            setup_quality=67,
            actionability="ACTIONABLE",
            action="BUY",
            market_regime="EXPANDING",
            signal_context="trend_aligned",
        )
        market_context = MarketContext(regime="trend_up", btc_trend="bullish", volatility_percentile=68, volume_ratio=1.7, atr=1.05)
        regime = RegimeInfo(regime="TREND_UP", confidence=0.76, volatility_state="expanding", momentum_state="accelerating")
        scenario = Scenario(name="CONTINUATION", direction="bullish", probability=0.66, reasoning="Impulse remains accepted")

        stable_context = build_scanner_context(
            result=result,
            market_context=market_context,
            regime=regime,
            scenario=scenario,
            enhanced=enhanced,
            primary_candles=stable_primary,
            confirmation_candles=stable_confirmation,
            anchor_candles=stable_anchor,
            context_candles_by_tf={"2h": stable_anchor, "4h": stable_anchor, "6h": stable_anchor},
            btc_closes=[c.close for c in stable_confirmation],
            settings=settings,
            now_ms=int((stable_primary[-1].time + 60) * 1000),
        )
        unstable_context = build_scanner_context(
            result=result,
            market_context=market_context,
            regime=regime,
            scenario=scenario,
            enhanced=enhanced,
            primary_candles=unstable_primary,
            confirmation_candles=unstable_confirmation,
            anchor_candles=unstable_anchor,
            context_candles_by_tf={"2h": unstable_anchor, "4h": unstable_anchor, "6h": unstable_anchor},
            btc_closes=[c.close for c in unstable_confirmation],
            settings=settings,
            now_ms=int((unstable_primary[-1].time + 60) * 1000),
        )

        self.assertGreater(stable_context.reliability_score, unstable_context.reliability_score)
        self.assertGreater(stable_context.composite_score, unstable_context.composite_score)
        self.assertLess(stable_context.execution_risk, unstable_context.execution_risk)


if __name__ == "__main__":
    unittest.main()
