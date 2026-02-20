from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import engine, get_session
from app.dependencies import get_twelvedata
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
    return {"results": results}
