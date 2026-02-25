"""Seed service for dashboard tickers."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard import DashboardTicker

logger = logging.getLogger(__name__)

# (category, symbol, display_name, data_source, display_format, display_order)
DASHBOARD_TICKERS: list[tuple[str, str, str, str, str, int]] = [
    # Equities
    ("equities", "SPY", "S&P 500 (SPY)", "twelvedata_ws", "price", 1),
    ("equities", "QQQ", "Nasdaq 100 (QQQ)", "twelvedata_ws", "price", 2),
    ("equities", "IWM", "Russell 2000 (IWM)", "twelvedata_ws", "price", 3),
    ("equities", "VIXY", "Volatility (VIXY)", "twelvedata_ws", "price", 4),
    ("equities", "UKX", "FTSE 100 (UKX)", "twelvedata_ws", "price", 5),
    ("equities", "EWJ", "Japan (EWJ)", "twelvedata_ws", "price", 6),
    ("equities", "FEZ", "Euro Stoxx 50 (FEZ)", "twelvedata_ws", "price", 7),
    ("equities", "EWH", "Hong Kong (EWH)", "twelvedata_ws", "price", 8),
    # Rates
    ("rates", "DGS2", "2-Year Treasury", "fred_daily", "percentage", 1),
    ("rates", "DGS10", "10-Year Treasury", "fred_daily", "percentage", 2),
    ("rates", "SPREAD_2S10S", "2s10s Spread", "fred_daily", "percentage", 3),
    # Credit
    ("credit", "BAMLC0A0CM", "IG Credit Spread", "fred_daily", "percentage", 1),
    ("credit", "BAMLH0A0HYM2", "HY Credit Spread", "fred_daily", "percentage", 2),
    # Currencies
    ("currencies", "UUP", "US Dollar (UUP)", "twelvedata_ws", "price", 1),
    # Commodities
    ("commodities", "USO", "Crude Oil (USO)", "twelvedata_ws", "price", 1),
    ("commodities", "UNG", "Natural Gas (UNG)", "twelvedata_ws", "price", 2),
    ("commodities", "GLD", "Gold (GLD)", "twelvedata_ws", "price", 3),
    # Critical Minerals
    ("critical_minerals", "CPER", "Copper (CPER)", "twelvedata_ws", "price", 1),
    ("critical_minerals", "URA", "Uranium (URA)", "twelvedata_ws", "price", 2),
    ("critical_minerals", "LIT", "Lithium (LIT)", "twelvedata_ws", "price", 3),
    ("critical_minerals", "REMX", "Rare Earth (REMX)", "twelvedata_ws", "price", 4),
    # Crypto
    ("crypto", "BTC/USD", "Bitcoin", "twelvedata_ws", "price", 1),
    ("crypto", "ETH/USD", "Ethereum", "twelvedata_ws", "price", 2),
    # Futures
    ("futures", "ES", "S&P 500 Futures (ES)", "twelvedata_ws", "price", 1),
    ("futures", "NQ", "Nasdaq Futures (NQ)", "twelvedata_ws", "price", 2),
    ("futures", "CL", "Crude Oil Futures (CL)", "twelvedata_ws", "price", 3),
    ("futures", "GC", "Gold Futures (GC)", "twelvedata_ws", "price", 4),
]


async def seed_dashboard_tickers(session: AsyncSession) -> int:
    """Seed dashboard tickers into the database.

    Uses a check-then-update/insert pattern keyed on symbol to ensure
    idempotent operation. Existing rows are updated to match the seed
    data; new rows are inserted.

    Returns the total number of tickers seeded (inserted + updated).
    """
    result = await session.execute(select(DashboardTicker))
    existing = {ticker.symbol: ticker for ticker in result.scalars().all()}

    inserted = 0
    updated = 0

    for category, symbol, display_name, data_source, display_format, display_order in (
        DASHBOARD_TICKERS
    ):
        if symbol in existing:
            ticker = existing[symbol]
            ticker.category = category
            ticker.display_name = display_name
            ticker.data_source = data_source
            ticker.display_format = display_format
            ticker.display_order = display_order
            ticker.is_active = True
            updated += 1
        else:
            session.add(
                DashboardTicker(
                    category=category,
                    symbol=symbol,
                    display_name=display_name,
                    data_source=data_source,
                    display_format=display_format,
                    display_order=display_order,
                    is_active=True,
                )
            )
            inserted += 1

    await session.commit()

    total = inserted + updated
    logger.info(
        "Dashboard tickers seeded: %d inserted, %d updated, %d total",
        inserted,
        updated,
        total,
    )
    return total
