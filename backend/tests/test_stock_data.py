"""Tests for StockDataService — the stock data pipeline orchestrator."""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch


from app.services.stock_data import StockDataService, _parse_split_ratio
from app.services.twelvedata import TwelveDataClient


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _mock_session():
    """Create a mock AsyncSession with standard behaviour."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


def _mock_client():
    """Create a mock TwelveDataClient."""
    return AsyncMock(spec=TwelveDataClient)


def _make_stock(stock_id=1, symbol="AAPL"):
    """Create a mock Stock ORM object."""
    stock = MagicMock()
    stock.id = stock_id
    stock.symbol = symbol
    stock.last_updated = None
    return stock


# ------------------------------------------------------------------
# _parse_split_ratio (pure unit tests)
# ------------------------------------------------------------------


class TestParseSplitRatio:
    def test_valid_four_to_one(self):
        assert _parse_split_ratio("4:1") == (4, 1)

    def test_valid_two_to_one(self):
        assert _parse_split_ratio("2:1") == (2, 1)

    def test_valid_with_whitespace(self):
        assert _parse_split_ratio("  3:1  ") == (3, 1)

    def test_invalid_string_returns_fallback(self):
        assert _parse_split_ratio("not-a-ratio") == (1, 1)

    def test_empty_string_returns_fallback(self):
        assert _parse_split_ratio("") == (1, 1)

    def test_non_numeric_parts_returns_fallback(self):
        assert _parse_split_ratio("a:b") == (1, 1)

    def test_single_colon_no_numbers(self):
        assert _parse_split_ratio(":") == (1, 1)

    def test_reverse_split(self):
        """Reverse split like 1:10."""
        assert _parse_split_ratio("1:10") == (1, 10)


# ------------------------------------------------------------------
# fetch_profile
# ------------------------------------------------------------------


class TestFetchProfile:
    async def test_fetch_profile_upserts_and_returns_stock(self):
        """fetch_profile calls get_stock_profile, executes upsert, re-selects, returns Stock."""
        client = _mock_client()
        session = _mock_session()

        profile_data = {
            "symbol": "AAPL",
            "name": "Apple Inc",
            "exchange": "NASDAQ",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "currency": "USD",
        }
        client.get_stock_profile = AsyncMock(return_value=profile_data)

        mock_stock = _make_stock(stock_id=42, symbol="AAPL")
        # First execute -> pg_insert (no return needed)
        # Second execute -> re-select returning the stock
        select_result = MagicMock()
        select_result.scalar_one.return_value = mock_stock
        session.execute = AsyncMock(side_effect=[MagicMock(), select_result])

        service = StockDataService(client, session)
        stock = await service.fetch_profile("AAPL")

        assert stock.id == 42
        assert stock.symbol == "AAPL"
        client.get_stock_profile.assert_called_once_with("AAPL")
        assert session.execute.call_count == 2
        session.commit.assert_called_once()

    async def test_fetch_profile_uses_symbol_fallback_when_missing(self):
        """When the API returns no 'symbol' key, use the input symbol uppercased."""
        client = _mock_client()
        session = _mock_session()

        # profile missing 'symbol' key
        client.get_stock_profile = AsyncMock(return_value={"name": "Unknown Co"})

        mock_stock = _make_stock(stock_id=1, symbol="XYZ")
        select_result = MagicMock()
        select_result.scalar_one.return_value = mock_stock
        session.execute = AsyncMock(side_effect=[MagicMock(), select_result])

        service = StockDataService(client, session)
        stock = await service.fetch_profile("xyz")

        assert stock.symbol == "XYZ"
        client.get_stock_profile.assert_called_once_with("xyz")


# ------------------------------------------------------------------
# fetch_financials
# ------------------------------------------------------------------


class TestFetchFinancials:
    async def test_fetch_all_six_combinations(self):
        """Income, balance_sheet, cash_flow x annual, quarterly = 6 fetcher calls."""
        client = _mock_client()
        session = _mock_session()
        # Each fetcher returns one row
        sample_row = [{"fiscal_date": "2024-09-30", "revenue": "100000"}]
        client.get_income_statement = AsyncMock(return_value=sample_row)
        client.get_balance_sheet = AsyncMock(return_value=sample_row)
        client.get_cash_flow = AsyncMock(return_value=sample_row)

        # session.execute for each upsert — 6 combinations x 1 row each = 6 calls
        session.execute = AsyncMock(return_value=MagicMock())

        service = StockDataService(client, session)
        total = await service.fetch_financials(1, "AAPL")

        # 3 statement types x 2 periods x 1 row = 6
        assert total == 6
        # Each fetcher called twice (annual + quarterly)
        assert client.get_income_statement.call_count == 2
        assert client.get_balance_sheet.call_count == 2
        assert client.get_cash_flow.call_count == 2
        # Verify both period types were requested
        client.get_income_statement.assert_any_call("AAPL", period="annual")
        client.get_income_statement.assert_any_call("AAPL", period="quarterly")

    async def test_partial_failure_one_type_fails(self):
        """If one statement type fails, other types still proceed."""
        client = _mock_client()
        session = _mock_session()

        sample_row = [{"fiscal_date": "2024-09-30", "data": "ok"}]
        client.get_income_statement = AsyncMock(side_effect=Exception("API down"))
        client.get_balance_sheet = AsyncMock(return_value=sample_row)
        client.get_cash_flow = AsyncMock(return_value=sample_row)

        session.execute = AsyncMock(return_value=MagicMock())

        service = StockDataService(client, session)
        total = await service.fetch_financials(1, "AAPL")

        # income failed for both periods, balance_sheet + cash_flow = 2 types x 2 periods = 4 rows
        assert total == 4
        # balance_sheet and cash_flow still called
        assert client.get_balance_sheet.call_count == 2
        assert client.get_cash_flow.call_count == 2

    async def test_empty_rows_returns_zero(self):
        """Empty API response results in 0 upserts."""
        client = _mock_client()
        session = _mock_session()

        client.get_income_statement = AsyncMock(return_value=[])
        client.get_balance_sheet = AsyncMock(return_value=[])
        client.get_cash_flow = AsyncMock(return_value=[])

        service = StockDataService(client, session)
        total = await service.fetch_financials(1, "AAPL")

        assert total == 0
        # No execute calls for upserts (only commit calls if any)
        session.execute.assert_not_called()

    async def test_rows_without_fiscal_date_are_skipped(self):
        """Rows missing fiscal_date should be silently skipped."""
        client = _mock_client()
        session = _mock_session()

        rows_with_missing_date = [
            {"fiscal_date": "2024-09-30", "revenue": "100"},
            {"revenue": "200"},  # no fiscal_date
        ]
        client.get_income_statement = AsyncMock(return_value=rows_with_missing_date)
        client.get_balance_sheet = AsyncMock(return_value=[])
        client.get_cash_flow = AsyncMock(return_value=[])

        session.execute = AsyncMock(return_value=MagicMock())

        service = StockDataService(client, session)
        total = await service.fetch_financials(1, "AAPL")

        # Only the row with fiscal_date was upserted: 1 row x 2 periods = 2
        assert total == 2


# ------------------------------------------------------------------
# fetch_price_history
# ------------------------------------------------------------------


class TestFetchPriceHistory:
    async def test_first_fetch_full_history(self):
        """No existing data -> fetches full 5000 candles with no start_date."""
        client = _mock_client()
        session = _mock_session()

        # First execute -> last date query returning None
        last_date_result = MagicMock()
        last_date_result.scalar_one_or_none.return_value = None

        candles = [
            {
                "datetime": "2024-01-02",
                "open": "150.0",
                "high": "152.0",
                "low": "149.0",
                "close": "151.0",
                "volume": "50000000",
            },
            {
                "datetime": "2024-01-03",
                "open": "151.0",
                "high": "153.0",
                "low": "150.0",
                "close": "152.5",
                "volume": "45000000",
            },
        ]
        client.get_time_series = AsyncMock(return_value=candles)

        # session.execute: first call is the last-date query, rest are candle inserts
        session.execute = AsyncMock(
            side_effect=[last_date_result, MagicMock(), MagicMock()]
        )

        service = StockDataService(client, session)
        count = await service.fetch_price_history(1, "AAPL")

        assert count == 2
        client.get_time_series.assert_called_once_with(
            "AAPL", interval="1day", start_date=None, outputsize=5000
        )
        session.commit.assert_called_once()

    async def test_append_from_last_date(self):
        """Existing data -> gap fill from last_date + 1 day."""
        client = _mock_client()
        session = _mock_session()

        last_stored = date(2024, 6, 15)
        last_date_result = MagicMock()
        last_date_result.scalar_one_or_none.return_value = last_stored

        candles = [
            {
                "datetime": "2024-06-16",
                "open": "200.0",
                "high": "202.0",
                "low": "199.0",
                "close": "201.0",
                "volume": "30000000",
            },
        ]
        client.get_time_series = AsyncMock(return_value=candles)

        session.execute = AsyncMock(side_effect=[last_date_result, MagicMock()])

        service = StockDataService(client, session)
        count = await service.fetch_price_history(1, "AAPL")

        assert count == 1
        client.get_time_series.assert_called_once_with(
            "AAPL", interval="1day", start_date="2024-06-16", outputsize=5000
        )

    async def test_up_to_date_returns_zero(self):
        """Last stored date is today -> no fetch needed, return 0."""
        client = _mock_client()
        session = _mock_session()

        last_date_result = MagicMock()
        last_date_result.scalar_one_or_none.return_value = date.today()

        session.execute = AsyncMock(return_value=last_date_result)

        service = StockDataService(client, session)
        count = await service.fetch_price_history(1, "AAPL")

        assert count == 0
        client.get_time_series.assert_not_called()

    async def test_empty_candles_returns_zero(self):
        """API returns empty candles list -> 0 rows inserted."""
        client = _mock_client()
        session = _mock_session()

        last_date_result = MagicMock()
        last_date_result.scalar_one_or_none.return_value = None
        client.get_time_series = AsyncMock(return_value=[])

        session.execute = AsyncMock(return_value=last_date_result)

        service = StockDataService(client, session)
        count = await service.fetch_price_history(1, "AAPL")

        assert count == 0

    async def test_candle_without_datetime_skipped(self):
        """Candle rows missing 'datetime' key are skipped."""
        client = _mock_client()
        session = _mock_session()

        last_date_result = MagicMock()
        last_date_result.scalar_one_or_none.return_value = None

        candles = [
            {
                "open": "100.0",
                "high": "101.0",
                "low": "99.0",
                "close": "100.5",
                "volume": "100",
            },
            {
                "datetime": "2024-01-02",
                "open": "100.0",
                "high": "101.0",
                "low": "99.0",
                "close": "100.5",
                "volume": "100",
            },
        ]
        client.get_time_series = AsyncMock(return_value=candles)
        session.execute = AsyncMock(side_effect=[last_date_result, MagicMock()])

        service = StockDataService(client, session)
        count = await service.fetch_price_history(1, "AAPL")

        # Only one candle had datetime
        assert count == 1

    async def test_candle_without_volume(self):
        """Candle with no volume -> volume stored as None."""
        client = _mock_client()
        session = _mock_session()

        last_date_result = MagicMock()
        last_date_result.scalar_one_or_none.return_value = None

        candles = [
            {
                "datetime": "2024-01-02",
                "open": "100.0",
                "high": "101.0",
                "low": "99.0",
                "close": "100.5",
                # no "volume" key
            },
        ]
        client.get_time_series = AsyncMock(return_value=candles)
        session.execute = AsyncMock(side_effect=[last_date_result, MagicMock()])

        service = StockDataService(client, session)
        count = await service.fetch_price_history(1, "AAPL")

        assert count == 1


# ------------------------------------------------------------------
# fetch_dividends
# ------------------------------------------------------------------


class TestFetchDividends:
    async def test_insert_new_dividends(self):
        """New dividends are added via session.add."""
        client = _mock_client()
        session = _mock_session()

        client.get_dividends = AsyncMock(
            return_value=[
                {"ex_date": "2024-08-10", "amount": "0.25"},
                {"ex_date": "2024-11-10", "amount": "0.26"},
            ]
        )

        # Existing dates query returns empty set
        existing_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        existing_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=existing_result)

        service = StockDataService(client, session)
        count = await service.fetch_dividends(1, "AAPL")

        assert count == 2
        assert session.add.call_count == 2
        session.commit.assert_called_once()

    async def test_dedup_existing_dates_skipped(self):
        """Dividends with existing ex_dates are not re-inserted."""
        client = _mock_client()
        session = _mock_session()

        client.get_dividends = AsyncMock(
            return_value=[
                {"ex_date": "2024-08-10", "amount": "0.25"},
                {"ex_date": "2024-11-10", "amount": "0.26"},
            ]
        )

        # One date already exists
        existing_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [date(2024, 8, 10)]
        existing_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=existing_result)

        service = StockDataService(client, session)
        count = await service.fetch_dividends(1, "AAPL")

        assert count == 1  # only one new dividend
        assert session.add.call_count == 1

    async def test_empty_dividends_returns_zero(self):
        """No dividend data from API -> returns 0."""
        client = _mock_client()
        session = _mock_session()

        client.get_dividends = AsyncMock(return_value=[])

        service = StockDataService(client, session)
        count = await service.fetch_dividends(1, "AAPL")

        assert count == 0
        session.add.assert_not_called()

    async def test_dividend_without_ex_date_skipped(self):
        """Dividend rows missing ex_date are skipped."""
        client = _mock_client()
        session = _mock_session()

        client.get_dividends = AsyncMock(
            return_value=[
                {"amount": "0.25"},  # no ex_date
                {"ex_date": "2024-11-10", "amount": "0.26"},
            ]
        )

        existing_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        existing_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=existing_result)

        service = StockDataService(client, session)
        count = await service.fetch_dividends(1, "AAPL")

        assert count == 1
        assert session.add.call_count == 1


# ------------------------------------------------------------------
# fetch_splits
# ------------------------------------------------------------------


class TestFetchSplits:
    async def test_insert_new_splits_with_ratio_fields(self):
        """Splits with explicit ratio_from/ratio_to fields are used directly."""
        client = _mock_client()
        session = _mock_session()

        client.get_splits = AsyncMock(
            return_value=[
                {"date": "2020-08-31", "ratio_from": "1", "ratio_to": "4"},
            ]
        )

        existing_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        existing_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=existing_result)

        service = StockDataService(client, session)
        count = await service.fetch_splits(1, "AAPL")

        assert count == 1
        assert session.add.call_count == 1
        # Verify the StockSplit object
        added_obj = session.add.call_args[0][0]
        assert added_obj.ratio_to == 4
        assert added_obj.ratio_from == 1

    async def test_ratio_parsed_from_description(self):
        """When ratio_from/ratio_to absent, parse from description."""
        client = _mock_client()
        session = _mock_session()

        client.get_splits = AsyncMock(
            return_value=[
                {"date": "2020-08-31", "description": "4:1"},
            ]
        )

        existing_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        existing_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=existing_result)

        service = StockDataService(client, session)
        count = await service.fetch_splits(1, "AAPL")

        assert count == 1
        added_obj = session.add.call_args[0][0]
        assert added_obj.ratio_to == 4
        assert added_obj.ratio_from == 1

    async def test_unparseable_ratio_falls_back_to_one_one(self):
        """If description can't be parsed, fallback to 1:1."""
        client = _mock_client()
        session = _mock_session()

        client.get_splits = AsyncMock(
            return_value=[
                {"date": "2020-08-31", "description": "weird split"},
            ]
        )

        existing_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        existing_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=existing_result)

        service = StockDataService(client, session)
        count = await service.fetch_splits(1, "AAPL")

        assert count == 1
        added_obj = session.add.call_args[0][0]
        assert added_obj.ratio_to == 1
        assert added_obj.ratio_from == 1

    async def test_dedup_existing_split_dates_skipped(self):
        """Splits with existing dates are not re-inserted."""
        client = _mock_client()
        session = _mock_session()

        client.get_splits = AsyncMock(
            return_value=[
                {"date": "2020-08-31", "description": "4:1"},
                {"date": "2014-06-09", "description": "7:1"},
            ]
        )

        existing_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [date(2020, 8, 31)]
        existing_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=existing_result)

        service = StockDataService(client, session)
        count = await service.fetch_splits(1, "AAPL")

        assert count == 1  # only the 2014 split is new
        assert session.add.call_count == 1

    async def test_empty_splits_returns_zero(self):
        """No split data from API -> returns 0."""
        client = _mock_client()
        session = _mock_session()

        client.get_splits = AsyncMock(return_value=[])

        service = StockDataService(client, session)
        count = await service.fetch_splits(1, "AAPL")

        assert count == 0
        session.add.assert_not_called()


# ------------------------------------------------------------------
# fetch_earnings
# ------------------------------------------------------------------


class TestFetchEarnings:
    async def test_insert_new_earnings(self):
        """New earnings dates are added via session.add."""
        client = _mock_client()
        session = _mock_session()

        client.get_earnings_calendar = AsyncMock(
            return_value=[
                {"date": "2025-01-30", "fiscal_quarter": "Q1 2025", "confirmed": True},
                {"date": "2025-04-30", "fiscal_quarter": "Q2 2025", "confirmed": False},
            ]
        )

        existing_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        existing_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=existing_result)

        service = StockDataService(client, session)
        count = await service.fetch_earnings(1, "AAPL")

        assert count == 2
        assert session.add.call_count == 2
        session.commit.assert_called_once()

    async def test_update_existing_earnings_confirmed_status(self):
        """Existing earnings record is updated (e.g. confirmed status change)."""
        client = _mock_client()
        session = _mock_session()

        client.get_earnings_calendar = AsyncMock(
            return_value=[
                {"date": "2025-01-30", "fiscal_quarter": "Q1 2025", "confirmed": True},
            ]
        )

        # First execute: load existing report_dates
        existing_dates_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [date(2025, 1, 30)]
        existing_dates_result.scalars.return_value = scalars_mock

        # Second execute: fetch existing EarningsCalendar for update
        existing_earnings = MagicMock()
        existing_earnings.fiscal_quarter = "Q1 2025"
        existing_earnings.confirmed = False
        existing_earnings.fetched_at = None
        update_result = MagicMock()
        update_result.scalar_one_or_none.return_value = existing_earnings

        session.execute = AsyncMock(side_effect=[existing_dates_result, update_result])

        service = StockDataService(client, session)
        count = await service.fetch_earnings(1, "AAPL")

        # count is 0 because existing records are updated, not inserted
        assert count == 0
        # But the existing record was modified
        assert existing_earnings.confirmed is True
        assert existing_earnings.fiscal_quarter == "Q1 2025"

    async def test_empty_earnings_returns_zero(self):
        """No earnings data from API -> returns 0."""
        client = _mock_client()
        session = _mock_session()

        client.get_earnings_calendar = AsyncMock(return_value=[])

        service = StockDataService(client, session)
        count = await service.fetch_earnings(1, "AAPL")

        assert count == 0
        session.add.assert_not_called()

    async def test_earnings_without_date_skipped(self):
        """Earnings rows missing 'date' key are skipped."""
        client = _mock_client()
        session = _mock_session()

        client.get_earnings_calendar = AsyncMock(
            return_value=[
                {"fiscal_quarter": "Q1 2025", "confirmed": True},  # no 'date' key
                {"date": "2025-04-30", "fiscal_quarter": "Q2 2025", "confirmed": False},
            ]
        )

        existing_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        existing_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=existing_result)

        service = StockDataService(client, session)
        count = await service.fetch_earnings(1, "AAPL")

        assert count == 1
        assert session.add.call_count == 1

    async def test_mixed_new_and_existing_earnings(self):
        """Mix of new inserts and existing updates in one batch."""
        client = _mock_client()
        session = _mock_session()

        client.get_earnings_calendar = AsyncMock(
            return_value=[
                {
                    "date": "2025-01-30",
                    "fiscal_quarter": "Q1 2025",
                    "confirmed": True,
                },  # existing
                {
                    "date": "2025-04-30",
                    "fiscal_quarter": "Q2 2025",
                    "confirmed": False,
                },  # new
            ]
        )

        existing_dates_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [date(2025, 1, 30)]
        existing_dates_result.scalars.return_value = scalars_mock

        existing_earnings = MagicMock()
        existing_earnings.fiscal_quarter = "Q1 2025"
        existing_earnings.confirmed = False
        existing_earnings.fetched_at = None
        update_result = MagicMock()
        update_result.scalar_one_or_none.return_value = existing_earnings

        session.execute = AsyncMock(side_effect=[existing_dates_result, update_result])

        service = StockDataService(client, session)
        count = await service.fetch_earnings(1, "AAPL")

        # Only the new one counts as inserted
        assert count == 1
        assert session.add.call_count == 1
        # Existing one was updated in-place
        assert existing_earnings.confirmed is True


# ------------------------------------------------------------------
# fetch_full_profile (orchestrator)
# ------------------------------------------------------------------


class TestFetchFullProfile:
    async def test_calls_all_methods(self):
        """fetch_full_profile calls profile + all 5 data methods."""
        client = _mock_client()
        session = _mock_session()

        mock_stock = _make_stock(stock_id=42, symbol="AAPL")
        service = StockDataService(client, session)

        with (
            patch.object(
                service, "fetch_profile", new_callable=AsyncMock
            ) as mock_profile,
            patch.object(
                service, "fetch_financials", new_callable=AsyncMock
            ) as mock_fin,
            patch.object(
                service, "fetch_price_history", new_callable=AsyncMock
            ) as mock_prices,
            patch.object(
                service, "fetch_dividends", new_callable=AsyncMock
            ) as mock_divs,
            patch.object(
                service, "fetch_splits", new_callable=AsyncMock
            ) as mock_splits,
            patch.object(
                service, "fetch_earnings", new_callable=AsyncMock
            ) as mock_earnings,
        ):
            mock_profile.return_value = mock_stock

            result = await service.fetch_full_profile("AAPL")

            mock_profile.assert_called_once_with("AAPL")
            mock_fin.assert_called_once_with(42, "AAPL")
            mock_prices.assert_called_once_with(42, "AAPL")
            mock_divs.assert_called_once_with(42, "AAPL")
            mock_splits.assert_called_once_with(42, "AAPL")
            mock_earnings.assert_called_once_with(42, "AAPL")

            assert result.id == 42
            session.commit.assert_called_once()
            session.refresh.assert_called_once_with(mock_stock)

    async def test_partial_failure_resilience(self):
        """If one data method fails, others still run and last_updated is set."""
        client = _mock_client()
        session = _mock_session()

        mock_stock = _make_stock(stock_id=42, symbol="AAPL")
        service = StockDataService(client, session)

        with (
            patch.object(
                service, "fetch_profile", new_callable=AsyncMock
            ) as mock_profile,
            patch.object(
                service, "fetch_financials", new_callable=AsyncMock
            ) as mock_fin,
            patch.object(
                service, "fetch_price_history", new_callable=AsyncMock
            ) as mock_prices,
            patch.object(
                service, "fetch_dividends", new_callable=AsyncMock
            ) as mock_divs,
            patch.object(
                service, "fetch_splits", new_callable=AsyncMock
            ) as mock_splits,
            patch.object(
                service, "fetch_earnings", new_callable=AsyncMock
            ) as mock_earnings,
        ):
            mock_profile.return_value = mock_stock
            # Financials fails
            mock_fin.side_effect = Exception("API timeout on financials")
            # Price history fails too
            mock_prices.side_effect = Exception("Network error")

            result = await service.fetch_full_profile("AAPL")

            # Remaining methods still called despite earlier failures
            mock_divs.assert_called_once_with(42, "AAPL")
            mock_splits.assert_called_once_with(42, "AAPL")
            mock_earnings.assert_called_once_with(42, "AAPL")

            # last_updated was still set
            assert mock_stock.last_updated is not None
            session.add.assert_called_once_with(mock_stock)
            session.commit.assert_called_once()
            assert result.id == 42

    async def test_last_updated_is_utc_datetime(self):
        """last_updated should be set to a timezone-aware UTC datetime."""
        client = _mock_client()
        session = _mock_session()

        mock_stock = _make_stock(stock_id=1, symbol="AAPL")
        service = StockDataService(client, session)

        with (
            patch.object(
                service, "fetch_profile", new_callable=AsyncMock
            ) as mock_profile,
            patch.object(service, "fetch_financials", new_callable=AsyncMock),
            patch.object(service, "fetch_price_history", new_callable=AsyncMock),
            patch.object(service, "fetch_dividends", new_callable=AsyncMock),
            patch.object(service, "fetch_splits", new_callable=AsyncMock),
            patch.object(service, "fetch_earnings", new_callable=AsyncMock),
        ):
            mock_profile.return_value = mock_stock

            await service.fetch_full_profile("AAPL")

            ts = mock_stock.last_updated
            assert isinstance(ts, datetime)
            assert ts.tzinfo is not None
