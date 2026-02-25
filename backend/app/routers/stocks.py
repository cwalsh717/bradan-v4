"""Stock profile REST endpoints."""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_twelvedata
from app.models.stocks import (
    Dividend,
    EarningsCalendar,
    FinancialStatement,
    PriceHistory,
    Stock,
    StockSplit,
)
from app.schemas.stocks import (
    DividendRecord,
    FinancialRecord,
    PriceRecord,
    SplitRecord,
    StockEnvelope,
    StockProfile,
)
from app.services.stock_data import StockDataService
from app.services.ttm import TTMService
from app.services.twelvedata import TwelveDataClient

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

# Default TTL when no earnings calendar date is available.
_DEFAULT_TTL = timedelta(hours=24)


async def _get_stock_or_404(
    symbol: str, session: AsyncSession
) -> Stock:
    """Look up a stock by symbol and raise 404 if not found."""
    result = await session.execute(
        select(Stock).where(Stock.symbol == symbol.upper())
    )
    stock = result.scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Stock '{symbol}' not found")
    return stock


async def _next_refresh_for_stock(
    stock: Stock, data_as_of: Optional[datetime], session: AsyncSession
) -> Optional[datetime]:
    """Compute the next refresh timestamp.

    Uses the next upcoming earnings report date if available, otherwise
    falls back to data_as_of + 24 hours.
    """
    if data_as_of is None:
        return None

    # Try to find the next future earnings report date.
    result = await session.execute(
        select(EarningsCalendar.report_date)
        .where(
            EarningsCalendar.stock_id == stock.id,
            EarningsCalendar.report_date >= date.today(),
        )
        .order_by(EarningsCalendar.report_date.asc())
        .limit(1)
    )
    next_report: Optional[date] = result.scalar_one_or_none()

    if next_report is not None:
        return datetime.combine(next_report, datetime.min.time(), tzinfo=timezone.utc)

    return data_as_of + _DEFAULT_TTL


def _envelope(
    data,
    data_as_of: Optional[datetime],
    next_refresh: Optional[datetime],
) -> StockEnvelope:
    return StockEnvelope(data=data, data_as_of=data_as_of, next_refresh=next_refresh)


# ------------------------------------------------------------------
# GET /api/stocks/{symbol}/profile
# ------------------------------------------------------------------


@router.get("/{symbol}/profile", response_model=StockEnvelope)
async def get_stock_profile(
    symbol: str,
    session: AsyncSession = Depends(get_session),
    twelvedata: TwelveDataClient = Depends(get_twelvedata),
):
    """Return the stock profile, fetching from Twelve Data if not cached."""
    result = await session.execute(
        select(Stock).where(Stock.symbol == symbol.upper())
    )
    stock = result.scalar_one_or_none()

    if stock is None:
        svc = StockDataService(client=twelvedata, session=session)
        stock = await svc.fetch_full_profile(symbol)

    data_as_of = stock.last_updated
    next_refresh = await _next_refresh_for_stock(stock, data_as_of, session)

    return _envelope(
        data=StockProfile.model_validate(stock),
        data_as_of=data_as_of,
        next_refresh=next_refresh,
    )


# ------------------------------------------------------------------
# GET /api/stocks/{symbol}/financials
# ------------------------------------------------------------------


@router.get("/{symbol}/financials", response_model=StockEnvelope)
async def get_financials(
    symbol: str,
    period: str = Query("annual", pattern="^(annual|quarterly|ttm)$"),
    session: AsyncSession = Depends(get_session),
):
    """Return financial statements for a stock, with annual/quarterly/ttm periods."""
    stock = await _get_stock_or_404(symbol, session)

    if period == "ttm":
        ttm_svc = TTMService(session=session)
        ttm_data = await ttm_svc.compute_ttm(stock.id)

        if ttm_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"No quarterly data available to compute TTM for '{symbol}'",
            )

        data_as_of = stock.last_updated
        next_refresh = await _next_refresh_for_stock(stock, data_as_of, session)
        return _envelope(data=ttm_data, data_as_of=data_as_of, next_refresh=next_refresh)

    # annual or quarterly
    result = await session.execute(
        select(FinancialStatement)
        .where(
            FinancialStatement.stock_id == stock.id,
            FinancialStatement.period == period,
        )
        .order_by(FinancialStatement.fiscal_date.desc())
    )
    statements = result.scalars().all()

    records = [FinancialRecord.model_validate(s) for s in statements]
    data_as_of = stock.last_updated
    next_refresh = await _next_refresh_for_stock(stock, data_as_of, session)

    return _envelope(data=records, data_as_of=data_as_of, next_refresh=next_refresh)


# ------------------------------------------------------------------
# GET /api/stocks/{symbol}/price-history
# ------------------------------------------------------------------


@router.get("/{symbol}/price-history", response_model=StockEnvelope)
async def get_price_history(
    symbol: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Return daily price history for a stock with optional date range filtering."""
    stock = await _get_stock_or_404(symbol, session)

    query = select(PriceHistory).where(PriceHistory.stock_id == stock.id)

    if start_date is not None:
        query = query.where(PriceHistory.date >= start_date)
    if end_date is not None:
        query = query.where(PriceHistory.date <= end_date)

    query = query.order_by(PriceHistory.date.asc())

    result = await session.execute(query)
    rows = result.scalars().all()

    records = [PriceRecord.model_validate(r) for r in rows]
    data_as_of = stock.last_updated
    next_refresh = await _next_refresh_for_stock(stock, data_as_of, session)

    return _envelope(data=records, data_as_of=data_as_of, next_refresh=next_refresh)


# ------------------------------------------------------------------
# GET /api/stocks/{symbol}/dividends
# ------------------------------------------------------------------


@router.get("/{symbol}/dividends", response_model=StockEnvelope)
async def get_dividends(
    symbol: str,
    session: AsyncSession = Depends(get_session),
):
    """Return dividend history for a stock."""
    stock = await _get_stock_or_404(symbol, session)

    result = await session.execute(
        select(Dividend)
        .where(Dividend.stock_id == stock.id)
        .order_by(Dividend.ex_date.desc())
    )
    rows = result.scalars().all()

    records = [DividendRecord.model_validate(r) for r in rows]
    data_as_of = stock.last_updated
    next_refresh = await _next_refresh_for_stock(stock, data_as_of, session)

    return _envelope(data=records, data_as_of=data_as_of, next_refresh=next_refresh)


# ------------------------------------------------------------------
# GET /api/stocks/{symbol}/splits
# ------------------------------------------------------------------


@router.get("/{symbol}/splits", response_model=StockEnvelope)
async def get_splits(
    symbol: str,
    session: AsyncSession = Depends(get_session),
):
    """Return stock split history for a stock."""
    stock = await _get_stock_or_404(symbol, session)

    result = await session.execute(
        select(StockSplit)
        .where(StockSplit.stock_id == stock.id)
        .order_by(StockSplit.date.desc())
    )
    rows = result.scalars().all()

    records = [SplitRecord.model_validate(r) for r in rows]
    data_as_of = stock.last_updated
    next_refresh = await _next_refresh_for_stock(stock, data_as_of, session)

    return _envelope(data=records, data_as_of=data_as_of, next_refresh=next_refresh)
