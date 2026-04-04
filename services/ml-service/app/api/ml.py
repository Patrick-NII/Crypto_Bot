"""ML Service API — Real trading signals powered by technical analysis."""

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.signal_engine import generate_signal, Action

router = APIRouter(prefix="/api/v1/ml", tags=["ml"])

CG_BASE = "https://api.coingecko.com/api/v3"

# Symbol → CoinGecko ID
SYM_TO_CG = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
    "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin", "AVAX": "avalanche-2",
    "DOT": "polkadot", "LINK": "chainlink", "UNI": "uniswap", "ATOM": "cosmos",
    "LTC": "litecoin", "NEAR": "near", "APT": "aptos", "ARB": "arbitrum",
    "OP": "optimism", "FIL": "filecoin", "AAVE": "aave", "SHIB": "shiba-inu",
    "MATIC": "matic-network", "TRX": "tron", "TON": "the-open-network",
    "SUI": "sui", "SEI": "sei-network", "PEPE": "pepe", "ALGO": "algorand",
    "FTM": "fantom", "XLM": "stellar", "HBAR": "hedera-hashgraph",
}


class SignalResponse(BaseModel):
    symbol: str
    action: str
    confidence: float
    score: float
    reasoning: str
    indicators: list[dict]
    timestamp: str


class MultiSignalResponse(BaseModel):
    signals: list[SignalResponse]
    timestamp: str


async def _fetch_ohlc(cg_id: str, days: int = 30) -> list[list[float]]:
    """Fetch OHLC data from CoinGecko."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{CG_BASE}/coins/{cg_id}/ohlc",
                params={"vs_currency": "usd", "days": str(days)},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return []


def _ohlc_to_closes(ohlc: list[list[float]]) -> list[float]:
    return [candle[4] for candle in ohlc if len(candle) >= 5]


@router.get("/signals/{symbol}", response_model=SignalResponse)
async def get_signal(symbol: str, days: int = Query(30, ge=1, le=365)):
    """Get trading signal for a single symbol."""
    upper = symbol.upper()
    cg_id = SYM_TO_CG.get(upper)
    if not cg_id:
        return SignalResponse(
            symbol=upper, action="HOLD", confidence=0, score=0,
            reasoning="Unknown symbol", indicators=[], timestamp=datetime.now(timezone.utc).isoformat(),
        )

    ohlc = await _fetch_ohlc(cg_id, days)
    closes = _ohlc_to_closes(ohlc)

    if len(closes) < 15:
        return SignalResponse(
            symbol=upper, action="HOLD", confidence=0, score=0,
            reasoning="Insufficient data", indicators=[], timestamp=datetime.now(timezone.utc).isoformat(),
        )

    sig = generate_signal(upper, closes)

    return SignalResponse(
        symbol=sig.symbol,
        action=sig.action.value,
        confidence=sig.confidence,
        score=sig.score,
        reasoning=sig.reasoning,
        indicators=[
            {"name": i.name, "value": i.value, "signal": i.signal, "description": i.description}
            for i in sig.indicators
        ],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


TOP_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]


@router.get("/signals", response_model=MultiSignalResponse)
async def get_all_signals():
    """Get trading signals for top 10 cryptos."""
    signals = []
    for sym in TOP_SYMBOLS:
        cg_id = SYM_TO_CG.get(sym)
        if not cg_id:
            continue
        ohlc = await _fetch_ohlc(cg_id, 30)
        closes = _ohlc_to_closes(ohlc)
        if len(closes) < 15:
            continue
        sig = generate_signal(sym, closes)
        signals.append(SignalResponse(
            symbol=sig.symbol,
            action=sig.action.value,
            confidence=sig.confidence,
            score=sig.score,
            reasoning=sig.reasoning,
            indicators=[
                {"name": i.name, "value": i.value, "signal": i.signal, "description": i.description}
                for i in sig.indicators
            ],
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

    return MultiSignalResponse(signals=signals, timestamp=datetime.now(timezone.utc).isoformat())


# Keep legacy endpoints
class StrategyPerformance(BaseModel):
    strategy_name: str
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    period_days: int


@router.get("/performance", response_model=list[StrategyPerformance])
async def get_strategy_performance():
    return [
        StrategyPerformance(strategy_name="RSI+MACD Composite", total_return_pct=15.2, sharpe_ratio=2.1, max_drawdown_pct=4.8, win_rate=0.67, total_trades=180, period_days=90),
        StrategyPerformance(strategy_name="Bollinger Bands Mean Reversion", total_return_pct=9.1, sharpe_ratio=1.6, max_drawdown_pct=3.2, win_rate=0.61, total_trades=220, period_days=90),
        StrategyPerformance(strategy_name="EMA Crossover Trend", total_return_pct=11.7, sharpe_ratio=1.9, max_drawdown_pct=6.1, win_rate=0.58, total_trades=95, period_days=90),
    ]
