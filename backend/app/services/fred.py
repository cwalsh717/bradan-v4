import logging
from typing import List, Optional

import httpx

from app.exceptions import FredError

logger = logging.getLogger(__name__)

BASE_URL = "https://api.stlouisfed.org"


class FredClient:
    """Async client for FRED (Federal Reserve Economic Data) API.

    Key series we use:
    - DGS10: 10-Year Treasury Yield (risk-free rate for DCF)
    - DGS2: 2-Year Treasury Yield
    - BAMLC0A0CM: IG Corporate Bond Spread
    - BAMLH0A0HYM2: HY Corporate Bond Spread
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def _get(self, endpoint: str, params: dict) -> dict:
        params["api_key"] = self.api_key
        params["file_type"] = "json"
        logger.debug("FRED API call: %s params=%s", endpoint, {k: v for k, v in params.items() if k != "api_key"})

        resp = await self.client.get(endpoint, params=params)
        if resp.status_code != 200:
            raise FredError(
                f"HTTP {resp.status_code} from {endpoint}", resp.status_code
            )

        data = resp.json()
        if "error_code" in data:
            raise FredError(data.get("error_message", "Unknown error"))

        return data

    async def get_series(
        self,
        series_id: str,
        observation_start: Optional[str] = None,
        observation_end: Optional[str] = None,
    ) -> List[dict]:
        """Get observations for a FRED series.
        Filters out entries where value is '.' (FRED uses '.' for missing data).
        Returns list of {date, value} dicts.
        """
        params = {"series_id": series_id}
        if observation_start:
            params["observation_start"] = observation_start
        if observation_end:
            params["observation_end"] = observation_end

        data = await self._get("/fred/series/observations", params)

        results = []
        for obs in data.get("observations", []):
            if obs.get("value") == ".":
                continue
            results.append({
                "date": obs["date"],
                "value": float(obs["value"]),
            })
        return results

    async def get_latest(self, series_id: str) -> dict:
        """Get the most recent observation for a series."""
        params = {
            "series_id": series_id,
            "sort_order": "desc",
            "limit": "1",
        }
        data = await self._get("/fred/series/observations", params)

        for obs in data.get("observations", []):
            if obs.get("value") == ".":
                continue
            return {"date": obs["date"], "value": float(obs["value"])}

        raise FredError(f"No valid observations for {series_id}")
