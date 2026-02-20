import httpx
import pytest

from app.exceptions import FredError
from app.services.fred import FredClient
from tests.conftest import make_fred_transport


async def _make_client(response_data, status_code=200):
    client = FredClient(api_key="test_key")
    await client.client.aclose()
    client.client = httpx.AsyncClient(
        base_url="https://api.stlouisfed.org",
        transport=make_fred_transport(response_data, status_code),
    )
    return client


async def test_get_series_returns_date_value_dicts():
    client = await _make_client({
        "observations": [
            {"date": "2025-01-10", "value": "4.25"},
            {"date": "2025-01-11", "value": "4.30"},
        ]
    })
    results = await client.get_series("DGS10")
    assert len(results) == 2
    assert results[0] == {"date": "2025-01-10", "value": 4.25}
    assert results[1] == {"date": "2025-01-11", "value": 4.30}
    await client.close()


async def test_get_series_filters_missing_data():
    client = await _make_client({
        "observations": [
            {"date": "2025-01-10", "value": "4.25"},
            {"date": "2025-01-11", "value": "."},
            {"date": "2025-01-12", "value": "4.35"},
        ]
    })
    results = await client.get_series("DGS10")
    assert len(results) == 2
    assert all(r["value"] != "." for r in results)
    await client.close()


async def test_get_latest_returns_single_observation():
    client = await _make_client({
        "observations": [
            {"date": "2025-01-12", "value": "4.35"},
        ]
    })
    result = await client.get_latest("DGS10")
    assert result == {"date": "2025-01-12", "value": 4.35}
    await client.close()


async def test_error_response_raises_fred_error():
    client = await _make_client({
        "error_code": 400,
        "error_message": "Bad Request: series_id is required",
    })
    with pytest.raises(FredError, match="series_id is required"):
        await client.get_series("INVALID")
    await client.close()


async def test_non_200_raises_fred_error():
    client = await _make_client({"message": "Server Error"}, status_code=500)
    with pytest.raises(FredError, match="HTTP 500"):
        await client.get_series("DGS10")
    await client.close()
