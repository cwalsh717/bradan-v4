from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.exceptions import FredError, TwelveDataError
from app.routers import utility
from app.services.fred import FredClient
from app.services.twelvedata import TwelveDataClient
import app.dependencies as deps

app = FastAPI(title="Bradán v4", version="0.1.0")


@app.on_event("startup")
async def startup():
    deps.twelvedata_client = TwelveDataClient(settings.TWELVE_DATA_API_KEY)
    deps.fred_client = FredClient(settings.FRED_API_KEY)


@app.on_event("shutdown")
async def shutdown():
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
