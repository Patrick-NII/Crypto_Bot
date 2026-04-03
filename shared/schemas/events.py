"""
Shared event schemas for inter-service communication via Redis pub/sub.
"""
from enum import Enum
from datetime import datetime
from typing import Any


class EventType(str, Enum):
    # Market events
    PRICE_UPDATE = "market.price_update"
    MARKET_ALERT = "market.alert"

    # Trading events
    ORDER_CREATED = "trading.order_created"
    ORDER_FILLED = "trading.order_filled"
    ORDER_CANCELLED = "trading.order_cancelled"
    ORDER_FAILED = "trading.order_failed"

    # Portfolio events
    POSITION_OPENED = "portfolio.position_opened"
    POSITION_CLOSED = "portfolio.position_closed"
    PORTFOLIO_REBALANCE = "portfolio.rebalance"

    # Risk events
    STOP_LOSS_TRIGGERED = "risk.stop_loss_triggered"
    TAKE_PROFIT_TRIGGERED = "risk.take_profit_triggered"
    RISK_LIMIT_EXCEEDED = "risk.limit_exceeded"
    DRAWDOWN_ALERT = "risk.drawdown_alert"

    # ML events
    STRATEGY_OPTIMIZED = "ml.strategy_optimized"
    SIGNAL_GENERATED = "ml.signal_generated"
    MODEL_UPDATED = "ml.model_updated"

    # Notification events
    NOTIFICATION_SEND = "notification.send"


class EventSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


def create_event(
    event_type: EventType,
    payload: dict[str, Any],
    source: str,
    severity: EventSeverity = EventSeverity.INFO,
) -> dict:
    return {
        "event_type": event_type.value,
        "payload": payload,
        "source": source,
        "severity": severity.value,
        "timestamp": datetime.utcnow().isoformat(),
    }
