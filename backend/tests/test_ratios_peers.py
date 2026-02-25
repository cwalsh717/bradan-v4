"""Tests for GET /api/stocks/{symbol}/ratios and GET /api/stocks/{symbol}/peers.

All external APIs are mocked. Follows existing test patterns from
test_endpoints_phase2.py: mock get_session via dependency_overrides,
exercise endpoints through httpx.ASGITransport + AsyncClient.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import get_session
from app.services.ratios import compute_ratios


# ---------------------------------------------------------------------------
# Helpers (reuse patterns from test_endpoints_phase2)
# ---------------------------------------------------------------------------


def _make_mock_stock(**overrides):
    """Return a MagicMock that looks like a Stock ORM instance."""
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    defaults = {
        "id": 1,
        "symbol": "AAPL",
        "name": "Apple Inc",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "currency": "USD",
        "last_updated": now,
    }
    defaults.update(overrides)
    stock = MagicMock()
    for k, v in defaults.items():
        setattr(stock, k, v)
    return stock


def _scalar_one_or_none_result(value):
    """Build a mock result whose .scalar_one_or_none() returns *value*."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalars_all_result(rows):
    """Build a mock result whose .scalars().all() returns *rows*."""
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = rows
    result.scalars.return_value = scalars
    return result


def _all_result(rows):
    """Build a mock result whose .all() returns *rows*."""
    result = MagicMock()
    result.all.return_value = rows
    return result


def _make_session_with_side_effects(side_effects):
    """Build an AsyncMock session whose execute returns values in order."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=side_effects)
    return mock_db


def _session_override(mock_db):
    """Return an async generator factory suitable for dependency_overrides."""

    async def _override():
        yield mock_db

    return _override


def _make_ttm_data():
    """Create a realistic TTM dataset for ratio computation."""
    return {
        "income": {
            "revenue": 400000,
            "cost_of_revenue": 220000,
            "gross_profit": 180000,
            "operating_income": 120000,
            "net_income": 95000,
            "interest_expense": 5000,
            "income_before_tax": 115000,
            "income_tax_expense": 20000,
        },
        "balance_sheet": {
            "total_assets": 350000,
            "total_shareholders_equity": 80000,
            "total_debt": 110000,
            "current_assets": 140000,
            "current_liabilities": 120000,
            "inventory": 10000,
            "cash_and_cash_equivalents": 50000,
            "shares_outstanding": 15000,
        },
        "cash_flow": {
            "depreciation_and_amortization": 8000,
            "capital_expenditure": -12000,
        },
        "quarters_used": 4,
        "period_start": "2024-03-31",
        "period_end": "2024-12-31",
    }


# ======================================================================
# Unit tests for compute_ratios
# ======================================================================


def test_compute_ratios_full_data():
    """All ratios should be computed from complete TTM data with price."""
    ttm = _make_ttm_data()
    ratios = compute_ratios(ttm, current_price=200.0, shares_outstanding=15000)

    # Profitability
    assert ratios["gross_margin"] is not None
    assert abs(ratios["gross_margin"] - 180000 / 400000) < 0.001
    assert ratios["operating_margin"] is not None
    assert abs(ratios["operating_margin"] - 120000 / 400000) < 0.001
    assert ratios["net_margin"] is not None
    assert abs(ratios["net_margin"] - 95000 / 400000) < 0.001
    assert ratios["roe"] is not None
    assert abs(ratios["roe"] - 95000 / 80000) < 0.001
    assert ratios["roa"] is not None
    assert abs(ratios["roa"] - 95000 / 350000) < 0.001
    assert ratios["roic"] is not None

    # Liquidity
    assert ratios["current_ratio"] is not None
    assert abs(ratios["current_ratio"] - 140000 / 120000) < 0.001
    assert ratios["quick_ratio"] is not None
    assert abs(ratios["quick_ratio"] - (140000 - 10000) / 120000) < 0.001

    # Leverage
    assert ratios["debt_to_equity"] is not None
    assert abs(ratios["debt_to_equity"] - 110000 / 80000) < 0.001
    assert ratios["debt_to_assets"] is not None
    assert ratios["interest_coverage"] is not None
    assert abs(ratios["interest_coverage"] - 120000 / 5000) < 0.001

    # Valuation (should be present since we provided price + shares)
    assert ratios["pe_ratio"] is not None
    assert ratios["pb_ratio"] is not None
    assert ratios["ps_ratio"] is not None
    assert ratios["ev_to_ebitda"] is not None

    # Efficiency
    assert ratios["asset_turnover"] is not None
    assert ratios["inventory_turnover"] is not None
    assert abs(ratios["inventory_turnover"] - 220000 / 10000) < 0.001


def test_compute_ratios_missing_inputs_returns_null():
    """Ratios with missing inputs should be None, not errors."""
    # Minimal TTM with just income statement
    ttm = {
        "income": {
            "revenue": 100000,
            "net_income": 10000,
        },
        "balance_sheet": {},
        "cash_flow": {},
    }
    ratios = compute_ratios(ttm)

    # Net margin should work (revenue + net_income available)
    assert ratios["net_margin"] is not None
    assert abs(ratios["net_margin"] - 0.1) < 0.001

    # These should be None due to missing inputs
    assert ratios["roe"] is None  # no equity
    assert ratios["roa"] is None  # no total_assets
    assert ratios["current_ratio"] is None  # no current_assets/liabilities
    assert ratios["debt_to_equity"] is None  # no debt or equity
    assert ratios["pe_ratio"] is None  # no price
    assert ratios["inventory_turnover"] is None  # no inventory or COGS


def test_compute_ratios_no_price_valuation_null():
    """Valuation ratios should be None when no price is provided."""
    ttm = _make_ttm_data()
    ratios = compute_ratios(ttm, current_price=None)

    assert ratios["pe_ratio"] is None
    assert ratios["pb_ratio"] is None
    assert ratios["ps_ratio"] is None
    assert ratios["ev_to_ebitda"] is None

    # Non-valuation ratios should still work
    assert ratios["gross_margin"] is not None
    assert ratios["current_ratio"] is not None


def test_compute_ratios_zero_denominator():
    """Division by zero should return None, not raise."""
    ttm = {
        "income": {
            "revenue": 0,
            "operating_income": 0,
            "net_income": 0,
        },
        "balance_sheet": {
            "total_assets": 0,
            "total_shareholders_equity": 0,
            "current_liabilities": 0,
        },
        "cash_flow": {},
    }
    ratios = compute_ratios(ttm)

    assert ratios["gross_margin"] is None
    assert ratios["operating_margin"] is None
    assert ratios["roe"] is None
    assert ratios["roa"] is None
    assert ratios["current_ratio"] is None


def test_compute_ratios_derives_gross_profit_from_cogs():
    """Gross margin should be computed from revenue - COGS if gross_profit missing."""
    ttm = {
        "income": {
            "revenue": 100000,
            "cost_of_revenue": 60000,
            # No "gross_profit" key
        },
        "balance_sheet": {},
        "cash_flow": {},
    }
    ratios = compute_ratios(ttm)
    assert ratios["gross_margin"] is not None
    assert abs(ratios["gross_margin"] - 0.4) < 0.001


def test_compute_ratios_alternative_balance_sheet_keys():
    """Should handle alternative key names in balance sheet data."""
    ttm = {
        "income": {"revenue": 100000, "net_income": 10000},
        "balance_sheet": {
            "stockholders_equity": 50000,  # alternative to total_shareholders_equity
            "short_term_debt": 5000,
            "long_term_debt": 15000,
            "total_assets": 100000,
        },
        "cash_flow": {},
    }
    ratios = compute_ratios(ttm)
    assert ratios["roe"] is not None
    assert abs(ratios["roe"] - 10000 / 50000) < 0.001
    assert ratios["debt_to_equity"] is not None
    assert abs(ratios["debt_to_equity"] - 20000 / 50000) < 0.001


# ======================================================================
# Endpoint tests: GET /api/stocks/{symbol}/ratios
# ======================================================================


async def test_ratios_endpoint_returns_envelope():
    """Ratios endpoint returns correct response envelope with computed ratios."""
    stock = _make_mock_stock()
    ttm_data = _make_ttm_data()

    # Call 1: _get_stock_or_404 -> stock
    # TTMService.compute_ttm is patched separately
    # Call 2: select PriceHistory.close (current price) -> 200.0
    # Call 3: _next_refresh_for_stock earnings -> None
    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stock),  # stock lookup
            _scalar_one_or_none_result(Decimal("200.00")),  # price lookup
            _scalar_one_or_none_result(None),  # earnings calendar
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.stocks.TTMService") as MockTTM:
            mock_ttm = AsyncMock()
            mock_ttm.compute_ttm = AsyncMock(return_value=ttm_data)
            MockTTM.return_value = mock_ttm

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/stocks/AAPL/ratios")

        assert resp.status_code == 200
        body = resp.json()

        # Check envelope structure
        assert "data" in body
        assert "data_as_of" in body
        assert "next_refresh" in body

        data = body["data"]
        # Check some expected ratios are present
        assert "gross_margin" in data
        assert "operating_margin" in data
        assert "pe_ratio" in data
        assert data["gross_margin"] is not None
        assert data["pe_ratio"] is not None  # price is available
    finally:
        app.dependency_overrides.clear()


async def test_ratios_endpoint_no_price_valuation_null():
    """Valuation ratios should be null when no price history exists."""
    stock = _make_mock_stock()
    ttm_data = _make_ttm_data()

    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stock),  # stock lookup
            _scalar_one_or_none_result(None),  # price lookup -> no price
            _scalar_one_or_none_result(None),  # earnings calendar
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.stocks.TTMService") as MockTTM:
            mock_ttm = AsyncMock()
            mock_ttm.compute_ttm = AsyncMock(return_value=ttm_data)
            MockTTM.return_value = mock_ttm

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/stocks/AAPL/ratios")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["pe_ratio"] is None
        assert data["pb_ratio"] is None
        assert data["ps_ratio"] is None
        assert data["ev_to_ebitda"] is None
        # Non-valuation ratios should still work
        assert data["gross_margin"] is not None
    finally:
        app.dependency_overrides.clear()


async def test_ratios_endpoint_404_no_financials():
    """Returns 404 when no financial statements exist for ratio computation."""
    stock = _make_mock_stock()

    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stock),  # stock lookup
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.stocks.TTMService") as MockTTM:
            mock_ttm = AsyncMock()
            mock_ttm.compute_ttm = AsyncMock(return_value=None)  # No TTM data
            MockTTM.return_value = mock_ttm

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/stocks/AAPL/ratios")

        assert resp.status_code == 404
        assert "no financial statements" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


async def test_ratios_endpoint_stock_not_found():
    """Returns 404 when the stock itself does not exist."""
    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(None),  # stock lookup -> miss
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/stocks/NOPE/ratios")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# ======================================================================
# Endpoint tests: GET /api/stocks/{symbol}/peers
# ======================================================================


async def test_peers_returns_same_industry_stocks():
    """Returns peers in the same Damodaran industry."""
    stock = _make_mock_stock()

    # Sector mapping for this stock
    mapping = MagicMock()
    mapping.damodaran_industry_id = 5
    mapping.twelvedata_sector = "Technology"
    mapping.twelvedata_industry = "Consumer Electronics"

    # Peer mapping rows (same damodaran_industry_id)
    peer_mapping_1 = MagicMock()
    peer_mapping_1.twelvedata_sector = "Technology"
    peer_mapping_1.twelvedata_industry = "Consumer Electronics"

    # Peer stocks
    peer1 = _make_mock_stock(id=2, symbol="MSFT", name="Microsoft Corp")
    peer2 = _make_mock_stock(id=3, symbol="GOOG", name="Alphabet Inc")

    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stock),  # stock lookup
            _scalar_one_or_none_result(mapping),  # sector mapping lookup
            _all_result([peer_mapping_1]),  # peer mappings query
            _scalars_all_result([peer1, peer2]),  # peer stocks query
            _scalar_one_or_none_result(None),  # earnings calendar
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/stocks/AAPL/peers")

        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        data = body["data"]
        assert isinstance(data, list)
        assert len(data) == 2
        symbols = {p["symbol"] for p in data}
        assert "MSFT" in symbols
        assert "GOOG" in symbols
        # Queried stock should NOT be in results
        assert "AAPL" not in symbols
    finally:
        app.dependency_overrides.clear()


async def test_peers_excludes_queried_stock():
    """The queried stock itself should not appear in peer results."""
    stock = _make_mock_stock()

    mapping = MagicMock()
    mapping.damodaran_industry_id = 5

    peer_mapping = MagicMock()
    peer_mapping.twelvedata_sector = "Technology"
    peer_mapping.twelvedata_industry = "Consumer Electronics"

    # Only one peer besides the queried stock
    peer = _make_mock_stock(id=2, symbol="MSFT", name="Microsoft Corp")

    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stock),  # stock lookup
            _scalar_one_or_none_result(mapping),  # sector mapping
            _all_result([peer_mapping]),  # peer mappings
            _scalars_all_result([peer]),  # peer stocks (AAPL filtered by query)
            _scalar_one_or_none_result(None),  # earnings calendar
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/stocks/AAPL/peers")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["symbol"] == "MSFT"
    finally:
        app.dependency_overrides.clear()


async def test_peers_empty_when_no_mapping():
    """Returns empty list when no sector mapping exists for the stock."""
    stock = _make_mock_stock()

    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stock),  # stock lookup
            _scalar_one_or_none_result(None),  # sector mapping -> None
            _scalar_one_or_none_result(None),  # earnings calendar
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/stocks/AAPL/peers")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
    finally:
        app.dependency_overrides.clear()


async def test_peers_empty_when_no_peers_found():
    """Returns empty list when mapping exists but no other stocks share it."""
    stock = _make_mock_stock()

    mapping = MagicMock()
    mapping.damodaran_industry_id = 5

    peer_mapping = MagicMock()
    peer_mapping.twelvedata_sector = "Technology"
    peer_mapping.twelvedata_industry = "Consumer Electronics"

    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stock),  # stock lookup
            _scalar_one_or_none_result(mapping),  # sector mapping
            _all_result([peer_mapping]),  # peer mappings
            _scalars_all_result([]),  # no peer stocks found
            _scalar_one_or_none_result(None),  # earnings calendar
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/stocks/AAPL/peers")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
    finally:
        app.dependency_overrides.clear()


async def test_peers_stock_not_found():
    """Returns 404 when the stock itself does not exist."""
    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(None),  # stock lookup -> miss
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/stocks/NOPE/peers")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


async def test_peers_response_envelope():
    """Peers endpoint wraps results in standard response envelope."""
    stock = _make_mock_stock()

    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stock),  # stock lookup
            _scalar_one_or_none_result(None),  # no mapping
            _scalar_one_or_none_result(None),  # earnings calendar
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/stocks/AAPL/peers")

        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "data_as_of" in body
        assert "next_refresh" in body
    finally:
        app.dependency_overrides.clear()
