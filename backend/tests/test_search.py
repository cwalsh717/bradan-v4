from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.search import SearchService
from app.services.twelvedata import TwelveDataClient
from tests.conftest import make_twelvedata_transport


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_search_endpoint_returns_results():
    """Test the /api/search endpoint returns results with mocked dependencies."""
    from app.database import get_session
    from app.dependencies import get_twelvedata

    mock_td = AsyncMock(spec=TwelveDataClient)
    mock_td.symbol_search = AsyncMock(return_value=[
        {"symbol": "AAPL", "instrument_name": "Apple Inc", "exchange": "NASDAQ",
         "instrument_type": "Common Stock", "currency": "USD"},
    ])

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def mock_session_override():
        yield mock_db

    app.dependency_overrides[get_session] = mock_session_override
    app.dependency_overrides[get_twelvedata] = lambda: mock_td

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/search?q=AAPL")

        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) >= 1
    finally:
        app.dependency_overrides.clear()


async def test_search_empty_query_returns_422(client):
    resp = await client.get("/api/search?q=")
    assert resp.status_code == 422


async def test_search_service_queries_db_first():
    """SearchService queries local DB before hitting the API."""
    mock_td = AsyncMock(spec=TwelveDataClient)
    mock_td.symbol_search = AsyncMock(return_value=[])

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()

    # Simulate 6 DB results so API is NOT called
    mock_stocks = []
    for i in range(6):
        s = MagicMock()
        s.symbol = f"TST{i}"
        s.name = f"Test Stock {i}"
        s.exchange = "NYSE"
        s.currency = "USD"
        mock_stocks.append(s)

    mock_scalars.all.return_value = mock_stocks
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_result)

    service = SearchService(mock_td)
    results = await service.search("TST", mock_db)

    assert len(results) == 6
    assert all(r["cached"] is True for r in results)
    mock_td.symbol_search.assert_not_called()


async def test_search_service_falls_back_to_twelvedata():
    """SearchService hits Twelve Data when local results < 5."""
    mock_td = AsyncMock(spec=TwelveDataClient)
    mock_td.symbol_search = AsyncMock(return_value=[
        {"symbol": "AAPL", "instrument_name": "Apple Inc", "exchange": "NASDAQ",
         "instrument_type": "Common Stock", "currency": "USD"},
    ])

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []  # No local results
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_result)

    service = SearchService(mock_td)
    results = await service.search("AAPL", mock_db)

    assert len(results) == 1
    assert results[0]["cached"] is False
    mock_td.symbol_search.assert_called_once_with("AAPL")


async def test_search_deduplication():
    """Same symbol from DB and API should not duplicate."""
    mock_td = AsyncMock(spec=TwelveDataClient)
    mock_td.symbol_search = AsyncMock(return_value=[
        {"symbol": "AAPL", "instrument_name": "Apple Inc", "exchange": "NASDAQ",
         "instrument_type": "Common Stock", "currency": "USD"},
        {"symbol": "AAPLC", "instrument_name": "Apple CEDEAR", "exchange": "BCBA",
         "instrument_type": "Depositary Receipt", "currency": "USD"},
    ])

    # One local AAPL result
    mock_stock = MagicMock()
    mock_stock.symbol = "AAPL"
    mock_stock.name = "Apple Inc"
    mock_stock.exchange = "NASDAQ"
    mock_stock.currency = "USD"

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_stock]
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_result)

    service = SearchService(mock_td)
    results = await service.search("AAPL", mock_db)

    symbols = [r["symbol"] for r in results]
    assert symbols.count("AAPL") == 1  # Not duplicated


async def test_search_cached_flag():
    """Local stocks have cached=True, API-only have cached=False."""
    mock_td = AsyncMock(spec=TwelveDataClient)
    mock_td.symbol_search = AsyncMock(return_value=[
        {"symbol": "MSFT", "instrument_name": "Microsoft", "exchange": "NASDAQ",
         "instrument_type": "Common Stock", "currency": "USD"},
    ])

    mock_stock = MagicMock()
    mock_stock.symbol = "AAPL"
    mock_stock.name = "Apple Inc"
    mock_stock.exchange = "NASDAQ"
    mock_stock.currency = "USD"

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_stock]
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_result)

    service = SearchService(mock_td)
    results = await service.search("A", mock_db)

    by_symbol = {r["symbol"]: r for r in results}
    assert by_symbol["AAPL"]["cached"] is True
    assert by_symbol["MSFT"]["cached"] is False
