"""ORM models mirroring the trading-engine schema for auto-trading tables.

These models are READ/WRITE against the same ``gluetrade_trading`` database
owned by trading-engine. They are intentionally identical in structure —
trading-engine owns the migrations, ai-agent-service just consumes and writes
through its own async engine.
"""

from app.models.db.auto import (
    AutoDecisionRow,
    AutoSessionRow,
    SmsNotificationRow,
    TradeGroupRow,
)

__all__ = [
    "AutoSessionRow",
    "AutoDecisionRow",
    "TradeGroupRow",
    "SmsNotificationRow",
]
