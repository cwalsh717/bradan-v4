"""Dashboard REST and WebSocket endpoints."""

import asyncio
from collections import defaultdict

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_fred_scheduler, get_ws_manager
from app.models.dashboard import DashboardTicker

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ------------------------------------------------------------------
# GET /api/dashboard/config
# ------------------------------------------------------------------


@router.get("/config")
async def get_dashboard_config(
    session: AsyncSession = Depends(get_session),
):
    """Return active dashboard tickers grouped by category."""
    result = await session.execute(
        select(DashboardTicker)
        .where(DashboardTicker.is_active.is_(True))
        .order_by(DashboardTicker.category, DashboardTicker.display_order)
    )
    tickers = result.scalars().all()

    grouped: dict[str, list[dict]] = defaultdict(list)
    for t in tickers:
        grouped[t.category].append(
            {
                "id": t.id,
                "symbol": t.symbol,
                "display_name": t.display_name,
                "data_source": t.data_source,
                "display_format": t.display_format,
                "display_order": t.display_order,
            }
        )

    categories = [{"name": name, "tickers": items} for name, items in grouped.items()]

    return {"categories": categories}


# ------------------------------------------------------------------
# WS /api/dashboard/stream
# ------------------------------------------------------------------


@router.websocket("/stream")
async def dashboard_stream(
    websocket: WebSocket,
    session: AsyncSession = Depends(get_session),
):
    """Stream live dashboard prices to the connected client.

    Reads from the in-memory WS manager (for twelvedata_ws symbols) and
    FRED scheduler (for fred_daily symbols), then pushes a snapshot every
    second.
    """
    await websocket.accept()

    ws_mgr = get_ws_manager()
    fred_sched = get_fred_scheduler()

    # Load dashboard tickers to know which symbols / sources to include.
    result = await session.execute(
        select(DashboardTicker).where(DashboardTicker.is_active.is_(True))
    )
    tickers = result.scalars().all()

    try:
        while True:
            prices: dict[str, dict] = {}

            for t in tickers:
                if t.data_source == "twelvedata_ws" and ws_mgr is not None:
                    price_data = ws_mgr.get_price(t.symbol)
                    if price_data is not None:
                        prices[t.symbol] = price_data
                elif t.data_source == "fred_daily" and fred_sched is not None:
                    fred_data = fred_sched.get_value(t.symbol)
                    if fred_data is not None:
                        prices[t.symbol] = fred_data

            await websocket.send_json({"prices": prices})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
