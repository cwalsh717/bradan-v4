"""DCF orchestration service: gathers data, checks eligibility, runs engine, manages saved runs."""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dcf import (
    CountryRiskPremium,
    DamodaranIndustry,
    DcfAuditLog,
    DcfValuation,
)
from app.models.shared import FredSeries
from app.models.stocks import PriceHistory, Stock
from app.services.dcf_engine import (
    DCFError,
    DCFInputs,
    compute_dcf,
    compute_sensitivity_matrix,
    apply_scenario,
)
from app.services.sector_mapping import SectorMappingResult, sector_mapping_service
from app.services.ttm import TTMService

logger = logging.getLogger(__name__)

# Twelve Data JSONB field names
_INCOME_FIELDS = {
    "revenue": "revenue",
    "ebit": "operating_income",
    "pretax_income": "income_before_tax",
    "tax_provision": "income_tax_expense",
    "interest_expense": "interest_expense",
}

_CASHFLOW_FIELDS = {
    "capex": "capital_expenditure",
    "depreciation": "depreciation_and_amortization",
}

_BALANCE_FIELDS = {
    "total_debt": "total_debt",
    "cash": "cash_and_cash_equivalents",
    "book_equity": "total_shareholders_equity",
    "current_assets": "current_assets",
    "current_liabilities": "current_liabilities",
    "shares_outstanding": "shares_outstanding",
    "minority_interest": "minority_interest",
}


class DCFEligibilityError(Exception):
    """Raised when a stock is not eligible for DCF valuation."""

    def __init__(self, reason: str, detail: str):
        self.reason = reason
        self.detail = detail
        super().__init__(detail)


def _safe_decimal(data: dict, key: str, default: Decimal = Decimal("0")) -> Decimal:
    """Extract a value from JSONB data and convert to Decimal safely."""
    val = data.get(key)
    if val is None:
        return default
    try:
        return Decimal(str(val))
    except Exception:
        return default


class DCFService:
    """Orchestrates DCF valuation: data gathering, eligibility, computation, persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # Data gathering
    # ------------------------------------------------------------------

    async def _get_stock(self, symbol: str) -> Stock:
        result = await self.session.execute(
            select(Stock).where(Stock.symbol == symbol.upper())
        )
        stock = result.scalar_one_or_none()
        if stock is None:
            raise DCFEligibilityError(
                "missing_stock", f"Stock '{symbol}' not found in database."
            )
        return stock

    async def _get_ttm(self, stock_id: int) -> dict:
        ttm_service = TTMService(self.session)
        ttm = await ttm_service.compute_ttm(stock_id)
        if ttm is None:
            raise DCFEligibilityError(
                "missing_financials",
                "No quarterly financial data available for TTM computation.",
            )
        return ttm

    async def _get_risk_free_rate(self) -> Decimal:
        result = await self.session.execute(
            select(FredSeries.value)
            .where(FredSeries.series_id == "DGS10")
            .order_by(FredSeries.observation_date.desc())
            .limit(1)
        )
        val = result.scalar_one_or_none()
        if val is None:
            raise DCFEligibilityError(
                "missing_rate", "No risk-free rate (DGS10) available in database."
            )
        # FRED returns percentage (e.g. 4.25 for 4.25%), convert to decimal
        return Decimal(str(val)) / Decimal("100")

    async def _get_current_price(self, stock_id: int) -> Decimal:
        """Get latest closing price from price_history."""
        result = await self.session.execute(
            select(PriceHistory.close)
            .where(PriceHistory.stock_id == stock_id)
            .order_by(PriceHistory.date.desc())
            .limit(1)
        )
        price = result.scalar_one_or_none()
        if price is None:
            raise DCFEligibilityError("missing_price", "No price data available.")
        return Decimal(str(price))

    async def _get_country_risk(
        self, country: str = "United States"
    ) -> tuple[Decimal, Decimal]:
        """Returns (equity_risk_premium, country_risk_premium)."""
        result = await self.session.execute(
            select(CountryRiskPremium).where(CountryRiskPremium.country == country)
        )
        row = result.scalar_one_or_none()
        if row is None:
            # Fallback to US defaults
            return Decimal("0.0460"), Decimal("0")
        return Decimal(str(row.equity_risk_premium)), Decimal(
            str(row.country_risk_premium)
        )

    # ------------------------------------------------------------------
    # Extract financials from TTM JSONB
    # ------------------------------------------------------------------

    def _extract_financials(self, ttm: dict) -> dict:
        """Extract DCF-relevant fields from TTM result."""
        income = ttm.get("income", {})
        cashflow = ttm.get("cash_flow", {})
        balance = ttm.get("balance_sheet", {})

        # Try multiple possible key names for each field
        revenue = _safe_decimal(income, "revenue")
        ebit = _safe_decimal(income, "operating_income")
        if ebit == 0:
            ebit = _safe_decimal(income, "ebit")
        pretax_income = _safe_decimal(income, "income_before_tax")
        if pretax_income == 0:
            pretax_income = _safe_decimal(income, "pretax_income")
        tax_provision = _safe_decimal(income, "income_tax_expense")
        if tax_provision == 0:
            tax_provision = _safe_decimal(income, "tax_provision")
        interest_expense = _safe_decimal(income, "interest_expense")

        capex = abs(_safe_decimal(cashflow, "capital_expenditure"))
        if capex == 0:
            capex = abs(_safe_decimal(cashflow, "capital_expenditures"))
        depreciation = _safe_decimal(cashflow, "depreciation_and_amortization")
        if depreciation == 0:
            depreciation = _safe_decimal(cashflow, "depreciation")

        total_debt = _safe_decimal(balance, "total_debt")
        if total_debt == 0:
            short = _safe_decimal(balance, "short_term_debt")
            long = _safe_decimal(balance, "long_term_debt")
            total_debt = short + long

        cash = _safe_decimal(balance, "cash_and_cash_equivalents")
        if cash == 0:
            cash = _safe_decimal(balance, "cash_and_short_term_investments")
        book_equity = _safe_decimal(balance, "total_shareholders_equity")
        if book_equity == 0:
            book_equity = _safe_decimal(balance, "stockholders_equity")

        current_assets = _safe_decimal(balance, "current_assets")
        current_liabilities = _safe_decimal(balance, "current_liabilities")
        shares = _safe_decimal(balance, "shares_outstanding")
        if shares == 0:
            shares = _safe_decimal(balance, "common_shares_outstanding")

        minority = _safe_decimal(balance, "minority_interest")

        # Working capital change: we use current balance sheet WC.
        # For TTM, working_capital_change is approximated from balance sheet.
        working_capital = current_assets - current_liabilities

        return {
            "revenue": revenue,
            "ebit": ebit,
            "pretax_income": pretax_income,
            "tax_provision": tax_provision,
            "interest_expense": interest_expense,
            "capex": capex,
            "depreciation": depreciation,
            "total_debt": total_debt,
            "cash": cash,
            "book_equity": book_equity,
            "shares_outstanding": shares,
            "minority_interest": minority,
            "working_capital": working_capital,
        }

    # ------------------------------------------------------------------
    # Build engine inputs
    # ------------------------------------------------------------------

    async def _build_inputs(
        self,
        stock: Stock,
        ttm: dict,
        sector: SectorMappingResult,
        overrides: Optional[dict] = None,
    ) -> DCFInputs:
        """Build DCFInputs from gathered data and optional user overrides."""
        fin = self._extract_financials(ttm)
        risk_free = await self._get_risk_free_rate()
        price = await self._get_current_price(stock.id)
        erp, crp = await self._get_country_risk()

        # Working capital change: approximate as 0 for base year (more precise
        # would require comparing two quarters' WC, but this is a v1 simplification)
        wc_change = Decimal("0")

        inputs = DCFInputs(
            revenue=fin["revenue"],
            ebit=fin["ebit"],
            tax_provision=fin["tax_provision"],
            pretax_income=fin["pretax_income"],
            capex=fin["capex"],
            depreciation=fin["depreciation"],
            working_capital_change=wc_change,
            interest_expense=fin["interest_expense"],
            total_debt=fin["total_debt"],
            cash_and_equivalents=fin["cash"],
            book_value_equity=fin["book_equity"],
            shares_outstanding=fin["shares_outstanding"],
            current_price=price,
            risk_free_rate=risk_free,
            equity_risk_premium=erp,
            country_risk_premium=crp,
            unlevered_beta=sector.unlevered_beta,
            sector_avg_debt_to_equity=sector.avg_debt_to_equity,
            sector_avg_roc=Decimal(str(sector.avg_roc)),
            minority_interests=fin["minority_interest"],
        )

        # Apply user overrides
        if overrides:
            if overrides.get("forecast_years") is not None:
                inputs.forecast_years = overrides["forecast_years"]
            if overrides.get("stable_growth_rate") is not None:
                inputs.stable_growth_rate = Decimal(
                    str(overrides["stable_growth_rate"])
                )
            if overrides.get("stable_roc") is not None:
                inputs.stable_roc = Decimal(str(overrides["stable_roc"]))
            if overrides.get("stable_beta") is not None:
                inputs.stable_beta = Decimal(str(overrides["stable_beta"]))
            if overrides.get("stable_debt_to_equity") is not None:
                inputs.stable_debt_to_equity = Decimal(
                    str(overrides["stable_debt_to_equity"])
                )
            if overrides.get("risk_free_rate") is not None:
                inputs.risk_free_rate = Decimal(str(overrides["risk_free_rate"]))
            if overrides.get("equity_risk_premium") is not None:
                inputs.equity_risk_premium = Decimal(
                    str(overrides["equity_risk_premium"])
                )
            if overrides.get("marginal_tax_rate") is not None:
                inputs.marginal_tax_rate = Decimal(str(overrides["marginal_tax_rate"]))

        return inputs

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    async def compute_default(self, symbol: str) -> dict:
        """Compute or retrieve the default (system) DCF valuation."""
        stock = await self._get_stock(symbol)
        sector = await sector_mapping_service.get_mapping(self.session, stock)

        if not sector.is_eligible:
            raise DCFEligibilityError(
                sector.rejection_reason or "ineligible",
                f"Stock not eligible for DCF: {sector.rejection_reason}",
            )

        ttm = await self._get_ttm(stock.id)
        inputs = await self._build_inputs(stock, ttm, sector)

        # Apply moderate scenario defaults
        inputs = apply_scenario(
            inputs,
            "moderate",
            sector_avg_reinvestment_rate=Decimal(str(sector.avg_roc)),
            sector_avg_roc=Decimal(str(sector.avg_roc)),
        )

        try:
            result = compute_dcf(inputs, scenario="moderate")
        except DCFError as e:
            raise DCFEligibilityError("negative_ebit", str(e))

        # Get fiscal date from TTM
        fiscal_date = ttm.get("period_end")

        # Persist default valuation
        await self._save_valuation(
            stock=stock,
            sector=sector,
            fiscal_date=fiscal_date,
            inputs=inputs,
            result=result,
            is_default=True,
            user_id=None,
            run_name=None,
        )

        return self._format_result(stock, result, fiscal_date, inputs)

    async def compute_custom(
        self,
        symbol: str,
        overrides: dict,
        scenario: Optional[str] = None,
    ) -> dict:
        """Compute an ephemeral custom DCF run (not saved)."""
        stock = await self._get_stock(symbol)
        sector = await sector_mapping_service.get_mapping(self.session, stock)

        if not sector.is_eligible:
            raise DCFEligibilityError(
                sector.rejection_reason or "ineligible",
                f"Stock not eligible for DCF: {sector.rejection_reason}",
            )

        ttm = await self._get_ttm(stock.id)
        inputs = await self._build_inputs(stock, ttm, sector, overrides)

        effective_scenario = scenario or overrides.get("scenario", "custom")
        if effective_scenario in ("conservative", "moderate", "optimistic"):
            inputs = apply_scenario(
                inputs,
                effective_scenario,
                sector_avg_reinvestment_rate=Decimal(str(sector.avg_roc)),
                sector_avg_roc=Decimal(str(sector.avg_roc)),
            )

        try:
            result = compute_dcf(inputs, scenario=effective_scenario)
        except DCFError as e:
            raise DCFEligibilityError("negative_ebit", str(e))

        fiscal_date = ttm.get("period_end")
        return self._format_result(stock, result, fiscal_date, inputs)

    async def save_run(
        self,
        symbol: str,
        user_id: str,
        run_name: str,
        overrides: dict,
    ) -> dict:
        """Compute and save a custom DCF run."""
        stock = await self._get_stock(symbol)
        sector = await sector_mapping_service.get_mapping(self.session, stock)

        if not sector.is_eligible:
            raise DCFEligibilityError(
                sector.rejection_reason or "ineligible",
                f"Stock not eligible for DCF: {sector.rejection_reason}",
            )

        ttm = await self._get_ttm(stock.id)
        inputs = await self._build_inputs(stock, ttm, sector, overrides)

        scenario = overrides.get("scenario", "custom")
        if scenario in ("conservative", "moderate", "optimistic"):
            inputs = apply_scenario(
                inputs,
                scenario,
                sector_avg_reinvestment_rate=Decimal(str(sector.avg_roc)),
                sector_avg_roc=Decimal(str(sector.avg_roc)),
            )

        try:
            result = compute_dcf(inputs, scenario=scenario)
        except DCFError as e:
            raise DCFEligibilityError("negative_ebit", str(e))

        fiscal_date = ttm.get("period_end")

        valuation = await self._save_valuation(
            stock=stock,
            sector=sector,
            fiscal_date=fiscal_date,
            inputs=inputs,
            result=result,
            is_default=False,
            user_id=user_id,
            run_name=run_name,
        )

        formatted = self._format_result(stock, result, fiscal_date, inputs)
        formatted["run_id"] = valuation.id
        formatted["run_name"] = run_name
        return formatted

    async def list_runs(self, symbol: str, user_id: str) -> list[dict]:
        """List saved DCF runs for a stock by a user."""
        stock = await self._get_stock(symbol)
        result = await self.session.execute(
            select(DcfValuation)
            .where(
                DcfValuation.stock_id == stock.id,
                DcfValuation.user_id == user_id,
                DcfValuation.is_saved.is_(True),
            )
            .order_by(DcfValuation.computed_at.desc())
        )
        runs = result.scalars().all()
        return [
            {
                "id": r.id,
                "run_name": r.run_name or "Untitled",
                "scenario": r.outputs.get("scenario", "custom"),
                "value_per_share": r.outputs.get("value_per_share", 0),
                "implied_upside": r.outputs.get("implied_upside", 0),
                "computed_at": str(r.computed_at),
                "source_fiscal_date": str(r.source_fiscal_date)
                if r.source_fiscal_date
                else None,
            }
            for r in runs
        ]

    async def get_run(self, symbol: str, run_id: int, user_id: str) -> dict:
        """Get a specific saved DCF run."""
        stock = await self._get_stock(symbol)
        result = await self.session.execute(
            select(DcfValuation).where(
                DcfValuation.id == run_id,
                DcfValuation.stock_id == stock.id,
                DcfValuation.user_id == user_id,
            )
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise DCFEligibilityError("not_found", f"DCF run {run_id} not found.")
        return {
            "run_id": run.id,
            "run_name": run.run_name,
            **run.outputs,
        }

    async def delete_run(self, symbol: str, run_id: int, user_id: str) -> bool:
        """Delete a saved DCF run."""
        stock = await self._get_stock(symbol)
        # Delete audit logs first
        await self.session.execute(
            delete(DcfAuditLog).where(DcfAuditLog.dcf_valuation_id == run_id)
        )
        result = await self.session.execute(
            delete(DcfValuation).where(
                DcfValuation.id == run_id,
                DcfValuation.stock_id == stock.id,
                DcfValuation.user_id == user_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def get_sensitivity(self, symbol: str) -> dict:
        """Compute sensitivity matrix for the default valuation."""
        stock = await self._get_stock(symbol)
        sector = await sector_mapping_service.get_mapping(self.session, stock)

        if not sector.is_eligible:
            raise DCFEligibilityError(
                sector.rejection_reason or "ineligible",
                f"Stock not eligible for DCF: {sector.rejection_reason}",
            )

        ttm = await self._get_ttm(stock.id)
        inputs = await self._build_inputs(stock, ttm, sector)
        inputs = apply_scenario(
            inputs,
            "moderate",
            sector_avg_reinvestment_rate=Decimal(str(sector.avg_roc)),
            sector_avg_roc=Decimal(str(sector.avg_roc)),
        )

        try:
            result = compute_dcf(inputs, scenario="moderate")
        except DCFError as e:
            raise DCFEligibilityError("negative_ebit", str(e))

        matrix = compute_sensitivity_matrix(inputs, result)

        return {
            "wacc_values": [float(v) for v in matrix["wacc_values"]],
            "growth_values": [float(v) for v in matrix["growth_values"]],
            "matrix": [[float(c) for c in row] for row in matrix["matrix"]],
            "base_wacc": float(matrix["base_wacc"]),
            "base_growth": float(matrix["base_growth"]),
            "base_value": float(result.value_per_share),
        }

    async def get_sector_context(self, symbol: str) -> dict:
        """Get Damodaran industry data for a stock."""
        stock = await self._get_stock(symbol)
        sector = await sector_mapping_service.get_mapping(self.session, stock)

        # Also load the full industry record for additional fields
        result = await self.session.execute(
            select(DamodaranIndustry).where(
                DamodaranIndustry.id == sector.damodaran_industry_id
            )
        )
        industry = result.scalar_one_or_none()

        return {
            "industry_name": sector.industry_name,
            "match_confidence": sector.confidence,
            "confidence_level": sector.confidence_level,
            "manually_verified": sector.manually_verified,
            "unlevered_beta": float(sector.unlevered_beta),
            "avg_effective_tax_rate": float(sector.avg_effective_tax_rate),
            "avg_debt_to_equity": float(sector.avg_debt_to_equity),
            "avg_operating_margin": float(sector.avg_operating_margin),
            "avg_roc": float(sector.avg_roc),
            "avg_reinvestment_rate": float(industry.avg_reinvestment_rate)
            if industry and industry.avg_reinvestment_rate
            else 0.0,
            "cost_of_capital": float(sector.cost_of_capital),
            "fundamental_growth_rate": float(industry.fundamental_growth_rate)
            if industry and industry.fundamental_growth_rate
            else 0.0,
            "num_firms": industry.num_firms if industry else 0,
        }

    async def get_summary(self, symbol: str) -> dict:
        """Generate plain-English valuation summary."""
        stock = await self._get_stock(symbol)
        sector = await sector_mapping_service.get_mapping(self.session, stock)

        if not sector.is_eligible:
            raise DCFEligibilityError(
                sector.rejection_reason or "ineligible",
                f"Stock not eligible for DCF: {sector.rejection_reason}",
            )

        ttm = await self._get_ttm(stock.id)
        inputs = await self._build_inputs(stock, ttm, sector)
        inputs = apply_scenario(
            inputs,
            "moderate",
            sector_avg_reinvestment_rate=Decimal(str(sector.avg_roc)),
            sector_avg_roc=Decimal(str(sector.avg_roc)),
        )

        try:
            result = compute_dcf(inputs, scenario="moderate")
        except DCFError as e:
            raise DCFEligibilityError("negative_ebit", str(e))

        # Build verdict
        upside = float(result.implied_upside)
        if upside > 0.15:
            verdict = "undervalued"
        elif upside < -0.15:
            verdict = "overvalued"
        else:
            verdict = "fairly valued"

        vps = float(result.value_per_share)
        price = float(inputs.current_price)
        upside_pct = round(upside * 100, 1)

        summary_text = (
            f"Based on a discounted cash flow analysis, {stock.name or stock.symbol} "
            f"appears to be {verdict} with an estimated intrinsic value of "
            f"${vps:.2f} per share compared to its current price of ${price:.2f}. "
            f"This implies a {'upside' if upside > 0 else 'downside'} of {abs(upside_pct)}%."
        )

        key_assumptions = [
            f"Revenue growth of {float(result.expected_growth) * 100:.1f}% based on reinvestment rate and return on capital",
            f"WACC of {float(result.wacc) * 100:.1f}% used as the discount rate",
            f"Terminal growth rate of {float(result.terminal_growth) * 100:.1f}% (capped at risk-free rate)",
            f"Beta transitions from {float(result.levered_beta):.2f} to {float(result.projections[-1].beta):.2f} over {result.forecast_years} years",
        ]

        risk_factors = []
        tv_pct = (
            float(result.pv_terminal) / float(result.enterprise_value) * 100
            if float(result.enterprise_value) > 0
            else 0
        )
        if tv_pct > 75:
            risk_factors.append(
                f"Terminal value represents {tv_pct:.0f}% of total value — highly sensitive to long-term assumptions"
            )
        if float(result.reinvestment_rate) > 1.0:
            risk_factors.append(
                "Company is reinvesting more than it earns — growth funded by external capital"
            )
        if float(result.return_on_capital) < float(result.wacc):
            risk_factors.append(
                "Return on capital is below cost of capital — company may be destroying value"
            )
        if sector.confidence_level == "medium":
            risk_factors.append(
                f"Industry mapping confidence is {sector.confidence:.0%} — sector averages may not be representative"
            )
        if not risk_factors:
            risk_factors.append("Standard DCF model assumptions apply")

        return {
            "symbol": stock.symbol,
            "company_name": stock.name or stock.symbol,
            "value_per_share": vps,
            "current_price": price,
            "implied_upside": upside,
            "verdict": verdict,
            "summary_text": summary_text,
            "key_assumptions": key_assumptions,
            "risk_factors": risk_factors,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _save_valuation(
        self,
        stock: Stock,
        sector: SectorMappingResult,
        fiscal_date: Optional[str],
        inputs: DCFInputs,
        result,
        is_default: bool,
        user_id: Optional[str],
        run_name: Optional[str],
    ) -> DcfValuation:
        """Persist a DCF valuation to the database."""
        if is_default:
            await self.session.execute(
                delete(DcfValuation).where(
                    DcfValuation.stock_id == stock.id,
                    DcfValuation.is_default.is_(True),
                )
            )

        outputs = self._format_result(stock, result, fiscal_date, inputs)

        valuation = DcfValuation(
            stock_id=stock.id,
            damodaran_industry_id=sector.damodaran_industry_id,
            source_fiscal_date=date.fromisoformat(fiscal_date) if fiscal_date else None,
            model_type="fcff",
            is_default=is_default,
            user_id=user_id,
            run_name=run_name,
            is_saved=not is_default,
            inputs=self._serialize_inputs(inputs),
            outputs=outputs,
        )
        self.session.add(valuation)
        await self.session.flush()

        # Audit log
        event = "computed" if is_default else "input_override"
        audit = DcfAuditLog(
            dcf_valuation_id=valuation.id,
            event=event,
            details={"scenario": result.scenario, "user_id": user_id},
        )
        self.session.add(audit)
        await self.session.commit()

        return valuation

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _format_result(
        self,
        stock: Stock,
        result,
        fiscal_date: Optional[str],
        inputs: Optional[DCFInputs] = None,
    ) -> dict:
        """Convert DCFResult to API-friendly dict."""
        upside = float(result.implied_upside)
        if upside > 0.15:
            verdict = "undervalued"
        elif upside < -0.15:
            verdict = "overvalued"
        else:
            verdict = "fairly valued"

        now = datetime.now(timezone.utc)

        current_price = float(inputs.current_price) if inputs else 0
        market_cap = (
            float(inputs.shares_outstanding * inputs.current_price) if inputs else 0
        )

        return {
            "symbol": stock.symbol,
            "company_name": stock.name or stock.symbol,
            "value_per_share": float(result.value_per_share),
            "current_price": current_price,
            "implied_upside": float(result.implied_upside),
            "verdict": verdict,
            "computed_inputs": {
                "effective_tax_rate": float(result.effective_tax_rate),
                "computed_tax_rate": float(result.computed_tax_rate),
                "ebit_after_tax": float(result.ebit_after_tax),
                "reinvestment": float(result.reinvestment),
                "reinvestment_rate": float(result.reinvestment_rate),
                "return_on_capital": float(result.return_on_capital),
                "expected_growth": float(result.expected_growth),
                "levered_beta": float(result.levered_beta),
                "cost_of_equity": float(result.cost_of_equity),
                "synthetic_rating": result.synthetic_rating,
                "default_spread": float(result.default_spread),
                "cost_of_debt_pretax": float(result.cost_of_debt_pretax),
                "cost_of_debt_aftertax": float(result.cost_of_debt_aftertax),
                "wacc": float(result.wacc),
                "debt_ratio": float(result.debt_ratio),
                "market_cap": market_cap,
            },
            "projections": [
                {
                    "year": p.year,
                    "growth_rate": float(p.growth_rate),
                    "revenue": float(p.revenue),
                    "ebit": float(p.ebit),
                    "ebit_after_tax": float(p.ebit_after_tax),
                    "reinvestment_rate": float(p.reinvestment_rate),
                    "reinvestment": float(p.reinvestment),
                    "fcff": float(p.fcff),
                    "beta": float(p.beta),
                    "cost_of_equity": float(p.cost_of_equity),
                    "debt_ratio": float(p.debt_ratio),
                    "wacc": float(p.wacc),
                    "roc": float(p.roc),
                    "pv_factor": float(p.pv_factor),
                    "pv_fcff": float(p.pv_fcff),
                }
                for p in result.projections
            ],
            "terminal": {
                "terminal_growth": float(result.terminal_growth),
                "terminal_roc": float(result.terminal_roc),
                "terminal_wacc": float(result.terminal_wacc),
                "terminal_reinvestment_rate": float(result.terminal_reinvestment_rate),
                "terminal_fcff": float(result.terminal_fcff),
                "terminal_value": float(result.terminal_value),
                "pv_terminal": float(result.pv_terminal),
            },
            "equity_bridge": result.equity_bridge
            if isinstance(result.equity_bridge, dict)
            else {},
            "scenario": result.scenario,
            "forecast_years": result.forecast_years,
            "source_fiscal_date": fiscal_date or str(date.today()),
            "computed_at": now.isoformat(),
            "pv_operating_cashflows": float(result.pv_operating_cashflows),
            "terminal_value_pct": float(
                result.pv_terminal / result.enterprise_value * 100
            )
            if float(result.enterprise_value) > 0
            else 0,
        }

    @staticmethod
    def _serialize_inputs(inputs: DCFInputs) -> dict:
        """Serialize DCFInputs to JSON-safe dict for JSONB storage."""
        return {
            "revenue": float(inputs.revenue),
            "ebit": float(inputs.ebit),
            "tax_provision": float(inputs.tax_provision),
            "pretax_income": float(inputs.pretax_income),
            "capex": float(inputs.capex),
            "depreciation": float(inputs.depreciation),
            "working_capital_change": float(inputs.working_capital_change),
            "interest_expense": float(inputs.interest_expense),
            "total_debt": float(inputs.total_debt),
            "cash_and_equivalents": float(inputs.cash_and_equivalents),
            "book_value_equity": float(inputs.book_value_equity),
            "shares_outstanding": float(inputs.shares_outstanding),
            "current_price": float(inputs.current_price),
            "risk_free_rate": float(inputs.risk_free_rate),
            "equity_risk_premium": float(inputs.equity_risk_premium),
            "country_risk_premium": float(inputs.country_risk_premium),
            "unlevered_beta": float(inputs.unlevered_beta),
            "sector_avg_debt_to_equity": float(inputs.sector_avg_debt_to_equity),
            "sector_avg_roc": float(inputs.sector_avg_roc),
            "forecast_years": inputs.forecast_years,
            "stable_growth_rate": float(inputs.stable_growth_rate)
            if inputs.stable_growth_rate
            else None,
            "stable_roc": float(inputs.stable_roc) if inputs.stable_roc else None,
            "stable_beta": float(inputs.stable_beta),
            "marginal_tax_rate": float(inputs.marginal_tax_rate),
        }
