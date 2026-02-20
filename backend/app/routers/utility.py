from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.database import engine

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
