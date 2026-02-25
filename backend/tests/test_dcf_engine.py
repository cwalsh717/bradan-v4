"""
Tests for the DCF computation engine.

Pure computation tests — no database, no async.
Validates the two-stage FCFF valuation model against:
  - SAP golden case (from Damodaran Session 10)
  - Sub-computation unit tests
  - Edge cases
  - Sensitivity matrix
  - Scenario presets
"""

import pytest
from decimal import Decimal

from app.services.dcf_engine import (
    DCFInputs,
    DCFResult,
    DCFError,
    compute_dcf,
    compute_sensitivity_matrix,
    apply_scenario,
    _lever_beta,
    _get_synthetic_rating,
    _compute_cost_of_equity,
    _compute_wacc,
    _linear_transition,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _approx(actual: Decimal, expected: Decimal, tolerance: Decimal) -> bool:
    """Check if actual is within tolerance of expected."""
    return abs(actual - expected) <= tolerance


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sap_inputs():
    """
    SAP validation case from dcf_methodology.md (Damodaran Session 10).

    The book_value_equity is set so that invested capital (BV + Debt - Cash)
    equals ~7095M, yielding ROC ~19.93% as per the reference case.
    """
    return DCFInputs(
        revenue=Decimal("17000"),
        ebit=Decimal("1820"),
        tax_provision=Decimal("406"),
        pretax_income=Decimal("1820"),
        capex=Decimal("831"),
        depreciation=Decimal("0"),
        working_capital_change=Decimal("-19"),
        interest_expense=Decimal("25"),
        total_debt=Decimal("558"),
        cash_and_equivalents=Decimal("3018"),
        book_value_equity=Decimal("9555"),  # IC = 9555 + 558 - 3018 = 7095
        shares_outstanding=Decimal("326"),
        current_price=Decimal("122"),
        risk_free_rate=Decimal("0.0341"),
        equity_risk_premium=Decimal("0.0400"),
        country_risk_premium=Decimal("0.0025"),
        unlevered_beta=Decimal("1.25"),
        sector_avg_debt_to_equity=Decimal("0.20"),
        sector_avg_roc=Decimal("0.10"),
        forecast_years=10,
        stable_growth_rate=Decimal("0.0341"),
        stable_roc=Decimal("0.0662"),
        stable_beta=Decimal("1.0"),
        stable_debt_to_equity=Decimal("0.20"),
        marginal_tax_rate=Decimal("0.25"),
        minority_interests=Decimal("55"),
        preferred_stock=Decimal("305"),
    )


@pytest.fixture
def sample_inputs():
    """A typical mid-cap company with moderate growth and leverage."""
    return DCFInputs(
        revenue=Decimal("50000"),
        ebit=Decimal("8000"),
        tax_provision=Decimal("1600"),
        pretax_income=Decimal("7500"),
        capex=Decimal("3000"),
        depreciation=Decimal("1500"),
        working_capital_change=Decimal("200"),
        interest_expense=Decimal("500"),
        total_debt=Decimal("10000"),
        cash_and_equivalents=Decimal("5000"),
        book_value_equity=Decimal("30000"),
        shares_outstanding=Decimal("1000"),
        current_price=Decimal("50"),
        risk_free_rate=Decimal("0.04"),
        equity_risk_premium=Decimal("0.05"),
        country_risk_premium=Decimal("0.00"),
        unlevered_beta=Decimal("1.10"),
        sector_avg_debt_to_equity=Decimal("0.30"),
        sector_avg_roc=Decimal("0.12"),
        forecast_years=10,
        stable_growth_rate=Decimal("0.03"),
        stable_roc=None,
        stable_beta=Decimal("1.0"),
        stable_debt_to_equity=None,
        marginal_tax_rate=Decimal("0.25"),
        minority_interests=Decimal("0"),
        preferred_stock=Decimal("0"),
    )


# ===========================================================================
# 1. SAP Validation Case (Golden Test)
# ===========================================================================


class TestSAPValidation:
    """Validate the engine against the SAP reference case from Damodaran."""

    def test_sap_ebit_after_tax(self, sap_inputs):
        """EBIT(1-t) should be approximately 1414M."""
        result = compute_dcf(sap_inputs)
        assert _approx(result.ebit_after_tax, Decimal("1414"), Decimal("71"))

    def test_sap_reinvestment(self, sap_inputs):
        """Reinvestment = CapEx - Depr + WC change = 831 - 0 + (-19) = 812M."""
        result = compute_dcf(sap_inputs)
        assert _approx(result.reinvestment, Decimal("812"), Decimal("41"))

    def test_sap_return_on_capital(self, sap_inputs):
        """ROC should be approximately 19.93%."""
        result = compute_dcf(sap_inputs)
        # Within 1 percentage point absolute tolerance
        assert _approx(result.return_on_capital, Decimal("0.1993"), Decimal("0.01"))

    def test_sap_expected_growth(self, sap_inputs):
        """Expected growth = RR x ROC should be approximately 11.44%."""
        result = compute_dcf(sap_inputs)
        assert _approx(result.expected_growth, Decimal("0.1144"), Decimal("0.02"))

    def test_sap_levered_beta(self, sap_inputs):
        """Levered beta should be approximately 1.26 (low debt, close to unlevered)."""
        result = compute_dcf(sap_inputs)
        assert _approx(result.levered_beta, Decimal("1.26"), Decimal("0.02"))

    def test_sap_cost_of_equity(self, sap_inputs):
        """Cost of equity should be approximately 8.77%."""
        result = compute_dcf(sap_inputs)
        # CAPM: Rf + beta*ERP + CRP = 3.41% + 1.26*4% + 0.25% ~ 8.70%
        assert _approx(result.cost_of_equity, Decimal("0.0877"), Decimal("0.005"))

    def test_sap_value_per_share_positive(self, sap_inputs):
        """Value per share must be a positive number."""
        result = compute_dcf(sap_inputs)
        assert result.value_per_share > Decimal("0")

    def test_sap_projections_count(self, sap_inputs):
        """Should have exactly 10 year projections."""
        result = compute_dcf(sap_inputs)
        assert len(result.projections) == 10

    def test_sap_terminal_value_positive(self, sap_inputs):
        """Terminal value must be positive."""
        result = compute_dcf(sap_inputs)
        assert result.terminal_value > Decimal("0")

    def test_sap_synthetic_rating_aaa(self, sap_inputs):
        """SAP with coverage = 1820/25 = 72.8 should get AAA rating."""
        result = compute_dcf(sap_inputs)
        assert result.synthetic_rating == "AAA"

    def test_sap_equity_bridge_components(self, sap_inputs):
        """Equity bridge should subtract debt, minority, preferred and add cash."""
        result = compute_dcf(sap_inputs)
        bridge = result.equity_bridge
        assert bridge["plus_cash"] == Decimal("3018")
        assert bridge["minus_debt"] == Decimal("558")
        assert bridge["minus_minority_interests"] == Decimal("55")
        assert bridge["minus_preferred_stock"] == Decimal("305")

    def test_sap_wacc(self, sap_inputs):
        """WACC should be approximately 8.68%."""
        result = compute_dcf(sap_inputs)
        assert _approx(result.wacc, Decimal("0.0868"), Decimal("0.005"))


# ===========================================================================
# 2. Sub-computation Unit Tests
# ===========================================================================


class TestLeverBeta:
    """Tests for the _lever_beta Hamada equation."""

    def test_lever_beta_zero_debt(self):
        """With D/E = 0, levered beta equals unlevered beta."""
        result = _lever_beta(
            unlevered_beta=Decimal("1.20"),
            tax_rate=Decimal("0.25"),
            debt_to_equity=Decimal("0"),
        )
        assert result == Decimal("1.20")

    def test_lever_beta_high_debt(self):
        """With D/E = 1.0, levered beta must exceed unlevered beta."""
        unlevered = Decimal("1.0")
        result = _lever_beta(
            unlevered_beta=unlevered,
            tax_rate=Decimal("0.25"),
            debt_to_equity=Decimal("1.0"),
        )
        # levered = 1.0 * (1 + 0.75 * 1.0) = 1.75
        assert result > unlevered
        assert _approx(result, Decimal("1.75"), Decimal("0.001"))

    def test_lever_beta_moderate_debt(self):
        """D/E = 0.3, tax = 20% => levered = 1.1 * (1 + 0.8 * 0.3) = 1.364."""
        result = _lever_beta(
            unlevered_beta=Decimal("1.1"),
            tax_rate=Decimal("0.20"),
            debt_to_equity=Decimal("0.3"),
        )
        assert _approx(result, Decimal("1.364"), Decimal("0.001"))


class TestSyntheticRating:
    """Tests for the _get_synthetic_rating interest coverage mapper."""

    def test_synthetic_rating_aaa(self):
        """Zero interest expense maps to AAA."""
        rating, spread = _get_synthetic_rating(
            ebit=Decimal("1000"), interest_expense=Decimal("0")
        )
        assert rating == "AAA"
        assert spread == Decimal("0.0075")

    def test_synthetic_rating_negative_interest(self):
        """Negative interest expense also maps to AAA."""
        rating, spread = _get_synthetic_rating(
            ebit=Decimal("500"), interest_expense=Decimal("-10")
        )
        assert rating == "AAA"
        assert spread == Decimal("0.0075")

    def test_synthetic_rating_coverage_aa(self):
        """Coverage 7.0 should map to AA (6.50-8.50 range)."""
        # EBIT=700, interest=100 => coverage=7.0
        rating, spread = _get_synthetic_rating(
            ebit=Decimal("700"), interest_expense=Decimal("100")
        )
        assert rating == "AA"
        assert spread == Decimal("0.0100")

    def test_synthetic_rating_coverage_a_plus(self):
        """Coverage 6.0 should map to A+ (5.50-6.50 range)."""
        rating, spread = _get_synthetic_rating(
            ebit=Decimal("600"), interest_expense=Decimal("100")
        )
        assert rating == "A+"
        assert spread == Decimal("0.0150")

    def test_synthetic_rating_coverage_bbb(self):
        """Coverage 2.75 should map to BBB (2.50-3.00 range)."""
        rating, spread = _get_synthetic_rating(
            ebit=Decimal("275"), interest_expense=Decimal("100")
        )
        assert rating == "BBB"
        assert spread == Decimal("0.0225")

    def test_synthetic_rating_coverage_ccc(self):
        """Coverage 1.0 should map to CCC (0.80-1.25 range)."""
        rating, spread = _get_synthetic_rating(
            ebit=Decimal("100"), interest_expense=Decimal("100")
        )
        assert rating == "CCC"
        assert spread == Decimal("0.1000")

    def test_synthetic_rating_coverage_d(self):
        """Coverage 0.1 should map to D (< 0.20 range)."""
        rating, spread = _get_synthetic_rating(
            ebit=Decimal("10"), interest_expense=Decimal("100")
        )
        assert rating == "D"
        assert spread == Decimal("0.1500")


class TestCostOfEquity:
    """Tests for the _compute_cost_of_equity CAPM function."""

    def test_cost_of_equity_capm(self):
        """CAPM: Rf + beta * ERP + CRP with known inputs."""
        # 0.04 + 1.2 * 0.05 + 0.01 = 0.04 + 0.06 + 0.01 = 0.11
        result = _compute_cost_of_equity(
            risk_free=Decimal("0.04"),
            levered_beta=Decimal("1.2"),
            erp=Decimal("0.05"),
            crp=Decimal("0.01"),
        )
        assert result == Decimal("0.11")

    def test_cost_of_equity_zero_crp(self):
        """US company with no country risk premium."""
        # 0.03 + 1.0 * 0.06 + 0 = 0.09
        result = _compute_cost_of_equity(
            risk_free=Decimal("0.03"),
            levered_beta=Decimal("1.0"),
            erp=Decimal("0.06"),
            crp=Decimal("0"),
        )
        assert result == Decimal("0.09")

    def test_cost_of_equity_high_beta(self):
        """High-beta stock should yield higher cost of equity."""
        result = _compute_cost_of_equity(
            risk_free=Decimal("0.04"),
            levered_beta=Decimal("2.0"),
            erp=Decimal("0.05"),
            crp=Decimal("0"),
        )
        # 0.04 + 2.0 * 0.05 = 0.14
        assert result == Decimal("0.14")


class TestWACC:
    """Tests for the _compute_wacc function."""

    def test_wacc_computation(self):
        """Known inputs: Ke=10%, Kd_at=3%, E_weight=0.8, D_weight=0.2."""
        result = _compute_wacc(
            cost_of_equity=Decimal("0.10"),
            cost_of_debt_after_tax=Decimal("0.03"),
            equity_weight=Decimal("0.80"),
            debt_weight=Decimal("0.20"),
        )
        # 0.10 * 0.80 + 0.03 * 0.20 = 0.08 + 0.006 = 0.086
        assert result == Decimal("0.086")

    def test_wacc_all_equity(self):
        """100% equity company: WACC equals cost of equity."""
        result = _compute_wacc(
            cost_of_equity=Decimal("0.12"),
            cost_of_debt_after_tax=Decimal("0.04"),
            equity_weight=Decimal("1.0"),
            debt_weight=Decimal("0.0"),
        )
        assert result == Decimal("0.12")

    def test_wacc_symmetry(self):
        """WACC must lie between Ke and Kd(1-t)."""
        ke = Decimal("0.12")
        kd = Decimal("0.04")
        result = _compute_wacc(
            cost_of_equity=ke,
            cost_of_debt_after_tax=kd,
            equity_weight=Decimal("0.60"),
            debt_weight=Decimal("0.40"),
        )
        assert kd <= result <= ke


class TestLinearTransition:
    """Tests for the _linear_transition interpolation function."""

    def test_linear_transition_midpoint(self):
        """Step 5 out of 10: base=10, target=20 => 15."""
        result = _linear_transition(base=Decimal("10"), target=Decimal("20"), t=5, n=10)
        assert result == Decimal("15")

    def test_linear_transition_start(self):
        """Step 0 out of 10: should return base."""
        result = _linear_transition(base=Decimal("10"), target=Decimal("20"), t=0, n=10)
        assert result == Decimal("10")

    def test_linear_transition_end(self):
        """Step 10 out of 10: should return target."""
        result = _linear_transition(
            base=Decimal("10"), target=Decimal("20"), t=10, n=10
        )
        assert result == Decimal("20")

    def test_linear_transition_zero_n(self):
        """If n=0, return target immediately."""
        result = _linear_transition(base=Decimal("10"), target=Decimal("20"), t=0, n=0)
        assert result == Decimal("20")

    def test_linear_transition_decreasing(self):
        """Transition from high to low value."""
        result = _linear_transition(
            base=Decimal("1.5"), target=Decimal("1.0"), t=5, n=10
        )
        assert result == Decimal("1.25")


# ===========================================================================
# 3. Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Tests for error handling and boundary conditions."""

    def test_negative_ebit_raises(self, sample_inputs):
        """EBIT <= 0 must raise DCFError."""
        sample_inputs.ebit = Decimal("-500")
        with pytest.raises(DCFError, match="EBIT must be positive"):
            compute_dcf(sample_inputs)

    def test_zero_ebit_raises(self, sample_inputs):
        """EBIT = 0 must also raise DCFError."""
        sample_inputs.ebit = Decimal("0")
        with pytest.raises(DCFError, match="EBIT must be positive"):
            compute_dcf(sample_inputs)

    def test_zero_shares_raises(self, sample_inputs):
        """Shares outstanding = 0 must raise DCFError."""
        sample_inputs.shares_outstanding = Decimal("0")
        with pytest.raises(DCFError, match="Shares outstanding must be positive"):
            compute_dcf(sample_inputs)

    def test_negative_shares_raises(self, sample_inputs):
        """Negative shares outstanding must raise DCFError."""
        sample_inputs.shares_outstanding = Decimal("-100")
        with pytest.raises(DCFError, match="Shares outstanding must be positive"):
            compute_dcf(sample_inputs)

    def test_zero_debt_company(self):
        """A company with zero debt and zero interest should complete without error."""
        inputs = DCFInputs(
            revenue=Decimal("20000"),
            ebit=Decimal("3000"),
            tax_provision=Decimal("600"),
            pretax_income=Decimal("3000"),
            capex=Decimal("1000"),
            depreciation=Decimal("500"),
            working_capital_change=Decimal("100"),
            interest_expense=Decimal("0"),
            total_debt=Decimal("0"),
            cash_and_equivalents=Decimal("2000"),
            book_value_equity=Decimal("15000"),
            shares_outstanding=Decimal("500"),
            current_price=Decimal("40"),
            risk_free_rate=Decimal("0.04"),
            equity_risk_premium=Decimal("0.05"),
            country_risk_premium=Decimal("0.00"),
            unlevered_beta=Decimal("1.0"),
            sector_avg_debt_to_equity=Decimal("0.20"),
            sector_avg_roc=Decimal("0.10"),
            forecast_years=10,
            stable_growth_rate=Decimal("0.03"),
            stable_roc=None,
            stable_beta=Decimal("1.0"),
            stable_debt_to_equity=None,
            marginal_tax_rate=Decimal("0.25"),
        )
        result = compute_dcf(inputs)
        assert result.value_per_share > Decimal("0")
        assert result.synthetic_rating == "AAA"
        assert result.debt_ratio == Decimal("0")

    def test_growth_capped_at_risk_free(self):
        """
        If stable_growth_rate > risk_free_rate, terminal growth is capped
        at risk_free_rate. Verify via the result's terminal_growth.
        """
        inputs = DCFInputs(
            revenue=Decimal("20000"),
            ebit=Decimal("3000"),
            tax_provision=Decimal("600"),
            pretax_income=Decimal("3000"),
            capex=Decimal("1000"),
            depreciation=Decimal("500"),
            working_capital_change=Decimal("100"),
            interest_expense=Decimal("200"),
            total_debt=Decimal("5000"),
            cash_and_equivalents=Decimal("2000"),
            book_value_equity=Decimal("15000"),
            shares_outstanding=Decimal("500"),
            current_price=Decimal("40"),
            risk_free_rate=Decimal("0.03"),
            equity_risk_premium=Decimal("0.05"),
            country_risk_premium=Decimal("0.00"),
            unlevered_beta=Decimal("1.0"),
            sector_avg_debt_to_equity=Decimal("0.20"),
            sector_avg_roc=Decimal("0.10"),
            forecast_years=5,
            stable_growth_rate=Decimal("0.10"),  # Deliberately > risk_free_rate
            stable_roc=Decimal("0.15"),
            stable_beta=Decimal("1.0"),
            stable_debt_to_equity=Decimal("0.20"),
            marginal_tax_rate=Decimal("0.25"),
        )
        result = compute_dcf(inputs)
        # Terminal growth should be capped at risk_free_rate
        assert result.terminal_growth <= Decimal("0.03")

    def test_negative_working_capital_change(self):
        """Negative working capital change (cash release) should work fine."""
        inputs = DCFInputs(
            revenue=Decimal("30000"),
            ebit=Decimal("5000"),
            tax_provision=Decimal("1000"),
            pretax_income=Decimal("4800"),
            capex=Decimal("1500"),
            depreciation=Decimal("700"),
            working_capital_change=Decimal("-500"),  # WC decreasing = cash inflow
            interest_expense=Decimal("200"),
            total_debt=Decimal("4000"),
            cash_and_equivalents=Decimal("3000"),
            book_value_equity=Decimal("20000"),
            shares_outstanding=Decimal("800"),
            current_price=Decimal("35"),
            risk_free_rate=Decimal("0.04"),
            equity_risk_premium=Decimal("0.05"),
            country_risk_premium=Decimal("0.00"),
            unlevered_beta=Decimal("1.05"),
            sector_avg_debt_to_equity=Decimal("0.25"),
            sector_avg_roc=Decimal("0.11"),
            forecast_years=10,
            stable_growth_rate=Decimal("0.03"),
            stable_roc=None,
            stable_beta=Decimal("1.0"),
            stable_debt_to_equity=None,
            marginal_tax_rate=Decimal("0.25"),
        )
        result = compute_dcf(inputs)
        assert result.value_per_share > Decimal("0")
        # Reinvestment = (1500 - 700) + (-500) = 300
        assert _approx(result.reinvestment, Decimal("300"), Decimal("1"))


# ===========================================================================
# 4. Sensitivity Matrix
# ===========================================================================


class TestSensitivityMatrix:
    """Tests for the sensitivity analysis matrix."""

    def test_sensitivity_matrix_dimensions(self, sample_inputs):
        """WACC column count should be 9 (-4 to +4 at 0.5% steps)."""
        result = compute_dcf(sample_inputs)
        matrix = compute_sensitivity_matrix(sample_inputs, result)
        assert len(matrix["wacc_values"]) == 9
        # Each row should have 9 entries
        for row in matrix["matrix"]:
            assert len(row) == 9

    def test_sensitivity_matrix_growth_range(self, sample_inputs):
        """Growth values should range from 0% to risk_free_rate in 0.5% steps."""
        result = compute_dcf(sample_inputs)
        matrix = compute_sensitivity_matrix(sample_inputs, result)
        growth_vals = matrix["growth_values"]
        assert growth_vals[0] == Decimal("0")
        assert growth_vals[-1] <= sample_inputs.risk_free_rate + Decimal("0.001")
        # Step size should be 0.5%
        if len(growth_vals) >= 2:
            step = growth_vals[1] - growth_vals[0]
            assert step == Decimal("0.005")

    def test_sensitivity_center_matches_base(self, sample_inputs):
        """
        The cell at (base_growth, base_wacc) should approximately match
        the base-case value_per_share.
        """
        result = compute_dcf(sample_inputs)
        matrix = compute_sensitivity_matrix(sample_inputs, result)

        base_wacc = matrix["base_wacc"]
        base_growth = matrix["base_growth"]

        # Find the closest WACC column index
        wacc_diffs = [abs(w - base_wacc) for w in matrix["wacc_values"]]
        wacc_idx = wacc_diffs.index(min(wacc_diffs))

        # Find the closest growth row index
        growth_diffs = [abs(g - base_growth) for g in matrix["growth_values"]]
        growth_idx = growth_diffs.index(min(growth_diffs))

        center_value = matrix["matrix"][growth_idx][wacc_idx]
        # Should be within 15% of base case (not exact due to grid discretization)
        diff_pct = abs(center_value - result.value_per_share) / result.value_per_share
        assert diff_pct < Decimal("0.15"), (
            f"Center cell {center_value} too far from base {result.value_per_share} "
            f"(diff={diff_pct:.2%})"
        )

    def test_sensitivity_wacc_monotonic(self, sample_inputs):
        """Higher WACC should generally yield lower value per share (for a given growth)."""
        result = compute_dcf(sample_inputs)
        matrix = compute_sensitivity_matrix(sample_inputs, result)
        # Pick a middle growth row
        mid_row_idx = len(matrix["growth_values"]) // 2
        row = matrix["matrix"][mid_row_idx]
        # Filter out zeros (invalid cells where growth >= WACC)
        valid = [v for v in row if v > Decimal("0")]
        if len(valid) >= 2:
            # Values should be non-increasing as WACC increases (left to right)
            for i in range(len(valid) - 1):
                assert valid[i] >= valid[i + 1], (
                    f"Value should decrease with higher WACC: "
                    f"{valid[i]} should be >= {valid[i + 1]}"
                )


# ===========================================================================
# 5. Scenario Presets
# ===========================================================================


class TestScenarioPresets:
    """Tests for the apply_scenario function."""

    def test_apply_scenario_conservative(self, sample_inputs):
        """Conservative: stable_growth should be risk_free - 2%."""
        modified = apply_scenario(sample_inputs, "conservative")
        expected_growth = sample_inputs.risk_free_rate - Decimal("0.02")
        assert modified.stable_growth_rate == expected_growth

    def test_apply_scenario_conservative_keeps_beta(self, sample_inputs):
        """Conservative: beta should NOT converge to 1.0 (stays at current levered)."""
        modified = apply_scenario(sample_inputs, "conservative")
        # The stable beta should be set to the current levered beta, not 1.0
        assert modified.stable_beta != Decimal("1.0")

    def test_apply_scenario_conservative_growth_less_than_moderate(self, sample_inputs):
        """Conservative stable_growth should be less than moderate stable_growth."""
        conservative = apply_scenario(sample_inputs, "conservative")
        moderate = apply_scenario(sample_inputs, "moderate")
        assert conservative.stable_growth_rate < moderate.stable_growth_rate

    def test_apply_scenario_moderate(self, sample_inputs):
        """Moderate: stable_beta = 1.0, growth = risk_free - 1%."""
        modified = apply_scenario(sample_inputs, "moderate")
        assert modified.stable_beta == Decimal("1.0")
        expected_growth = sample_inputs.risk_free_rate - Decimal("0.01")
        assert modified.stable_growth_rate == expected_growth
        # ROC defaults to WACC (None means compute_dcf will set it)
        assert modified.stable_roc is None

    def test_apply_scenario_optimistic(self, sample_inputs):
        """Optimistic: growth = risk_free, ROC = 1.5x WACC estimate."""
        modified = apply_scenario(sample_inputs, "optimistic")
        assert modified.stable_growth_rate == sample_inputs.risk_free_rate
        assert modified.stable_beta == Decimal("1.0")
        # ROC should be set to 1.5x estimated stable WACC (a positive number)
        assert modified.stable_roc is not None
        assert modified.stable_roc > Decimal("0")

    def test_apply_scenario_optimistic_growth_highest(self, sample_inputs):
        """Optimistic should have the highest stable growth of the three scenarios."""
        conservative = apply_scenario(sample_inputs, "conservative")
        moderate = apply_scenario(sample_inputs, "moderate")
        optimistic = apply_scenario(sample_inputs, "optimistic")
        assert optimistic.stable_growth_rate >= moderate.stable_growth_rate
        assert moderate.stable_growth_rate >= conservative.stable_growth_rate

    def test_apply_scenario_custom_passthrough(self, sample_inputs):
        """Unknown/custom scenario should return inputs unchanged."""
        modified = apply_scenario(sample_inputs, "custom")
        assert modified.stable_growth_rate == sample_inputs.stable_growth_rate
        assert modified.stable_beta == sample_inputs.stable_beta
        assert modified.stable_roc == sample_inputs.stable_roc

    def test_scenario_conservative_produces_lower_value(self, sample_inputs):
        """
        Running the full DCF with conservative inputs should generally produce
        a lower value per share than moderate.
        """
        conservative_inputs = apply_scenario(sample_inputs, "conservative")
        moderate_inputs = apply_scenario(sample_inputs, "moderate")
        conservative_result = compute_dcf(conservative_inputs, scenario="conservative")
        moderate_result = compute_dcf(moderate_inputs, scenario="moderate")
        assert conservative_result.value_per_share <= moderate_result.value_per_share


# ===========================================================================
# 6. Full DCF Integration Tests
# ===========================================================================


class TestFullDCF:
    """Integration tests for the complete compute_dcf pipeline."""

    def test_result_has_all_fields(self, sample_inputs):
        """DCFResult should have all expected fields populated."""
        result = compute_dcf(sample_inputs)
        assert isinstance(result, DCFResult)
        assert result.value_per_share is not None
        assert result.enterprise_value is not None
        assert result.equity_value is not None
        assert result.implied_upside is not None
        assert result.terminal_value > Decimal("0")
        assert len(result.projections) == sample_inputs.forecast_years
        assert result.scenario == "moderate"

    def test_projections_years_sequential(self, sample_inputs):
        """Projection years should be 1 through forecast_years."""
        result = compute_dcf(sample_inputs)
        years = [p.year for p in result.projections]
        assert years == list(range(1, sample_inputs.forecast_years + 1))

    def test_pv_factors_decreasing(self, sample_inputs):
        """PV discount factors should decrease each year."""
        result = compute_dcf(sample_inputs)
        for i in range(len(result.projections) - 1):
            assert result.projections[i].pv_factor > result.projections[i + 1].pv_factor

    def test_enterprise_value_decomposition(self, sample_inputs):
        """EV = PV of operating CFs + PV of terminal value."""
        result = compute_dcf(sample_inputs)
        expected_ev = result.pv_operating_cashflows + result.pv_terminal
        assert _approx(result.enterprise_value, expected_ev, Decimal("0.02"))

    def test_equity_bridge_arithmetic(self, sample_inputs):
        """Equity = EV + Cash - Debt - Minority - Preferred."""
        result = compute_dcf(sample_inputs)
        expected_equity = (
            result.enterprise_value
            + sample_inputs.cash_and_equivalents
            - sample_inputs.total_debt
            - sample_inputs.minority_interests
            - sample_inputs.preferred_stock
        )
        assert _approx(result.equity_value, expected_equity, Decimal("0.02"))

    def test_value_per_share_from_equity(self, sample_inputs):
        """Value per share = Equity Value / Shares Outstanding."""
        result = compute_dcf(sample_inputs)
        expected_vps = result.equity_value / sample_inputs.shares_outstanding
        assert _approx(
            result.value_per_share,
            expected_vps.quantize(Decimal("0.01")),
            Decimal("0.02"),
        )

    def test_implied_upside_calculation(self, sample_inputs):
        """Implied upside = (VPS - Price) / Price."""
        result = compute_dcf(sample_inputs)
        expected = (
            result.value_per_share - sample_inputs.current_price
        ) / sample_inputs.current_price
        assert _approx(result.implied_upside, expected, Decimal("0.001"))

    def test_five_year_forecast(self, sample_inputs):
        """Changing forecast_years to 5 should produce 5 projections."""
        sample_inputs.forecast_years = 5
        result = compute_dcf(sample_inputs)
        assert len(result.projections) == 5
        assert result.forecast_years == 5
