"""Pydantic request / response schemas for the portfolio domain."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_default: bool = False


class PortfolioUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_default: Optional[bool] = None


class PortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: Optional[str] = None
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
    exchange: Optional[str] = None
    quantity: Decimal = Field(..., ge=0)
    average_entry_price: Decimal = Field(..., ge=0)
    current_price: Decimal = Field(default=Decimal("0"), ge=0)
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None


class PositionUpdate(BaseModel):
    quantity: Optional[Decimal] = Field(None, ge=0)
    average_entry_price: Optional[Decimal] = Field(None, ge=0)
    current_price: Optional[Decimal] = Field(None, ge=0)
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None


class PositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    portfolio_id: uuid.UUID
    symbol: str
    asset_type: str
    exchange: Optional[str] = None
    quantity: Decimal
    average_entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    opened_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

class TransactionCreate(BaseModel):
    portfolio_id: uuid.UUID
    position_id: Optional[uuid.UUID] = None
    symbol: str = Field(..., min_length=1, max_length=32)
    side: str = Field(..., pattern=r"^(buy|sell)$")
    quantity: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., ge=0)
    fee: Decimal = Field(default=Decimal("0"), ge=0)
    exchange: Optional[str] = None
    order_id: Optional[str] = None
    strategy: Optional[str] = None
    notes: Optional[str] = None
    executed_at: Optional[datetime] = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    portfolio_id: uuid.UUID
    position_id: Optional[uuid.UUID] = None
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    exchange: Optional[str] = None
    order_id: Optional[str] = None
    strategy: Optional[str] = None
    notes: Optional[str] = None
    executed_at: datetime


# ---------------------------------------------------------------------------
# Portfolio with positions (nested response)
# ---------------------------------------------------------------------------

class PortfolioWithPositions(PortfolioResponse):
    positions: List[PositionResponse] = []


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
    allocation: List[AllocationEntry]
