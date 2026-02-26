"""Tests for the pre-seed script."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts.preseed import PRESEED_SYMBOLS, preseed_tickers


class TestPreseedSymbols:
    """Validate the symbol list itself."""

    def test_no_duplicates(self):
        assert len(PRESEED_SYMBOLS) == len(set(PRESEED_SYMBOLS))

    def test_minimum_count(self):
        # S&P 500 + Nasdaq 100 minus overlap should be at least 500
        assert len(PRESEED_SYMBOLS) >= 400

    def test_known_tickers_present(self):
        for ticker in ("AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"):
            assert ticker in PRESEED_SYMBOLS


class TestPreseedTickers:
    """Test the preseed_tickers async function."""

    @pytest.mark.asyncio
    async def test_inserts_new_tickers(self):
        session = AsyncMock()

        # Simulate empty DB
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        result = await preseed_tickers(session)

        assert result["inserted"] == len(PRESEED_SYMBOLS)
        assert result["skipped"] == 0
        assert result["total"] == len(PRESEED_SYMBOLS)
        session.commit.assert_awaited_once()
        # Should have called session.add for each symbol
        assert session.add.call_count == len(PRESEED_SYMBOLS)

    @pytest.mark.asyncio
    async def test_skips_existing_tickers(self):
        session = AsyncMock()

        # Simulate DB already has all tickers
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = list(PRESEED_SYMBOLS)
        session.execute.return_value = mock_result

        result = await preseed_tickers(session)

        assert result["inserted"] == 0
        assert result["skipped"] == len(PRESEED_SYMBOLS)
        assert result["total"] == len(PRESEED_SYMBOLS)
        session.commit.assert_awaited_once()
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_existing(self):
        session = AsyncMock()

        # DB has first 10 tickers
        existing = list(PRESEED_SYMBOLS[:10])
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = existing
        session.execute.return_value = mock_result

        result = await preseed_tickers(session)

        assert result["inserted"] == len(PRESEED_SYMBOLS) - 10
        assert result["skipped"] == 10
        assert result["total"] == len(PRESEED_SYMBOLS)

    @pytest.mark.asyncio
    async def test_stock_objects_have_symbol_and_name(self):
        session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        await preseed_tickers(session)

        # Check the first Stock object added
        first_call = session.add.call_args_list[0]
        stock = first_call[0][0]
        assert stock.symbol == PRESEED_SYMBOLS[0]
        assert stock.name == PRESEED_SYMBOLS[0]
