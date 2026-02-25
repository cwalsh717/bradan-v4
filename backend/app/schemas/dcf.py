"""Pydantic schemas for DCF valuation API request/response types."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Response schemas — DCF computation results
# ---------------------------------------------------------------------------


class YearProjection(BaseModel):
    """Single year in the DCF projection."""

    year: int
    growth_rate: float
    revenue: float
    ebit: float
    ebit_after_tax: float
    reinvestment_rate: float
    reinvestment: float
    fcff: float
    beta: float
    cost_of_equity: float
    debt_ratio: float
    wacc: float
    roc: float
    pv_factor: float
    pv_fcff: float


class EquityBridge(BaseModel):
    """Enterprise value to equity value bridge."""

    enterprise_value: float
    plus_cash: float
    minus_debt: float
    minus_minority_interests: float
    minus_preferred_stock: float
    equity_value: float
    shares_outstanding: float
    value_per_share: float


class DCFComputedInputs(BaseModel):
    """All computed/assumed inputs for transparency."""

    effective_tax_rate: float
    computed_tax_rate: float
    ebit_after_tax: float
    reinvestment: float
    reinvestment_rate: float
    return_on_capital: float
    expected_growth: float
    levered_beta: float
    cost_of_equity: float
    synthetic_rating: str
    default_spread: float
    cost_of_debt_pretax: float
    cost_of_debt_aftertax: float
    wacc: float
    debt_ratio: float
    market_cap: float


class TerminalValue(BaseModel):
    """Terminal value computation details."""

    terminal_growth: float
    terminal_roc: float
    terminal_wacc: float
    terminal_reinvestment_rate: float
    terminal_fcff: float
    terminal_value: float
    pv_terminal: float


class DCFResult(BaseModel):
    """Full DCF valuation result."""

    symbol: str
    company_name: str
    value_per_share: float
    current_price: float
    implied_upside: float
    verdict: str  # "undervalued", "overvalued", "fairly valued"

    computed_inputs: DCFComputedInputs
    projections: list[YearProjection]
    terminal: TerminalValue
    equity_bridge: EquityBridge

    scenario: str  # "moderate", "conservative", "optimistic", "custom"
    forecast_years: int
    source_fiscal_date: str  # ISO date
    computed_at: str  # ISO datetime

    pv_operating_cashflows: float
    terminal_value_pct: float  # terminal as % of total value


class DCFDefaultResponse(BaseModel):
    """Response for GET /api/dcf/{symbol}/default."""

    data: DCFResult
    data_as_of: str
    next_refresh: Optional[str] = None


# ---------------------------------------------------------------------------
# Sensitivity analysis
# ---------------------------------------------------------------------------


class SensitivityMatrix(BaseModel):
    """WACC vs growth rate sensitivity table."""

    wacc_values: list[float]
    growth_values: list[float]
    matrix: list[list[float]]  # matrix[growth_idx][wacc_idx] = value_per_share
    base_wacc: float
    base_growth: float
    base_value: float


class SensitivityResponse(BaseModel):
    """Response for GET /api/dcf/{symbol}/sensitivity."""

    data: SensitivityMatrix


# ---------------------------------------------------------------------------
# Plain-English summary
# ---------------------------------------------------------------------------


class DCFSummary(BaseModel):
    """Plain-English valuation summary."""

    symbol: str
    company_name: str
    value_per_share: float
    current_price: float
    implied_upside: float
    verdict: str
    summary_text: str
    key_assumptions: list[str]
    risk_factors: list[str]


class DCFSummaryResponse(BaseModel):
    """Response for GET /api/dcf/{symbol}/summary."""

    data: DCFSummary


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class DCFOverrides(BaseModel):
    """User slider overrides for custom DCF run."""

    forecast_years: Optional[int] = None
    stable_growth_rate: Optional[float] = None
    stable_roc: Optional[float] = None
    stable_beta: Optional[float] = None
    stable_debt_to_equity: Optional[float] = None
    risk_free_rate: Optional[float] = None
    equity_risk_premium: Optional[float] = None
    growth_rate_override: Optional[float] = None
    reinvestment_rate_override: Optional[float] = None
    wacc_override: Optional[float] = None
    marginal_tax_rate: Optional[float] = None
    scenario: Optional[str] = None


class DCFSaveRequest(BaseModel):
    """Request to save a custom DCF run."""

    run_name: str
    overrides: DCFOverrides


# ---------------------------------------------------------------------------
# Saved run schemas
# ---------------------------------------------------------------------------


class DCFRunMeta(BaseModel):
    """Metadata for a saved DCF run."""

    id: int
    run_name: str
    scenario: str
    value_per_share: float
    implied_upside: float
    computed_at: str
    source_fiscal_date: str

    model_config = ConfigDict(from_attributes=True)


class DCFRunListResponse(BaseModel):
    """Response for GET /api/dcf/{symbol}/runs."""

    data: list[DCFRunMeta]


class DCFRunDetailResponse(BaseModel):
    """Response for GET /api/dcf/{symbol}/runs/{run_id}."""

    data: DCFResult
    run_name: str
    run_id: int


# ---------------------------------------------------------------------------
# Sector context
# ---------------------------------------------------------------------------


class SectorContext(BaseModel):
    """Damodaran industry data for slider context."""

    industry_name: str
    match_confidence: float
    confidence_level: str
    manually_verified: bool

    unlevered_beta: float
    avg_effective_tax_rate: float
    avg_debt_to_equity: float
    avg_operating_margin: float
    avg_roc: float
    avg_reinvestment_rate: float
    cost_of_capital: float
    fundamental_growth_rate: float
    num_firms: int


class SectorContextResponse(BaseModel):
    """Response for GET /api/dcf/{symbol}/sector-context."""

    data: SectorContext


class DCFConstraints(BaseModel):
    """Slider constraint rules."""

    forecast_years: dict
    stable_growth_rate: dict
    stable_beta: dict
    stable_roc: dict
    stable_debt_to_equity: dict
    marginal_tax_rate: dict


class DCFConstraintsResponse(BaseModel):
    """Response for GET /api/dcf/constraints."""

    data: DCFConstraints


# ---------------------------------------------------------------------------
# Eligibility / error
# ---------------------------------------------------------------------------


class DCFEligibilityError(BaseModel):
    """Returned when stock is not eligible for DCF."""

    eligible: bool = False
    reason: str
    detail: str
