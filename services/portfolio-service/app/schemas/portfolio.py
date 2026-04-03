"""Pydantic request / response schemas for the portfolio domain."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    is_default: bool = False


class PortfolioUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_default: bool | None = None


class PortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None = None
    is_default: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------

class PositionCreate(BaseModel):
    portfolio_id: uuid.UUID
    symbol: str = Field(..., min_length=1, max_length=32)
    asset_type: str = Field(default="crypto", max_length=32)
    exchange: str | None = None
    quantity: Decimal = Field(..., ge=0)
    average_entry_price: Decimal = Field(..., ge=0)
    current_price: Decimal = Field(default=Decimal("0"), ge=0)
    stop_loss_price: Decimal | None = None
    take_profit_price: Decimal | None = None


class PositionUpdate(BaseModel):
    quantity: Decimal | None = Field(None, ge=0)
    average_entry_price: Decimal | None = Field(None, ge=0)
    current_price: Decimal | None = Field(None, ge=0)
    stop_loss_price: Decimal | None = None
    take_profit_price: Decimal | None = None


class PositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    portfolio_id: uuid.UUID
    symbol: str
    asset_type: str
    exchange: str | None = None
    quantity: Decimal
    average_entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    stop_loss_price: Decimal | None = None
    take_profit_price: Decimal | None = None
    opened_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

class TransactionCreate(BaseModel):
    portfolio_id: uuid.UUID
    position_id: uuid.UUID | None = None
    symbol: str = Field(..., min_length=1, max_length=32)
    side: str = Field(..., pattern=r"^(buy|sell)$")
    quantity: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., ge=0)
    fee: Decimal = Field(default=Decimal("0"), ge=0)
    exchange: str | None = None
    order_id: str | None = None
    strategy: str | None = None
    notes: str | None = None
    executed_at: datetime | None = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    portfolio_id: uuid.UUID
    position_id: uuid.UUID | None = None
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    exchange: str | None = None
    order_id: str | None = None
    strategy: str | None = None
    notes: str | None = None
    executed_at: datetime


# ---------------------------------------------------------------------------
# Portfolio with positions (nested response)
# ---------------------------------------------------------------------------

class PortfolioWithPositions(PortfolioResponse):
    positions: list[PositionResponse] = []


# ---------------------------------------------------------------------------
# Portfolio summary (aggregated view)
# ---------------------------------------------------------------------------

class AllocationEntry(BaseModel):
    asset_type: str
    value: Decimal
    percentage: Decimal


class PortfolioSummary(BaseModel):
    portfolio_id: uuid.UUID
    portfolio_name: str
    total_value: Decimal
    total_pnl: Decimal
    total_pnl_pct: Decimal
    positions_count: int
    allocation: list[AllocationEntry]
