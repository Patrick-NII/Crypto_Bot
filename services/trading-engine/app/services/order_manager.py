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
                except Exception as exc:
                    await user_client.close()
                    raise RuntimeError(f"Live order failed: {exc}")
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
