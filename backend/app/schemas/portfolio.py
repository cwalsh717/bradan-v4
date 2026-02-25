"""Pydantic request/response schemas for portfolio endpoints."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator


# ── Request schemas ──────────────────────────────────────────────


class PortfolioCreate(BaseModel):
    """Create a new portfolio."""

    name: str
    mode: str = "watchlist"

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        allowed = {"watchlist", "full"}
        if v not in allowed:
            raise ValueError(f"mode must be one of {allowed}")
        return v


class PortfolioUpdate(BaseModel):
    """Partial update for an existing portfolio."""

    name: Optional[str] = None
    mode: Optional[str] = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed = {"watchlist", "full"}
            if v not in allowed:
                raise ValueError(f"mode must be one of {allowed}")
        return v


class HoldingCreate(BaseModel):
    """Add a stock holding to a portfolio."""

    stock_id: int
    shares: Optional[Decimal] = None
    cost_basis_per_share: Optional[Decimal] = None


# ── Response schemas ─────────────────────────────────────────────


class PortfolioResponse(BaseModel):
    """Portfolio summary returned by list/create/update endpoints."""

    id: int
    name: str
    mode: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    holdings_count: int

    model_config = {"from_attributes": True}


class HoldingResponse(BaseModel):
    """Single holding with optional live-price enrichment."""

    id: int
    stock_id: int
    symbol: str
    name: str
    shares: Optional[Decimal] = None
    cost_basis_per_share: Optional[Decimal] = None
    added_at: datetime
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    gain_loss: Optional[float] = None
    gain_loss_pct: Optional[float] = None

    model_config = {"from_attributes": True}


class PerformanceSummary(BaseModel):
    """Aggregated portfolio performance with per-holding detail."""

    total_value: float
    total_cost_basis: float
    total_gain_loss: float
    total_gain_loss_pct: Optional[float] = None
    holdings: list[HoldingResponse]


class SnapshotResponse(BaseModel):
    """A point-in-time portfolio snapshot."""

    id: int
    date: date
    total_value: float
    total_cost_basis: float
    total_gain_loss: float
    holdings_snapshot: dict

    model_config = {"from_attributes": True}
