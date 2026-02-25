from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


from app.services.fred import FredClient
from app.services.fred_data import FredDataService


def _make_session():
    """Create a mock AsyncSession."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


def _make_client():
    """Create a mock FredClient."""
    client = AsyncMock(spec=FredClient)
    return client


# ---------- fetch_series ----------


async def test_fetch_series_upserts_and_returns_count():
    """fetch_series calls client.get_series, upserts rows, and returns the count."""
    client = _make_client()
    session = _make_session()

    client.get_series = AsyncMock(return_value=[
        {"date": "2024-01-02", "value": 3.88},
        {"date": "2024-01-03", "value": 3.92},
        {"date": "2024-01-04", "value": 3.95},
    ])

    service = FredDataService(client, session)
    count = await service.fetch_series("DGS10", observation_start="2024-01-01")

    assert count == 3
    client.get_series.assert_called_once_with(
        "DGS10", observation_start="2024-01-01"
    )
    session.execute.assert_called_once()
    session.commit.assert_called_once()


async def test_fetch_series_empty_returns_zero():
    """fetch_series returns 0 when the API returns no observations."""
    client = _make_client()
    session = _make_session()

    client.get_series = AsyncMock(return_value=[])

    service = FredDataService(client, session)
    count = await service.fetch_series("DGS10")

    assert count == 0
    session.execute.assert_not_called()
    session.commit.assert_not_called()


# ---------- fetch_all_series ----------


async def test_fetch_all_series_fetches_all_tracked():
    """fetch_all_series calls fetch_series for each of the 4 tracked series."""
    client = _make_client()
    session = _make_session()

    service = FredDataService(client, session)

    with patch.object(service, "fetch_series", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = 10
        results = await service.fetch_all_series(observation_start="2024-01-01")

    assert len(results) == 4
    assert set(results.keys()) == {"DGS10", "DGS2", "BAMLC0A0CM", "BAMLH0A0HYM2"}
    assert all(v == 10 for v in results.values())
    assert mock_fetch.call_count == 4


# ---------- fetch_daily_update ----------


async def test_fetch_daily_update_with_existing_data():
    """When existing data exists, fetch_series is called with the max observation date."""
    client = _make_client()
    session = _make_session()

    service = FredDataService(client, session)
    existing_date = date(2024, 6, 15)

    with (
        patch.object(
            service, "_get_max_observation_date", new_callable=AsyncMock
        ) as mock_max,
        patch.object(service, "fetch_series", new_callable=AsyncMock) as mock_fetch,
    ):
        mock_max.return_value = existing_date
        mock_fetch.return_value = 5

        results = await service.fetch_daily_update()

    assert len(results) == 4
    # Every call should use the existing date as observation_start
    for call_args in mock_fetch.call_args_list:
        assert call_args[0][1] == existing_date.isoformat()


async def test_fetch_daily_update_no_existing_data():
    """When no data exists, backfills from 1 year ago."""
    client = _make_client()
    session = _make_session()

    service = FredDataService(client, session)
    one_year_ago = (date.today() - timedelta(days=365)).isoformat()

    with (
        patch.object(
            service, "_get_max_observation_date", new_callable=AsyncMock
        ) as mock_max,
        patch.object(service, "fetch_series", new_callable=AsyncMock) as mock_fetch,
    ):
        mock_max.return_value = None
        mock_fetch.return_value = 250

        results = await service.fetch_daily_update()

    assert len(results) == 4
    assert all(v == 250 for v in results.values())
    # Every call should use one_year_ago
    for call_args in mock_fetch.call_args_list:
        assert call_args[0][1] == one_year_ago


# ---------- get_latest_value ----------


async def test_get_latest_value_found():
    """get_latest_value returns {date, value} when a row exists."""
    client = _make_client()
    session = _make_session()

    mock_row = MagicMock()
    mock_row.observation_date = date(2024, 6, 20)
    mock_row.value = Decimal("4.2500")

    mock_result = MagicMock()
    mock_result.first.return_value = mock_row
    session.execute = AsyncMock(return_value=mock_result)

    service = FredDataService(client, session)
    result = await service.get_latest_value("DGS10")

    assert result is not None
    assert result["date"] == "2024-06-20"
    assert result["value"] == 4.25


async def test_get_latest_value_not_found():
    """get_latest_value returns None when no row exists for the series."""
    client = _make_client()
    session = _make_session()

    mock_result = MagicMock()
    mock_result.first.return_value = None
    session.execute = AsyncMock(return_value=mock_result)

    service = FredDataService(client, session)
    result = await service.get_latest_value("NONEXIST")

    assert result is None
