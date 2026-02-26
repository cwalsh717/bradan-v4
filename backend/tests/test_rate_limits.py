"""Tests for rate limit tracking."""

from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import pytest

from app.services.twelvedata import RateLimitTracker, TwelveDataClient


class TestRateLimitTracker:
    """Test the in-memory rate limit tracker."""

    def test_initial_state(self):
        tracker = RateLimitTracker()
        status = tracker.get_status()
        assert status["calls_today"] == 0
        assert status["credits_used_today"] == 0
        assert status["last_call"] is None
        assert status["endpoints"] == {}

    def test_record_call_increments(self):
        tracker = RateLimitTracker()
        tracker.record_call("/profile", None)
        status = tracker.get_status()
        assert status["calls_today"] == 1
        assert status["credits_used_today"] == 1  # /profile = 1 credit
        assert status["last_call"] is not None

    def test_credit_costs(self):
        tracker = RateLimitTracker()
        tracker.record_call("/profile", None)           # 1 credit
        tracker.record_call("/income_statement", None)   # 100 credits
        tracker.record_call("/balance_sheet", None)      # 100 credits
        tracker.record_call("/cash_flow", None)          # 100 credits
        tracker.record_call("/time_series", None)        # 1 credit
        status = tracker.get_status()
        assert status["calls_today"] == 5
        assert status["credits_used_today"] == 302

    def test_endpoint_breakdown(self):
        tracker = RateLimitTracker()
        tracker.record_call("/profile", None)
        tracker.record_call("/profile", None)
        tracker.record_call("/time_series", None)
        status = tracker.get_status()
        assert status["endpoints"]["/profile"]["calls"] == 2
        assert status["endpoints"]["/profile"]["credits"] == 2
        assert status["endpoints"]["/time_series"]["calls"] == 1

    def test_parses_rate_limit_headers(self):
        tracker = RateLimitTracker()
        headers = {
            "x-ratelimit-used": "42",
            "x-ratelimit-remaining": "568",
        }
        tracker.record_call("/profile", headers)
        status = tracker.get_status()
        assert status["api_reported_used"] == 42
        assert status["api_reported_remaining"] == 568

    def test_daily_reset(self):
        tracker = RateLimitTracker()
        tracker.record_call("/profile", None)
        assert tracker.get_status()["calls_today"] == 1

        # Simulate date change
        tomorrow = datetime(2026, 3, 1, tzinfo=timezone.utc)
        with patch("app.services.twelvedata.datetime") as mock_dt:
            mock_dt.now.return_value = tomorrow
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            tracker._today = "2026-02-28"  # Force "yesterday"
            tracker._maybe_reset()

        assert tracker.get_status()["calls_today"] == 0

    def test_unknown_endpoint_defaults_to_1_credit(self):
        tracker = RateLimitTracker()
        tracker.record_call("/some_unknown_endpoint", None)
        assert tracker.get_status()["credits_used_today"] == 1


class TestTwelveDataClientRateTracking:
    """Test that the client records calls in the tracker."""

    @pytest.mark.asyncio
    async def test_get_records_to_tracker(self):
        client = TwelveDataClient(api_key="test_key")
        await client.client.aclose()

        # Mock transport that returns valid data
        def handler(request):
            return httpx.Response(
                200,
                json={"name": "Apple Inc"},
                headers={"x-ratelimit-used": "5", "x-ratelimit-remaining": "605"},
            )

        client.client = httpx.AsyncClient(
            base_url="https://api.twelvedata.com",
            transport=httpx.MockTransport(handler),
        )

        await client.get_stock_profile("AAPL")

        status = client.rate_tracker.get_status()
        assert status["calls_today"] == 1
        assert status["api_reported_used"] == 5
        assert status["api_reported_remaining"] == 605

        await client.close()
