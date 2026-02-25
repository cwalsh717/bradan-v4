"""Pydantic response schemas for stock profile endpoints."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class StockEnvelope(BaseModel):
    """Standard response envelope for all stock endpoints."""

    data: Any
    data_as_of: Optional[datetime] = None
    next_refresh: Optional[datetime] = None


class StockProfile(BaseModel):
    """Stock profile fields returned within the envelope."""

    id: int
    symbol: str
    name: str
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    currency: Optional[str] = None
    last_updated: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FinancialRecord(BaseModel):
    """A single financial statement record."""

    id: int
    statement_type: str
    period: str
    fiscal_date: str
    data: dict
    fetched_at: datetime

    model_config = {"from_attributes": True}


class PriceRecord(BaseModel):
    """A single price history record."""

    id: int
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int] = None
    fetched_at: datetime

    model_config = {"from_attributes": True}


class DividendRecord(BaseModel):
    """A single dividend record."""

    id: int
    ex_date: str
    amount: float
    fetched_at: datetime

    model_config = {"from_attributes": True}


class SplitRecord(BaseModel):
    """A single stock split record."""

    id: int
    date: str
    ratio_from: int
    ratio_to: int

    model_config = {"from_attributes": True}
