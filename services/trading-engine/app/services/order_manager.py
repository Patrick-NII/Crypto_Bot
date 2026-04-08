"""Order manager -- orchestrates the full order lifecycle.

Flow:
  1. Fetch current price from the market-data service.
  2. Validate the order via the risk service.
  3. Execute via the paper trader or the live exchange client.
  4. Publish an event to Redis.
  5. Return the resulting order.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
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
from app.repositories.order_repository import order_repository
from app.services.exchange_client import ExchangeClient
from app.services.paper_trader import PaperTrader

logger = logging.getLogger(__name__)
_STABLES = {"USDT", "USDC", "BUSD", "FDUSD", "USD", "DAI", "TUSD"}

# TTL for the live-mode in-memory stores.
# V2 should replace these with a persistent database.
_LIVE_ORDER_TTL_SECONDS = 86400  # 24h
_CLIENT_ORDER_ID_TTL_SECONDS = 86400  # 24h


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

        # Live-mode in-memory stores (volatile — replaced by DB in V2).
        # Key: f"{user_id}:{internal_order_id}"
        # Value: {"order": Order, "exchange_order_id": str, "symbol": str, "expires_at": float}
        self._live_order_store: Dict[str, Dict[str, Any]] = {}
        # Idempotency cache. Key: f"{user_id}:{client_order_id}" -> (internal_order_id, expires_at)
        self._client_order_id_store: Dict[str, tuple[str, float]] = {}

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

    # ------------------------------------------------------------------
    # Live-mode store helpers (volatile in-memory, TTL 24h)
    # ------------------------------------------------------------------

    def _live_key(self, user_id: str, order_id: str) -> str:
        return f"{user_id}:{order_id}"

    def _remember_live_order(
        self,
        user_id: str,
        order: Order,
        exchange_order_id: Optional[str],
        *,
        client_order_id: Optional[str] = None,
        quote_quantity: Optional[Decimal] = None,
    ) -> None:
        """Remember a live order for later lookup / cancel.

        Writes through to the persistent ``orders`` table so that the mapping
        survives restarts. The in-memory store remains as a fast cache.
        """
        if not exchange_order_id or not order.id:
            return
        self._live_order_store[self._live_key(user_id, order.id)] = {
            "order": order,
            "exchange_order_id": exchange_order_id,
            "symbol": order.symbol,
            "expires_at": time.time() + _LIVE_ORDER_TTL_SECONDS,
        }
        # Opportunistic expiry sweep (cheap, bounded)
        self._sweep_live_stores()
        # Persist to DB (best-effort, fire-and-forget so trade latency stays low)
        try:
            asyncio.create_task(
                order_repository.save_order(
                    user_id,
                    order,
                    client_order_id=client_order_id,
                    quote_quantity=quote_quantity,
                )
            )
        except Exception as exc:
            logger.debug("Order persistence skipped: %s", exc)

    def _lookup_live_order(self, user_id: str, order_id: str) -> Optional[Dict[str, Any]]:
        entry = self._live_order_store.get(self._live_key(user_id, order_id))
        if entry is None:
            return None
        if entry["expires_at"] < time.time():
            self._live_order_store.pop(self._live_key(user_id, order_id), None)
            return None
        return entry

    def _forget_live_order(self, user_id: str, order_id: str) -> None:
        self._live_order_store.pop(self._live_key(user_id, order_id), None)

    def _remember_client_order_id(
        self,
        user_id: str,
        client_order_id: str,
        internal_order_id: str,
    ) -> None:
        """Cache the (user, client_order_id) → internal_id mapping in RAM and DB."""
        self._client_order_id_store[f"{user_id}:{client_order_id}"] = (
            internal_order_id,
            time.time() + _CLIENT_ORDER_ID_TTL_SECONDS,
        )
        try:
            asyncio.create_task(
                order_repository.remember_client_order_id(
                    user_id, client_order_id, internal_order_id
                )
            )
        except Exception as exc:
            logger.debug("Idempotency persistence skipped: %s", exc)

    async def _lookup_client_order_id_async(
        self,
        user_id: str,
        client_order_id: str,
    ) -> Optional[str]:
        """Async lookup that consults RAM first, then the durable DB."""
        entry = self._client_order_id_store.get(f"{user_id}:{client_order_id}")
        if entry is not None:
            internal_id, expires_at = entry
            if expires_at >= time.time():
                return internal_id
            self._client_order_id_store.pop(f"{user_id}:{client_order_id}", None)
        # Fall back to the persistent table
        db_id = await order_repository.lookup_client_order_id(user_id, client_order_id)
        if db_id:
            self._client_order_id_store[f"{user_id}:{client_order_id}"] = (
                db_id,
                time.time() + _CLIENT_ORDER_ID_TTL_SECONDS,
            )
        return db_id

    def _lookup_client_order_id(
        self,
        user_id: str,
        client_order_id: str,
    ) -> Optional[str]:
        """Synchronous RAM-only lookup. Use the async variant for full lookup."""
        entry = self._client_order_id_store.get(f"{user_id}:{client_order_id}")
        if entry is None:
            return None
        internal_id, expires_at = entry
        if expires_at < time.time():
            self._client_order_id_store.pop(f"{user_id}:{client_order_id}", None)
            return None
        return internal_id

    def _sweep_live_stores(self) -> None:
        """Drop expired entries. O(n) but n is bounded by active users."""
        now = time.time()
        expired_orders = [k for k, v in self._live_order_store.items() if v["expires_at"] < now]
        for k in expired_orders:
            self._live_order_store.pop(k, None)
        expired_keys = [k for k, (_, exp) in self._client_order_id_store.items() if exp < now]
        for k in expired_keys:
            self._client_order_id_store.pop(k, None)

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
        # 0. Idempotency — if this client_order_id has already produced an
        # order, return the existing one without re-executing. The lookup
        # consults RAM first, then the durable idempotency_keys table.
        if order_create.client_order_id:
            existing_id = await self._lookup_client_order_id_async(
                user_id, order_create.client_order_id
            )
            if existing_id is not None:
                live_entry = self._lookup_live_order(user_id, existing_id)
                if live_entry is not None:
                    logger.info(
                        "Idempotent replay for client_order_id=%s -> %s",
                        order_create.client_order_id,
                        existing_id,
                    )
                    return live_entry["order"]
                paper_order = await self._paper_trader.get_order(user_id, existing_id)
                if paper_order is not None:
                    return paper_order
                # Fallback: rehydrate from DB
                db_order = await order_repository.get_order(existing_id)
                if db_order is not None:
                    return db_order

        # 1. Normalise symbol
        symbol = ExchangeClient.normalize_symbol(order_create.symbol)
        order_create.symbol = symbol

        # 2. Fetch current price
        current_price = await self._fetch_current_price(symbol)

        # 3. Resolve quote_quantity → base quantity when needed.
        # - Paper mode always uses base quantity (converted here).
        # - Live MARKET BUY can ride native quoteOrderQty in _execute_live.
        # - Live MARKET SELL must be converted (Binance does not accept quote for sells).
        base_quantity_for_risk = order_create.quantity
        if order_create.quote_quantity is not None:
            if current_price <= 0:
                raise ValueError("Cannot resolve quote_quantity without a price reference.")
            base_quantity_for_risk = Decimal(str(order_create.quote_quantity)) / Decimal(str(current_price))
            # For non-native flows (paper + live sell), overwrite the order payload
            is_native_quote_buy = (
                order_create.order_type == OrderType.MARKET
                and order_create.side == OrderSide.BUY
                and auth_header is not None
                and settings.TRADING_MODE != "paper_only"  # always try live path first
            )
            if not is_native_quote_buy:
                order_create.quantity = base_quantity_for_risk
                order_create.quote_quantity = None

        # Ensure risk evaluation always has a base quantity value
        if order_create.quantity is None:
            order_create.quantity = base_quantity_for_risk

        # 4. Risk evaluation (best-effort -- if risk service is down we still allow paper)
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
                quantity=order_create.quantity or Decimal("0"),
                price=order_create.price,
                stop_price=order_create.stop_price,
                take_profit_price=order_create.take_profit_price,
                trailing_pct=order_create.trailing_pct,
                exchange="paper" if settings.TRADING_MODE == "paper" else settings.DEFAULT_EXCHANGE,
                portfolio_id=order_create.portfolio_id,
                strategy=order_create.strategy,
                error_message="Order rejected by risk service",
            )
            await self._publish_event(
                "ORDER_FAILED", order, user_id=user_id, auth_header=auth_header
            )
            return order

        # 5. Execute — try live with per-user credentials, fallback to paper
        if auth_header:
            user_client = await self._get_user_exchange_client(auth_header)
            if user_client is not None:
                try:
                    order = await self._execute_live(
                        order_create,
                        exchange_client=user_client,
                        user_id=user_id,
                    )
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
                order = await self._execute_live(order_create, user_id=user_id)
            else:
                order = await self._execute_paper(order_create, current_price, user_id)
        elif settings.TRADING_MODE == "paper":
            order = await self._execute_paper(order_create, current_price, user_id)
        else:
            order = await self._execute_live(order_create, user_id=user_id)

        # 6. Idempotency bookkeeping
        if order_create.client_order_id and order.status != OrderStatus.FAILED:
            self._remember_client_order_id(user_id, order_create.client_order_id, order.id)

        # 7. Publish event
        event_type = (
            "ORDER_FILLED" if order.status == OrderStatus.FILLED else "ORDER_CREATED"
        )
        await self._publish_event(
            event_type, order, user_id=user_id, auth_header=auth_header
        )

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

    async def cancel_order(
        self,
        order_id: str,
        user_id: str = "default",
        auth_header: Optional[str] = None,
    ) -> Order:
        """Cancel an order by ID.

        Paper mode delegates to ``PaperTrader``. Live mode looks up the
        internal ID in ``_live_order_store`` to retrieve the exchange's own
        order id, then calls the CCXT cancel endpoint.
        """
        # Paper first
        paper_order = await self._paper_trader.get_order(user_id, order_id)
        if paper_order is not None:
            cancelled = await self._paper_trader.cancel_order(user_id, order_id)
            if cancelled is None:
                raise ValueError(f"Order {order_id} not found")
            await self._publish_event("ORDER_CANCELLED", cancelled, user_id=user_id)
            return cancelled

        # Live mode lookup
        entry = self._lookup_live_order(user_id, order_id)
        if entry is None:
            raise ValueError(f"Order {order_id} not found")

        client = await self._get_user_exchange_client(auth_header) if auth_header else None
        close_client = client is not None
        if client is None:
            client = self._exchange_client
        if client is None:
            raise RuntimeError("No exchange client available to cancel live order")

        try:
            await client.cancel_order(entry["exchange_order_id"], entry["symbol"])
        except Exception as exc:
            logger.error("Live cancel failed for %s: %s", order_id, exc)
            if close_client:
                await client.close()
            raise ValueError(f"Impossible d'annuler l'ordre: {exc}") from exc
        finally:
            if close_client and client is not None:
                await client.close()

        # Update in-memory copy
        cached_order: Order = entry["order"]
        cached_order.status = OrderStatus.CANCELLED
        self._remember_live_order(user_id, cached_order, entry["exchange_order_id"])
        await self._publish_event(
            "ORDER_CANCELLED", cached_order, user_id=user_id, auth_header=auth_header
        )
        return cached_order

    async def get_order(
        self,
        order_id: str,
        user_id: str = "default",
        auth_header: Optional[str] = None,
    ) -> Optional[Order]:
        """Retrieve a single order.

        Looks first in the paper trader, then in the live store, then falls
        back to calling ``exchange.fetch_order`` for the latest state.
        """
        paper_order = await self._paper_trader.get_order(user_id, order_id)
        if paper_order is not None:
            return paper_order

        entry = self._lookup_live_order(user_id, order_id)
        if entry is None:
            return None

        cached_order: Order = entry["order"]
        # If the order is already final, return the cached copy
        if cached_order.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.FAILED,
            OrderStatus.EXPIRED,
        ):
            return cached_order

        # Refresh from exchange
        client = await self._get_user_exchange_client(auth_header) if auth_header else None
        close_client = client is not None
        if client is None:
            client = self._exchange_client
        if client is None:
            return cached_order

        try:
            raw = await client.get_order(entry["exchange_order_id"], entry["symbol"])
            cached_order.status = self._map_ccxt_status(raw.get("status", "open"))
            cached_order.filled_quantity = Decimal(str(raw.get("filled", cached_order.filled_quantity) or 0))
            avg = raw.get("average") or raw.get("price")
            if avg:
                cached_order.filled_price = Decimal(str(avg))
            self._remember_live_order(user_id, cached_order, entry["exchange_order_id"])
        except Exception as exc:
            logger.debug("Live get_order refresh failed for %s: %s", order_id, exc)
        finally:
            if close_client and client is not None:
                await client.close()

        return cached_order

    async def list_orders(
        self,
        user_id: str = "default",
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        auth_header: Optional[str] = None,
    ) -> List[Order]:
        """Return orders matching filters.

        The result merges three sources:
        1. Paper trader (always included for users in paper mode).
        2. Locally remembered live orders (the ones we placed this session).
        3. Fresh CCXT lookup of open + recent closed orders (best-effort).
        """
        # Paper trader first (non-empty in paper mode)
        paper_orders = await self._paper_trader.get_all_orders(
            user_id=user_id,
            status=status,
            symbol=symbol,
            limit=limit,
            offset=offset,
        )

        # If the user has no live client, return paper-only
        client: Optional[ExchangeClient] = None
        close_client = False
        if auth_header:
            client = await self._get_user_exchange_client(auth_header)
            close_client = client is not None
        if client is None and settings.TRADING_MODE == "live" and self._exchange_client:
            client = self._exchange_client

        if client is None:
            return paper_orders

        try:
            # 1. Cached live orders (already adapted to Order model)
            cached_orders = [
                entry["order"]
                for entry in self._live_order_store.values()
                if entry["order"] and entry["expires_at"] > time.time()
            ]
            # Filter by user via the key prefix
            prefix = f"{user_id}:"
            cached_orders = [
                entry["order"]
                for k, entry in self._live_order_store.items()
                if k.startswith(prefix) and entry["expires_at"] > time.time()
            ]

            # 2. Open orders from exchange (most authoritative)
            try:
                raw_open = await client.get_open_orders(symbol)
            except Exception as exc:
                logger.debug("fetch_open_orders failed: %s", exc)
                raw_open = []

            # 3. Recent closed (last N)
            try:
                raw_closed = await client.fetch_closed_orders(symbol, limit=limit)
            except Exception as exc:
                logger.debug("fetch_closed_orders failed: %s", exc)
                raw_closed = []

            live_orders: List[Order] = list(cached_orders)
            seen_exchange_ids = {
                o.exchange_order_id for o in live_orders if o.exchange_order_id
            }
            for raw in list(raw_open) + list(raw_closed):
                ex_id = str(raw.get("id") or "")
                if not ex_id or ex_id in seen_exchange_ids:
                    continue
                seen_exchange_ids.add(ex_id)
                try:
                    order = Order(
                        symbol=str(raw.get("symbol") or symbol or ""),
                        side=OrderSide(raw.get("side", "buy")),
                        order_type=OrderType(raw.get("type", "market")),
                        status=self._map_ccxt_status(str(raw.get("status", "open"))),
                        quantity=Decimal(str(raw.get("amount", 0) or 0)),
                        filled_quantity=Decimal(str(raw.get("filled", 0) or 0)),
                        price=Decimal(str(raw.get("price"))) if raw.get("price") else None,
                        filled_price=Decimal(str(raw.get("average"))) if raw.get("average") else None,
                        fee=Decimal(str((raw.get("fee") or {}).get("cost", 0) or 0)),
                        exchange=settings.DEFAULT_EXCHANGE,
                        exchange_order_id=ex_id,
                    )
                    live_orders.append(order)
                except Exception as exc:
                    logger.debug("Could not parse exchange order %s: %s", ex_id, exc)

            # Apply status/symbol filters client-side
            filtered: List[Order] = list(paper_orders) + live_orders
            if status:
                filtered = [o for o in filtered if o.status.value == status]
            if symbol:
                normalized = ExchangeClient.normalize_symbol(symbol)
                filtered = [o for o in filtered if o.symbol == normalized]

            # Sort newest first + paginate
            filtered.sort(key=lambda o: o.created_at or 0, reverse=True)
            return filtered[offset : offset + limit]
        finally:
            if close_client and client is not None:
                await client.close()

    async def list_open_orders(
        self,
        user_id: str = "default",
        symbol: Optional[str] = None,
        auth_header: Optional[str] = None,
    ) -> List[Order]:
        """Shortcut: return only OPEN / PENDING orders for the given user.

        Used by the WS relay (minimise payload) and by the frontend polling
        fallback.
        """
        orders = await self.list_orders(
            user_id=user_id,
            status=None,
            symbol=symbol,
            limit=200,
            offset=0,
            auth_header=auth_header,
        )
        return [
            o for o in orders
            if o.status in (OrderStatus.OPEN, OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED)
        ]

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
        # Live: rough count from the local store
        prefix = f"{user_id}:"
        entries = [
            entry["order"]
            for k, entry in self._live_order_store.items()
            if k.startswith(prefix) and entry["expires_at"] > time.time()
        ]
        if status:
            entries = [o for o in entries if o.status.value == status]
        if symbol:
            normalized = ExchangeClient.normalize_symbol(symbol)
            entries = [o for o in entries if o.symbol == normalized]
        return len(entries)

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
    # Boot reconciliation
    # ------------------------------------------------------------------

    async def reconcile_at_boot(self) -> None:
        """Rehydrate ``_live_order_store`` from the persistent orders table.

        On a fresh restart the in-memory cache is empty. We re-read every
        order whose status is open / pending / partially_filled, and
        repopulate the cache so that subsequent ``cancel_order`` /
        ``get_order`` calls work without forcing the user to provide the
        Binance exchange_order_id explicitly.

        We do NOT call CCXT here because the per-user credentials live in
        auth-service and are only available with a JWT. The reconciliation
        is therefore "soft": we trust the DB as a snapshot, and the next
        ``list_orders`` call from the user will refresh against Binance.
        """
        try:
            session = await order_repository._session()
        except Exception as exc:
            logger.warning("Cannot reconcile orders at boot: %s", exc)
            return
        try:
            from sqlalchemy import select as _select

            from app.models.db.order import OrderRow

            stmt = _select(OrderRow).where(
                OrderRow.status.in_(["pending", "open", "partially_filled"]),
                OrderRow.exchange_order_id.isnot(None),
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            from app.repositories.order_repository import _row_to_order

            count = 0
            for row in rows:
                order = _row_to_order(row)
                self._live_order_store[self._live_key(row.user_id, row.id)] = {
                    "order": order,
                    "exchange_order_id": row.exchange_order_id,
                    "symbol": row.symbol,
                    "expires_at": time.time() + _LIVE_ORDER_TTL_SECONDS,
                }
                count += 1
            logger.info("Reconciled %d open orders from DB at boot", count)
        finally:
            await session.close()

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
        """Execute an order via the paper trader and persist its row."""
        try:
            order = await self._paper_trader.place_order(user_id, order_create, current_price)
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

        # Persist paper orders too — the fill consumer in portfolio-service
        # listens to all orders regardless of exchange.
        try:
            asyncio.create_task(
                order_repository.save_order(
                    user_id,
                    order,
                    client_order_id=order_create.client_order_id,
                    quote_quantity=order_create.quote_quantity,
                )
            )
        except Exception:
            pass

        return order

    async def _execute_live(
        self,
        order_create: OrderCreate,
        exchange_client: Optional[ExchangeClient] = None,
        user_id: str = "default",
    ) -> Order:
        """Execute an order on the live exchange via CCXT."""
        client = exchange_client or self._exchange_client
        if client is None:
            raise RuntimeError("Exchange client not initialised for live trading")

        symbol = order_create.symbol
        side = order_create.side.value

        # Build CCXT params (idempotency key)
        ccxt_params: Dict[str, Any] = {}
        if order_create.client_order_id:
            ccxt_params["newClientOrderId"] = order_create.client_order_id

        native_quote = (
            order_create.quote_quantity is not None
            and order_create.order_type == OrderType.MARKET
            and order_create.side == OrderSide.BUY
        )

        try:
            if order_create.order_type == OrderType.MARKET:
                if native_quote:
                    result = await client.place_market_order_quote(
                        symbol,
                        side,
                        float(order_create.quote_quantity),  # type: ignore[arg-type]
                        params=ccxt_params or None,
                    )
                else:
                    quantity = float(order_create.quantity or 0)
                    result = await client.place_market_order(
                        symbol, side, quantity, params=ccxt_params or None
                    )
            elif order_create.order_type == OrderType.LIMIT:
                if order_create.price is None:
                    raise ValueError("Limit orders require a price")
                quantity = float(order_create.quantity or 0)
                result = await client.place_limit_order(
                    symbol,
                    side,
                    quantity,
                    float(order_create.price),
                    params=ccxt_params or None,
                )
            elif order_create.order_type == OrderType.STOP_LOSS:
                if order_create.stop_price is None:
                    raise ValueError("Stop-loss orders require a stop_price")
                # Use stop_price as the limit price too if no explicit limit is set
                limit_price = float(order_create.price or order_create.stop_price)
                quantity = float(order_create.quantity or 0)
                result = await client.place_stop_loss_order(
                    symbol,
                    side,
                    quantity,
                    float(order_create.stop_price),
                    limit_price,
                    params=ccxt_params or None,
                )
            elif order_create.order_type == OrderType.TAKE_PROFIT:
                if order_create.stop_price is None:
                    raise ValueError("Take-profit orders require a stop_price (trigger)")
                limit_price = float(order_create.price or order_create.stop_price)
                quantity = float(order_create.quantity or 0)
                result = await client.place_take_profit_order(
                    symbol,
                    side,
                    quantity,
                    float(order_create.stop_price),
                    limit_price,
                    params=ccxt_params or None,
                )
            elif order_create.order_type == OrderType.OCO:
                if (
                    order_create.price is None
                    or order_create.stop_price is None
                    or order_create.take_profit_price is None
                ):
                    raise ValueError(
                        "OCO orders require price (TP limit), stop_price (SL trigger), "
                        "and take_profit_price (SL limit)"
                    )
                quantity = float(order_create.quantity or 0)
                # For OCO, we use:
                #   price                = TP limit
                #   stop_price           = SL trigger
                #   take_profit_price    = SL limit (the price posted after the trigger)
                result = await client.place_oco_order(
                    symbol,
                    side,
                    quantity,
                    float(order_create.price),
                    float(order_create.stop_price),
                    float(order_create.take_profit_price),
                    params=ccxt_params or None,
                )
            else:
                raise ValueError(
                    f"Live execution of {order_create.order_type.value} not yet supported"
                )

            # Map CCXT response to Order model
            filled_qty = Decimal(str(result.get("filled", 0) or 0))
            submitted_qty = result.get("amount") or order_create.quantity or filled_qty
            avg_price = result.get("average") or result.get("price")
            status = self._map_ccxt_status(result.get("status", "open"))
            exchange_order_id = str(result.get("id", ""))

            order = Order(
                symbol=symbol,
                side=order_create.side,
                order_type=order_create.order_type,
                status=status,
                quantity=Decimal(str(submitted_qty)),
                filled_quantity=filled_qty,
                price=order_create.price,
                filled_price=Decimal(str(avg_price)) if avg_price else None,
                fee=Decimal(str((result.get("fee") or {}).get("cost", 0) or 0)),
                exchange=settings.DEFAULT_EXCHANGE,
                exchange_order_id=exchange_order_id,
                portfolio_id=order_create.portfolio_id,
                strategy=order_create.strategy,
            )

            # Remember the mapping for later cancel/lookup
            self._remember_live_order(
                user_id,
                order,
                exchange_order_id,
                client_order_id=order_create.client_order_id,
                quote_quantity=order_create.quote_quantity,
            )
            return order
        except Exception as exc:
            logger.error("Live order execution failed: %s", exc)
            order = Order(
                symbol=symbol,
                side=order_create.side,
                order_type=order_create.order_type,
                status=OrderStatus.FAILED,
                quantity=order_create.quantity or Decimal("0"),
                price=order_create.price,
                exchange=settings.DEFAULT_EXCHANGE,
                portfolio_id=order_create.portfolio_id,
                strategy=order_create.strategy,
                error_message=str(exc),
            )
            # Persist failed orders so they show up in history / debugging
            try:
                asyncio.create_task(
                    order_repository.save_order(
                        user_id,
                        order,
                        client_order_id=order_create.client_order_id,
                        quote_quantity=order_create.quote_quantity,
                    )
                )
            except Exception:
                pass
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
        auth_header: Optional[str] = None,
    ) -> None:
        """Publish an order event to Redis pub/sub.

        Publishes on two channels:
          - ``trading:orders``       : raw event used by analytics/Telegram
          - ``trading:user-orders``  : enriched event used by EmailDispatcher

        The enriched payload uses the ``event_type`` taxonomy expected by
        :mod:`notification-service.event_bridge`:
          ``order_filled_buy`` / ``order_filled_sell`` / ``order_failed``
        """
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
                "avg_price": str(order.filled_price) if order.filled_price else str(order.price or ""),
                "fee": str(order.fee),
                "exchange": order.exchange,
                "user_id": user_id,
                "portfolio_id": order.portfolio_id,
            }
            await self._redis.publish("trading:orders", json.dumps(payload))
            logger.debug("Published event %s for order %s", event_type, order.id[:8])

            # Also publish enriched event for EmailDispatcher (only for filled / failed orders)
            if event_type in ("ORDER_FILLED", "ORDER_FAILED"):
                user_info = await self._fetch_user_info(user_id, auth_header)
                if user_info and user_info.get("email"):
                    if event_type == "ORDER_FILLED":
                        sub_event = (
                            "order_filled_buy"
                            if order.side.value == "buy"
                            else "order_filled_sell"
                        )
                    else:
                        sub_event = "order_failed"
                    enriched = {
                        **payload,
                        "event_type": sub_event,
                        "user_email": user_info["email"],
                        "username": user_info.get("username", ""),
                        "user_timezone": user_info.get("timezone", "UTC"),
                        "price": str(order.filled_price) if order.filled_price else str(order.price or ""),
                    }
                    await self._redis.publish(
                        "trading:user-orders", json.dumps(enriched)
                    )
        except Exception as exc:
            logger.warning("Failed to publish event to Redis: %s", exc)

    async def _fetch_user_info(
        self,
        user_id: Optional[str],
        auth_header: Optional[str],
    ) -> dict:
        """Fetch lightweight user info from auth-service for event enrichment.

        Cached briefly to avoid hammering auth-service on bursts. Returns empty
        dict on failure (the publish path then skips the enriched event).
        """
        if not auth_header:
            return {}
        cache = getattr(self, "_user_info_cache", None)
        if cache is None:
            cache = {}
            self._user_info_cache = cache
        if user_id and user_id in cache:
            return cache[user_id]
        try:
            import httpx

            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(
                    f"{settings.AUTH_SERVICE_URL}/api/v1/auth/me",
                    headers={"Authorization": auth_header},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    info = {
                        "email": data.get("email", ""),
                        "username": data.get("username", ""),
                        "timezone": data.get("timezone", "UTC"),
                    }
                    if user_id:
                        cache[user_id] = info
                    return info
        except Exception as exc:
            logger.debug("User info fetch failed: %s", exc)
        return {}
