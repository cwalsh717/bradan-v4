"""Pre-seed a single stock to validate live API response shapes.

Usage:
    cd backend && python -m scripts.preseed_single AAPL
"""

import asyncio
import logging
import sys

from sqlalchemy import func, select

from app.config import settings
from app.database import async_session
from app.models.stocks import (
    Dividend,
    EarningsCalendar,
    FinancialStatement,
    PriceHistory,
    Stock,
    StockSplit,
)
from app.services.stock_data import StockDataService
from app.services.twelvedata import TwelveDataClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    symbol = symbol.upper()

    logger.info("Pre-seeding %s against %s", symbol, settings.DATABASE_URL.split("@")[-1])

    client = TwelveDataClient(settings.TWELVE_DATA_API_KEY)

    try:
        async with async_session() as session:
            svc = StockDataService(client, session)
            stock = await svc.fetch_full_profile(symbol)

            logger.info("Stock record: id=%d symbol=%s name=%s sector=%s industry=%s",
                        stock.id, stock.symbol, stock.name, stock.sector, stock.industry)

        # Query row counts
        async with async_session() as session:
            stock_row = (await session.execute(
                select(Stock).where(Stock.symbol == symbol)
            )).scalar_one()
            sid = stock_row.id

            counts = {}
            for label, model, col in [
                ("financials", FinancialStatement, FinancialStatement.stock_id),
                ("price_history", PriceHistory, PriceHistory.stock_id),
                ("dividends", Dividend, Dividend.stock_id),
                ("splits", StockSplit, StockSplit.stock_id),
                ("earnings", EarningsCalendar, EarningsCalendar.stock_id),
            ]:
                result = await session.execute(
                    select(func.count()).where(col == sid)
                )
                counts[label] = result.scalar()

        print(f"\n{'='*50}")
        print(f"  Pre-seed results for {symbol}")
        print(f"{'='*50}")
        print(f"  Profile:    OK (id={stock_row.id}, sector={stock_row.sector})")
        for label, count in counts.items():
            status = "OK" if count > 0 else "EMPTY"
            print(f"  {label:14s} {count:>5d} rows  [{status}]")
        print(f"{'='*50}")

        # Financial statement breakdown
        async with async_session() as session:
            result = await session.execute(
                select(
                    FinancialStatement.statement_type,
                    FinancialStatement.period,
                    func.count(),
                ).where(
                    FinancialStatement.stock_id == sid
                ).group_by(
                    FinancialStatement.statement_type,
                    FinancialStatement.period,
                )
            )
            print("\n  Financial statement breakdown:")
            for st_type, period, cnt in result.all():
                print(f"    {st_type}/{period}: {cnt} rows")

        all_ok = all(c > 0 for c in counts.values())
        if all_ok:
            print(f"\n  All data types populated for {symbol}. Safe to run full pre-seed.")
        else:
            empty = [k for k, v in counts.items() if v == 0]
            print(f"\n  WARNING: Empty tables: {empty}")
            print("  Investigate before running full pre-seed.")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
