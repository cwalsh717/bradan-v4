import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shared import FredSeries
from app.services.fred import FredClient

logger = logging.getLogger(__name__)


class FredDataService:
    """Fetches FRED series data and upserts into the database."""

    TRACKED_SERIES = ["DGS10", "DGS2", "BAMLC0A0CM", "BAMLH0A0HYM2"]

    def __init__(self, client: FredClient, session: AsyncSession):
        self.client = client
        self.session = session

    async def fetch_series(
        self,
        series_id: str,
        observation_start: Optional[str] = None,
    ) -> int:
        """Fetch a single FRED series and upsert into fred_series table.

        Returns the number of rows upserted.
        """
        logger.info(
            "Fetching FRED series %s from %s",
            series_id,
            observation_start or "all available",
        )
        observations = await self.client.get_series(
            series_id, observation_start=observation_start
        )

        if not observations:
            logger.info("No observations returned for %s", series_id)
            return 0

        rows = [
            {
                "series_id": series_id,
                "observation_date": obs["date"],
                "value": Decimal(str(obs["value"])),
            }
            for obs in observations
        ]

        stmt = pg_insert(FredSeries).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_fred_series_composite",
            set_={
                "value": stmt.excluded.value,
                "fetched_at": func.now(),
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()

        logger.info(
            "Upserted %d observations for %s", len(rows), series_id
        )
        return len(rows)

    async def fetch_all_series(
        self,
        observation_start: Optional[str] = None,
    ) -> dict[str, int]:
        """Fetch all tracked series.

        Returns a dict mapping series_id to the number of rows upserted.
        """
        results = {}
        for series_id in self.TRACKED_SERIES:
            count = await self.fetch_series(series_id, observation_start)
            results[series_id] = count
        return results

    async def fetch_daily_update(self) -> dict[str, int]:
        """Incremental update: for each tracked series, fetch only data newer
        than the latest observation already stored in the database.

        If no data exists for a series, backfills the last year.

        Returns a dict mapping series_id to the number of rows upserted.
        """
        results = {}
        one_year_ago = (date.today() - timedelta(days=365)).isoformat()

        for series_id in self.TRACKED_SERIES:
            latest_date = await self._get_max_observation_date(series_id)

            if latest_date is not None:
                observation_start = latest_date.isoformat()
                logger.info(
                    "Daily update for %s: fetching from %s",
                    series_id,
                    observation_start,
                )
            else:
                observation_start = one_year_ago
                logger.info(
                    "No existing data for %s: backfilling from %s",
                    series_id,
                    observation_start,
                )

            count = await self.fetch_series(series_id, observation_start)
            results[series_id] = count

        return results

    async def get_latest_value(
        self, series_id: str
    ) -> Optional[dict]:
        """Query DB for the most recent observation of a series.

        Returns {date, value} or None if no data exists.
        """
        stmt = (
            select(FredSeries.observation_date, FredSeries.value)
            .where(FredSeries.series_id == series_id)
            .order_by(FredSeries.observation_date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.first()

        if row is None:
            return None

        return {
            "date": row.observation_date.isoformat(),
            "value": float(row.value),
        }

    async def _get_max_observation_date(
        self, series_id: str
    ) -> Optional[date]:
        """Get the latest observation_date stored for a given series."""
        stmt = select(func.max(FredSeries.observation_date)).where(
            FredSeries.series_id == series_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
