"""Notification event publisher for the auto-trader.

Publishes structured events on Redis channel ``notification:events`` for the
notification-service dispatchers (Telegram + SMS) to consume. Each dispatcher
is responsible for fetching the user preferences for its own channel
(``user.preferences.telegram`` vs ``user.preferences.sms``), rate limiting,
delivery, and persistence.

We also publish on the legacy channel ``sms:events`` for backward
compatibility while the existing SMS dispatcher migrates.

Event types (must match the keys in ``user.preferences.sms.events``):
    - trade_buy           : a buy order was filled
    - trade_sell          : a sell order was filled
    - trade_failed        : an order failed during execution
    - stop_loss_hit       : a stop-loss was triggered
    - take_profit_hit     : a take-profit was triggered
    - circuit_breaker     : an automatic safety stop fired
    - emergency_halt      : user or system triggered emergency stop
    - daily_recap         : end-of-day recap SMS
    - position_opened_large : a position > N% of portfolio was opened
    - pnl_milestone       : P&L crossed ±X%
    - auto_armed          : auto-trading enabled
    - auto_disarmed       : auto-trading disabled
    - heartbeat_miss      : dead-man switch alert
    - new_login_unknown   : login from a new IP/device
    - api_key_error       : Binance API key invalid or expired
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict

logger = logging.getLogger(__name__)

_PRIMARY_CHANNEL = "notification:events"
_LEGACY_CHANNEL = "sms:events"


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


async def publish_event(
    redis_client: Any,
    user_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    """Publish a notification event to Redis for the channel dispatchers.

    Silent on failure — auto-trader cycles must not be broken by hiccups.
    Publishes on the primary ``notification:events`` channel and the
    legacy ``sms:events`` for backward compatibility.
    """
    if redis_client is None:
        logger.debug("No redis client — event %s dropped", event_type)
        return
    envelope = {
        "user_id": user_id,
        "event_type": event_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    serialised = json.dumps(envelope, default=_json_default)
    try:
        await redis_client.publish(_PRIMARY_CHANNEL, serialised)
        await redis_client.publish(_LEGACY_CHANNEL, serialised)
        logger.debug("notification event published: %s for user %s", event_type, user_id)
    except Exception as exc:
        logger.warning("Failed to publish notification event %s: %s", event_type, exc)
