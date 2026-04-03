"""Exchange client wrapping CCXT for unified exchange access.

Provides async methods for placing orders, fetching balances, and
querying tickers across any exchange supported by CCXT.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import ccxt
import ccxt.async_support as ccxt_async

logger = logging.getLogger(__name__)


class ExchangeClient:
    """Unified exchange interface via CCXT.

    Supports both live and sandbox (paper) modes.  When *sandbox* is
    ``True`` the client enables the exchange's built-in test/sandbox
    environment (if available).
    """

    def __init__(
        self,
        exchange_id: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        sandbox: bool = False,
    ) -> None:
        exchange_class = getattr(ccxt_async, exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Unsupported exchange: {exchange_id}")

        config: Dict[str, Any] = {
            "enableRateLimit": True,
        }
        if api_key and api_secret:
            config["apiKey"] = api_key
            config["secret"] = api_secret

        self._exchange: ccxt_async.Exchange = exchange_class(config)

        if sandbox:
            try:
                self._exchange.set_sandbox_mode(True)
                logger.info("Exchange %s initialised in SANDBOX mode", exchange_id)
            except ccxt.NotSupported:
                logger.warning(
                    "Exchange %s does not support sandbox mode; proceeding in live mode",
                    exchange_id,
                )
        else:
            logger.info("Exchange %s initialised in LIVE mode", exchange_id)

        self._exchange_id = exchange_id

    # ------------------------------------------------------------------
    # Symbol helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """Normalise a symbol to a CCXT-compatible trading pair.

        Examples:
            ``"BTC"``       -> ``"BTC/USDT"``
            ``"BTC/USDT"``  -> ``"BTC/USDT"``
            ``"BTCUSDT"``   -> ``"BTC/USDT"``  (best-effort)
            ``"eth"``       -> ``"ETH/USDT"``
        """
        symbol = symbol.strip().upper()

        # Already in correct form
        if "/" in symbol:
            return symbol

        # Common quote currencies to detect in concatenated symbols
        quote_currencies = ["USDT", "USDC", "BUSD", "USD", "BTC", "ETH", "BNB"]
        for quote in quote_currencies:
            if symbol.endswith(quote) and len(symbol) > len(quote):
                base = symbol[: -len(quote)]
                return f"{base}/{quote}"

        # Bare base asset -- default to USDT pair
        return f"{symbol}/USDT"

    # ------------------------------------------------------------------
    # Order methods
    # ------------------------------------------------------------------

    async def place_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> Dict[str, Any]:
        """Place a market order and return the exchange response."""
        symbol = self.normalize_symbol(symbol)
        logger.info("Placing MARKET %s %s %s", side, quantity, symbol)
        try:
            result = await self._exchange.create_order(
                symbol=symbol,
                type="market",
                side=side,
                amount=quantity,
            )
            logger.info("Market order placed: %s", result.get("id"))
            return result
        except ccxt.BaseError as exc:
            logger.error("Market order failed: %s", exc)
            raise

    async def place_limit_order(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> Dict[str, Any]:
        """Place a limit order and return the exchange response."""
        symbol = self.normalize_symbol(symbol)
        logger.info("Placing LIMIT %s %s %s @ %s", side, quantity, symbol, price)
        try:
            result = await self._exchange.create_order(
                symbol=symbol,
                type="limit",
                side=side,
                amount=quantity,
                price=price,
            )
            logger.info("Limit order placed: %s", result.get("id"))
            return result
        except ccxt.BaseError as exc:
            logger.error("Limit order failed: %s", exc)
            raise

    async def cancel_order(
        self, exchange_order_id: str, symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cancel an open order on the exchange."""
        if symbol:
            symbol = self.normalize_symbol(symbol)
        logger.info("Cancelling order %s on %s", exchange_order_id, symbol)
        try:
            result = await self._exchange.cancel_order(exchange_order_id, symbol)
            logger.info("Order %s cancelled", exchange_order_id)
            return result
        except ccxt.BaseError as exc:
            logger.error("Cancel order failed: %s", exc)
            raise

    async def get_order(
        self, exchange_order_id: str, symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch the current state of an order from the exchange."""
        if symbol:
            symbol = self.normalize_symbol(symbol)
        try:
            result = await self._exchange.fetch_order(exchange_order_id, symbol)
            return result
        except ccxt.BaseError as exc:
            logger.error("Fetch order failed: %s", exc)
            raise

    async def get_open_orders(
        self, symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return all open orders, optionally filtered by symbol."""
        if symbol:
            symbol = self.normalize_symbol(symbol)
        try:
            result = await self._exchange.fetch_open_orders(symbol)
            return result
        except ccxt.BaseError as exc:
            logger.error("Fetch open orders failed: %s", exc)
            raise

    async def get_balance(self) -> Dict[str, Any]:
        """Return account balances from the exchange."""
        try:
            result = await self._exchange.fetch_balance()
            return result
        except ccxt.BaseError as exc:
            logger.error("Fetch balance failed: %s", exc)
            raise

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch the latest ticker for *symbol*."""
        symbol = self.normalize_symbol(symbol)
        try:
            result = await self._exchange.fetch_ticker(symbol)
            return result
        except ccxt.BaseError as exc:
            logger.error("Fetch ticker failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying exchange connection."""
        await self._exchange.close()
