"""Portfolio CRUD, holdings, performance, and snapshot history endpoints."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.dependencies as deps

from app.auth import get_current_user
from app.database import get_session
from app.models.stocks import Stock
from app.models.users import PortfolioHolding, User
from app.schemas.portfolio import (
    HoldingCreate,
    HoldingResponse,
    PerformanceSummary,
    PortfolioCreate,
    PortfolioResponse,
    PortfolioUpdate,
    SnapshotResponse,
)
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])


# ------------------------------------------------------------------
# GET /api/portfolios
# ------------------------------------------------------------------


@router.get("", response_model=list[PortfolioResponse])
async def list_portfolios(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all portfolios for the authenticated user."""
    svc = PortfolioService(session=session, ws_manager=deps.ws_manager)
    portfolios = await svc.list_portfolios(user.id)

    if not portfolios:
        return []

    # Count holdings per portfolio in a single query
    counts_result = await session.execute(
        select(PortfolioHolding.portfolio_id, func.count(PortfolioHolding.id))
        .where(PortfolioHolding.portfolio_id.in_([p.id for p in portfolios]))
        .group_by(PortfolioHolding.portfolio_id)
    )
    counts = dict(counts_result.all())

    return [
        PortfolioResponse(
            id=p.id,
            name=p.name,
            mode=p.mode,
            created_at=p.created_at,
            updated_at=p.updated_at,
            holdings_count=counts.get(p.id, 0),
        )
        for p in portfolios
    ]


# ------------------------------------------------------------------
# POST /api/portfolios
# ------------------------------------------------------------------


@router.post("", response_model=PortfolioResponse, status_code=201)
async def create_portfolio(
    body: PortfolioCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new portfolio."""
    svc = PortfolioService(session=session, ws_manager=deps.ws_manager)
    portfolio = await svc.create_portfolio(
        user_id=user.id, name=body.name, mode=body.mode
    )
    return PortfolioResponse(
        id=portfolio.id,
        name=portfolio.name,
        mode=portfolio.mode,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        holdings_count=0,
    )


# ------------------------------------------------------------------
# PATCH /api/portfolios/{portfolio_id}
# ------------------------------------------------------------------


@router.patch("/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio(
    portfolio_id: int,
    body: PortfolioUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update a portfolio's name and/or mode."""
    svc = PortfolioService(session=session, ws_manager=deps.ws_manager)
    portfolio = await svc.update_portfolio(
        portfolio_id=portfolio_id,
        user_id=user.id,
        name=body.name,
        mode=body.mode,
    )

    # Count holdings for the updated portfolio
    count_result = await session.execute(
        select(func.count(PortfolioHolding.id)).where(
            PortfolioHolding.portfolio_id == portfolio.id
        )
    )
    holdings_count = count_result.scalar_one()

    return PortfolioResponse(
        id=portfolio.id,
        name=portfolio.name,
        mode=portfolio.mode,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        holdings_count=holdings_count,
    )


# ------------------------------------------------------------------
# DELETE /api/portfolios/{portfolio_id}
# ------------------------------------------------------------------


@router.delete("/{portfolio_id}", status_code=204)
async def delete_portfolio(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a portfolio and all its holdings/snapshots (CASCADE)."""
    svc = PortfolioService(session=session, ws_manager=deps.ws_manager)
    await svc.delete_portfolio(portfolio_id=portfolio_id, user_id=user.id)
    return Response(status_code=204)


# ------------------------------------------------------------------
# GET /api/portfolios/{portfolio_id}/holdings
# ------------------------------------------------------------------


@router.get("/{portfolio_id}/holdings", response_model=list[HoldingResponse])
async def list_holdings(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List holdings with live prices for a portfolio."""
    svc = PortfolioService(session=session, ws_manager=deps.ws_manager)
    holdings = await svc.list_holdings(portfolio_id=portfolio_id, user_id=user.id)
    return [HoldingResponse(**h) for h in holdings]


# ------------------------------------------------------------------
# POST /api/portfolios/{portfolio_id}/holdings
# ------------------------------------------------------------------


@router.post(
    "/{portfolio_id}/holdings", response_model=HoldingResponse, status_code=201
)
async def add_holding(
    portfolio_id: int,
    body: HoldingCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Add a stock holding to a portfolio."""
    svc = PortfolioService(session=session, ws_manager=deps.ws_manager)
    holding = await svc.add_holding(
        portfolio_id=portfolio_id,
        user_id=user.id,
        stock_id=body.stock_id,
        shares=float(body.shares) if body.shares is not None else None,
        cost_basis_per_share=float(body.cost_basis_per_share)
        if body.cost_basis_per_share is not None
        else None,
    )

    # Fetch the stock to populate symbol and name in the response
    stock_result = await session.execute(select(Stock).where(Stock.id == body.stock_id))
    stock = stock_result.scalar_one()

    return HoldingResponse(
        id=holding.id,
        stock_id=holding.stock_id,
        symbol=stock.symbol,
        name=stock.name,
        shares=holding.shares,
        cost_basis_per_share=holding.cost_basis_per_share,
        added_at=holding.added_at,
        current_price=None,
        market_value=None,
        gain_loss=None,
        gain_loss_pct=None,
    )


# ------------------------------------------------------------------
# DELETE /api/portfolios/{portfolio_id}/holdings/{holding_id}
# ------------------------------------------------------------------


@router.delete("/{portfolio_id}/holdings/{holding_id}", status_code=204)
async def remove_holding(
    portfolio_id: int,
    holding_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Remove a holding from a portfolio."""
    svc = PortfolioService(session=session, ws_manager=deps.ws_manager)
    await svc.remove_holding(
        portfolio_id=portfolio_id, user_id=user.id, holding_id=holding_id
    )
    return Response(status_code=204)


# ------------------------------------------------------------------
# GET /api/portfolios/{portfolio_id}/performance
# ------------------------------------------------------------------


@router.get("/{portfolio_id}/performance", response_model=PerformanceSummary)
async def get_performance(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Compute and return portfolio-level P&L summary."""
    svc = PortfolioService(session=session, ws_manager=deps.ws_manager)
    perf = await svc.get_performance(portfolio_id=portfolio_id, user_id=user.id)
    return PerformanceSummary(
        total_value=perf["total_value"] or 0.0,
        total_cost_basis=perf["total_cost_basis"] or 0.0,
        total_gain_loss=perf["total_gain_loss"] or 0.0,
        total_gain_loss_pct=perf["total_gain_loss_pct"],
        holdings=[HoldingResponse(**h) for h in perf["holdings"]],
    )


# ------------------------------------------------------------------
# GET /api/portfolios/{portfolio_id}/history
# ------------------------------------------------------------------


@router.get("/{portfolio_id}/history", response_model=list[SnapshotResponse])
async def get_history(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return snapshot history for a portfolio."""
    svc = PortfolioService(session=session, ws_manager=deps.ws_manager)
    snapshots = await svc.get_history(portfolio_id=portfolio_id, user_id=user.id)
    return [SnapshotResponse.model_validate(s) for s in snapshots]
