"""WebSocket connection manager for broadcasting live price updates."""

import json
import logging
from datetime import datetime, timezone

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts messages."""

    def __init__(self) -> None:
        self._active_connections: list[WebSocket] = []

    @property
    def active_count(self) -> int:
        """Number of currently connected clients."""
        return len(self._active_connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self._active_connections.append(websocket)
        logger.info(
            "WebSocket client connected (total: %d)", self.active_count
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the active list."""
        if websocket in self._active_connections:
            self._active_connections.remove(websocket)
        logger.info(
            "WebSocket client disconnected (total: %d)", self.active_count
        )

    async def send_personal(self, websocket: WebSocket, message: dict) -> None:
        """Send a message to a specific WebSocket client."""
        try:
            await websocket.send_json(message)
        except Exception:
            logger.debug("Failed to send personal message, removing client")
            self.disconnect(websocket)

    async def broadcast(self, message: dict) -> None:
        """Broadcast a message to all connected WebSocket clients.

        Disconnects clients that fail to receive the message.
        """
        if not self._active_connections:
            return

        disconnected: list[WebSocket] = []

        for connection in self._active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for ws in disconnected:
            self.disconnect(ws)

        if disconnected:
            logger.info(
                "Cleaned up %d stale WebSocket connections", len(disconnected)
            )

    async def broadcast_price_update(self, price_data: dict) -> None:
        """Broadcast a price update to all connected clients.

        Args:
            price_data: Dict of symbol -> price info to broadcast.
        """
        message = {
            "type": "price_update",
            "data": price_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self.broadcast(message)

    async def broadcast_error(self, error: str) -> None:
        """Broadcast an error message to all connected clients."""
        message = {
            "type": "error",
            "data": {"message": error},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self.broadcast(message)

    async def handle_client_message(
        self, websocket: WebSocket, raw_message: str
    ) -> None:
        """Handle an incoming message from a WebSocket client.

        Supports:
        - ping/pong heartbeats
        - subscribe to specific symbols (future use)
        """
        try:
            msg = json.loads(raw_message)
        except json.JSONDecodeError:
            await self.send_personal(
                websocket,
                {"type": "error", "data": {"message": "Invalid JSON"}},
            )
            return

        msg_type = msg.get("type", "")

        if msg_type == "ping":
            await self.send_personal(
                websocket,
                {
                    "type": "pong",
                    "data": {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        elif msg_type == "subscribe":
            # Acknowledge subscription (actual filtering is a future enhancement)
            symbols = msg.get("data", {}).get("symbols", [])
            await self.send_personal(
                websocket,
                {
                    "type": "subscribed",
                    "data": {"symbols": symbols},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        else:
            await self.send_personal(
                websocket,
                {
                    "type": "error",
                    "data": {"message": f"Unknown message type: {msg_type}"},
                },
            )


# Singleton manager instance
manager = ConnectionManager()
