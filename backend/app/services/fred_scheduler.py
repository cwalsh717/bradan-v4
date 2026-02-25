import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.fred import FredClient
from app.services.fred_data import FredDataService

logger = logging.getLogger(__name__)

TRACKED_SERIES = FredDataService.TRACKED_SERIES
SPREAD_KEY = "SPREAD_2S10S"
FETCH_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours


class FredScheduler:
    """Background scheduler that fetches FRED data daily and maintains
    an in-memory cache of latest values for fast dashboard reads."""

    def __init__(
        self,
        client: FredClient,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self.client = client
        self.session_factory = session_factory
        self.latest_values: dict[str, dict] = {}
        self._task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Public cache accessors
    # ------------------------------------------------------------------

    def get_value(self, series_id: str) -> Optional[dict]:
        """Return the cached latest value for a single FRED series."""
        return self.latest_values.get(series_id)

    def get_all_values(self) -> dict[str, dict]:
        """Return all cached values (for dashboard fan-out)."""
        return dict(self.latest_values)

    # ------------------------------------------------------------------
    # Fetch logic
    # ------------------------------------------------------------------

    async def fetch_and_cache(self) -> None:
        """Create a DB session, run the daily FRED fetch, then populate
        the in-memory cache with the latest value for each series plus
        the computed 2s10s spread."""
        logger.info("FRED scheduler: starting fetch_and_cache")
        async with self.session_factory() as session:
            try:
                service = FredDataService(self.client, session)
                results = await service.fetch_daily_update()
                logger.info(
                    "FRED scheduler: fetch_daily_update returned %s", results
                )

                now = datetime.now(timezone.utc)

                for series_id in TRACKED_SERIES:
                    latest = await service.get_latest_value(series_id)
                    if latest is not None:
                        self.latest_values[series_id] = {
                            "value": latest["value"],
                            "date": latest["date"],
                            "updated_at": now,
                        }
                    else:
                        logger.warning(
                            "FRED scheduler: no data for %s", series_id
                        )

                self._compute_spread(now)
                logger.info(
                    "FRED scheduler: cache populated with %d entries",
                    len(self.latest_values),
                )
            except Exception:
                logger.exception("FRED scheduler: fetch_and_cache failed")

    def _compute_spread(self, now: datetime) -> None:
        """Compute SPREAD_2S10S = DGS10 - DGS2 and store in the cache."""
        dgs10 = self.latest_values.get("DGS10")
        dgs2 = self.latest_values.get("DGS2")

        if dgs10 is None or dgs2 is None:
            logger.warning(
                "FRED scheduler: cannot compute spread — missing DGS10 or DGS2"
            )
            return

        spread = round(dgs10["value"] - dgs2["value"], 4)
        # Use the more recent date of the two underlying series
        spread_date = max(dgs10["date"], dgs2["date"])

        self.latest_values[SPREAD_KEY] = {
            "value": spread,
            "date": spread_date,
            "updated_at": now,
        }
        logger.info("FRED scheduler: SPREAD_2S10S = %.4f", spread)

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Run an initial fetch immediately, then schedule a background
        task that repeats every 24 hours."""
        logger.info("FRED scheduler: starting")
        await self.fetch_and_cache()
        self._task = asyncio.create_task(self._run_loop())

    async def _run_loop(self) -> None:
        """Background loop that fetches every FETCH_INTERVAL_SECONDS."""
        while True:
            try:
                await asyncio.sleep(FETCH_INTERVAL_SECONDS)
                await self.fetch_and_cache()
            except asyncio.CancelledError:
                logger.info("FRED scheduler: background loop cancelled")
                raise
            except Exception:
                logger.exception(
                    "FRED scheduler: error in background loop, "
                    "will retry next cycle"
                )

    def stop(self) -> None:
        """Cancel the background task if running."""
        if self._task is not None:
            self._task.cancel()
            logger.info("FRED scheduler: stopped")
            self._task = None
