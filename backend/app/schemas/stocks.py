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


class RatiosResponse(BaseModel):
    """Flat dict of computed financial ratios."""

    # Profitability
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    roic: Optional[float] = None
    # Liquidity
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    # Leverage
    debt_to_equity: Optional[float] = None
    debt_to_assets: Optional[float] = None
    interest_coverage: Optional[float] = None
    # Valuation
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    # Efficiency
    asset_turnover: Optional[float] = None
    inventory_turnover: Optional[float] = None


class PeerRecord(BaseModel):
    """A single peer stock in the same Damodaran industry."""

    symbol: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
