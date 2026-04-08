"""Symbol info service — cache for Binance exchange filters (LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL).

Exposes a typed ``SymbolInfo`` DTO that the frontend uses to validate orders
client-side BEFORE submission. This eliminates the late-error class where the
user taps a quantity that violates ``stepSize`` and the order is rejected only
after the API round-trip.

The cache is in-memory with a 1h TTL. When the client we cache from belongs to
a user-specific ExchangeClient, the same singleton is safe to share because
the filter values are exchange-wide (not per-user).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from app.services.exchange_client import ExchangeClient, _precision_to_step

logger = logging.getLogger(__name__)

# Cache TTL (seconds). Binance updates exchangeInfo when listing new pairs
# or adjusting filters; 1h is a reasonable compromise.
_CACHE_TTL_SECONDS = 3600


@dataclass(frozen=True)
class SymbolInfo:
    """Parsed exchange filters for a trading pair.

    Fields use ``Decimal`` for financial quantities and ``str`` for anything
    that will be serialised back to the frontend (JSON-safe).
    """

    symbol: str                  # "BTC/USDT"
    base_asset: str              # "BTC"
    quote_asset: str             # "USDT"
    step_size: Decimal           # LOT_SIZE stepSize (e.g. 0.00001)
    tick_size: Decimal           # PRICE_FILTER tickSize (e.g. 0.01)
    min_qty: Decimal             # LOT_SIZE minQty
    max_qty: Decimal             # LOT_SIZE maxQty
    min_notional: Decimal        # MIN_NOTIONAL minNotional (cost floor in quote asset)
    base_precision: int          # digits after the decimal for base amounts
    quote_precision: int         # digits after the decimal for quote amounts
    is_spot: bool = True         # whether the market supports spot trading

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe representation for the API response."""
        return {
            "symbol": self.symbol,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "step_size": str(self.step_size),
            "tick_size": str(self.tick_size),
            "min_qty": str(self.min_qty),
            "max_qty": str(self.max_qty),
            "min_notional": str(self.min_notional),
            "base_precision": self.base_precision,
            "quote_precision": self.quote_precision,
            "is_spot": self.is_spot,
        }


def _precision_decimals(precision: Any) -> int:
    """Return the number of decimal places represented by *precision*.

    CCXT precision is either a step size (``0.00001``) or a decimal count
    (``5``). We always return an integer count here for the frontend.
    """
    step = _precision_to_step(precision)
    if step <= 0:
        return 8
    if step >= 1:
        return 0
    # e.g. 0.00001 -> 5
    import math
    return max(0, int(round(-math.log10(step))))


def _parse_market(symbol: str, market: dict[str, Any]) -> SymbolInfo:
    """Build a ``SymbolInfo`` from a raw CCXT market object."""
    base_asset = str(market.get("base") or symbol.split("/")[0]).upper()
    quote_asset = str(market.get("quote") or (symbol.split("/")[1] if "/" in symbol else "USDT")).upper()

    limits = market.get("limits") or {}
    precision = market.get("precision") or {}

    amount_limits = limits.get("amount") or {}
    price_limits = limits.get("price") or {}
    cost_limits = limits.get("cost") or {}

    step_size = Decimal(str(_precision_to_step(precision.get("amount")) or 0)) or Decimal("0.00000001")
    tick_size = Decimal(str(_precision_to_step(precision.get("price")) or 0)) or Decimal("0.01")

    min_qty_raw = amount_limits.get("min")
    max_qty_raw = amount_limits.get("max")
    min_notional_raw = cost_limits.get("min")

    min_qty = Decimal(str(min_qty_raw)) if min_qty_raw is not None else step_size
    max_qty = Decimal(str(max_qty_raw)) if max_qty_raw is not None else Decimal("9000000")
    min_notional = Decimal(str(min_notional_raw)) if min_notional_raw is not None else Decimal("5")

    base_prec = _precision_decimals(precision.get("amount"))
    quote_prec = _precision_decimals(precision.get("price"))

    is_spot = bool(market.get("spot", True))

    return SymbolInfo(
        symbol=symbol,
        base_asset=base_asset,
        quote_asset=quote_asset,
        step_size=step_size,
        tick_size=tick_size,
        min_qty=min_qty,
        max_qty=max_qty,
        min_notional=min_notional,
        base_precision=base_prec,
        quote_precision=quote_prec,
        is_spot=is_spot,
    )


class SymbolInfoService:
    """In-memory cache + resolver for symbol filters.

    The cache key is the **normalised** symbol ("BTC/USDT"). When a caller
    asks for "BTC", we normalise via ExchangeClient.normalize_symbol first.
    """

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, SymbolInfo]] = {}

    def _get_cached(self, symbol: str) -> Optional[SymbolInfo]:
        entry = self._cache.get(symbol)
        if entry is None:
            return None
        ts, info = entry
        if time.time() - ts > _CACHE_TTL_SECONDS:
            self._cache.pop(symbol, None)
            return None
        return info

    def _put(self, symbol: str, info: SymbolInfo) -> None:
        self._cache[symbol] = (time.time(), info)

    async def get_symbol_info(
        self,
        symbol: str,
        client: ExchangeClient,
    ) -> Optional[SymbolInfo]:
        """Return the ``SymbolInfo`` for *symbol* or ``None`` if the pair doesn't exist.

        Uses *client* to call ``load_markets`` once. Subsequent calls are served
        from cache. If the cached entry expired we refresh transparently.
        """
        normalized = ExchangeClient.normalize_symbol(symbol)
        cached = self._get_cached(normalized)
        if cached is not None:
            return cached

        try:
            await client._ensure_markets_loaded()
        except Exception as exc:
            logger.warning("Failed to load markets for symbol_info lookup: %s", exc)
            return None

        markets = client._exchange.markets or {}
        market = markets.get(normalized)
        if market is None:
            logger.debug("Symbol %s not found in exchange markets", normalized)
            return None

        info = _parse_market(normalized, market)
        self._put(normalized, info)
        return info

    async def validate_symbol(self, symbol: str, client: ExchangeClient) -> bool:
        """Return ``True`` when *symbol* exists on the exchange."""
        info = await self.get_symbol_info(symbol, client)
        return info is not None

    def invalidate(self, symbol: Optional[str] = None) -> None:
        """Invalidate a specific symbol or the whole cache (on admin request)."""
        if symbol is None:
            self._cache.clear()
            return
        self._cache.pop(ExchangeClient.normalize_symbol(symbol), None)


# Module-level singleton used by OrderManager + API
symbol_info_service = SymbolInfoService()
