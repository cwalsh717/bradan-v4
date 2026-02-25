"""Phase 4 test suite: Damodaran seed, sector mapping, DCF service, DCF endpoints."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.damodaran_seed import (
    COUNTRY_RISK_PREMIUMS,
    DAMODARAN_INDUSTRIES,
    DEFAULT_SPREADS,
    seed_damodaran_data,
)
from app.services.sector_mapping import (
    SectorMappingService,
    _normalise,
    _score_pair,
)


# ======================================================================
# Damodaran seed tests
# ======================================================================


async def test_seed_inserts_all_default_spreads():
    """When no existing spreads, all 15 are inserted."""
    mock_session = AsyncMock()

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    counts = await seed_damodaran_data(mock_session)

    assert counts["default_spreads"] == 15
    assert counts["country_risk_premiums"] == 13
    assert counts["damodaran_industries"] == 25
    mock_session.commit.assert_awaited_once()


async def test_seed_updates_existing_spreads():
    """Existing spreads are updated, not duplicated."""
    mock_session = AsyncMock()

    # Simulate 3 existing spreads
    existing = []
    for rating, _ in DEFAULT_SPREADS[:3]:
        m = MagicMock()
        m.rating = rating
        existing.append(m)

    def make_mock_result(existing_list):
        r = MagicMock()
        s = MagicMock()
        s.all.return_value = existing_list
        r.scalars.return_value = s
        return r

    results = [
        make_mock_result(existing),  # default_spreads
        make_mock_result([]),  # country_risk_premiums
        make_mock_result([]),  # damodaran_industries
    ]
    mock_session.execute = AsyncMock(side_effect=results)

    counts = await seed_damodaran_data(mock_session)

    assert counts["default_spreads"] == 15
    # 15 total - 3 existing updates = 12 new inserts, but all 15 counted
    assert mock_session.add.call_count == 12 + 13 + 25  # inserts for new items


async def test_seed_is_idempotent():
    """When all data exists, count stays the same and no new adds."""
    mock_session = AsyncMock()

    def make_all_existing(data_list, key_fn):
        existing = []
        for item in data_list:
            m = MagicMock()
            key_fn(m, item)
            existing.append(m)
        return existing

    spreads = make_all_existing(
        DEFAULT_SPREADS, lambda m, item: setattr(m, "rating", item[0])
    )
    countries = make_all_existing(
        COUNTRY_RISK_PREMIUMS, lambda m, item: setattr(m, "country", item[0])
    )
    industries = make_all_existing(
        DAMODARAN_INDUSTRIES, lambda m, item: setattr(m, "industry_name", item[0])
    )

    def make_mock_result(existing_list):
        r = MagicMock()
        s = MagicMock()
        s.all.return_value = existing_list
        r.scalars.return_value = s
        return r

    results = [
        make_mock_result(spreads),
        make_mock_result(countries),
        make_mock_result(industries),
    ]
    mock_session.execute = AsyncMock(side_effect=results)

    counts = await seed_damodaran_data(mock_session)

    assert counts["default_spreads"] == 15
    assert counts["country_risk_premiums"] == 13
    assert counts["damodaran_industries"] == 25
    # No new inserts when everything already exists
    assert mock_session.add.call_count == 0


async def test_seed_data_values_are_decimals():
    """All seed data values should be proper Decimal types."""
    for rating, spread in DEFAULT_SPREADS:
        assert isinstance(spread, Decimal), f"Spread for {rating} is not Decimal"
        assert spread > 0

    for country, _, ds, erp, crp in COUNTRY_RISK_PREMIUMS:
        assert isinstance(erp, Decimal), f"ERP for {country} is not Decimal"
        assert erp > 0

    for item in DAMODARAN_INDUSTRIES:
        name = item[0]
        beta = item[2]
        assert isinstance(beta, Decimal), f"Beta for {name} is not Decimal"


# ======================================================================
# Sector mapping helper tests
# ======================================================================


def test_normalise_strips_parenthetical():
    assert _normalise("Software (System & Application)") == "software"


def test_normalise_lowercase_strip():
    assert _normalise("  BANKING  ") == "banking"


def test_score_pair_exact_match():
    assert _score_pair("software", "software") == 1.0


def test_score_pair_substring():
    score = _score_pair("software", "software system")
    assert score > 0.80


def test_score_pair_different():
    score = _score_pair("banking", "aerospace")
    assert score < 0.5


# ======================================================================
# Sector mapping service tests
# ======================================================================


def test_is_financial_company_sector():
    svc = SectorMappingService()
    assert svc.is_financial_company("Financial Services", "Banking") is True
    assert svc.is_financial_company("Financials", "Insurance") is True


def test_is_financial_company_industry():
    svc = SectorMappingService()
    assert svc.is_financial_company("", "Regional Banks") is True
    assert svc.is_financial_company("", "REITS") is True


def test_is_not_financial_company():
    svc = SectorMappingService()
    assert svc.is_financial_company("Technology", "Software") is False
    assert svc.is_financial_company("Healthcare", "Pharmaceuticals") is False


def test_is_financial_company_substring_match():
    svc = SectorMappingService()
    assert svc.is_financial_company("", "Diversified Banks") is True
    assert svc.is_financial_company("", "Life Insurance Company") is True


async def test_sector_mapping_fuzzy_match():
    """Fuzzy match should find a reasonable match for known industries."""
    svc = SectorMappingService()
    mock_session = AsyncMock()

    # Create mock Damodaran industries
    industries = []
    for i, item in enumerate(DAMODARAN_INDUSTRIES):
        m = MagicMock()
        m.id = i + 1
        m.industry_name = item[0]
        industries.append(m)

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = industries
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    # "Technology" / "Software" should match "Software (System & Application)"
    dam_id, confidence = await svc.fuzzy_match(mock_session, "Technology", "Software")
    matched_name = next(m.industry_name for m in industries if m.id == dam_id)
    assert "Software" in matched_name
    assert confidence > 0.5


async def test_sector_mapping_exact_industry_match():
    """Exact industry name should yield very high confidence."""
    svc = SectorMappingService()
    mock_session = AsyncMock()

    industries = []
    for i, item in enumerate(DAMODARAN_INDUSTRIES):
        m = MagicMock()
        m.id = i + 1
        m.industry_name = item[0]
        industries.append(m)

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = industries
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    dam_id, confidence = await svc.fuzzy_match(mock_session, "", "Semiconductor")
    matched_name = next(m.industry_name for m in industries if m.id == dam_id)
    assert matched_name == "Semiconductor"
    assert confidence >= 0.95


# ======================================================================
# DCF service integration tests (mocked DB)
# ======================================================================


def _make_stock(
    symbol="AAPL", name="Apple Inc", sector="Technology", industry="Software"
):
    stock = MagicMock()
    stock.id = 1
    stock.symbol = symbol
    stock.name = name
    stock.sector = sector
    stock.industry = industry
    return stock


def _make_ttm():
    """Create a mock TTM result with all needed financial data."""
    return {
        "income": {
            "revenue": 400000,
            "operating_income": 120000,
            "income_before_tax": 115000,
            "income_tax_expense": 20000,
            "interest_expense": 5000,
        },
        "cash_flow": {
            "capital_expenditure": -12000,
            "depreciation_and_amortization": 8000,
        },
        "balance_sheet": {
            "total_debt": 110000,
            "cash_and_cash_equivalents": 50000,
            "total_shareholders_equity": 80000,
            "current_assets": 140000,
            "current_liabilities": 120000,
            "shares_outstanding": 15000,
            "minority_interest": 0,
        },
        "period_end": "2024-06-30",
        "quarters_used": 4,
    }


def _make_sector_result():
    from app.services.sector_mapping import SectorMappingResult

    return SectorMappingResult(
        damodaran_industry_id=1,
        industry_name="Software (System & Application)",
        confidence=0.92,
        confidence_level="high",
        manually_verified=False,
        is_eligible=True,
        rejection_reason=None,
        unlevered_beta=Decimal("1.22"),
        avg_effective_tax_rate=Decimal("0.06"),
        avg_debt_to_equity=Decimal("0.06"),
        avg_operating_margin=Decimal("0.21"),
        avg_roc=Decimal("0.30"),
        cost_of_capital=Decimal("0.10"),
    )


@patch("app.services.dcf_service.sector_mapping_service")
async def test_dcf_service_compute_default(mock_sms):
    """compute_default should run full DCF pipeline and return a result dict."""
    from app.services.dcf_service import DCFService

    mock_session = AsyncMock()
    service = DCFService(mock_session)

    stock = _make_stock()
    ttm = _make_ttm()
    sector = _make_sector_result()

    # Mock _get_stock
    mock_stock_result = MagicMock()
    mock_stock_result.scalar_one_or_none.return_value = stock

    # Mock risk-free rate
    mock_rf_result = MagicMock()
    mock_rf_result.scalar_one_or_none.return_value = Decimal("4.25")

    # Mock current price
    mock_price_result = MagicMock()
    mock_price_result.scalar_one_or_none.return_value = Decimal("175.00")

    # Mock country risk
    mock_country = MagicMock()
    mock_country.equity_risk_premium = Decimal("0.0460")
    mock_country.country_risk_premium = Decimal("0.0000")
    mock_country_result = MagicMock()
    mock_country_result.scalar_one_or_none.return_value = mock_country

    # Mock TTM
    with patch.object(service, "_get_ttm", new_callable=AsyncMock, return_value=ttm):
        mock_sms.get_mapping = AsyncMock(return_value=sector)

        # Set up session.execute to return different results based on call order
        mock_session.execute = AsyncMock(
            side_effect=[
                mock_stock_result,  # _get_stock
                mock_rf_result,  # _get_risk_free_rate
                mock_price_result,  # _get_current_price
                mock_country_result,  # _get_country_risk
                MagicMock(),  # _save_valuation delete
                MagicMock(),  # _save_valuation flush
            ]
        )
        mock_session.flush = AsyncMock()

        # Mock the save path to avoid complex DB ops
        with patch.object(
            service, "_save_valuation", new_callable=AsyncMock
        ) as mock_save:
            mock_valuation = MagicMock()
            mock_valuation.id = 1
            mock_save.return_value = mock_valuation

            result = await service.compute_default("AAPL")

    assert result["symbol"] == "AAPL"
    assert result["value_per_share"] > 0
    assert "projections" in result
    assert len(result["projections"]) == 10
    assert "terminal" in result
    assert "equity_bridge" in result
    assert result["scenario"] == "moderate"


@patch("app.services.dcf_service.sector_mapping_service")
async def test_dcf_service_ineligible_financial(mock_sms):
    """Financial companies should be rejected."""
    from app.services.dcf_service import DCFService, DCFEligibilityError

    mock_session = AsyncMock()
    service = DCFService(mock_session)

    stock = _make_stock(sector="Financial Services", industry="Banks")
    sector = _make_sector_result()
    sector.is_eligible = False
    sector.rejection_reason = "financial_firm"

    mock_stock_result = MagicMock()
    mock_stock_result.scalar_one_or_none.return_value = stock
    mock_session.execute = AsyncMock(return_value=mock_stock_result)
    mock_sms.get_mapping = AsyncMock(return_value=sector)

    with pytest.raises(DCFEligibilityError) as exc_info:
        await service.compute_default("JPM")

    assert exc_info.value.reason == "financial_firm"


@patch("app.services.dcf_service.sector_mapping_service")
async def test_dcf_service_missing_stock(mock_sms):
    """Missing stock should raise eligibility error."""
    from app.services.dcf_service import DCFService, DCFEligibilityError

    mock_session = AsyncMock()
    service = DCFService(mock_session)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(DCFEligibilityError) as exc_info:
        await service.compute_default("FAKE")

    assert exc_info.value.reason == "missing_stock"


# ======================================================================
# DCF endpoint tests
# ======================================================================


@patch("app.services.dcf_service.sector_mapping_service")
async def test_dcf_constraints_endpoint(mock_sms):
    """GET /api/dcf/constraints should return slider rules."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/dcf/constraints")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "forecast_years" in data
    assert data["forecast_years"]["min"] == 5
    assert data["forecast_years"]["max"] == 10
    assert "stable_growth_rate" in data
    assert "stable_beta" in data


@patch("app.services.dcf_service.sector_mapping_service")
async def test_dcf_default_missing_stock(mock_sms):
    """GET /api/dcf/{symbol}/default should return 422 for missing stock."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services.dcf_service import DCFEligibilityError

    with patch("app.routers.dcf.DCFService") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.compute_default = AsyncMock(
            side_effect=DCFEligibilityError("missing_stock", "Stock 'FAKE' not found")
        )
        mock_cls.return_value = mock_instance

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/dcf/FAKE/default")

    assert resp.status_code == 422
    body = resp.json()
    assert body["detail"]["reason"] == "missing_stock"


@patch("app.services.dcf_service.sector_mapping_service")
async def test_dcf_save_requires_auth(mock_sms):
    """POST /api/dcf/{symbol}/save should require authentication."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/dcf/AAPL/save",
            json={"run_name": "test", "overrides": {}},
        )

    assert resp.status_code == 401


@patch("app.services.dcf_service.sector_mapping_service")
async def test_dcf_runs_requires_auth(mock_sms):
    """GET /api/dcf/{symbol}/runs should require authentication."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/dcf/AAPL/runs")

    assert resp.status_code == 401


@patch("app.services.dcf_service.sector_mapping_service")
async def test_dcf_delete_requires_auth(mock_sms):
    """DELETE /api/dcf/{symbol}/runs/1 should require authentication."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete("/api/dcf/AAPL/runs/1")

    assert resp.status_code == 401


@patch("app.services.dcf_service.sector_mapping_service")
async def test_dcf_summary_missing_stock(mock_sms):
    """GET /api/dcf/{symbol}/summary should return 422 for ineligible stock."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services.dcf_service import DCFEligibilityError

    with patch("app.routers.dcf.DCFService") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.get_summary = AsyncMock(
            side_effect=DCFEligibilityError("missing_stock", "Stock not found")
        )
        mock_cls.return_value = mock_instance

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/dcf/FAKE/summary")

    assert resp.status_code == 422


@patch("app.services.dcf_service.sector_mapping_service")
async def test_dcf_sensitivity_missing_stock(mock_sms):
    """GET /api/dcf/{symbol}/sensitivity should return 422 for ineligible stock."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services.dcf_service import DCFEligibilityError

    with patch("app.routers.dcf.DCFService") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.get_sensitivity = AsyncMock(
            side_effect=DCFEligibilityError("missing_stock", "Stock not found")
        )
        mock_cls.return_value = mock_instance

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/dcf/FAKE/sensitivity")

    assert resp.status_code == 422


@patch("app.services.dcf_service.sector_mapping_service")
async def test_dcf_sector_context_missing_stock(mock_sms):
    """GET /api/dcf/{symbol}/sector-context should return 404 for missing stock."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services.dcf_service import DCFEligibilityError

    with patch("app.routers.dcf.DCFService") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.get_sector_context = AsyncMock(
            side_effect=DCFEligibilityError("missing_stock", "Stock not found")
        )
        mock_cls.return_value = mock_instance

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/dcf/FAKE/sector-context")

    assert resp.status_code == 404


# ======================================================================
# DCF service helper tests
# ======================================================================


def test_safe_decimal_normal():
    from app.services.dcf_service import _safe_decimal

    assert _safe_decimal({"key": "123.45"}, "key") == Decimal("123.45")


def test_safe_decimal_none():
    from app.services.dcf_service import _safe_decimal

    assert _safe_decimal({"key": None}, "key") == Decimal("0")


def test_safe_decimal_missing_key():
    from app.services.dcf_service import _safe_decimal

    assert _safe_decimal({}, "key") == Decimal("0")


def test_safe_decimal_integer():
    from app.services.dcf_service import _safe_decimal

    assert _safe_decimal({"key": 42}, "key") == Decimal("42")


def test_extract_financials():
    """_extract_financials should correctly map TTM JSONB keys to DCF fields."""
    from app.services.dcf_service import DCFService

    mock_session = AsyncMock()
    service = DCFService(mock_session)

    ttm = _make_ttm()
    fin = service._extract_financials(ttm)

    assert fin["revenue"] == Decimal("400000")
    assert fin["ebit"] == Decimal("120000")
    assert fin["total_debt"] == Decimal("110000")
    assert fin["cash"] == Decimal("50000")
    assert fin["shares_outstanding"] == Decimal("15000")
    assert fin["capex"] == Decimal("12000")  # abs(-12000)


def test_extract_financials_alternative_keys():
    """Should handle alternative key names in JSONB data."""
    from app.services.dcf_service import DCFService

    mock_session = AsyncMock()
    service = DCFService(mock_session)

    ttm = {
        "income": {
            "revenue": 100000,
            "ebit": 20000,  # alternative to operating_income
            "pretax_income": 18000,
            "tax_provision": 3000,
            "interest_expense": 2000,
        },
        "cash_flow": {
            "capital_expenditures": -5000,  # alternative key
            "depreciation": 3000,  # alternative key
        },
        "balance_sheet": {
            "short_term_debt": 5000,
            "long_term_debt": 15000,
            "cash_and_short_term_investments": 10000,
            "stockholders_equity": 40000,
            "current_assets": 50000,
            "current_liabilities": 30000,
            "common_shares_outstanding": 5000,
        },
    }

    fin = service._extract_financials(ttm)
    assert fin["ebit"] == Decimal("20000")
    assert fin["total_debt"] == Decimal("20000")  # 5000 + 15000
    assert fin["cash"] == Decimal("10000")
    assert fin["shares_outstanding"] == Decimal("5000")
    assert fin["capex"] == Decimal("5000")
