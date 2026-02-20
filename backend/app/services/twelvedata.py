import logging
import time
from typing import List, Optional

import httpx

from app.exceptions import TwelveDataError

logger = logging.getLogger(__name__)

BASE_URL = "https://api.twelvedata.com"
RATE_LIMIT = 610  # credits per minute


class TwelveDataClient:
    """Async client for Twelve Data REST API.

    Pro tier: 610 API credits/minute.
    Key endpoints and their credit costs:
    - /time_series: 1 credit per symbol
    - /income_statement: 100 credits per symbol
    - /balance_sheet: 100 credits per symbol
    - /cash_flow: 100 credits per symbol
    - /profile: 1 credit per symbol
    - /dividends: 1 credit per symbol
    - /splits: 1 credit per symbol
    - /earnings_calendar: 1 credit per symbol
    - /symbol_search: 1 credit
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)
        self._request_timestamps: List[float] = []

    async def close(self):
        await self.client.aclose()

    def _track_request(self):
        now = time.monotonic()
        self._request_timestamps = [
            t for t in self._request_timestamps if now - t < 60
        ]
        self._request_timestamps.append(now)
        count = len(self._request_timestamps)
        if count > RATE_LIMIT * 0.8:
            logger.warning("Approaching rate limit: %d requests in last 60s", count)

    async def _get(self, endpoint: str, params: dict) -> dict:
        params["apikey"] = self.api_key
        self._track_request()
        symbol = params.get("symbol", "")
        logger.debug("Twelve Data API call: %s symbol=%s", endpoint, symbol)

        resp = await self.client.get(endpoint, params=params)
        if resp.status_code != 200:
            raise TwelveDataError(
                f"HTTP {resp.status_code} from {endpoint}", resp.status_code
            )

        data = resp.json()
        if data.get("status") == "error":
            raise TwelveDataError(data.get("message", "Unknown error"))

        return data

    async def symbol_search(self, query: str) -> List[dict]:
        """Search for stocks by name or symbol."""
        data = await self._get("/symbol_search", {"symbol": query})
        return data.get("data", [])

    async def get_stock_profile(self, symbol: str) -> dict:
        """Get company profile."""
        return await self._get("/profile", {"symbol": symbol})

    async def get_time_series(
        self,
        symbol: str,
        interval: str = "1day",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        outputsize: int = 5000,
    ) -> List[dict]:
        """Get historical OHLCV data. outputsize max is 5000 per request."""
        params = {"symbol": symbol, "interval": interval, "outputsize": outputsize}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        data = await self._get("/time_series", params)
        return data.get("values", [])

    async def get_income_statement(
        self, symbol: str, period: str = "quarterly"
    ) -> List[dict]:
        """Get income statements. 100 credits per call."""
        data = await self._get(
            "/income_statement", {"symbol": symbol, "period": period}
        )
        return data.get("income_statement", [])

    async def get_balance_sheet(
        self, symbol: str, period: str = "quarterly"
    ) -> List[dict]:
        """Get balance sheets. 100 credits per call."""
        data = await self._get(
            "/balance_sheet", {"symbol": symbol, "period": period}
        )
        return data.get("balance_sheet", [])

    async def get_cash_flow(
        self, symbol: str, period: str = "quarterly"
    ) -> List[dict]:
        """Get cash flow statements. 100 credits per call."""
        data = await self._get("/cash_flow", {"symbol": symbol, "period": period})
        return data.get("cash_flow", [])

    async def get_dividends(self, symbol: str) -> List[dict]:
        """Get dividend history."""
        data = await self._get("/dividends", {"symbol": symbol})
        return data.get("dividends", [])

    async def get_splits(self, symbol: str) -> List[dict]:
        """Get stock split history."""
        data = await self._get("/splits", {"symbol": symbol})
        return data.get("splits", [])

    async def get_earnings_calendar(self, symbol: str) -> List[dict]:
        """Get upcoming and past earnings dates."""
        data = await self._get("/earnings_calendar", {"symbol": symbol})
        return data.get("earnings_calendar", [])
