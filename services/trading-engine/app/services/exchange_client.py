"""Exchange client wrapping CCXT for unified exchange access.

Provides async methods for placing orders, fetching balances, and
querying tickers across any exchange supported by CCXT.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import ccxt
import ccxt.async_support as ccxt_async

logger = logging.getLogger(__name__)

# Minimum notional fallback (USDT) when market info unavailable
_DEFAULT_MIN_NOTIONAL = 5.0

# ── Binance error code → user-friendly message ──
_BINANCE_ERRORS: dict[int, str] = {
    -1013: "Montant trop petit (minimum ~5 USDT par ordre).",
    -2010: "Solde insuffisant ou paire non autorisee pour ce compte.",
    -2015: "Cle API invalide ou permissions insuffisantes.",
    -1021: "Erreur de synchronisation avec Binance — reessayez.",
    -1111: "Precision du montant incorrecte.",
    -4010: "Quantite invalide (precision non respectee).",
    -1102: "Parametre obligatoire manquant.",
    -1100: "Requete invalide.",
}

# ── CCXT exception type → user-friendly message ──
_CCXT_ERROR_MAP: dict[type, str] = {}  # populated after import


def _init_ccxt_error_map() -> None:
    """Build mapping after ccxt is imported."""
    _CCXT_ERROR_MAP.update({
        ccxt.InsufficientFunds: "Solde insuffisant pour cet ordre.",
        ccxt.InvalidOrder: "Ordre invalide — verifiez le montant et la paire.",
        ccxt.AuthenticationError: "Cle API invalide ou permissions manquantes.",
        ccxt.ExchangeNotAvailable: "Binance temporairement indisponible — reessayez.",
        ccxt.DDoSProtection: "Trop de requetes — attendez quelques secondes.",
        ccxt.RequestTimeout: "Timeout — Binance n'a pas repondu a temps.",
        ccxt.BadRequest: "Requete incorrecte — verifiez les parametres.",
    })


_init_ccxt_error_map()


def parse_exchange_error(exc: Exception) -> str:
    """Extract a clear user-facing message from a CCXT/Binance exception."""
    msg = str(exc)

    # Try to extract Binance error code from the message
    # Format: binance {"code":-XXXX,"msg":"..."}
    import re
    code_match = re.search(r'"code"\s*:\s*(-?\d+)', msg)
    if code_match:
        code = int(code_match.group(1))
        if code in _BINANCE_ERRORS:
            return _BINANCE_ERRORS[code]

    # Fallback: match by CCXT exception type
    for exc_type, user_msg in _CCXT_ERROR_MAP.items():
        if isinstance(exc, exc_type):
            return user_msg

    # Last resort: clean up the raw message
    if len(msg) > 150:
        return "Erreur lors de l'execution de l'ordre."
    return msg


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
    # Market info / filters
    # ------------------------------------------------------------------

    async def _ensure_markets_loaded(self) -> None:
        """Load exchange markets if not already cached."""
        if not self._exchange.markets:
            await self._exchange.load_markets()

    async def adjust_quantity(self, symbol: str, quantity: float, price: float) -> float:
        """Adjust quantity to respect Binance LOT_SIZE and MIN_NOTIONAL filters.

        - Rounds quantity down to the allowed step size
        - Ensures notional (qty * price) >= minNotional
        - Returns 0 if the order is too small to be valid
        """
        symbol = self.normalize_symbol(symbol)
        try:
            await self._ensure_markets_loaded()
        except Exception as exc:
            logger.warning("Could not load markets for filter check: %s", exc)
            return quantity  # proceed without adjustment

        market = self._exchange.markets.get(symbol)
        if not market:
            return quantity

        limits = market.get("limits", {})
        precision = market.get("precision", {})

        # Step size (LOT_SIZE filter)
        amount_min = limits.get("amount", {}).get("min")
        amount_precision = precision.get("amount")

        if amount_precision is not None:
            # Round down to allowed decimal places
            factor = 10 ** int(amount_precision)
            quantity = math.floor(quantity * factor) / factor

        if amount_min and quantity < amount_min:
            logger.warning("Quantity %s below minimum %s for %s", quantity, amount_min, symbol)
            return 0.0

        # Min notional (NOTIONAL / MIN_NOTIONAL filter)
        cost_min = limits.get("cost", {}).get("min")
        min_notional = cost_min if cost_min else _DEFAULT_MIN_NOTIONAL
        notional = quantity * price

        if notional < min_notional:
            # Try to bump quantity up to meet minimum
            adjusted = min_notional / price
            if amount_precision is not None:
                factor = 10 ** int(amount_precision)
                adjusted = math.ceil(adjusted * factor) / factor
            logger.info(
                "Notional %.4f < min %.2f for %s — adjusting qty from %.8f to %.8f",
                notional, min_notional, symbol, quantity, adjusted,
            )
            quantity = adjusted

        return quantity

    # ------------------------------------------------------------------
    # Order methods
    # ------------------------------------------------------------------

    async def place_market_order(
        self, symbol: str, side: str, quantity: float, price: float = 0.0
    ) -> Dict[str, Any]:
        """Place a market order with automatic filter adjustment."""
        symbol = self.normalize_symbol(symbol)

        # Fetch current price if not provided (needed for notional check)
        if price <= 0:
            try:
                ticker = await self._exchange.fetch_ticker(symbol)
                price = ticker.get("last", 0) or ticker.get("close", 0) or 0
            except Exception:
                pass

        # Adjust quantity for Binance filters
        if price > 0:
            quantity = await self.adjust_quantity(symbol, quantity, price)
            if quantity <= 0:
                raise ValueError(f"Order too small for {symbol} after filter adjustment (min notional: {_DEFAULT_MIN_NOTIONAL} USDT)")

        logger.info("Placing MARKET %s %.8f %s (notional ~%.2f)", side, quantity, symbol, quantity * price)
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
            raise ValueError(parse_exchange_error(exc)) from exc

    async def place_limit_order(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> Dict[str, Any]:
        """Place a limit order with automatic filter adjustment."""
        symbol = self.normalize_symbol(symbol)

        # Adjust quantity for Binance filters
        quantity = await self.adjust_quantity(symbol, quantity, price)
        if quantity <= 0:
            raise ValueError(f"Order too small for {symbol} after filter adjustment")

        logger.info("Placing LIMIT %s %.8f %s @ %.4f", side, quantity, symbol, price)
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
            raise ValueError(parse_exchange_error(exc)) from exc

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
