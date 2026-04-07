"""Order manager -- orchestrates the full order lifecycle.

Flow:
  1. Fetch current price from the market-data service.
  2. Validate the order via the risk service.
  3. Execute via the paper trader or the live exchange client.
  4. Publish an event to Redis.
  5. Return the resulting order.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.models.order import (
    Order,
    OrderCreate,
    OrderPreflightResponse,
    OrderSide,
    OrderStatus,
    OrderType,
)
from app.services.exchange_client import ExchangeClient
from app.services.paper_trader import PaperTrader

logger = logging.getLogger(__name__)
_STABLES = {"USDT", "USDC", "BUSD", "FDUSD", "USD", "DAI", "TUSD"}


class OrderManager:
    """Orchestrates order flow: validation -> risk check -> execution -> notification."""

    def __init__(self) -> None:
        self._paper_trader = PaperTrader()
        self._exchange_client: Optional[ExchangeClient] = None
        self._redis: Any = None  # set via ``init_redis``
        self._http = httpx.AsyncClient(timeout=settings.ORDER_TIMEOUT_SECONDS)

        # Initialise a fallback exchange client from env vars for live mode
        if settings.TRADING_MODE == "live" and settings.BINANCE_API_KEY:
            self._exchange_client = ExchangeClient(
                exchange_id=settings.DEFAULT_EXCHANGE,
                api_key=settings.BINANCE_API_KEY,
                api_secret=settings.BINANCE_API_SECRET,
                sandbox=False,
            )

    # ------------------------------------------------------------------
    # Per-user exchange client from auth-service credentials
    # ------------------------------------------------------------------

    async def _get_user_exchange_client(
        self,
        auth_header: Optional[str],
        provider: str = "binance",
    ) -> Optional[ExchangeClient]:
        """Fetch decrypted credentials from the auth-service and build an ExchangeClient."""
        if not auth_header:
            return None
        url = f"{settings.AUTH_SERVICE_URL}/api/v1/auth/me/exchange-connections/{provider}/credentials"
        try:
            resp = await self._http.get(url, headers={"Authorization": auth_header})
            if resp.status_code != 200:
                logger.warning("Could not fetch user credentials (status %s): %s", resp.status_code, resp.text)
                return None
            creds = resp.json()
            return ExchangeClient(
                exchange_id=provider,
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                sandbox=creds.get("sandbox_mode", False),
            )
        except Exception as exc:
            logger.warning("Failed to fetch user exchange credentials: %s", exc)
            return None

    async def init_redis(self) -> None:
        """Lazily connect to Redis (called during app startup)."""
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                decode_responses=True,
            )
            await self._redis.ping()
            logger.info("Redis connection established")
        except Exception as exc:
            logger.warning("Redis unavailable, events will not be published: %s", exc)
            self._redis = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_order(
        self,
        order_create: OrderCreate,
        user_id: str = "default",
        auth_header: Optional[str] = None,
    ) -> Order:
        """Create, validate, execute, and publish an order.

        Raises ``ValueError`` for validation failures and ``RuntimeError``
        for execution errors.
        """
        # 1. Normalise symbol
        symbol = ExchangeClient.normalize_symbol(order_create.symbol)
        order_create.symbol = symbol

        # 2. Fetch current price
        current_price = await self._fetch_current_price(symbol)

        # 3. Risk evaluation (best-effort -- if risk service is down we still allow paper)
        risk_approved = await self._evaluate_risk(
            order_create,
            current_price,
            user_id,
            auth_header=auth_header,
        )
        if not risk_approved:
            order = Order(
                symbol=symbol,
                side=order_create.side,
                order_type=order_create.order_type,
                status=OrderStatus.FAILED,
                quantity=order_create.quantity,
                price=order_create.price,
                stop_price=order_create.stop_price,
                take_profit_price=order_create.take_profit_price,
                trailing_pct=order_create.trailing_pct,
                exchange="paper" if settings.TRADING_MODE == "paper" else settings.DEFAULT_EXCHANGE,
                portfolio_id=order_create.portfolio_id,
                strategy=order_create.strategy,
                error_message="Order rejected by risk service",
            )
            await self._publish_event("ORDER_FAILED", order, user_id=user_id)
            return order

        # 4. Execute — try live with per-user credentials, fallback to paper
        if auth_header:
            user_client = await self._get_user_exchange_client(auth_header)
            if user_client is not None:
                try:
                    order = await self._execute_live(order_create, exchange_client=user_client)
                except ValueError as exc:
                    # User-facing error (translated by parse_exchange_error)
                    await user_client.close()
                    raise ValueError(str(exc)) from exc
                except Exception as exc:
                    await user_client.close()
                    raise RuntimeError(f"Erreur technique: {exc}")
                finally:
                    await user_client.close()
            elif settings.TRADING_MODE == "live" and self._exchange_client:
                order = await self._execute_live(order_create)
            else:
                order = await self._execute_paper(order_create, current_price, user_id)
        elif settings.TRADING_MODE == "paper":
            order = await self._execute_paper(order_create, current_price, user_id)
        else:
            order = await self._execute_live(order_create)

        # 5. Publish event
        event_type = (
            "ORDER_FILLED" if order.status == OrderStatus.FILLED else "ORDER_CREATED"
        )
        await self._publish_event(event_type, order, user_id=user_id)

        return order

    async def preview_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        user_id: str = "default",
        reference_price: Optional[Decimal] = None,
        auth_header: Optional[str] = None,
    ) -> OrderPreflightResponse:
        """Return a preflight preview for the requested order."""
        normalized_symbol = ExchangeClient.normalize_symbol(symbol)
        client: Optional[ExchangeClient] = None
        should_close = False

        if auth_header:
            client = await self._get_user_exchange_client(auth_header)
            should_close = client is not None

        if client is None and settings.TRADING_MODE == "live" and self._exchange_client:
            client = self._exchange_client

        if client is None:
            base_asset, quote_asset = normalized_symbol.split("/")
            if settings.TRADING_MODE == "paper":
                paper_balances = await self._paper_trader.get_balance(user_id)
                current_price = await self._fetch_current_price(normalized_symbol)
                estimated_notional = quantity * current_price
                estimated_fee = estimated_notional * Decimal("0.001")
                available_quote = Decimal(str(paper_balances.get(quote_asset, Decimal("0"))))
                available_base = Decimal(str(paper_balances.get(base_asset, Decimal("0"))))
                blocking_reason = None
                can_execute = True
                if side == "buy" and available_quote < estimated_notional + estimated_fee:
                    can_execute = False
                    blocking_reason = (
                        f"Solde {quote_asset} insuffisant en mode paper: {available_quote} disponible, "
                        f"~{estimated_notional + estimated_fee:.2f} requis."
                    )
                if side == "sell" and available_base < quantity:
                    can_execute = False
                    blocking_reason = (
                        f"Quantite {base_asset} insuffisante en mode paper: {available_base} disponible, "
                        f"{quantity} requis."
                    )
                return OrderPreflightResponse(
                    requested_symbol=normalized_symbol,
                    resolved_symbol=normalized_symbol,
                    side=side,
                    base_asset=base_asset,
                    quote_asset=quote_asset,
                    input_quantity=str(quantity),
                    adjusted_quantity=str(quantity),
                    reference_price=str(reference_price) if reference_price is not None else str(current_price),
                    estimated_price=str(current_price),
                    estimated_notional=str(estimated_notional),
                    estimated_fee=str(estimated_fee),
                    fee_rate="0.001",
                    min_notional="5",
                    available_quote=str(available_quote),
                    available_base=str(available_base),
                    conversion_symbol=None,
                    conversion_side=None,
                    conversion_from_asset=None,
                    conversion_required_quantity=None,
                    conversion_estimated_spend=None,
                    can_execute=can_execute,
                    blocking_reason=blocking_reason,
                    notes=["Mode paper: execution simulee sur la paire par defaut."],
                )
            return OrderPreflightResponse(
                requested_symbol=normalized_symbol,
                resolved_symbol=normalized_symbol,
                side=side,
                base_asset=base_asset,
                quote_asset=quote_asset,
                input_quantity=str(quantity),
                adjusted_quantity=str(quantity),
                reference_price=str(reference_price) if reference_price is not None else None,
                conversion_symbol=None,
                conversion_side=None,
                conversion_from_asset=None,
                conversion_required_quantity=None,
                conversion_estimated_spend=None,
                can_execute=False,
                blocking_reason="Connectez Binance dans Settings puis activez le trading pour obtenir un ticket d'ordre executable.",
                notes=["Aucune connexion exchange exploitable n'est disponible pour cet ordre."],
            )

        try:
            preview = await client.preview_market_order(
                normalized_symbol,
                side=side,
                quantity=float(quantity),
                reference_price=float(reference_price) if reference_price is not None else 0.0,
            )
        finally:
            if should_close and client is not None:
                await client.close()

        return OrderPreflightResponse(
            requested_symbol=str(preview["requested_symbol"]),
            resolved_symbol=str(preview["resolved_symbol"]),
            side=side,
            base_asset=str(preview["base_asset"]),
            quote_asset=str(preview["quote_asset"]),
            input_quantity=str(preview["input_quantity"]),
            adjusted_quantity=str(preview["adjusted_quantity"]),
            reference_price=str(preview["reference_price"]) if preview["reference_price"] is not None else None,
            estimated_price=str(preview["estimated_price"]) if preview["estimated_price"] is not None else None,
            estimated_notional=str(preview["estimated_notional"]) if preview["estimated_notional"] is not None else None,
            estimated_fee=str(preview["estimated_fee"]) if preview["estimated_fee"] is not None else None,
            fee_rate=str(preview["fee_rate"]),
            min_notional=str(preview["min_notional"]) if preview["min_notional"] is not None else None,
            available_quote=str(preview["available_quote"]) if preview["available_quote"] is not None else None,
            available_base=str(preview["available_base"]) if preview["available_base"] is not None else None,
            conversion_symbol=str(preview["conversion_symbol"]) if preview.get("conversion_symbol") is not None else None,
            conversion_side=str(preview["conversion_side"]) if preview.get("conversion_side") is not None else None,
            conversion_from_asset=str(preview["conversion_from_asset"]) if preview.get("conversion_from_asset") is not None else None,
            conversion_required_quantity=str(preview["conversion_required_quantity"]) if preview.get("conversion_required_quantity") is not None else None,
            conversion_estimated_spend=str(preview["conversion_estimated_spend"]) if preview.get("conversion_estimated_spend") is not None else None,
            can_execute=bool(preview["can_execute"]),
            blocking_reason=str(preview["blocking_reason"]) if preview["blocking_reason"] is not None else None,
            notes=[str(item) for item in preview.get("notes", [])],
        )

    async def cancel_order(self, order_id: str, user_id: str = "default") -> Order:
        """Cancel an order by ID."""
        if settings.TRADING_MODE == "paper":
            order = await self._paper_trader.cancel_order(user_id, order_id)
            if order is None:
                raise ValueError(f"Order {order_id} not found")
            await self._publish_event("ORDER_CANCELLED", order, user_id=user_id)
            return order

        # Live mode -- we need the exchange_order_id
        raise NotImplementedError("Live order cancellation not yet supported")

    async def get_order(
        self,
        order_id: str,
        user_id: str = "default",
    ) -> Optional[Order]:
        """Retrieve a single order."""
        if settings.TRADING_MODE == "paper":
            return await self._paper_trader.get_order(user_id, order_id)
        raise NotImplementedError("Live order lookup not yet supported")

    async def list_orders(
        self,
        user_id: str = "default",
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Order]:
        """Return orders matching filters."""
        if settings.TRADING_MODE == "paper":
            return await self._paper_trader.get_all_orders(
                user_id=user_id,
                status=status,
                symbol=symbol,
                limit=limit,
                offset=offset,
            )
        raise NotImplementedError("Live order listing not yet supported")

    async def count_orders(
        self,
        user_id: str = "default",
        status: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> int:
        """Count orders matching filters."""
        if settings.TRADING_MODE == "paper":
            return await self._paper_trader.count_orders(
                user_id=user_id,
                status=status,
                symbol=symbol,
            )
        return 0

    async def get_balance(
        self,
        user_id: str = "default",
        auth_header: Optional[str] = None,
    ) -> Dict[str, Decimal]:
        """Return current trading balances.

        When *auth_header* is provided the method tries to fetch the user's
        exchange credentials from the auth-service and query Binance directly.
        Falls back to paper balances when no live credentials are available.
        """
        # Try per-user live credentials first
        if auth_header:
            client = await self._get_user_exchange_client(auth_header)
            if client is not None:
                try:
                    raw = await client.get_balance()
                    total = raw.get("total", {})
                    return {k: Decimal(str(v)) for k, v in total.items() if v and float(v) > 0}
                except Exception as exc:
                    logger.error("Live balance fetch failed for user %s: %s", user_id, exc)
                finally:
                    await client.close()

        # Fallback: global exchange client (env vars) in live mode
        if settings.TRADING_MODE == "live" and self._exchange_client:
            raw = await self._exchange_client.get_balance()
            total = raw.get("total", {})
            return {k: Decimal(str(v)) for k, v in total.items() if v and float(v) > 0}

        # Last resort: paper balances
        return await self._paper_trader.get_balance(user_id)

    # ------------------------------------------------------------------
    # Execute chain (multi-step orders for conversion flows)
    # ------------------------------------------------------------------

    async def execute_chain(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        user_id: str,
        auth_header: Optional[str] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Execute an order with automatic conversion chain if needed.

        Flow:
          1. Preflight the order
          2. If can_execute → place order directly
          3. If conversion needed → execute conversion step first, then retry
          4. Exponential backoff on rate limit / timeout

        Returns:
          {
            "status": "filled" | "failed",
            "steps": [{symbol, side, qty, result}, ...],
            "error": ErrorDetail | None,
          }
        """
        import asyncio

        steps: List[Dict[str, Any]] = []
        current_symbol = symbol
        current_qty = quantity

        for step_num in range(3):  # max 3 conversion steps
            # Preflight
            try:
                preview = await self.preview_order(
                    symbol=current_symbol,
                    side=side,
                    quantity=current_qty,
                    user_id=user_id,
                    auth_header=auth_header,
                )
            except Exception as exc:
                from app.services.error_catalog import classify_error
                detail = classify_error(exc)
                return {
                    "status": "failed",
                    "steps": steps,
                    "error": detail.to_dict(),
                }

            # If preflight says we can execute, try to place
            if preview.can_execute:
                for attempt in range(max_retries):
                    try:
                        order_create = OrderCreate(
                            symbol=current_symbol,
                            side=OrderSide(side),
                            order_type=OrderType.MARKET,
                            quantity=current_qty,
                        )
                        order = await self.create_order(
                            order_create,
                            user_id=user_id,
                            auth_header=auth_header,
                        )
                        steps.append({
                            "symbol": current_symbol,
                            "side": side,
                            "quantity": str(current_qty),
                            "status": order.status.value if hasattr(order.status, "value") else str(order.status),
                            "order_id": str(order.id) if order.id else None,
                        })
                        return {"status": "filled", "steps": steps, "error": None}
                    except (RuntimeError, ValueError) as exc:
                        from app.services.error_catalog import classify_error
                        detail = classify_error(exc)
                        # Retry only on exponential_backoff strategy
                        if detail.retry_strategy == "exponential_backoff" and attempt < max_retries - 1:
                            await asyncio.sleep(0.5 * (2 ** attempt))
                            continue
                        # Final failure
                        steps.append({
                            "symbol": current_symbol,
                            "side": side,
                            "quantity": str(current_qty),
                            "status": "failed",
                            "error": detail.to_dict(),
                        })
                        return {"status": "failed", "steps": steps, "error": detail.to_dict()}

            # Preflight blocked but suggests a conversion → execute it first
            if preview.conversion_symbol and preview.conversion_side and preview.conversion_required_quantity:
                conv_symbol = preview.conversion_symbol
                conv_side = preview.conversion_side
                conv_qty = Decimal(str(preview.conversion_required_quantity))

                try:
                    conv_order_create = OrderCreate(
                        symbol=conv_symbol,
                        side=OrderSide(conv_side if isinstance(conv_side, str) else conv_side.value),
                        order_type=OrderType.MARKET,
                        quantity=conv_qty,
                    )
                    conv_order = await self.create_order(
                        conv_order_create,
                        user_id=user_id,
                        auth_header=auth_header,
                    )
                    steps.append({
                        "symbol": conv_symbol,
                        "side": conv_side if isinstance(conv_side, str) else conv_side.value,
                        "quantity": str(conv_qty),
                        "status": conv_order.status.value if hasattr(conv_order.status, "value") else str(conv_order.status),
                        "order_id": str(conv_order.id) if conv_order.id else None,
                        "note": "conversion step",
                    })
                    # Wait a bit for balance to update
                    await asyncio.sleep(0.5)
                    # Loop back and retry the original order
                    continue
                except Exception as exc:
                    from app.services.error_catalog import classify_error
                    detail = classify_error(exc)
                    steps.append({
                        "symbol": conv_symbol,
                        "side": conv_side if isinstance(conv_side, str) else str(conv_side),
                        "status": "failed",
                        "error": detail.to_dict(),
                        "note": "conversion step failed",
                    })
                    return {"status": "failed", "steps": steps, "error": detail.to_dict()}

            # Blocked with no conversion possible
            from app.services.error_catalog import ErrorDetail
            blocking_reason = preview.blocking_reason or "Ordre non executable"
            error = ErrorDetail(
                code="APP_PREFLIGHT_BLOCKED",
                category="validation",
                severity="error",
                user_message=blocking_reason,
                retry_strategy="none",
                technical_message=blocking_reason,
            ).to_dict()
            return {"status": "failed", "steps": steps, "error": error}

        # Max conversion steps exceeded
        from app.services.error_catalog import ErrorDetail
        return {
            "status": "failed",
            "steps": steps,
            "error": ErrorDetail(
                "APP_CHAIN_TOO_LONG", "validation", "error",
                "Chaine de conversion trop longue. Ordre annule.",
            ).to_dict(),
        }

    async def check_pending_orders(self, user_id: Optional[str] = None) -> List[Order]:
        """Fetch current prices and check all pending paper orders."""
        if settings.TRADING_MODE != "paper":
            return []

        open_orders = await self._paper_trader.get_open_orders(user_id=user_id)
        if not open_orders:
            return []

        # Collect unique symbols
        symbols = list({o.symbol for o in open_orders})
        prices: Dict[str, Decimal] = {}
        for sym in symbols:
            try:
                price = await self._fetch_current_price(sym)
                prices[sym] = price
            except Exception as exc:
                logger.warning("Could not fetch price for %s: %s", sym, exc)

        changed = await self._paper_trader.check_pending_orders(prices, user_id=user_id)

        for order in changed:
            await self._publish_event(
                "ORDER_FILLED",
                order,
                user_id=self._paper_trader.get_order_owner(order.id),
            )

        return changed

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Release resources."""
        await self._http.aclose()
        if self._exchange_client:
            await self._exchange_client.close()
        if self._redis:
            await self._redis.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_current_price(self, symbol: str) -> Decimal:
        """Get the latest price for *symbol* from the market-data service.

        Falls back to the exchange client ticker if the service is
        unreachable.
        """
        # Try market-data service first
        base = symbol.split("/")[0] if "/" in symbol else symbol
        url = f"{settings.MARKET_DATA_SERVICE_URL}/api/v1/prices/{base.upper()}"
        try:
            resp = await self._http.get(url)
            if resp.status_code == 200:
                data = resp.json()
                # Market-data service returns {"success": true, "data": {"price": ...}}
                inner = data.get("data", data)
                price = inner.get("price") or inner.get("current_price") or inner.get("last")
                if price is not None:
                    return Decimal(str(price))
        except Exception as exc:
            logger.warning("Market-data service unreachable: %s", exc)

        # Fallback: use exchange client ticker
        if self._exchange_client:
            try:
                ticker = await self._exchange_client.get_ticker(symbol)
                last = ticker.get("last")
                if last is not None:
                    return Decimal(str(last))
            except Exception as exc:
                logger.warning("Exchange ticker fallback failed: %s", exc)

        raise RuntimeError(f"Unable to fetch current price for {symbol}")

    async def _evaluate_risk(
        self,
        order: OrderCreate,
        current_price: Decimal,
        user_id: str,
        auth_header: Optional[str] = None,
    ) -> bool:
        """Call the risk service to evaluate the order.

        Returns ``True`` if approved, ``False`` if rejected.  If the risk
        service is unavailable the order is approved by default in paper
        mode but rejected in live mode.
        """
        url = f"{settings.RISK_SERVICE_URL}/api/v1/risk/evaluate"
        portfolio_value, current_positions = await self._build_risk_snapshot(user_id)
        payload = {
            "user_id": user_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "quantity": str(order.quantity),
            "price": str(current_price),
            "portfolio_value": str(portfolio_value),
            "current_positions": current_positions,
            "portfolio_id": order.portfolio_id,
        }
        try:
            headers = {"Authorization": auth_header} if auth_header else None
            resp = await self._http.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                approved = data.get("approved", False)
                if not approved:
                    reason = data.get("reason", "unknown")
                    logger.warning("Risk service rejected order: %s", reason)
                return approved
            logger.warning("Risk service returned status %s", resp.status_code)
        except Exception as exc:
            logger.warning("Risk service unreachable: %s", exc)

        # Fallback policy
        if settings.TRADING_MODE == "paper":
            logger.info("Risk service unavailable; auto-approving for paper mode")
            return True
        logger.error("Risk service unavailable; rejecting live order")
        return False

    async def _build_risk_snapshot(
        self,
        user_id: str,
    ) -> tuple[Decimal, List[Dict[str, str]]]:
        """Build current portfolio value and position snapshot for the risk service."""
        balances = await self.get_balance(user_id)
        portfolio_value = Decimal("0")
        current_positions: List[Dict[str, str]] = []

        for asset, amount in balances.items():
            quantity = Decimal(str(amount))
            if quantity <= 0:
                continue

            symbol = asset.upper()
            if symbol in _STABLES:
                portfolio_value += quantity
                continue

            try:
                current_price = await self._fetch_current_price(symbol)
            except Exception as exc:
                logger.warning("Risk snapshot price lookup failed for %s: %s", symbol, exc)
                continue

            portfolio_value += quantity * current_price
            current_positions.append(
                {
                    "symbol": symbol,
                    "quantity": str(quantity),
                    "current_price": str(current_price),
                }
            )

        return portfolio_value, current_positions

    async def _execute_paper(
        self,
        order_create: OrderCreate,
        current_price: Decimal,
        user_id: str,
    ) -> Order:
        """Execute an order via the paper trader."""
        try:
            return await self._paper_trader.place_order(user_id, order_create, current_price)
        except ValueError as exc:
            logger.error("Paper trade execution failed: %s", exc)
            order = Order(
                symbol=order_create.symbol,
                side=order_create.side,
                order_type=order_create.order_type,
                status=OrderStatus.FAILED,
                quantity=order_create.quantity,
                price=order_create.price,
                stop_price=order_create.stop_price,
                exchange="paper",
                portfolio_id=order_create.portfolio_id,
                strategy=order_create.strategy,
                error_message=str(exc),
            )
            return order

    async def _execute_live(
        self,
        order_create: OrderCreate,
        exchange_client: Optional[ExchangeClient] = None,
    ) -> Order:
        """Execute an order on the live exchange via CCXT."""
        client = exchange_client or self._exchange_client
        if client is None:
            raise RuntimeError("Exchange client not initialised for live trading")

        symbol = order_create.symbol
        side = order_create.side.value
        quantity = float(order_create.quantity)

        try:
            if order_create.order_type == OrderType.MARKET:
                result = await client.place_market_order(
                    symbol, side, quantity
                )
            elif order_create.order_type == OrderType.LIMIT:
                if order_create.price is None:
                    raise ValueError("Limit orders require a price")
                result = await client.place_limit_order(
                    symbol, side, quantity, float(order_create.price)
                )
            else:
                raise ValueError(
                    f"Live execution of {order_create.order_type.value} not yet supported"
                )

            # Map CCXT response to Order model
            filled_qty = Decimal(str(result.get("filled", 0)))
            avg_price = result.get("average") or result.get("price")
            status = self._map_ccxt_status(result.get("status", "open"))

            order = Order(
                symbol=symbol,
                side=order_create.side,
                order_type=order_create.order_type,
                status=status,
                quantity=order_create.quantity,
                filled_quantity=filled_qty,
                price=order_create.price,
                filled_price=Decimal(str(avg_price)) if avg_price else None,
                fee=Decimal(str(result.get("fee", {}).get("cost", 0) or 0)),
                exchange=settings.DEFAULT_EXCHANGE,
                exchange_order_id=str(result.get("id", "")),
                portfolio_id=order_create.portfolio_id,
                strategy=order_create.strategy,
            )
            return order
        except Exception as exc:
            logger.error("Live order execution failed: %s", exc)
            order = Order(
                symbol=symbol,
                side=order_create.side,
                order_type=order_create.order_type,
                status=OrderStatus.FAILED,
                quantity=order_create.quantity,
                price=order_create.price,
                exchange=settings.DEFAULT_EXCHANGE,
                portfolio_id=order_create.portfolio_id,
                strategy=order_create.strategy,
                error_message=str(exc),
            )
            return order

    @staticmethod
    def _map_ccxt_status(ccxt_status: str) -> OrderStatus:
        """Map a CCXT order status string to our OrderStatus enum."""
        mapping = {
            "open": OrderStatus.OPEN,
            "closed": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "expired": OrderStatus.EXPIRED,
            "rejected": OrderStatus.FAILED,
        }
        return mapping.get(ccxt_status, OrderStatus.PENDING)

    async def _publish_event(
        self,
        event_type: str,
        order: Order,
        user_id: Optional[str] = None,
    ) -> None:
        """Publish an order event to Redis pub/sub."""
        if self._redis is None:
            return
        try:
            payload = {
                "event": event_type,
                "order_id": order.id,
                "symbol": order.symbol,
                "side": order.side.value,
                "status": order.status.value,
                "quantity": str(order.quantity),
                "filled_quantity": str(order.filled_quantity),
                "filled_price": str(order.filled_price) if order.filled_price else None,
                "fee": str(order.fee),
                "exchange": order.exchange,
                "user_id": user_id,
            }
            await self._redis.publish("trading:orders", json.dumps(payload))
            logger.debug("Published event %s for order %s", event_type, order.id[:8])
        except Exception as exc:
            logger.warning("Failed to publish event to Redis: %s", exc)
