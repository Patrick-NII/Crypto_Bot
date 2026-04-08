"""WebSocket endpoint for streaming per-user order updates.

Clients connect to ``ws://.../api/v1/orders/ws?token=<jwt>`` and receive a
JSON message for every change to their open orders.

Message format:
    {
        "event": "order_new" | "order_update" | "order_done",
        "order": { ...OrderResponse... }
    }
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.auth import resolve_user_id_from_auth_header

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


def _get_order_stream():
    from app.services.order_stream import order_stream_manager
    return order_stream_manager


def _get_order_manager():
    from app.main import order_manager
    return order_manager


@router.websocket("/api/v1/orders/ws")
async def orders_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="Bearer JWT"),
) -> None:
    """Stream the authenticated user's order updates.

    Authentication is done via the ``token`` query parameter because the
    ``Authorization`` header is not universally available in browser
    WebSocket clients.
    """
    # Resolve the user before accepting, so we can reject with a clean close
    auth_header = f"Bearer {token}" if token else None
    try:
        user_id = resolve_user_id_from_auth_header(auth_header)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if not user_id or user_id == "default":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    stream_mgr = _get_order_stream()
    order_mgr = _get_order_manager()
    if order_mgr is None:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    # Lazy-bind to order manager (idempotent)
    stream_mgr.attach(order_mgr)
    await stream_mgr.subscribe(user_id, auth_header)

    # Subscribe to the per-user Redis channel
    redis = getattr(order_mgr, "_redis", None)
    pubsub = None
    receive_task: Optional[asyncio.Task] = None

    try:
        if redis is None:
            await websocket.send_text(json.dumps({
                "event": "warning",
                "message": "Redis unavailable, falling back to polling.",
            }))
        else:
            pubsub = redis.pubsub()
            channel = f"trading:user-orders:{user_id}"
            await pubsub.subscribe(channel)
            logger.info("WS client subscribed to %s", channel)

        # Send an initial snapshot of open orders so the UI has data immediately
        try:
            initial = await order_mgr.list_open_orders(
                user_id=user_id, auth_header=auth_header
            )
            from app.models.order import OrderResponse
            for order in initial:
                await websocket.send_text(json.dumps({
                    "event": "order_new",
                    "order": OrderResponse.from_order(order).dict(),
                }, default=str))
        except Exception as exc:
            logger.debug("WS initial snapshot failed: %s", exc)

        # Keep the websocket alive and forward Redis messages
        async def _receive_ping() -> None:
            """Consume inbound messages so the socket stays alive."""
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                return

        receive_task = asyncio.create_task(_receive_ping())

        if pubsub is not None:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                raw = message.get("data")
                if isinstance(raw, bytes):
                    raw = raw.decode()
                try:
                    await websocket.send_text(raw)
                except Exception:
                    break
        else:
            # No Redis: just hold the connection open until the client leaves.
            await receive_task
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WS error for user=%s: %s", user_id, exc)
    finally:
        if receive_task is not None and not receive_task.done():
            receive_task.cancel()
            try:
                await receive_task
            except Exception:
                pass
        if pubsub is not None:
            try:
                await pubsub.unsubscribe()
                await pubsub.close()
            except Exception:
                pass
        try:
            await stream_mgr.unsubscribe(user_id)
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass
