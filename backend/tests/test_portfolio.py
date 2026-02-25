"""Tests for portfolio endpoints: CRUD, holdings, performance, history, auth.

All external APIs are mocked. Follows existing test patterns:
mock get_session + get_current_user via dependency_overrides,
exercise endpoints through httpx.ASGITransport + AsyncClient.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.auth import get_current_user
from app.database import get_session
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session_override(mock_db):
    """Return an async generator factory suitable for dependency_overrides."""

    async def _override():
        yield mock_db

    return _override


def _make_mock_user(id=1):
    user = MagicMock()
    user.id = id
    user.clerk_id = "clerk_123"
    user.email = "test@example.com"
    user.display_name = "Test User"
    return user


def _make_mock_portfolio(id=1, user_id=1, name="My Portfolio", mode="watchlist"):
    p = MagicMock()
    p.id = id
    p.user_id = user_id
    p.name = name
    p.mode = mode
    p.created_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    p.updated_at = None
    return p


def _make_mock_holding(id=1, portfolio_id=1, stock_id=1):
    h = MagicMock()
    h.id = id
    h.portfolio_id = portfolio_id
    h.stock_id = stock_id
    h.shares = Decimal("100.000000")
    h.cost_basis_per_share = Decimal("150.0000")
    h.added_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    return h


def _make_mock_stock(id=1, symbol="AAPL", name="Apple Inc"):
    s = MagicMock()
    s.id = id
    s.symbol = symbol
    s.name = name
    return s


def _counts_result(count_tuples):
    """Mock result for the holdings-count query in list_portfolios."""
    result = MagicMock()
    result.all.return_value = count_tuples
    return result


def _scalar_one_result(value):
    """Mock result for scalar_one() (e.g. holdings count in update_portfolio)."""
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _scalar_one_result_for_stock(stock):
    """Mock result for scalar_one() returning a Stock object."""
    result = MagicMock()
    result.scalar_one.return_value = stock
    return result


# ---------------------------------------------------------------------------
# 1. List portfolios — empty
# ---------------------------------------------------------------------------


async def test_list_portfolios_empty():
    """GET /api/portfolios with no portfolios returns []."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.list_portfolios.return_value = []

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/portfolios")

        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. List portfolios — with data
# ---------------------------------------------------------------------------


async def test_list_portfolios_with_data():
    """GET /api/portfolios returns portfolios with holdings counts."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()

    p1 = _make_mock_portfolio(id=1, name="Watchlist")
    p2 = _make_mock_portfolio(id=2, name="Full Portfolio", mode="full")

    # The session.execute for the holdings count query
    mock_db.execute = AsyncMock(return_value=_counts_result([(1, 3), (2, 1)]))

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.list_portfolios.return_value = [p1, p2]

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/portfolios")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "Watchlist"
        assert data[0]["holdings_count"] == 3
        assert data[1]["name"] == "Full Portfolio"
        assert data[1]["mode"] == "full"
        assert data[1]["holdings_count"] == 1
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. Create portfolio
# ---------------------------------------------------------------------------


async def test_create_portfolio():
    """POST /api/portfolios creates and returns 201."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()
    new_portfolio = _make_mock_portfolio(id=5, name="Tech Stocks")

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.create_portfolio.return_value = new_portfolio

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.post(
                    "/api/portfolios",
                    json={"name": "Tech Stocks", "mode": "watchlist"},
                )

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == 5
        assert data["name"] == "Tech Stocks"
        assert data["mode"] == "watchlist"
        assert data["holdings_count"] == 0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. Create portfolio — invalid mode
# ---------------------------------------------------------------------------


async def test_create_portfolio_invalid_mode():
    """POST /api/portfolios with mode='invalid' returns 422."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/portfolios",
                json={"name": "Bad", "mode": "invalid"},
            )

        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. Update portfolio — name
# ---------------------------------------------------------------------------


async def test_update_portfolio():
    """PATCH /api/portfolios/{id} updates name and returns 200."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()
    updated = _make_mock_portfolio(id=1, name="Renamed")
    updated.updated_at = datetime(2025, 7, 1, tzinfo=timezone.utc)

    # session.execute for the holdings count query
    mock_db.execute = AsyncMock(return_value=_scalar_one_result(2))

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.update_portfolio.return_value = updated

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.patch(
                    "/api/portfolios/1",
                    json={"name": "Renamed"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Renamed"
        assert data["holdings_count"] == 2
        assert data["updated_at"] is not None
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. Update portfolio — toggle mode
# ---------------------------------------------------------------------------


async def test_update_portfolio_toggle_mode():
    """PATCH mode from watchlist to full returns 200."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()
    updated = _make_mock_portfolio(id=1, name="My Portfolio", mode="full")
    updated.updated_at = datetime(2025, 7, 1, tzinfo=timezone.utc)

    mock_db.execute = AsyncMock(return_value=_scalar_one_result(0))

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.update_portfolio.return_value = updated

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.patch(
                    "/api/portfolios/1",
                    json={"mode": "full"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "full"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 7. Delete portfolio
# ---------------------------------------------------------------------------


async def test_delete_portfolio():
    """DELETE /api/portfolios/{id} returns 204."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.delete_portfolio.return_value = None

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.delete("/api/portfolios/1")

        assert resp.status_code == 204
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 8. Delete portfolio — not found
# ---------------------------------------------------------------------------


async def test_delete_portfolio_not_found():
    """DELETE non-existent portfolio returns 404."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.delete_portfolio.side_effect = HTTPException(
                status_code=404, detail="Portfolio not found"
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.delete("/api/portfolios/999")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Portfolio not found"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 9. List holdings
# ---------------------------------------------------------------------------


async def test_list_holdings():
    """GET /api/portfolios/{id}/holdings returns holdings with prices."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()

    holdings_data = [
        {
            "id": 1,
            "stock_id": 1,
            "symbol": "AAPL",
            "name": "Apple Inc",
            "shares": 100.0,
            "cost_basis_per_share": 150.0,
            "added_at": "2025-06-01 00:00:00+00:00",
            "current_price": 155.0,
            "market_value": 15500.0,
            "gain_loss": 500.0,
            "gain_loss_pct": 3.333333,
        },
    ]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.list_holdings.return_value = holdings_data

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/portfolios/1/holdings")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "AAPL"
        # Decimal fields are serialized as strings by Pydantic
        assert float(data[0]["shares"]) == 100.0
        assert data[0]["current_price"] == 155.0
        assert data[0]["market_value"] == 15500.0
        assert data[0]["gain_loss"] == 500.0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 10. Add holding
# ---------------------------------------------------------------------------


async def test_add_holding():
    """POST /api/portfolios/{id}/holdings returns 201."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()
    mock_holding = _make_mock_holding(id=10, portfolio_id=1, stock_id=1)
    mock_stock = _make_mock_stock(id=1, symbol="AAPL", name="Apple Inc")

    # session.execute for the stock lookup after add_holding
    mock_db.execute = AsyncMock(
        return_value=_scalar_one_result_for_stock(mock_stock)
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.add_holding.return_value = mock_holding

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.post(
                    "/api/portfolios/1/holdings",
                    json={"stock_id": 1, "shares": 100, "cost_basis_per_share": 150},
                )

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == 10
        assert data["symbol"] == "AAPL"
        assert data["name"] == "Apple Inc"
        # Decimal fields are serialized as strings by Pydantic
        assert float(data["shares"]) == 100.0
        assert float(data["cost_basis_per_share"]) == 150.0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 11. Add holding — duplicate
# ---------------------------------------------------------------------------


async def test_add_holding_duplicate():
    """POST with a stock already in portfolio returns 409."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.add_holding.side_effect = HTTPException(
                status_code=409, detail="Stock already in portfolio"
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.post(
                    "/api/portfolios/1/holdings",
                    json={"stock_id": 1, "shares": 100, "cost_basis_per_share": 150},
                )

        assert resp.status_code == 409
        assert resp.json()["detail"] == "Stock already in portfolio"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 12. Remove holding
# ---------------------------------------------------------------------------


async def test_remove_holding():
    """DELETE /api/portfolios/{id}/holdings/{hid} returns 204."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.remove_holding.return_value = None

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.delete("/api/portfolios/1/holdings/5")

        assert resp.status_code == 204
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 13. Performance
# ---------------------------------------------------------------------------


async def test_get_performance():
    """GET /api/portfolios/{id}/performance returns P&L summary."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()

    perf_data = {
        "total_value": 15500.0,
        "total_cost_basis": 15000.0,
        "total_gain_loss": 500.0,
        "total_gain_loss_pct": 3.33,
        "holdings": [
            {
                "id": 1,
                "stock_id": 1,
                "symbol": "AAPL",
                "name": "Apple Inc",
                "shares": 100.0,
                "cost_basis_per_share": 150.0,
                "added_at": "2025-06-01 00:00:00+00:00",
                "current_price": 155.0,
                "market_value": 15500.0,
                "gain_loss": 500.0,
                "gain_loss_pct": 3.33,
            },
        ],
    }

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.get_performance.return_value = perf_data

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/portfolios/1/performance")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_value"] == 15500.0
        assert data["total_cost_basis"] == 15000.0
        assert data["total_gain_loss"] == 500.0
        assert data["total_gain_loss_pct"] == 3.33
        assert len(data["holdings"]) == 1
        assert data["holdings"][0]["symbol"] == "AAPL"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 14. History
# ---------------------------------------------------------------------------


async def test_get_history():
    """GET /api/portfolios/{id}/history returns snapshots."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()

    snap = MagicMock()
    snap.id = 1
    snap.portfolio_id = 1
    snap.date = date(2025, 6, 1)
    snap.total_value = Decimal("15500.00")
    snap.total_cost_basis = Decimal("15000.00")
    snap.total_gain_loss = Decimal("500.00")
    snap.holdings_snapshot = {"holdings": []}

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.get_history.return_value = [snap]

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/portfolios/1/history")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == 1
        assert data[0]["date"] == "2025-06-01"
        assert data[0]["total_value"] == 15500.0
        assert data[0]["total_gain_loss"] == 500.0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 15. Unauthenticated access rejected
# ---------------------------------------------------------------------------


async def test_endpoints_reject_unauthenticated():
    """Requests without auth header are rejected on portfolio endpoints."""
    # Clear any existing overrides so the real auth dependency runs
    app.dependency_overrides.clear()

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            endpoints = [
                ("GET", "/api/portfolios"),
                ("POST", "/api/portfolios"),
                ("PATCH", "/api/portfolios/1"),
                ("DELETE", "/api/portfolios/1"),
                ("GET", "/api/portfolios/1/holdings"),
                ("POST", "/api/portfolios/1/holdings"),
                ("DELETE", "/api/portfolios/1/holdings/1"),
                ("GET", "/api/portfolios/1/performance"),
                ("GET", "/api/portfolios/1/history"),
            ]

            for method, path in endpoints:
                resp = await c.request(method, path)
                # HTTPBearer rejects missing credentials with 401 or 403
                assert resp.status_code in (401, 403), (
                    f"{method} {path} should reject unauthenticated, got {resp.status_code}"
                )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 16. Portfolio not found for other user (ownership check)
# ---------------------------------------------------------------------------


async def test_portfolio_not_found_for_other_user():
    """Accessing another user's portfolio returns 404."""
    mock_user = _make_mock_user(id=99)  # Different user ID
    mock_db = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            # Service raises 404 when user_id doesn't match portfolio owner
            mock_svc.update_portfolio.side_effect = HTTPException(
                status_code=404, detail="Portfolio not found"
            )
            mock_svc.delete_portfolio.side_effect = HTTPException(
                status_code=404, detail="Portfolio not found"
            )
            mock_svc.list_holdings.side_effect = HTTPException(
                status_code=404, detail="Portfolio not found"
            )
            mock_svc.get_performance.side_effect = HTTPException(
                status_code=404, detail="Portfolio not found"
            )
            mock_svc.get_history.side_effect = HTTPException(
                status_code=404, detail="Portfolio not found"
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                # PATCH
                resp = await c.patch(
                    "/api/portfolios/1", json={"name": "Hacked"}
                )
                assert resp.status_code == 404

                # DELETE
                resp = await c.delete("/api/portfolios/1")
                assert resp.status_code == 404

                # GET holdings
                resp = await c.get("/api/portfolios/1/holdings")
                assert resp.status_code == 404

                # GET performance
                resp = await c.get("/api/portfolios/1/performance")
                assert resp.status_code == 404

                # GET history
                resp = await c.get("/api/portfolios/1/history")
                assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 17. Create portfolio with full mode
# ---------------------------------------------------------------------------


async def test_create_portfolio_full_mode():
    """POST /api/portfolios with mode='full' succeeds."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()
    new_portfolio = _make_mock_portfolio(id=3, name="Full Tracker", mode="full")

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.create_portfolio.return_value = new_portfolio

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.post(
                    "/api/portfolios",
                    json={"name": "Full Tracker", "mode": "full"},
                )

        assert resp.status_code == 201
        data = resp.json()
        assert data["mode"] == "full"
        assert data["holdings_count"] == 0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 18. Add holding — watchlist mode (no shares/cost)
# ---------------------------------------------------------------------------


async def test_add_holding_watchlist_no_shares():
    """POST holding with only stock_id (no shares) returns 201."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()
    mock_holding = _make_mock_holding(id=20, portfolio_id=1, stock_id=2)
    mock_holding.shares = None
    mock_holding.cost_basis_per_share = None
    mock_stock = _make_mock_stock(id=2, symbol="MSFT", name="Microsoft Corp")

    mock_db.execute = AsyncMock(
        return_value=_scalar_one_result_for_stock(mock_stock)
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.add_holding.return_value = mock_holding

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.post(
                    "/api/portfolios/1/holdings",
                    json={"stock_id": 2},
                )

        assert resp.status_code == 201
        data = resp.json()
        assert data["symbol"] == "MSFT"
        assert data["shares"] is None
        assert data["cost_basis_per_share"] is None
        assert data["current_price"] is None
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 19. Remove holding — not found
# ---------------------------------------------------------------------------


async def test_remove_holding_not_found():
    """DELETE non-existent holding returns 404."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.remove_holding.side_effect = HTTPException(
                status_code=404, detail="Holding not found"
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.delete("/api/portfolios/1/holdings/999")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Holding not found"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 20. Performance — empty portfolio
# ---------------------------------------------------------------------------


async def test_get_performance_empty():
    """Performance endpoint with no holdings returns zeroed summary."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()

    perf_data = {
        "total_value": None,
        "total_cost_basis": None,
        "total_gain_loss": None,
        "total_gain_loss_pct": None,
        "holdings": [],
    }

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.get_performance.return_value = perf_data

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/portfolios/1/performance")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_value"] == 0.0
        assert data["total_cost_basis"] == 0.0
        assert data["total_gain_loss"] == 0.0
        assert data["total_gain_loss_pct"] is None
        assert data["holdings"] == []
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 21. History — empty
# ---------------------------------------------------------------------------


async def test_get_history_empty():
    """GET history with no snapshots returns []."""
    mock_user = _make_mock_user()
    mock_db = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        with patch("app.routers.portfolio.PortfolioService") as MockSvc:
            mock_svc = AsyncMock()
            MockSvc.return_value = mock_svc
            mock_svc.get_history.return_value = []

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/portfolios/1/history")

        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        app.dependency_overrides.clear()
