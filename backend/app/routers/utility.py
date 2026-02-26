from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import engine, get_session
from app.dependencies import get_fred, get_twelvedata
from app.models.shared import Glossary
from app.services.fred import FredClient
from app.services.fred_data import FredDataService
from app.services.search import SearchService
from app.services.twelvedata import TwelveDataClient

router = APIRouter()


@router.get("/health")
async def health_check():
    db_status = "disconnected"
    table_count = 0

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            result = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
            )
            table_count = result.scalar()
            db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "database": db_status,
        "version": "0.1.0",
        "environment": settings.APP_ENV,
        "tables": table_count,
    }


@router.get("/api/search")
async def search_stocks(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_session),
    twelvedata: TwelveDataClient = Depends(get_twelvedata),
):
    service = SearchService(twelvedata)
    results = await service.search(q, db)
    now = datetime.now(timezone.utc)
    return {"data": results, "data_as_of": now.isoformat(), "next_refresh": None}


@router.get("/api/rates/risk-free")
async def get_risk_free_rate(
    db: AsyncSession = Depends(get_session),
    fred: FredClient = Depends(get_fred),
):
    service = FredDataService(client=fred, session=db)
    result = await service.get_latest_value("DGS10")

    if result is None:
        return JSONResponse(
            status_code=503,
            content={"message": "FRED data not available"},
        )

    now = datetime.now(timezone.utc)
    next_day = now + timedelta(days=1)

    return {
        "data": {
            "series_id": "DGS10",
            "value": result["value"],
            "date": result["date"],
        },
        "data_as_of": now.isoformat(),
        "next_refresh": next_day.isoformat(),
    }


@router.get("/api/system/rate-status")
async def rate_status(
    twelvedata: TwelveDataClient = Depends(get_twelvedata),
):
    """Return current Twelve Data API rate limit usage."""
    return twelvedata.rate_tracker.get_status()


@router.get("/api/glossary")
async def get_glossary(db: AsyncSession = Depends(get_session)):
    """Return all glossary entries ordered by category and term."""
    result = await db.execute(
        select(Glossary).order_by(Glossary.category, Glossary.technical_term)
    )
    entries = result.scalars().all()
    return {
        "data": [
            {
                "technical_term": e.technical_term,
                "display_label": e.display_label,
                "technical_label": e.technical_label,
                "tooltip": e.tooltip,
                "category": e.category,
                "learn_more_url": e.learn_more_url,
            }
            for e in entries
        ]
    }
