"""Business logic for portfolio value calculations and price fetching."""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

import httpx

from app.core.config import settings


async def fetch_live_prices(symbols: List[str]) -> Dict[str, Decimal]:
    """Call the market-data-service to get current prices for *symbols*.

    Returns a mapping of symbol -> price.  Symbols that could not be resolved
    are silently omitted from the result.
    """
    if not symbols:
        return {}

    url = f"{settings.MARKET_DATA_SERVICE_URL}/api/v1/prices"
    params = {"symbols": ",".join(symbols)}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data: Dict[str, Any] = resp.json()
            # Expected shape: {"prices": {"BTC": 60000.0, ...}}
            raw_prices = data.get("prices", data)
            return {
                sym: Decimal(str(price))
                for sym, price in raw_prices.items()
            }
    except (httpx.HTTPError, ValueError, KeyError):
        # If market-data-service is unreachable, return empty; callers will
        # fall back to the last stored current_price on each position.
        return {}


def calculate_position_pnl(
    quantity: Decimal,
    average_entry_price: Decimal,
    current_price: Decimal,
) -> tuple[Decimal, Decimal]:
    """Return ``(unrealized_pnl, pnl_pct)`` for a single position.

    *pnl_pct* is expressed as a fraction (0.05 == 5 %).
    """
    if quantity == 0 or average_entry_price == 0:
        return Decimal("0"), Decimal("0")

    cost_basis = quantity * average_entry_price
    market_value = quantity * current_price
    unrealized_pnl = market_value - cost_basis
    pnl_pct = unrealized_pnl / cost_basis if cost_basis else Decimal("0")
    return unrealized_pnl, pnl_pct


def calculate_portfolio_value(
    positions: List[Any],
    prices: Optional[Dict[str, Decimal]] = None,
) -> Decimal:
    """Sum the market value of all *positions*.

    If *prices* is provided the live price is used; otherwise each position's
    stored ``current_price`` is used as a fallback.
    """
    prices = prices or {}
    total = Decimal("0")
    for pos in positions:
        price = prices.get(pos.symbol, Decimal(str(pos.current_price)))
        total += Decimal(str(pos.quantity)) * price
    return total


def calculate_allocation(
    positions: List[Any],
    prices: Optional[Dict[str, Decimal]] = None,
) -> List[Dict[str, Union[Decimal, str]]]:
    """Return allocation breakdown by ``asset_type``.

    Each entry contains *asset_type*, *value*, and *percentage* (0-100).
    """
    prices = prices or {}
    type_values: Dict[str, Decimal] = {}

    for pos in positions:
        price = prices.get(pos.symbol, Decimal(str(pos.current_price)))
        value = Decimal(str(pos.quantity)) * price
        type_values[pos.asset_type] = type_values.get(pos.asset_type, Decimal("0")) + value

    total = sum(type_values.values(), Decimal("0"))
    allocation: List[Dict[str, Union[Decimal, str]]] = []
    for asset_type, value in type_values.items():
        pct = (value / total * 100) if total else Decimal("0")
        allocation.append(
            {"asset_type": asset_type, "value": value, "percentage": round(pct, 2)}
        )
    return allocation
