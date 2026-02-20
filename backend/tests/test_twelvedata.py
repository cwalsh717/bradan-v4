import logging
import time

import httpx
import pytest

from app.exceptions import TwelveDataError
from app.services.twelvedata import TwelveDataClient
from tests.conftest import make_twelvedata_transport


async def _make_client(response_data, status_code=200):
    client = TwelveDataClient(api_key="test_key")
    await client.client.aclose()
    client.client = httpx.AsyncClient(
        base_url="https://api.twelvedata.com",
        transport=make_twelvedata_transport(response_data, status_code),
    )
    return client


async def test_symbol_search_returns_parsed_results():
    client = await _make_client({
        "data": [
            {"symbol": "AAPL", "instrument_name": "Apple Inc", "exchange": "NASDAQ",
             "instrument_type": "Common Stock", "currency": "USD"},
            {"symbol": "AAPLC", "instrument_name": "Apple CEDEAR", "exchange": "BCBA",
             "instrument_type": "Depositary Receipt", "currency": "USD"},
        ]
    })
    results = await client.symbol_search("AAPL")
    assert len(results) == 2
    assert results[0]["symbol"] == "AAPL"
    await client.close()


async def test_symbol_search_empty_query():
    client = await _make_client({"data": []})
    results = await client.symbol_search("")
    assert results == []
    await client.close()


async def test_get_stock_profile():
    profile_data = {
        "symbol": "AAPL", "name": "Apple Inc", "exchange": "NASDAQ",
        "sector": "Technology", "industry": "Consumer Electronics",
    }
    client = await _make_client(profile_data)
    result = await client.get_stock_profile("AAPL")
    assert result["symbol"] == "AAPL"
    assert result["name"] == "Apple Inc"
    await client.close()


async def test_get_time_series():
    client = await _make_client({
        "values": [
            {"datetime": "2025-01-10", "open": "150.0", "high": "152.0",
             "low": "149.0", "close": "151.0", "volume": "50000000"},
        ]
    })
    results = await client.get_time_series("AAPL")
    assert len(results) == 1
    assert results[0]["close"] == "151.0"
    await client.close()


async def test_get_income_statement():
    client = await _make_client({
        "income_statement": [
            {"fiscal_date": "2025-09-30", "sales": "100000000"},
        ]
    })
    results = await client.get_income_statement("AAPL")
    assert len(results) == 1
    assert results[0]["fiscal_date"] == "2025-09-30"
    await client.close()


async def test_get_balance_sheet():
    client = await _make_client({
        "balance_sheet": [
            {"fiscal_date": "2025-09-30", "total_assets": "500000000"},
        ]
    })
    results = await client.get_balance_sheet("AAPL")
    assert len(results) == 1
    await client.close()


async def test_get_cash_flow():
    client = await _make_client({
        "cash_flow": [
            {"fiscal_date": "2025-09-30", "operating_cash_flow": "30000000"},
        ]
    })
    results = await client.get_cash_flow("AAPL")
    assert len(results) == 1
    await client.close()


async def test_get_dividends():
    client = await _make_client({
        "dividends": [
            {"ex_date": "2025-08-10", "amount": "0.25"},
        ]
    })
    results = await client.get_dividends("AAPL")
    assert len(results) == 1
    assert results[0]["amount"] == "0.25"
    await client.close()


async def test_get_splits():
    client = await _make_client({
        "splits": [
            {"date": "2020-08-31", "ratio": "4:1"},
        ]
    })
    results = await client.get_splits("AAPL")
    assert len(results) == 1
    await client.close()


async def test_get_earnings_calendar():
    client = await _make_client({
        "earnings_calendar": [
            {"report_date": "2025-10-30", "fiscal_quarter": "Q4 2025"},
        ]
    })
    results = await client.get_earnings_calendar("AAPL")
    assert len(results) == 1
    assert results[0]["fiscal_quarter"] == "Q4 2025"
    await client.close()


async def test_error_response_raises_twelvedata_error():
    client = await _make_client({"status": "error", "message": "Invalid API key"})
    with pytest.raises(TwelveDataError, match="Invalid API key"):
        await client.symbol_search("AAPL")
    await client.close()


async def test_non_200_raises_twelvedata_error():
    client = await _make_client({"message": "Server Error"}, status_code=500)
    with pytest.raises(TwelveDataError, match="HTTP 500"):
        await client.symbol_search("AAPL")
    await client.close()


async def test_rate_limiter_warns_when_approaching_limit(caplog):
    client = await _make_client({"data": []})
    # Simulate many timestamps in the last 60 seconds
    now = time.monotonic()
    client._request_timestamps = [now - i * 0.1 for i in range(489)]  # 489 existing

    with caplog.at_level(logging.WARNING):
        await client.symbol_search("TEST")  # This makes 490 -> above 80% of 610

    assert "Approaching rate limit" in caplog.text
    await client.close()
