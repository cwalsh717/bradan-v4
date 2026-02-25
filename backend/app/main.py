import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.exceptions import FredError, TwelveDataError
from app.models.dashboard import DashboardTicker
from app.routers import dashboard, dcf, stocks, utility
from app.services.fred import FredClient
from app.services.fred_scheduler import FredScheduler
from app.services.damodaran_seed import seed_damodaran_data
from app.services.glossary_service import seed_glossary
from app.services.seed import seed_dashboard_tickers
from app.services.twelvedata import TwelveDataClient
from app.services.ws_manager import TwelveDataWSManager
import app.dependencies as deps

logger = logging.getLogger(__name__)

app = FastAPI(title="Bradán v4", version="0.1.0")


@app.on_event("startup")
async def startup():
    # API clients
    deps.twelvedata_client = TwelveDataClient(settings.TWELVE_DATA_API_KEY)
    deps.fred_client = FredClient(settings.FRED_API_KEY)

    # Seed dashboard tickers + Damodaran reference data
    async with async_session() as session:
        await seed_dashboard_tickers(session)
    async with async_session() as session:
        await seed_damodaran_data(session)
    async with async_session() as session:
        await seed_glossary(session)

    # WebSocket manager — connect to Twelve Data and subscribe dashboard symbols
    deps.ws_manager = TwelveDataWSManager(settings.TWELVE_DATA_API_KEY)
    await deps.ws_manager.start()

    # Load dashboard symbols and subscribe
    async with async_session() as session:
        result = await session.execute(
            select(DashboardTicker.symbol).where(
                DashboardTicker.is_active.is_(True),
                DashboardTicker.data_source == "twelvedata_ws",
            )
        )
        ws_symbols = {row for row in result.scalars().all()}
    await deps.ws_manager.set_dashboard_symbols(ws_symbols)
    logger.info("Subscribed to %d dashboard WS symbols", len(ws_symbols))

    # FRED scheduler — daily fetch + in-memory cache
    deps.fred_scheduler = FredScheduler(
        client=deps.fred_client, session_factory=async_session
    )
    await deps.fred_scheduler.start()


@app.on_event("shutdown")
async def shutdown():
    if deps.fred_scheduler:
        deps.fred_scheduler.stop()
    if deps.ws_manager:
        await deps.ws_manager.stop()
    if deps.twelvedata_client:
        await deps.twelvedata_client.close()
    if deps.fred_client:
        await deps.fred_client.close()


@app.exception_handler(TwelveDataError)
async def twelvedata_error_handler(request: Request, exc: TwelveDataError):
    return JSONResponse(
        status_code=exc.status_code or 502,
        content={"error": "twelvedata", "message": exc.message},
    )


@app.exception_handler(FredError)
async def fred_error_handler(request: Request, exc: FredError):
    return JSONResponse(
        status_code=exc.status_code or 502,
        content={"error": "fred", "message": exc.message},
    )


app.include_router(utility.router)
app.include_router(stocks.router)
app.include_router(dashboard.router)
app.include_router(dcf.router)
