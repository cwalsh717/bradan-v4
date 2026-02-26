"""Integration tests for Phase 2 stock profile and risk-free rate endpoints.

Tests follow the existing pattern from test_search.py: mock get_session and
dependency providers via app.dependency_overrides, then exercise the endpoints
through httpx.ASGITransport + AsyncClient.
"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import get_session
from app.dependencies import get_fred, get_twelvedata


# ---------------------------------------------------------------------------
# Helpers
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


# ---------------------------------------------------------------------------
# 1. GET /api/stocks/{symbol}/profile — cached stock
# ---------------------------------------------------------------------------


async def test_profile_cached_stock():
    """When the stock exists in DB, return 200 with envelope."""
    stock = _make_mock_stock()

    # Call 1: stock lookup -> returns stock
    # Call 2: _next_refresh_for_stock earnings query -> no upcoming earnings
    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stock),  # stock lookup
            _scalar_one_or_none_result(None),  # earnings calendar query
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)
    app.dependency_overrides[get_twelvedata] = lambda: AsyncMock()

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/stocks/AAPL/profile")

        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "data_as_of" in body
        assert "next_refresh" in body
        assert body["data"]["symbol"] == "AAPL"
        assert body["data"]["name"] == "Apple Inc"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. GET /api/stocks/{symbol}/profile — uncached triggers fetch
# ---------------------------------------------------------------------------


async def test_profile_uncached_triggers_fetch():
    """When the stock is NOT in DB, StockDataService.fetch_full_profile is called."""
    fetched_stock = _make_mock_stock()

    # Call 1: stock lookup -> None (not cached)
    # After fetch_full_profile runs, the endpoint uses the returned stock.
    # Call 2: _next_refresh_for_stock earnings query -> None
    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(None),  # stock lookup -> miss
            _scalar_one_or_none_result(None),  # earnings calendar query
        ]
    )

    mock_td = AsyncMock()

    app.dependency_overrides[get_session] = _session_override(mock_db)
    app.dependency_overrides[get_twelvedata] = lambda: mock_td

    try:
        with patch("app.routers.stocks.StockDataService") as MockSvc:
            mock_instance = AsyncMock()
            mock_instance.fetch_full_profile = AsyncMock(return_value=fetched_stock)
            MockSvc.return_value = mock_instance

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/stocks/AAPL/profile")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["symbol"] == "AAPL"
        MockSvc.assert_called_once_with(client=mock_td, session=mock_db)
        mock_instance.fetch_full_profile.assert_called_once_with("AAPL")
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2b. GET /api/stocks/{symbol}/profile — pre-seeded stub triggers fetch
# ---------------------------------------------------------------------------


async def test_profile_preseeded_stub_triggers_fetch():
    """When a pre-seeded stub exists (last_updated=None), fetch_full_profile is called."""
    stub_stock = _make_mock_stock(last_updated=None)
    fetched_stock = _make_mock_stock()

    # Call 1: stock lookup -> returns stub with last_updated=None
    # After fetch_full_profile runs, the endpoint uses the returned stock.
    # Call 2: _next_refresh_for_stock earnings query -> None
    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stub_stock),  # stock lookup -> stub
            _scalar_one_or_none_result(None),  # earnings calendar query
        ]
    )

    mock_td = AsyncMock()

    app.dependency_overrides[get_session] = _session_override(mock_db)
    app.dependency_overrides[get_twelvedata] = lambda: mock_td

    try:
        with patch("app.routers.stocks.StockDataService") as MockSvc:
            mock_instance = AsyncMock()
            mock_instance.fetch_full_profile = AsyncMock(return_value=fetched_stock)
            MockSvc.return_value = mock_instance

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/stocks/AAPL/profile")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["symbol"] == "AAPL"
        MockSvc.assert_called_once_with(client=mock_td, session=mock_db)
        mock_instance.fetch_full_profile.assert_called_once_with("AAPL")
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. GET /api/stocks/{symbol}/financials?period=annual
# ---------------------------------------------------------------------------


async def test_financials_annual():
    """Annual financials returns envelope with FinancialRecord list."""
    stock = _make_mock_stock()
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    stmt1 = MagicMock()
    stmt1.id = 10
    stmt1.statement_type = "income"
    stmt1.period = "annual"
    stmt1.fiscal_date = date(2024, 12, 31)
    stmt1.data = {"revenue": 100000}
    stmt1.fetched_at = now

    # Call 1: _get_stock_or_404 -> stock
    # Call 2: select FinancialStatement -> list of statements
    # Call 3: _next_refresh_for_stock earnings -> None
    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stock),
            _scalars_all_result([stmt1]),
            _scalar_one_or_none_result(None),
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/stocks/AAPL/financials?period=annual")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 1
        assert body["data"][0]["statement_type"] == "income"
        assert body["data"][0]["fiscal_date"] == "2024-12-31"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. GET /api/stocks/{symbol}/financials?period=ttm
# ---------------------------------------------------------------------------


async def test_financials_ttm():
    """TTM financials returns computed TTM data via TTMService."""
    stock = _make_mock_stock()
    ttm_data = {
        "income": {"revenue": 400000},
        "quarters_used": 4,
        "period_start": "2024-03-31",
        "period_end": "2024-12-31",
    }

    # Call 1: _get_stock_or_404 -> stock
    # Then TTMService.compute_ttm is called (uses its own session.execute calls).
    # Call 2 (earnings calendar): _next_refresh_for_stock -> None
    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stock),  # stock lookup
            _scalar_one_or_none_result(None),  # earnings calendar
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.stocks.TTMService") as MockTTM:
            mock_ttm_instance = AsyncMock()
            mock_ttm_instance.compute_ttm = AsyncMock(return_value=ttm_data)
            MockTTM.return_value = mock_ttm_instance

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/stocks/AAPL/financials?period=ttm")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["quarters_used"] == 4
        assert body["data"]["income"]["revenue"] == 400000
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. GET /api/stocks/{symbol}/financials?period=invalid — 422
# ---------------------------------------------------------------------------


async def test_financials_invalid_period():
    """An invalid period value returns 422 validation error."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/stocks/AAPL/financials?period=invalid")

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 6. GET /api/stocks/{symbol}/financials — stock not found
# ---------------------------------------------------------------------------


async def test_financials_stock_not_found():
    """When the stock does not exist, financials returns 404."""
    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(None),  # stock lookup -> miss
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/stocks/NOPE/financials?period=annual")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 7. GET /api/stocks/{symbol}/price-history
# ---------------------------------------------------------------------------


async def test_price_history():
    """Price history endpoint returns envelope with PriceRecord list."""
    stock = _make_mock_stock()
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    row = MagicMock()
    row.id = 100
    row.date = date(2025, 5, 30)
    row.open = 190.0
    row.high = 195.0
    row.low = 189.0
    row.close = 193.5
    row.volume = 50000000
    row.fetched_at = now

    # Call 1: _get_stock_or_404 -> stock
    # Call 2: select PriceHistory -> rows
    # Call 3: _next_refresh_for_stock earnings -> None
    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stock),
            _scalars_all_result([row]),
            _scalar_one_or_none_result(None),
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/stocks/AAPL/price-history")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 1
        assert body["data"][0]["close"] == 193.5
        assert body["data"][0]["volume"] == 50000000
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 8. GET /api/stocks/{symbol}/dividends
# ---------------------------------------------------------------------------


async def test_dividends():
    """Dividends endpoint returns envelope with DividendRecord list."""
    stock = _make_mock_stock()
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    div = MagicMock()
    div.id = 200
    div.ex_date = date(2025, 5, 15)
    div.amount = 0.25
    div.fetched_at = now

    # Call 1: _get_stock_or_404 -> stock
    # Call 2: select Dividend -> rows
    # Call 3: _next_refresh_for_stock earnings -> None
    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stock),
            _scalars_all_result([div]),
            _scalar_one_or_none_result(None),
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/stocks/AAPL/dividends")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 1
        assert body["data"][0]["amount"] == 0.25
        assert body["data"][0]["ex_date"] == "2025-05-15"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 9. GET /api/stocks/{symbol}/splits
# ---------------------------------------------------------------------------


async def test_splits():
    """Splits endpoint returns envelope with SplitRecord list."""
    stock = _make_mock_stock()

    split = MagicMock()
    split.id = 300
    split.date = date(2020, 8, 31)
    split.ratio_from = 1
    split.ratio_to = 4

    # Call 1: _get_stock_or_404 -> stock
    # Call 2: select StockSplit -> rows
    # Call 3: _next_refresh_for_stock earnings -> None
    mock_db = _make_session_with_side_effects(
        [
            _scalar_one_or_none_result(stock),
            _scalars_all_result([split]),
            _scalar_one_or_none_result(None),
        ]
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/stocks/AAPL/splits")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 1
        assert body["data"][0]["ratio_from"] == 1
        assert body["data"][0]["ratio_to"] == 4
        assert body["data"][0]["date"] == "2020-08-31"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 10. GET /api/rates/risk-free — data available
# ---------------------------------------------------------------------------


async def test_risk_free_rate_available():
    """When FRED data is in the DB, return 200 with DGS10 data."""
    mock_db = AsyncMock()
    mock_fred = AsyncMock()

    app.dependency_overrides[get_session] = _session_override(mock_db)
    app.dependency_overrides[get_fred] = lambda: mock_fred

    try:
        with patch("app.routers.utility.FredDataService") as MockFredSvc:
            mock_svc = AsyncMock()
            mock_svc.get_latest_value = AsyncMock(
                return_value={
                    "date": "2025-05-30",
                    "value": 4.28,
                }
            )
            MockFredSvc.return_value = mock_svc

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/rates/risk-free")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["series_id"] == "DGS10"
        assert body["data"]["value"] == 4.28
        assert body["data"]["date"] == "2025-05-30"
        assert "data_as_of" in body
        assert "next_refresh" in body
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 11. GET /api/rates/risk-free — data unavailable (503)
# ---------------------------------------------------------------------------


async def test_risk_free_rate_unavailable():
    """When no FRED data is found, return 503."""
    mock_db = AsyncMock()
    mock_fred = AsyncMock()

    app.dependency_overrides[get_session] = _session_override(mock_db)
    app.dependency_overrides[get_fred] = lambda: mock_fred

    try:
        with patch("app.routers.utility.FredDataService") as MockFredSvc:
            mock_svc = AsyncMock()
            mock_svc.get_latest_value = AsyncMock(return_value=None)
            MockFredSvc.return_value = mock_svc

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/rates/risk-free")

        assert resp.status_code == 503
        body = resp.json()
        assert "not available" in body["message"].lower()
    finally:
        app.dependency_overrides.clear()
