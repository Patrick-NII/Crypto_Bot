"""Shared math primitives for indicators — SMA, EMA, standard deviation.

Extracted verbatim from services/signal_engine.py to avoid duplication.
Pure Python, no external dependencies.
"""

from __future__ import annotations

import math


def sma(prices: list[float], period: int) -> list[float]:
    result: list[float] = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(prices[i])
        else:
            result.append(sum(prices[i - period + 1 : i + 1]) / period)
    return result


def ema(prices: list[float], period: int) -> list[float]:
    k = 2 / (period + 1)
    result = [prices[0]]
    for i in range(1, len(prices)):
        result.append(prices[i] * k + result[-1] * (1 - k))
    return result


def std(prices: list[float], period: int) -> list[float]:
    result: list[float] = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(0.0)
        else:
            window = prices[i - period + 1 : i + 1]
            mean = sum(window) / len(window)
            variance = sum((x - mean) ** 2 for x in window) / len(window)
            result.append(math.sqrt(variance))
    return result
