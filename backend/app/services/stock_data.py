"""Stock data pipeline: fetches from Twelve Data and upserts into PostgreSQL."""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stocks import (
    Dividend,
    EarningsCalendar,
    FinancialStatement,
    PriceHistory,
    Stock,
    StockSplit,
)
from app.services.twelvedata import TwelveDataClient

logger = logging.getLogger(__name__)


def _parse_date(value: str) -> date:
    """Parse a date string in YYYY-MM-DD format."""
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_split_ratio(description: str) -> tuple[int, int]:
    """Parse a split ratio from a description like '4:1', '4-for-1 split', etc.

    Returns (ratio_to, ratio_from) — e.g. '4:1' means 4 new shares for 1 old share.
    """
    import re

    # Try "X:Y" format
    parts = description.strip().split(":")
    if len(parts) == 2:
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            pass

    # Try "X-for-Y" format (e.g. "4-for-1 split")
    match = re.search(r"(\d+)-for-(\d+)", description)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Fallback: 1:1 (no-op)
    logger.warning("Could not parse split ratio from description: %s", description)
    return 1, 1


class StockDataService:
    """Orchestrates fetching stock data from Twelve Data and upserting into
    the database. Each method is independently callable and handles its own
    error logging so partial failures don't crash the full pipeline.
    """

    def __init__(self, client: TwelveDataClient, session: AsyncSession):
        self.client = client
        self.session = session

    async def fetch_full_profile(self, symbol: str) -> Stock:
        """Fetch all data types for a symbol and return the Stock record.

        Fetches profile first (to get stock_id), then all other data types
        in sequence. Partial failures are logged but do not abort the pipeline.
        """
        stock = await self.fetch_profile(symbol)
        stock_id = stock.id

        fetch_tasks = [
            ("financials", self.fetch_financials),
            ("price_history", self.fetch_price_history),
            ("dividends", self.fetch_dividends),
            ("splits", self.fetch_splits),
            ("earnings", self.fetch_earnings),
        ]

        for task_name, fetch_fn in fetch_tasks:
            try:
                await fetch_fn(stock_id, symbol)
            except Exception:
                logger.exception(
                    "Failed to fetch %s for %s (stock_id=%d)",
                    task_name,
                    symbol,
                    stock_id,
                )

        # Update last_updated timestamp
        stock.last_updated = datetime.now(timezone.utc)
        self.session.add(stock)
        await self.session.commit()
        await self.session.refresh(stock)

        return stock

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    async def fetch_profile(self, symbol: str) -> Stock:
        """Fetch company profile from Twelve Data and upsert into stocks table."""
        profile = await self.client.get_stock_profile(symbol)

        stmt = pg_insert(Stock).values(
            symbol=profile.get("symbol", symbol).upper(),
            name=profile.get("name", symbol),
            exchange=profile.get("exchange"),
            sector=profile.get("sector"),
            industry=profile.get("industry"),
            currency=profile.get("currency"),
            last_updated=datetime.now(timezone.utc),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_={
                "name": stmt.excluded.name,
                "exchange": stmt.excluded.exchange,
                "sector": stmt.excluded.sector,
                "industry": stmt.excluded.industry,
                "currency": stmt.excluded.currency,
                "last_updated": stmt.excluded.last_updated,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()

        # Re-fetch the stock record to get its id
        result = await self.session.execute(
            select(Stock).where(Stock.symbol == profile.get("symbol", symbol).upper())
        )
        stock = result.scalar_one()
        return stock

    # ------------------------------------------------------------------
    # Financial Statements
    # ------------------------------------------------------------------

    async def fetch_financials(self, stock_id: int, symbol: str) -> int:
        """Fetch income, balance_sheet, and cash_flow statements for both
        annual and quarterly periods. Returns total number of rows upserted.
        """
        total = 0
        statement_fetchers = {
            "income": self.client.get_income_statement,
            "balance_sheet": self.client.get_balance_sheet,
            "cash_flow": self.client.get_cash_flow,
        }

        for statement_type, fetcher in statement_fetchers.items():
            for period in ("annual", "quarterly"):
                try:
                    rows = await fetcher(symbol, period=period)
                    count = await self._upsert_financial_statements(
                        stock_id, statement_type, period, rows
                    )
                    total += count
                    logger.info(
                        "Upserted %d %s/%s statements for %s",
                        count,
                        statement_type,
                        period,
                        symbol,
                    )
                except Exception:
                    logger.exception(
                        "Failed to fetch %s/%s for %s",
                        statement_type,
                        period,
                        symbol,
                    )

        return total

    async def _upsert_financial_statements(
        self,
        stock_id: int,
        statement_type: str,
        period: str,
        rows: list[dict],
    ) -> int:
        """Upsert a batch of financial statement rows."""
        if not rows:
            return 0

        count = 0
        for row in rows:
            fiscal_date_str = row.get("fiscal_date")
            if not fiscal_date_str:
                continue

            fiscal_date = _parse_date(fiscal_date_str)

            stmt = pg_insert(FinancialStatement).values(
                stock_id=stock_id,
                statement_type=statement_type,
                period=period,
                fiscal_date=fiscal_date,
                data=row,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_financial_statements_composite",
                set_={
                    "data": stmt.excluded.data,
                    "fetched_at": datetime.now(timezone.utc),
                },
            )
            await self.session.execute(stmt)
            count += 1

        await self.session.commit()
        return count

    # ------------------------------------------------------------------
    # Price History
    # ------------------------------------------------------------------

    async def fetch_price_history(self, stock_id: int, symbol: str) -> int:
        """Fetch daily price history. Append-only: finds the last stored date
        and only fetches the gap. Returns number of rows inserted.
        """
        # Find the last stored date for this stock
        result = await self.session.execute(
            select(PriceHistory.date)
            .where(PriceHistory.stock_id == stock_id)
            .order_by(PriceHistory.date.desc())
            .limit(1)
        )
        last_date: Optional[date] = result.scalar_one_or_none()

        # Build API params
        start_date: Optional[str] = None
        if last_date is not None:
            # Fetch from the day after the last stored date
            gap_start = last_date + timedelta(days=1)
            if gap_start > date.today():
                logger.info("Price history for %s is up to date", symbol)
                return 0
            start_date = gap_start.isoformat()

        candles = await self.client.get_time_series(
            symbol,
            interval="1day",
            start_date=start_date,
            outputsize=5000,
        )

        if not candles:
            logger.info("No new price data for %s", symbol)
            return 0

        count = 0
        for candle in candles:
            candle_date_str = candle.get("datetime")
            if not candle_date_str:
                continue

            candle_date = _parse_date(candle_date_str)

            stmt = pg_insert(PriceHistory).values(
                stock_id=stock_id,
                date=candle_date,
                open=Decimal(candle["open"]),
                high=Decimal(candle["high"]),
                low=Decimal(candle["low"]),
                close=Decimal(candle["close"]),
                volume=int(candle["volume"]) if candle.get("volume") else None,
            )
            stmt = stmt.on_conflict_do_nothing(
                constraint="uq_price_history_stock_date",
            )
            await self.session.execute(stmt)
            count += 1

        await self.session.commit()
        logger.info("Inserted %d price candles for %s", count, symbol)
        return count

    # ------------------------------------------------------------------
    # Dividends
    # ------------------------------------------------------------------

    async def fetch_dividends(self, stock_id: int, symbol: str) -> int:
        """Fetch dividend history and upsert. Returns number of rows upserted."""
        dividends = await self.client.get_dividends(symbol)
        if not dividends:
            logger.info("No dividend data for %s", symbol)
            return 0

        # Load existing ex_dates for this stock to avoid duplicates
        result = await self.session.execute(
            select(Dividend.ex_date).where(Dividend.stock_id == stock_id)
        )
        existing_dates: set[date] = {row for row in result.scalars().all()}

        count = 0
        for div in dividends:
            ex_date_str = div.get("ex_date")
            if not ex_date_str:
                continue

            ex_date = _parse_date(ex_date_str)

            if ex_date in existing_dates:
                continue

            self.session.add(
                Dividend(
                    stock_id=stock_id,
                    ex_date=ex_date,
                    amount=Decimal(str(div["amount"])),
                )
            )
            existing_dates.add(ex_date)
            count += 1

        await self.session.commit()
        logger.info("Inserted %d dividends for %s", count, symbol)
        return count

    # ------------------------------------------------------------------
    # Stock Splits
    # ------------------------------------------------------------------

    async def fetch_splits(self, stock_id: int, symbol: str) -> int:
        """Fetch stock split history and upsert. Returns number of rows upserted."""
        splits = await self.client.get_splits(symbol)
        if not splits:
            logger.info("No split data for %s", symbol)
            return 0

        # Load existing split dates for this stock
        result = await self.session.execute(
            select(StockSplit.date).where(StockSplit.stock_id == stock_id)
        )
        existing_dates: set[date] = {row for row in result.scalars().all()}

        count = 0
        for split in splits:
            date_str = split.get("date")
            if not date_str:
                continue

            split_date = _parse_date(date_str)

            if split_date in existing_dates:
                continue

            # Parse ratio — Twelve Data provides from_factor/to_factor fields
            # or a description like "4-for-1 split" or "4:1"
            # from_factor = new shares count, to_factor = old shares count
            if "from_factor" in split and "to_factor" in split:
                ratio_to = int(split["from_factor"])
                ratio_from = int(split["to_factor"])
            else:
                description = split.get("description", "1:1")
                ratio_to, ratio_from = _parse_split_ratio(description)

            self.session.add(
                StockSplit(
                    stock_id=stock_id,
                    date=split_date,
                    ratio_from=ratio_from,
                    ratio_to=ratio_to,
                )
            )
            existing_dates.add(split_date)
            count += 1

        await self.session.commit()
        logger.info("Inserted %d stock splits for %s", count, symbol)
        return count

    # ------------------------------------------------------------------
    # Earnings Calendar
    # ------------------------------------------------------------------

    async def fetch_earnings(self, stock_id: int, symbol: str) -> int:
        """Fetch earnings calendar and upsert. Returns number of rows upserted."""
        earnings = await self.client.get_earnings_calendar(symbol)
        if not earnings:
            logger.info("No earnings calendar data for %s", symbol)
            return 0

        # Load existing report_dates for this stock
        result = await self.session.execute(
            select(EarningsCalendar.report_date).where(
                EarningsCalendar.stock_id == stock_id
            )
        )
        existing_dates: set[date] = {row for row in result.scalars().all()}

        count = 0
        for earning in earnings:
            date_str = earning.get("date")
            if not date_str:
                continue

            report_date = _parse_date(date_str)

            if report_date in existing_dates:
                # Update existing record (confirmed status may change)
                existing = (
                    await self.session.execute(
                        select(EarningsCalendar).where(
                            EarningsCalendar.stock_id == stock_id,
                            EarningsCalendar.report_date == report_date,
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    existing.fiscal_quarter = earning.get("fiscal_quarter", "")
                    existing.confirmed = earning.get("confirmed", False)
                    existing.fetched_at = datetime.now(timezone.utc)
                continue

            self.session.add(
                EarningsCalendar(
                    stock_id=stock_id,
                    report_date=report_date,
                    fiscal_quarter=earning.get("fiscal_quarter", ""),
                    confirmed=earning.get("confirmed", False),
                )
            )
            existing_dates.add(report_date)
            count += 1

        await self.session.commit()
        logger.info("Upserted %d earnings records for %s", count, symbol)
        return count
