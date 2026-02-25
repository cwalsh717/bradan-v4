"""
DCF Computation Engine — Two-Stage FCFF Valuation

Pure computation module with ZERO database access.
Takes typed inputs, runs two-stage FCFF valuation, returns structured outputs.

Based on Aswath Damodaran's FCFF framework.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Rounding context for final outputs
TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")

# Synthetic rating table: (lower_bound, upper_bound, rating, spread)
# Coverage ratio maps to rating and default spread
SYNTHETIC_RATING_TABLE: list[tuple[Decimal, Decimal, str, Decimal]] = [
    (Decimal("8.50"), Decimal("999999"), "AAA", Decimal("0.0075")),
    (Decimal("6.50"), Decimal("8.50"), "AA", Decimal("0.0100")),
    (Decimal("5.50"), Decimal("6.50"), "A+", Decimal("0.0150")),
    (Decimal("4.25"), Decimal("5.50"), "A", Decimal("0.0180")),
    (Decimal("3.00"), Decimal("4.25"), "A-", Decimal("0.0200")),
    (Decimal("2.50"), Decimal("3.00"), "BBB", Decimal("0.0225")),
    (Decimal("2.25"), Decimal("2.50"), "BB+", Decimal("0.0275")),
    (Decimal("2.00"), Decimal("2.25"), "BB", Decimal("0.0350")),
    (Decimal("1.75"), Decimal("2.00"), "B+", Decimal("0.0475")),
    (Decimal("1.50"), Decimal("1.75"), "B", Decimal("0.0650")),
    (Decimal("1.25"), Decimal("1.50"), "B-", Decimal("0.0800")),
    (Decimal("0.80"), Decimal("1.25"), "CCC", Decimal("0.1000")),
    (Decimal("0.65"), Decimal("0.80"), "CC", Decimal("0.1150")),
    (Decimal("0.20"), Decimal("0.65"), "C", Decimal("0.1270")),
    (Decimal("-999999"), Decimal("0.20"), "D", Decimal("0.1500")),
]


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class DCFInputs:
    """All inputs needed by the DCF engine. Passed in by the service layer."""

    # Base financials (from TTM)
    revenue: Decimal
    ebit: Decimal
    tax_provision: Decimal
    pretax_income: Decimal
    capex: Decimal
    depreciation: Decimal
    working_capital_change: Decimal
    interest_expense: Decimal

    # Balance sheet (latest quarter)
    total_debt: Decimal
    cash_and_equivalents: Decimal
    book_value_equity: Decimal
    shares_outstanding: Decimal
    current_price: Decimal  # for market cap

    # Market/reference data
    risk_free_rate: Decimal  # from FRED DGS10
    equity_risk_premium: Decimal  # from Damodaran
    country_risk_premium: Decimal  # from Damodaran
    unlevered_beta: Decimal  # from Damodaran industry
    sector_avg_debt_to_equity: Decimal  # for stable state
    sector_avg_roc: Decimal  # optional reference

    # Assumptions (can be overridden by user)
    forecast_years: int = 10
    stable_growth_rate: Optional[Decimal] = None  # defaults to risk_free - 1%
    stable_roc: Optional[Decimal] = None  # defaults to WACC (excess returns = 0)
    stable_beta: Decimal = Decimal("1.0")
    stable_debt_to_equity: Optional[Decimal] = None  # defaults to sector avg
    marginal_tax_rate: Decimal = Decimal("0.25")  # US default

    # Optional: minority interests, preferred stock (default 0)
    minority_interests: Decimal = Decimal("0")
    preferred_stock: Decimal = Decimal("0")


@dataclass
class YearProjection:
    """Single year in the high-growth projection."""

    year: int
    growth_rate: Decimal
    revenue: Decimal
    ebit: Decimal
    ebit_after_tax: Decimal
    reinvestment_rate: Decimal
    reinvestment: Decimal
    fcff: Decimal
    beta: Decimal
    cost_of_equity: Decimal
    debt_ratio: Decimal
    wacc: Decimal
    roc: Decimal
    pv_factor: Decimal
    pv_fcff: Decimal


@dataclass
class DCFResult:
    """Complete output of the DCF valuation."""

    # Key outputs
    value_per_share: Decimal
    enterprise_value: Decimal
    equity_value: Decimal
    implied_upside: Decimal  # (value_per_share - current_price) / current_price

    # Computed inputs (for display)
    effective_tax_rate: Decimal
    computed_tax_rate: Decimal  # what's actually used
    ebit_after_tax: Decimal
    reinvestment: Decimal
    reinvestment_rate: Decimal
    return_on_capital: Decimal
    expected_growth: Decimal
    levered_beta: Decimal
    cost_of_equity: Decimal
    synthetic_rating: str
    default_spread: Decimal
    cost_of_debt_pretax: Decimal
    cost_of_debt_aftertax: Decimal
    wacc: Decimal
    debt_ratio: Decimal  # D/(D+E)

    # Year-by-year projections
    projections: list[YearProjection]

    # Terminal value
    terminal_value: Decimal
    terminal_fcff: Decimal
    terminal_reinvestment_rate: Decimal
    terminal_wacc: Decimal
    terminal_growth: Decimal
    terminal_roc: Decimal
    pv_terminal: Decimal
    pv_operating_cashflows: Decimal

    # Equity bridge
    enterprise_value_detail: dict  # {pv_fcff, pv_terminal}
    equity_bridge: (
        dict  # {enterprise_value, +cash, -debt, -minority, -preferred, =equity}
    )

    # Metadata
    scenario: str  # "moderate", "conservative", "optimistic", "custom"
    forecast_years: int


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DCFError(Exception):
    """Raised when the DCF computation cannot proceed."""

    pass


# ---------------------------------------------------------------------------
# Helper Functions (pure computation)
# ---------------------------------------------------------------------------


def _compute_effective_tax_rate(
    tax_provision: Decimal, pretax_income: Decimal, marginal_tax_rate: Decimal
) -> tuple[Decimal, Decimal]:
    """
    Compute effective tax rate.
    Returns (raw_effective_rate, rate_to_use).
    If effective rate is < 0 or > 0.50, use marginal rate.
    """
    if pretax_income == 0:
        return Decimal("0"), marginal_tax_rate

    effective = tax_provision / pretax_income

    if effective < Decimal("0") or effective > Decimal("0.50"):
        return effective, marginal_tax_rate

    return effective, effective


def _compute_reinvestment(
    capex: Decimal, depreciation: Decimal, working_capital_change: Decimal
) -> Decimal:
    """Reinvestment = (CapEx - Depreciation) + delta Working Capital."""
    return (capex - depreciation) + working_capital_change


def _compute_invested_capital(
    book_value_equity: Decimal, total_debt: Decimal, cash: Decimal
) -> Decimal:
    """Invested Capital = BV Equity + Total Debt - Cash."""
    return book_value_equity + total_debt - cash


def _lever_beta(
    unlevered_beta: Decimal, tax_rate: Decimal, debt_to_equity: Decimal
) -> Decimal:
    """Lever beta using the Hamada equation."""
    return unlevered_beta * (Decimal("1") + (Decimal("1") - tax_rate) * debt_to_equity)


def _get_synthetic_rating(
    ebit: Decimal, interest_expense: Decimal
) -> tuple[str, Decimal]:
    """
    Map interest coverage ratio to synthetic rating and default spread.
    If interest_expense <= 0, company has no/negligible debt => AAA.
    """
    if interest_expense <= Decimal("0"):
        return ("AAA", Decimal("0.0075"))

    coverage = ebit / interest_expense

    for lower, upper, rating, spread in SYNTHETIC_RATING_TABLE:
        if coverage >= lower and (coverage < upper or upper == Decimal("999999")):
            return (rating, spread)

    # Fallback (should not happen with the table covering all ranges)
    return ("D", Decimal("0.1500"))


def _compute_cost_of_equity(
    risk_free: Decimal, levered_beta: Decimal, erp: Decimal, crp: Decimal
) -> Decimal:
    """CAPM: Cost of Equity = Rf + beta x ERP + CRP."""
    return risk_free + levered_beta * erp + crp


def _compute_wacc(
    cost_of_equity: Decimal,
    cost_of_debt_after_tax: Decimal,
    equity_weight: Decimal,
    debt_weight: Decimal,
) -> Decimal:
    """WACC = Ke x (E/(D+E)) + Kd(1-t) x (D/(D+E))."""
    return cost_of_equity * equity_weight + cost_of_debt_after_tax * debt_weight


def _linear_transition(base: Decimal, target: Decimal, t: int, n: int) -> Decimal:
    """Linearly interpolate from base to target at step t out of n."""
    if n == 0:
        return target
    fraction = Decimal(str(t)) / Decimal(str(n))
    return base + (target - base) * fraction


# ---------------------------------------------------------------------------
# Core Computation
# ---------------------------------------------------------------------------


def _compute_base_year(inputs: DCFInputs) -> dict:
    """
    Compute all base-year derived values from raw inputs.
    Returns a dict with all the intermediate values needed for projection.
    """
    if inputs.ebit <= Decimal("0"):
        raise DCFError(
            f"EBIT must be positive for DCF valuation (got {inputs.ebit}). "
            "Company with negative EBIT is not DCF-eligible."
        )

    # Tax rate
    effective_tax_rate, computed_tax_rate = _compute_effective_tax_rate(
        inputs.tax_provision, inputs.pretax_income, inputs.marginal_tax_rate
    )

    # EBIT after tax
    ebit_after_tax = inputs.ebit * (Decimal("1") - computed_tax_rate)

    # Reinvestment
    reinvestment = _compute_reinvestment(
        inputs.capex, inputs.depreciation, inputs.working_capital_change
    )

    # Reinvestment rate
    if ebit_after_tax > Decimal("0"):
        reinvestment_rate = reinvestment / ebit_after_tax
    else:
        reinvestment_rate = Decimal("0")

    # Invested capital
    invested_capital = _compute_invested_capital(
        inputs.book_value_equity, inputs.total_debt, inputs.cash_and_equivalents
    )

    # Return on capital
    if invested_capital > Decimal("0"):
        roc = ebit_after_tax / invested_capital
    else:
        roc = Decimal("0")

    # Expected growth = RR x ROC
    expected_growth = reinvestment_rate * roc

    # Market cap
    market_cap = inputs.shares_outstanding * inputs.current_price

    # Debt / Equity ratio (market value)
    if market_cap > Decimal("0"):
        debt_to_equity = inputs.total_debt / market_cap
    else:
        debt_to_equity = Decimal("0")

    # Debt ratio: D / (D + E)
    total_capital = inputs.total_debt + market_cap
    if total_capital > Decimal("0"):
        debt_ratio = inputs.total_debt / total_capital
    else:
        debt_ratio = Decimal("0")
    equity_ratio = Decimal("1") - debt_ratio

    # Beta
    levered_beta = _lever_beta(inputs.unlevered_beta, computed_tax_rate, debt_to_equity)

    # Cost of equity
    cost_of_equity = _compute_cost_of_equity(
        inputs.risk_free_rate,
        levered_beta,
        inputs.equity_risk_premium,
        inputs.country_risk_premium,
    )

    # Cost of debt
    synthetic_rating, default_spread = _get_synthetic_rating(
        inputs.ebit, inputs.interest_expense
    )
    cost_of_debt_pretax = inputs.risk_free_rate + default_spread
    cost_of_debt_aftertax = cost_of_debt_pretax * (Decimal("1") - computed_tax_rate)

    # WACC
    wacc = _compute_wacc(
        cost_of_equity, cost_of_debt_aftertax, equity_ratio, debt_ratio
    )

    # FCFF
    fcff = ebit_after_tax - reinvestment

    return {
        "effective_tax_rate": effective_tax_rate,
        "computed_tax_rate": computed_tax_rate,
        "ebit_after_tax": ebit_after_tax,
        "reinvestment": reinvestment,
        "reinvestment_rate": reinvestment_rate,
        "invested_capital": invested_capital,
        "roc": roc,
        "expected_growth": expected_growth,
        "market_cap": market_cap,
        "debt_to_equity": debt_to_equity,
        "debt_ratio": debt_ratio,
        "equity_ratio": equity_ratio,
        "levered_beta": levered_beta,
        "cost_of_equity": cost_of_equity,
        "synthetic_rating": synthetic_rating,
        "default_spread": default_spread,
        "cost_of_debt_pretax": cost_of_debt_pretax,
        "cost_of_debt_aftertax": cost_of_debt_aftertax,
        "wacc": wacc,
        "fcff": fcff,
    }


def _compute_projections(inputs: DCFInputs, base: dict) -> list[YearProjection]:
    """
    Build year-by-year projections for the high-growth period.
    All parameters transition linearly from base to stable over forecast_years.
    """
    n = inputs.forecast_years

    # Resolve stable-state defaults
    stable_growth = inputs.stable_growth_rate
    if stable_growth is None:
        stable_growth = inputs.risk_free_rate - Decimal("0.01")
    # Hard cap: terminal growth cannot exceed risk-free rate
    stable_growth = min(stable_growth, inputs.risk_free_rate)

    stable_de = inputs.stable_debt_to_equity
    if stable_de is None:
        stable_de = inputs.sector_avg_debt_to_equity

    # Stable debt ratio: D/(D+E) from D/E
    if (Decimal("1") + stable_de) != 0:
        stable_debt_ratio = stable_de / (Decimal("1") + stable_de)
    else:
        stable_debt_ratio = Decimal("0")

    # Base values for transition
    base_growth = base["expected_growth"]
    base_beta = base["levered_beta"]
    base_debt_ratio = base["debt_ratio"]
    base_roc = base["roc"]

    # Stable ROC: defaults to stable WACC if not specified
    # We compute stable WACC first to get the default
    stable_equity_ratio = Decimal("1") - stable_debt_ratio
    stable_cost_of_equity = _compute_cost_of_equity(
        inputs.risk_free_rate,
        inputs.stable_beta,
        inputs.equity_risk_premium,
        inputs.country_risk_premium,
    )
    stable_cost_of_debt_pretax = base["cost_of_debt_pretax"]
    stable_cost_of_debt_aftertax = stable_cost_of_debt_pretax * (
        Decimal("1") - inputs.marginal_tax_rate
    )
    stable_wacc = _compute_wacc(
        stable_cost_of_equity,
        stable_cost_of_debt_aftertax,
        stable_equity_ratio,
        stable_debt_ratio,
    )

    stable_roc = inputs.stable_roc
    if stable_roc is None:
        stable_roc = stable_wacc  # excess returns = 0

    projections: list[YearProjection] = []
    cumulative_ebit_after_tax = base["ebit_after_tax"]
    cumulative_revenue = inputs.revenue
    cumulative_discount = Decimal("1")

    for t in range(1, n + 1):
        # Linear transitions
        g_t = _linear_transition(base_growth, stable_growth, t, n)
        beta_t = _linear_transition(base_beta, inputs.stable_beta, t, n)
        dr_t = _linear_transition(base_debt_ratio, stable_debt_ratio, t, n)
        roc_t = _linear_transition(base_roc, stable_roc, t, n)

        # Grow EBIT(1-t) and revenue
        cumulative_ebit_after_tax = cumulative_ebit_after_tax * (Decimal("1") + g_t)
        cumulative_revenue = cumulative_revenue * (Decimal("1") + g_t)

        # Reinvestment rate from growth and ROC
        if roc_t > Decimal("0"):
            rr_t = g_t / roc_t
        else:
            rr_t = Decimal("0")

        reinvestment_t = cumulative_ebit_after_tax * rr_t
        fcff_t = cumulative_ebit_after_tax - reinvestment_t

        # Compute WACC for this year
        er_t = Decimal("1") - dr_t
        coe_t = _compute_cost_of_equity(
            inputs.risk_free_rate,
            beta_t,
            inputs.equity_risk_premium,
            inputs.country_risk_premium,
        )
        cod_at_t = base["cost_of_debt_pretax"] * (
            Decimal("1") - base["computed_tax_rate"]
        )
        wacc_t = _compute_wacc(coe_t, cod_at_t, er_t, dr_t)

        # Cumulative discount factor
        cumulative_discount = cumulative_discount / (Decimal("1") + wacc_t)

        # Implied EBIT (pre-tax) for display
        tax_rate = base["computed_tax_rate"]
        if (Decimal("1") - tax_rate) != 0:
            ebit_t = cumulative_ebit_after_tax / (Decimal("1") - tax_rate)
        else:
            ebit_t = cumulative_ebit_after_tax

        pv_fcff_t = fcff_t * cumulative_discount

        projections.append(
            YearProjection(
                year=t,
                growth_rate=g_t,
                revenue=cumulative_revenue,
                ebit=ebit_t,
                ebit_after_tax=cumulative_ebit_after_tax,
                reinvestment_rate=rr_t,
                reinvestment=reinvestment_t,
                fcff=fcff_t,
                beta=beta_t,
                cost_of_equity=coe_t,
                debt_ratio=dr_t,
                wacc=wacc_t,
                roc=roc_t,
                pv_factor=cumulative_discount,
                pv_fcff=pv_fcff_t,
            )
        )

    return projections


def _compute_terminal_value(
    inputs: DCFInputs,
    base: dict,
    projections: list[YearProjection],
) -> dict:
    """
    Compute terminal value using Gordon Growth Model.
    Returns dict with terminal value components.
    """
    # Resolve stable parameters
    stable_growth = inputs.stable_growth_rate
    if stable_growth is None:
        stable_growth = inputs.risk_free_rate - Decimal("0.01")
    stable_growth = min(stable_growth, inputs.risk_free_rate)

    stable_de = inputs.stable_debt_to_equity
    if stable_de is None:
        stable_de = inputs.sector_avg_debt_to_equity
    if (Decimal("1") + stable_de) != 0:
        stable_debt_ratio = stable_de / (Decimal("1") + stable_de)
    else:
        stable_debt_ratio = Decimal("0")
    stable_equity_ratio = Decimal("1") - stable_debt_ratio

    # Stable WACC
    stable_cost_of_equity = _compute_cost_of_equity(
        inputs.risk_free_rate,
        inputs.stable_beta,
        inputs.equity_risk_premium,
        inputs.country_risk_premium,
    )
    stable_cost_of_debt_pretax = base["cost_of_debt_pretax"]
    stable_cost_of_debt_aftertax = stable_cost_of_debt_pretax * (
        Decimal("1") - inputs.marginal_tax_rate
    )
    stable_wacc = _compute_wacc(
        stable_cost_of_equity,
        stable_cost_of_debt_aftertax,
        stable_equity_ratio,
        stable_debt_ratio,
    )

    # Stable ROC
    stable_roc = inputs.stable_roc
    if stable_roc is None:
        stable_roc = stable_wacc

    # Terminal reinvestment rate
    if stable_roc > Decimal("0"):
        terminal_rr = stable_growth / stable_roc
    else:
        terminal_rr = Decimal("0")

    # Last year's EBIT(1-t) from projections
    last_ebit_at = projections[-1].ebit_after_tax

    # Terminal FCFF = EBIT(1-t)_{n+1} x (1 - RR_stable)
    terminal_ebit_at = last_ebit_at * (Decimal("1") + stable_growth)
    terminal_fcff = terminal_ebit_at * (Decimal("1") - terminal_rr)

    # Terminal value = FCFF_{n+1} / (WACC_stable - g_stable)
    denominator = stable_wacc - stable_growth
    if denominator <= Decimal("0"):
        raise DCFError(
            f"Terminal value denominator is non-positive: WACC_stable={stable_wacc}, "
            f"g_stable={stable_growth}. Stable growth must be less than stable WACC."
        )

    terminal_value = terminal_fcff / denominator

    # PV of terminal value using last year's cumulative discount factor
    cumulative_discount = projections[-1].pv_factor
    pv_terminal = terminal_value * cumulative_discount

    return {
        "terminal_value": terminal_value,
        "terminal_fcff": terminal_fcff,
        "terminal_reinvestment_rate": terminal_rr,
        "terminal_wacc": stable_wacc,
        "terminal_growth": stable_growth,
        "terminal_roc": stable_roc,
        "pv_terminal": pv_terminal,
    }


def _compute_equity_bridge(
    pv_operating: Decimal,
    pv_terminal: Decimal,
    inputs: DCFInputs,
) -> dict:
    """
    Enterprise Value -> Equity Value -> Value per Share.
    """
    enterprise_value = pv_operating + pv_terminal
    equity_value = (
        enterprise_value
        + inputs.cash_and_equivalents
        - inputs.total_debt
        - inputs.minority_interests
        - inputs.preferred_stock
    )
    value_per_share = equity_value / inputs.shares_outstanding

    return {
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "value_per_share": value_per_share,
        "equity_bridge": {
            "enterprise_value": enterprise_value,
            "plus_cash": inputs.cash_and_equivalents,
            "minus_debt": inputs.total_debt,
            "minus_minority_interests": inputs.minority_interests,
            "minus_preferred_stock": inputs.preferred_stock,
            "equity_value": equity_value,
        },
    }


# ---------------------------------------------------------------------------
# Main Entry Points
# ---------------------------------------------------------------------------


def compute_dcf(inputs: DCFInputs, scenario: str = "moderate") -> DCFResult:
    """
    Main entry point -- runs full two-stage FCFF DCF valuation.

    Args:
        inputs: All financial data and assumptions.
        scenario: Label for the scenario.

    Returns:
        DCFResult with all computed values, projections, and equity bridge.

    Raises:
        DCFError: If inputs are invalid (e.g., negative EBIT).
    """
    if inputs.shares_outstanding <= Decimal("0"):
        raise DCFError("Shares outstanding must be positive.")

    # Step 1: Base year calculations
    base = _compute_base_year(inputs)

    # Step 2: Year-by-year projections
    projections = _compute_projections(inputs, base)

    # Step 3: Terminal value
    terminal = _compute_terminal_value(inputs, base, projections)

    # Step 4: Sum PV of operating cash flows
    pv_operating = sum((p.pv_fcff for p in projections), Decimal("0"))

    # Step 5: Equity bridge
    bridge = _compute_equity_bridge(pv_operating, terminal["pv_terminal"], inputs)

    # Implied upside
    if inputs.current_price > Decimal("0"):
        implied_upside = (
            bridge["value_per_share"] - inputs.current_price
        ) / inputs.current_price
    else:
        implied_upside = Decimal("0")

    return DCFResult(
        # Key outputs
        value_per_share=bridge["value_per_share"].quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        ),
        enterprise_value=bridge["enterprise_value"].quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        ),
        equity_value=bridge["equity_value"].quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        ),
        implied_upside=implied_upside.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP),
        # Computed inputs
        effective_tax_rate=base["effective_tax_rate"],
        computed_tax_rate=base["computed_tax_rate"],
        ebit_after_tax=base["ebit_after_tax"],
        reinvestment=base["reinvestment"],
        reinvestment_rate=base["reinvestment_rate"],
        return_on_capital=base["roc"],
        expected_growth=base["expected_growth"],
        levered_beta=base["levered_beta"],
        cost_of_equity=base["cost_of_equity"],
        synthetic_rating=base["synthetic_rating"],
        default_spread=base["default_spread"],
        cost_of_debt_pretax=base["cost_of_debt_pretax"],
        cost_of_debt_aftertax=base["cost_of_debt_aftertax"],
        wacc=base["wacc"],
        debt_ratio=base["debt_ratio"],
        # Projections
        projections=projections,
        # Terminal value
        terminal_value=terminal["terminal_value"],
        terminal_fcff=terminal["terminal_fcff"],
        terminal_reinvestment_rate=terminal["terminal_reinvestment_rate"],
        terminal_wacc=terminal["terminal_wacc"],
        terminal_growth=terminal["terminal_growth"],
        terminal_roc=terminal["terminal_roc"],
        pv_terminal=terminal["pv_terminal"],
        pv_operating_cashflows=pv_operating,
        # Equity bridge
        enterprise_value_detail={
            "pv_fcff": pv_operating,
            "pv_terminal": terminal["pv_terminal"],
        },
        equity_bridge=bridge["equity_bridge"],
        # Metadata
        scenario=scenario,
        forecast_years=inputs.forecast_years,
    )


def compute_sensitivity_matrix(inputs: DCFInputs, result: DCFResult) -> dict:
    """
    Generate WACC vs. terminal growth rate sensitivity table.

    WACC range: base_wacc +/- 2%, step 0.5% (9 values)
    Growth range: 0% to risk_free_rate, step 0.5%

    Each cell: recompute terminal value with that WACC/growth,
    keep PV of operating cash flows constant.

    Returns:
        {
            "wacc_values": [...],
            "growth_values": [...],
            "matrix": [[value_per_share, ...], ...],
            "base_wacc": Decimal,
            "base_growth": Decimal,
        }
    """
    base_wacc = result.terminal_wacc
    pv_operating = result.pv_operating_cashflows

    # Last year's cumulative discount factor
    last_pv_factor = result.projections[-1].pv_factor
    last_ebit_at = result.projections[-1].ebit_after_tax

    # WACC range: base +/- 2%, step 0.5%
    wacc_values: list[Decimal] = []
    step = Decimal("0.005")
    for i in range(-4, 5):
        wacc_values.append(base_wacc + step * Decimal(str(i)))

    # Growth range: 0% to risk_free_rate, step 0.5%
    growth_values: list[Decimal] = []
    g = Decimal("0")
    while g <= inputs.risk_free_rate + Decimal("0.0001"):
        growth_values.append(g)
        g += step

    matrix: list[list[Decimal]] = []

    for g in growth_values:
        row: list[Decimal] = []
        for w in wacc_values:
            denominator = w - g
            if denominator <= Decimal("0"):
                # Invalid: growth >= WACC, cannot compute
                row.append(Decimal("0"))
                continue

            # Terminal ROC for reinvestment rate
            terminal_roc = result.terminal_roc
            if terminal_roc > Decimal("0"):
                terminal_rr = g / terminal_roc
            else:
                terminal_rr = Decimal("0")

            terminal_ebit_at = last_ebit_at * (Decimal("1") + g)
            terminal_fcff = terminal_ebit_at * (Decimal("1") - terminal_rr)
            terminal_value = terminal_fcff / denominator
            pv_terminal = terminal_value * last_pv_factor

            ev = pv_operating + pv_terminal
            equity = (
                ev
                + inputs.cash_and_equivalents
                - inputs.total_debt
                - inputs.minority_interests
                - inputs.preferred_stock
            )
            vps = (equity / inputs.shares_outstanding).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            row.append(vps)
        matrix.append(row)

    return {
        "wacc_values": wacc_values,
        "growth_values": growth_values,
        "matrix": matrix,
        "base_wacc": base_wacc,
        "base_growth": result.terminal_growth,
    }


def apply_scenario(
    inputs: DCFInputs,
    scenario: str,
    sector_avg_reinvestment_rate: Decimal = Decimal("0"),
    sector_avg_roc: Decimal = Decimal("0"),
) -> DCFInputs:
    """
    Return modified inputs for a scenario preset.

    Scenarios:
        "conservative": sector avg growth, no beta improvement, ROC=WACC, g=rf-2%
        "moderate" (default): company's own rates, beta->1.0, ROC=WACC, g=rf-1%
        "optimistic": company's rates, beta->0.8-1.0, ROC=1.5xWACC, g=rf
    """
    import copy

    modified = copy.deepcopy(inputs)

    if scenario == "conservative":
        # Keep current beta (no improvement) -- compute current levered beta
        market_cap = inputs.shares_outstanding * inputs.current_price
        if market_cap > Decimal("0"):
            current_de = inputs.total_debt / market_cap
        else:
            current_de = Decimal("0")
        _, computed_tax = _compute_effective_tax_rate(
            inputs.tax_provision, inputs.pretax_income, inputs.marginal_tax_rate
        )
        current_levered_beta = _lever_beta(
            inputs.unlevered_beta, computed_tax, current_de
        )
        modified.stable_beta = current_levered_beta
        modified.stable_debt_to_equity = current_de  # no change in capital structure
        modified.stable_roc = None  # will default to WACC (excess returns = 0)
        modified.stable_growth_rate = inputs.risk_free_rate - Decimal("0.02")

    elif scenario == "moderate":
        # Default behavior -- company's own rates, beta -> 1.0, ROC = WACC
        modified.stable_beta = Decimal("1.0")
        modified.stable_debt_to_equity = None  # sector avg default
        modified.stable_roc = None  # WACC default
        modified.stable_growth_rate = inputs.risk_free_rate - Decimal("0.01")

    elif scenario == "optimistic":
        modified.stable_beta = Decimal("1.0")
        modified.stable_debt_to_equity = None  # sector avg default
        modified.stable_growth_rate = inputs.risk_free_rate  # max: risk-free rate

        # Terminal ROC = 1.5x WACC -- compute an estimate of stable WACC first
        stable_de = inputs.sector_avg_debt_to_equity
        if (Decimal("1") + stable_de) != 0:
            stable_dr = stable_de / (Decimal("1") + stable_de)
        else:
            stable_dr = Decimal("0")
        stable_er = Decimal("1") - stable_dr
        coe = _compute_cost_of_equity(
            inputs.risk_free_rate,
            Decimal("1.0"),
            inputs.equity_risk_premium,
            inputs.country_risk_premium,
        )
        _, spread = _get_synthetic_rating(inputs.ebit, inputs.interest_expense)
        cod_pretax = inputs.risk_free_rate + spread
        cod_at = cod_pretax * (Decimal("1") - inputs.marginal_tax_rate)
        est_wacc = _compute_wacc(coe, cod_at, stable_er, stable_dr)
        modified.stable_roc = est_wacc * Decimal("1.5")

    else:
        # "custom" or unknown -- return as-is
        pass

    return modified
