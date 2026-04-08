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


def _precision_to_step(precision: Any) -> float:
    """Convert CCXT precision to step size.

    CCXT returns precision as:
    - a step size (float like 0.00001) — newer format
    - a decimal places count (int like 5) — older format
    """
    if precision is None:
        return 0.0
    try:
        val = float(precision)
    except (TypeError, ValueError):
        return 0.0
    if val <= 0:
        return 0.0
    # If > 1, treat as decimal places count (e.g. 5 → 0.00001)
    if val >= 1:
        return 10 ** (-int(val))
    # Otherwise, it's already a step size (e.g. 0.00001)
    return val
_ESTIMATED_FEE_RATE = 0.001

# Error handling now delegates to the structured error catalog.
from app.services.error_catalog import classify_error, ErrorDetail


def parse_exchange_error(exc: Exception) -> str:
    """Return a user-friendly French message for a CCXT/Binance exception.

    Backward compat: still returns a string. For structured info use classify_error().
    """
    return classify_error(exc).user_message


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
            # Acknowledge the CCXT warning about higher rate limits when
            # querying open orders without a symbol. We do it intentionally
            # for the "all markets" polling path — CCXT still enforces the
            # Binance rate limiter.
            "options": {
                "warnOnFetchOpenOrdersWithoutSymbol": False,
            },
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

    async def validate_symbol(self, symbol: str) -> bool:
        """Return True when *symbol* exists in the exchange markets.

        Accepts any form (BTC, BTC/USDT, BTCUSDT) and normalises before
        checking. Loads markets on demand.
        """
        normalized = self.normalize_symbol(symbol)
        try:
            await self._ensure_markets_loaded()
        except Exception as exc:
            logger.warning("Could not load markets while validating %s: %s", symbol, exc)
            return False
        return normalized in (self._exchange.markets or {})

    async def adjust_quantity(self, symbol: str, quantity: float, price: float, side: str = "buy") -> float:
        """Adjust quantity to respect Binance LOT_SIZE and MIN_NOTIONAL filters.

        - Rounds quantity down to the allowed step size
        - For buy: ensures notional (qty * price) >= minNotional (bumps up)
        - For sell: does NOT bump up (user can't sell more than they have)
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

        # CCXT returns precision as either:
        # - a step size (float like 0.00001) — newer format
        # - a decimal places count (int like 5) — older format
        step = _precision_to_step(amount_precision)

        if step and step > 0:
            # Round down to nearest step
            quantity = math.floor(quantity / step) * step

        if amount_min and quantity < amount_min:
            logger.warning("Quantity %s below minimum %s for %s", quantity, amount_min, symbol)
            return 0.0

        # Min notional (NOTIONAL / MIN_NOTIONAL filter)
        cost_min = limits.get("cost", {}).get("min")
        min_notional = cost_min if cost_min else _DEFAULT_MIN_NOTIONAL
        notional = quantity * price

        if notional < min_notional and side == "buy":
            # Only bump up for buys (sell can't exceed available balance)
            adjusted = min_notional / price
            if step and step > 0:
                adjusted = math.ceil(adjusted / step) * step
            logger.info(
                "Notional %.4f < min %.2f for %s (buy) — adjusting qty from %.8f to %.8f",
                notional, min_notional, symbol, quantity, adjusted,
            )
            quantity = adjusted

        return quantity

    # ------------------------------------------------------------------
    # Order methods
    # ------------------------------------------------------------------

    # Alternative quote currencies to try when primary fails
    _ALT_QUOTES = ["EUR", "USDC", "BUSD", "BTC"]

    async def _detect_best_pair(self, base: str, preferred_symbol: str, side: str = "buy") -> str:
        """Choose the best executable pair for the user.

        For buy orders, prefer a market whose quote asset the user actually holds.
        """
        await self._ensure_markets_loaded()
        preferred_quote = preferred_symbol.split("/")[1] if "/" in preferred_symbol else "USDT"
        preferred_exists = preferred_symbol in (self._exchange.markets or {})

        if side != "buy":
            if preferred_exists:
                return preferred_symbol
            for quote in self._ALT_QUOTES:
                alt = f"{base}/{quote}"
                if alt in (self._exchange.markets or {}):
                    return alt
            return preferred_symbol

        free_balances: dict[str, float] = {}
        try:
            balance = await self._exchange.fetch_balance()
            free_balances = {
                str(asset).upper(): float(amount or 0)
                for asset, amount in (balance.get("free", {}) or {}).items()
            }
        except Exception:
            free_balances = {}

        candidate_quotes: list[str] = [preferred_quote, *self._ALT_QUOTES]
        seen: set[str] = set()
        for quote in candidate_quotes:
            quote = quote.upper()
            if quote in seen:
                continue
            seen.add(quote)
            pair = f"{base}/{quote}"
            if pair not in (self._exchange.markets or {}):
                continue
            if float(free_balances.get(quote, 0) or 0) > 0:
                return pair

        if preferred_exists:
            return preferred_symbol

        for quote in self._ALT_QUOTES:
            alt = f"{base}/{quote}"
            if alt in (self._exchange.markets or {}):
                return alt

        return preferred_symbol  # fallback

    def _market_min_notional(self, symbol: str) -> float:
        market = (self._exchange.markets or {}).get(symbol, {})
        limits = market.get("limits", {}) if isinstance(market, dict) else {}
        cost_min = (limits.get("cost", {}) or {}).get("min")
        return float(cost_min) if cost_min else _DEFAULT_MIN_NOTIONAL

    async def preview_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        reference_price: float = 0.0,
    ) -> Dict[str, Any]:
        """Return an execution preview for a market order without placing it."""
        normalized = self.normalize_symbol(symbol)
        base_asset, preferred_quote = normalized.split("/")
        symbol_to_use = await self._detect_best_pair(base_asset, normalized, side=side)
        base_for_order, quote_asset = symbol_to_use.split("/")
        notes: list[str] = []

        await self._ensure_markets_loaded()
        balances = await self._exchange.fetch_balance()
        free = balances.get("free", {}) or {}
        available_quote = float(free.get(quote_asset, 0) or 0)
        available_base = float(free.get(base_for_order, 0) or 0)

        estimated_price = reference_price if reference_price > 0 else 0.0
        volume_24h_quote: float = 0.0
        try:
            ticker = await self._exchange.fetch_ticker(symbol_to_use)
            estimated_price = float(ticker.get("last", 0) or ticker.get("close", 0) or estimated_price or 0)
            volume_24h_quote = float(ticker.get("quoteVolume", 0) or 0)
        except Exception:
            estimated_price = float(estimated_price or 0)

        requested_notional = quantity * reference_price if reference_price > 0 else 0.0
        adjusted_quantity = quantity

        if symbol_to_use != normalized:
            notes.append(f"Execution reroutee vers {symbol_to_use}.")
            if estimated_price > 0 and requested_notional > 0:
                adjusted_quantity = requested_notional / estimated_price

        min_notional = self._market_min_notional(symbol_to_use)
        if estimated_price > 0:
            adjusted_quantity = await self.adjust_quantity(symbol_to_use, adjusted_quantity, estimated_price, side=side)

        estimated_notional = adjusted_quantity * estimated_price if estimated_price > 0 else 0.0
        estimated_fee = estimated_notional * _ESTIMATED_FEE_RATE if estimated_notional > 0 else 0.0
        settlement_total = estimated_notional + estimated_fee if side == "buy" else max(estimated_notional - estimated_fee, 0)
        can_execute = True
        blocking_reason: str | None = None
        conversion_symbol: str | None = None
        conversion_side: str | None = None
        conversion_from_asset: str | None = None
        conversion_required_quantity: float | None = None
        conversion_estimated_spend: float | None = None

        if side == "buy":
            if available_quote <= 0:
                can_execute = False
                alternative_balances = []
                for quote in ["EUR", "USDT", "USDC", "BUSD", "BTC"]:
                    amount = float(free.get(quote, 0) or 0)
                    if amount > 0:
                        alternative_balances.append(f"{quote} {amount:.2f}")
                if alternative_balances:
                    blocking_reason = (
                        f"Aucun solde {quote_asset} disponible pour {symbol_to_use}. "
                        f"Soldes detectes: {', '.join(alternative_balances)}."
                    )
                    eur_pair = f"{base_asset}/EUR"
                    if float(free.get("EUR", 0) or 0) > 0 and eur_pair not in (self._exchange.markets or {}):
                        notes.append(f"La paire {eur_pair} n'existe pas sur Binance.")
                else:
                    blocking_reason = f"Aucun solde {quote_asset} disponible pour acheter {base_for_order}."

                required_quote_quantity = settlement_total * 1.005 if settlement_total > 0 else estimated_notional
                for funding_asset in ["EUR", "USD", "USDC", "BUSD", "BTC"]:
                    if funding_asset == quote_asset:
                        continue
                    funding_balance = float(free.get(funding_asset, 0) or 0)
                    if funding_balance <= 0:
                        continue
                    direct_symbol = f"{quote_asset}/{funding_asset}"
                    inverse_symbol = f"{funding_asset}/{quote_asset}"
                    direct_exists = direct_symbol in (self._exchange.markets or {})
                    inverse_exists = inverse_symbol in (self._exchange.markets or {})

                    if direct_exists:
                        candidate_required_quantity = required_quote_quantity if required_quote_quantity > 0 else None
                        candidate_estimated_spend: float | None = None
                        try:
                            conversion_ticker = await self._exchange.fetch_ticker(direct_symbol)
                            conversion_price = float(
                                conversion_ticker.get("last", 0) or conversion_ticker.get("close", 0) or 0
                            )
                            if conversion_price > 0 and candidate_required_quantity is not None:
                                candidate_estimated_spend = candidate_required_quantity * conversion_price * (1 + _ESTIMATED_FEE_RATE)
                        except Exception:
                            candidate_estimated_spend = None

                        if candidate_estimated_spend is None or funding_balance + 1e-12 >= candidate_estimated_spend:
                            conversion_symbol = direct_symbol
                            conversion_side = "buy"
                            conversion_from_asset = funding_asset
                            conversion_required_quantity = candidate_required_quantity
                            conversion_estimated_spend = candidate_estimated_spend
                            notes.append(
                                f"Vous pouvez acheter {quote_asset} avec {funding_asset} via {direct_symbol} pour financer cet achat."
                            )
                            break

                    if inverse_exists:
                        candidate_required_quantity: float | None = None
                        candidate_estimated_spend: float | None = None
                        try:
                            conversion_ticker = await self._exchange.fetch_ticker(inverse_symbol)
                            conversion_price = float(
                                conversion_ticker.get("last", 0) or conversion_ticker.get("close", 0) or 0
                            )
                            if conversion_price > 0 and required_quote_quantity > 0:
                                candidate_required_quantity = (required_quote_quantity / conversion_price) * (1 + _ESTIMATED_FEE_RATE)
                                candidate_estimated_spend = candidate_required_quantity
                        except Exception:
                            candidate_required_quantity = None
                            candidate_estimated_spend = None

                        if candidate_estimated_spend is None or funding_balance + 1e-12 >= candidate_estimated_spend:
                            conversion_symbol = inverse_symbol
                            conversion_side = "sell"
                            conversion_from_asset = funding_asset
                            conversion_required_quantity = candidate_required_quantity
                            conversion_estimated_spend = candidate_estimated_spend
                            notes.append(
                                f"Vous pouvez vendre {funding_asset} contre {quote_asset} via {inverse_symbol} pour financer cet achat."
                            )
                            break
            elif settlement_total > 0 and available_quote + 1e-12 < settlement_total:
                can_execute = False
                blocking_reason = (
                    f"Solde {quote_asset} insuffisant: {available_quote:.2f} disponible, "
                    f"~{settlement_total:.2f} requis."
                )
        else:
            if available_base + 1e-12 < adjusted_quantity:
                can_execute = False
                blocking_reason = (
                    f"Quantite {base_for_order} insuffisante: {available_base:.6f} disponible, "
                    f"{adjusted_quantity:.6f} requis."
                )
            elif min_notional > 0 and estimated_notional > 0 and estimated_notional < min_notional:
                can_execute = False
                blocking_reason = (
                    f"Valeur de vente trop faible: {estimated_notional:.4f} {quote_asset} (minimum {min_notional} {quote_asset}). "
                    f"Il faut au moins {(min_notional / estimated_price):.6f} {base_for_order} pour atteindre le minimum."
                )

        if normalized != symbol_to_use and preferred_quote != quote_asset and not any(
            pair == f"{base_asset}/{preferred_quote}" for pair in (self._exchange.markets or {})
        ):
            notes.append(f"La paire {base_asset}/{preferred_quote} n'existe pas sur Binance.")

        # Slippage warning: if order > 0.5% of 24h quote volume
        if volume_24h_quote > 0 and estimated_notional > 0:
            volume_pct = (estimated_notional / volume_24h_quote) * 100
            if volume_pct > 0.5:
                notes.append(
                    f"Slippage possible: cet ordre represente {volume_pct:.2f}% du volume 24h ({symbol_to_use})."
                )

        # Warn when symbol was rerouted (different quote currency than requested)
        if normalized != symbol_to_use:
            notes.append(f"Paire reroute de {normalized} vers {symbol_to_use}.")

        return {
            "requested_symbol": normalized,
            "resolved_symbol": symbol_to_use,
            "base_asset": base_for_order,
            "quote_asset": quote_asset,
            "input_quantity": quantity,
            "adjusted_quantity": adjusted_quantity,
            "reference_price": reference_price if reference_price > 0 else None,
            "estimated_price": estimated_price if estimated_price > 0 else None,
            "estimated_notional": estimated_notional if estimated_notional > 0 else None,
            "estimated_fee": estimated_fee if estimated_fee > 0 else None,
            "fee_rate": _ESTIMATED_FEE_RATE,
            "min_notional": min_notional,
            "available_quote": available_quote if quote_asset else None,
            "available_base": available_base if base_for_order else None,
            "conversion_symbol": conversion_symbol,
            "conversion_side": conversion_side,
            "conversion_from_asset": conversion_from_asset,
            "conversion_required_quantity": conversion_required_quantity,
            "conversion_estimated_spend": conversion_estimated_spend,
            "can_execute": can_execute,
            "blocking_reason": blocking_reason,
            "notes": notes,
        }

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float = 0.0,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Place a market order with automatic pair detection and filter adjustment.

        If the user has EUR instead of USDT, automatically switches to EUR pair.
        Extra ``params`` (e.g. ``{"newClientOrderId": "..."}``) are forwarded
        to CCXT verbatim.
        """
        preview = await self.preview_market_order(symbol, side, quantity, reference_price=price)
        symbol_to_use = str(preview["resolved_symbol"])
        quantity = float(preview["adjusted_quantity"] or quantity)
        price = float(preview["estimated_price"] or price or 0)

        if not bool(preview["can_execute"]):
            raise ValueError(str(preview["blocking_reason"] or "Ordre non executable dans l'etat actuel."))

        logger.info("Placing MARKET %s %.8f %s (notional ~%.2f)", side, quantity, symbol_to_use, quantity * price)
        try:
            result = await self._exchange.create_order(
                symbol=symbol_to_use,
                type="market",
                side=side,
                amount=quantity,
                params=params or {},
            )
            logger.info("Market order placed: %s on %s", result.get("id"), symbol_to_use)
            return result
        except ccxt.BaseError as exc:
            logger.error("Market order failed on %s: %s", symbol_to_use, exc)
            raise ValueError(parse_exchange_error(exc)) from exc

    async def place_market_order_quote(
        self,
        symbol: str,
        side: str,
        quote_quantity: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Place a BUY market order using Binance ``quoteOrderQty``.

        The user specifies how much quote asset (e.g. USDT) they want to
        spend, and Binance converts it to the matching base amount.

        Note: Binance only supports ``quoteOrderQty`` for BUY market orders.
        For SELL market orders, the caller must convert quote -> base first.
        """
        normalized = self.normalize_symbol(symbol)
        merged_params: Dict[str, Any] = {
            "quoteOrderQty": str(quote_quantity),
            **(params or {}),
        }
        logger.info(
            "Placing MARKET %s quoteOrderQty=%.4f on %s",
            side,
            quote_quantity,
            normalized,
        )
        try:
            result = await self._exchange.create_order(
                symbol=normalized,
                type="market",
                side=side,
                amount=None,
                price=None,
                params=merged_params,
            )
            logger.info(
                "Market-quote order placed: %s on %s",
                result.get("id"),
                normalized,
            )
            return result
        except ccxt.BaseError as exc:
            logger.error("Market-quote order failed on %s: %s", normalized, exc)
            raise ValueError(parse_exchange_error(exc)) from exc

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Place a limit order with automatic filter adjustment."""
        symbol = self.normalize_symbol(symbol)

        # Adjust quantity for Binance filters
        quantity = await self.adjust_quantity(symbol, quantity, price, side=side)
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
                params=params or {},
            )
            logger.info("Limit order placed: %s", result.get("id"))
            return result
        except ccxt.BaseError as exc:
            logger.error("Limit order failed: %s", exc)
            raise ValueError(parse_exchange_error(exc)) from exc

    async def place_stop_loss_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
        limit_price: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Place a STOP_LOSS_LIMIT order on Binance via CCXT.

        ``stop_price`` is the trigger; ``limit_price`` is the limit posted
        once the trigger fires.
        """
        normalized = self.normalize_symbol(symbol)
        merged_params = {"stopPrice": str(stop_price), **(params or {})}
        logger.info(
            "Placing STOP_LOSS_LIMIT %s %.8f %s stop=%.4f limit=%.4f",
            side, quantity, normalized, stop_price, limit_price,
        )
        try:
            return await self._exchange.create_order(
                symbol=normalized,
                type="STOP_LOSS_LIMIT",
                side=side,
                amount=quantity,
                price=limit_price,
                params=merged_params,
            )
        except ccxt.BaseError as exc:
            logger.error("STOP_LOSS_LIMIT failed: %s", exc)
            raise ValueError(parse_exchange_error(exc)) from exc

    async def place_take_profit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
        limit_price: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Place a TAKE_PROFIT_LIMIT order on Binance via CCXT."""
        normalized = self.normalize_symbol(symbol)
        merged_params = {"stopPrice": str(stop_price), **(params or {})}
        logger.info(
            "Placing TAKE_PROFIT_LIMIT %s %.8f %s stop=%.4f limit=%.4f",
            side, quantity, normalized, stop_price, limit_price,
        )
        try:
            return await self._exchange.create_order(
                symbol=normalized,
                type="TAKE_PROFIT_LIMIT",
                side=side,
                amount=quantity,
                price=limit_price,
                params=merged_params,
            )
        except ccxt.BaseError as exc:
            logger.error("TAKE_PROFIT_LIMIT failed: %s", exc)
            raise ValueError(parse_exchange_error(exc)) from exc

    async def place_oco_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_price: float,
        stop_limit_price: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Place a Binance OCO order: take-profit limit + stop-loss-limit.

        ``price`` is the upper take-profit limit; ``stop_price`` is the
        trigger for the stop-loss; ``stop_limit_price`` is the limit posted
        once the stop trigger fires.
        """
        normalized = self.normalize_symbol(symbol)
        await self._ensure_markets_loaded()
        request = {
            "symbol": normalized.replace("/", ""),
            "side": side.upper(),
            "quantity": str(quantity),
            "price": str(price),
            "stopPrice": str(stop_price),
            "stopLimitPrice": str(stop_limit_price),
            "stopLimitTimeInForce": "GTC",
        }
        if params:
            request.update(params)
        logger.info(
            "Placing OCO %s %.8f %s tp=%.4f stop=%.4f stop_limit=%.4f",
            side, quantity, normalized, price, stop_price, stop_limit_price,
        )
        try:
            # Binance exposes OCO via the dedicated endpoint
            method = getattr(self._exchange, "private_post_order_oco", None)
            if method is None:
                # Fallback for older CCXT versions
                method = getattr(self._exchange, "private_post_orderoco", None)
            if method is None:
                raise ValueError("OCO not supported by this CCXT version.")
            return await method(request)
        except ccxt.BaseError as exc:
            logger.error("OCO failed: %s", exc)
            raise ValueError(parse_exchange_error(exc)) from exc

    async def fetch_closed_orders(
        self,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return historical (closed) orders from the exchange.

        Binance requires a symbol for this call. When no symbol is given we
        return an empty list rather than raising — the caller will fall back
        to its local cache (the in-memory live order store).
        """
        if not symbol:
            return []
        symbol = self.normalize_symbol(symbol)
        try:
            if hasattr(self._exchange, "fetch_closed_orders"):
                return await self._exchange.fetch_closed_orders(symbol, limit=limit)
            if hasattr(self._exchange, "fetch_orders"):
                return await self._exchange.fetch_orders(symbol, limit=limit)
        except ccxt.BaseError as exc:
            logger.warning("fetch_closed_orders failed: %s", exc)
        return []

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
