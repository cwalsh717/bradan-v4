"""Portfolio service: CRUD for portfolios, holdings, performance, and snapshots."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.users import Portfolio, PortfolioHolding, PortfolioSnapshot
from app.models.stocks import Stock


class PortfolioService:
    """Handles all portfolio business logic: portfolios, holdings, performance, snapshots."""

    def __init__(self, session: AsyncSession, ws_manager=None):
        self.session = session
        self.ws_manager = ws_manager

    # ------------------------------------------------------------------
    # Portfolios
    # ------------------------------------------------------------------

    async def list_portfolios(self, user_id: int) -> list[Portfolio]:
        """List all portfolios for a user, newest first."""
        result = await self.session.execute(
            select(Portfolio)
            .where(Portfolio.user_id == user_id)
            .order_by(Portfolio.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_portfolio(
        self, user_id: int, name: str, mode: str = "watchlist"
    ) -> Portfolio:
        """Create a new portfolio for a user."""
        portfolio = Portfolio(user_id=user_id, name=name, mode=mode)
        self.session.add(portfolio)
        await self.session.flush()
        await self.session.commit()
        return portfolio

    async def get_portfolio(self, portfolio_id: int, user_id: int) -> Portfolio:
        """Get a single portfolio, verifying ownership. Raises 404 if not found."""
        result = await self.session.execute(
            select(Portfolio).where(
                Portfolio.id == portfolio_id,
                Portfolio.user_id == user_id,
            )
        )
        portfolio = result.scalar_one_or_none()
        if portfolio is None:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        return portfolio

    async def update_portfolio(
        self,
        portfolio_id: int,
        user_id: int,
        name: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> Portfolio:
        """Update portfolio name and/or mode. Preserves holding data on mode changes."""
        portfolio = await self.get_portfolio(portfolio_id, user_id)

        if name is not None:
            portfolio.name = name
        if mode is not None:
            # Mode changes preserve holding data:
            # full → watchlist: lot data preserved, just hidden by frontend
            # watchlist → full: stocks carry over, frontend shows "needs details" state
            portfolio.mode = mode

        portfolio.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.commit()
        return portfolio

    async def delete_portfolio(self, portfolio_id: int, user_id: int) -> None:
        """Delete a portfolio. CASCADE handles holdings and snapshots."""
        portfolio = await self.get_portfolio(portfolio_id, user_id)
        await self.session.delete(portfolio)
        await self.session.commit()

    # ------------------------------------------------------------------
    # Holdings
    # ------------------------------------------------------------------

    async def list_holdings(self, portfolio_id: int, user_id: int) -> list[dict]:
        """List holdings with live prices and computed gain/loss."""
        await self.get_portfolio(portfolio_id, user_id)

        result = await self.session.execute(
            select(PortfolioHolding, Stock)
            .join(Stock, PortfolioHolding.stock_id == Stock.id)
            .where(PortfolioHolding.portfolio_id == portfolio_id)
            .order_by(PortfolioHolding.added_at)
        )
        rows = result.all()

        holdings = []
        for holding, stock in rows:
            current_price = None
            if self.ws_manager:
                price_data = self.ws_manager.get_price(stock.symbol)
                if price_data and price_data.get("price") is not None:
                    current_price = Decimal(str(price_data["price"]))

            shares = Decimal(str(holding.shares)) if holding.shares is not None else None
            cost_basis = (
                Decimal(str(holding.cost_basis_per_share))
                if holding.cost_basis_per_share is not None
                else None
            )

            market_value = None
            gain_loss = None
            gain_loss_pct = None

            if shares is not None and current_price is not None:
                market_value = shares * current_price

                if cost_basis is not None:
                    total_cost = shares * cost_basis
                    if total_cost != 0:
                        gain_loss = market_value - total_cost
                        gain_loss_pct = float(gain_loss / total_cost * 100)
                    else:
                        gain_loss = market_value
                        gain_loss_pct = None

            holdings.append(
                {
                    "id": holding.id,
                    "stock_id": holding.stock_id,
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "shares": float(shares) if shares is not None else None,
                    "cost_basis_per_share": float(cost_basis)
                    if cost_basis is not None
                    else None,
                    "added_at": str(holding.added_at),
                    "current_price": float(current_price)
                    if current_price is not None
                    else None,
                    "market_value": float(market_value)
                    if market_value is not None
                    else None,
                    "gain_loss": float(gain_loss)
                    if gain_loss is not None
                    else None,
                    "gain_loss_pct": gain_loss_pct,
                }
            )

        return holdings

    async def add_holding(
        self,
        portfolio_id: int,
        user_id: int,
        stock_id: int,
        shares: Optional[float] = None,
        cost_basis_per_share: Optional[float] = None,
    ) -> PortfolioHolding:
        """Add a stock to a portfolio. Raises 404 if stock not found, 409 if duplicate."""
        await self.get_portfolio(portfolio_id, user_id)

        # Verify stock exists
        result = await self.session.execute(
            select(Stock).where(Stock.id == stock_id)
        )
        stock = result.scalar_one_or_none()
        if stock is None:
            raise HTTPException(status_code=404, detail="Stock not found")

        holding = PortfolioHolding(
            portfolio_id=portfolio_id,
            stock_id=stock_id,
            shares=Decimal(str(shares)) if shares is not None else None,
            cost_basis_per_share=Decimal(str(cost_basis_per_share))
            if cost_basis_per_share is not None
            else None,
        )
        self.session.add(holding)

        try:
            await self.session.flush()
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(
                status_code=409, detail="Stock already in portfolio"
            )

        return holding

    async def remove_holding(
        self, portfolio_id: int, user_id: int, holding_id: int
    ) -> None:
        """Remove a holding from a portfolio. Raises 404 if not found."""
        await self.get_portfolio(portfolio_id, user_id)

        result = await self.session.execute(
            select(PortfolioHolding).where(
                PortfolioHolding.id == holding_id,
                PortfolioHolding.portfolio_id == portfolio_id,
            )
        )
        holding = result.scalar_one_or_none()
        if holding is None:
            raise HTTPException(status_code=404, detail="Holding not found")

        await self.session.delete(holding)
        await self.session.commit()

    # ------------------------------------------------------------------
    # Performance
    # ------------------------------------------------------------------

    async def get_performance(self, portfolio_id: int, user_id: int) -> dict:
        """Compute portfolio-level performance totals from live holdings."""
        holdings = await self.list_holdings(portfolio_id, user_id)

        total_value = Decimal("0")
        total_cost_basis = Decimal("0")
        has_values = False

        for h in holdings:
            if h["market_value"] is not None:
                total_value += Decimal(str(h["market_value"]))
                has_values = True
            if (
                h["shares"] is not None
                and h["cost_basis_per_share"] is not None
            ):
                total_cost_basis += Decimal(str(h["shares"])) * Decimal(
                    str(h["cost_basis_per_share"])
                )

        total_gain_loss = total_value - total_cost_basis if has_values else None
        total_gain_loss_pct = (
            float(total_gain_loss / total_cost_basis * 100)
            if total_gain_loss is not None and total_cost_basis != 0
            else None
        )

        return {
            "total_value": float(total_value) if has_values else None,
            "total_cost_basis": float(total_cost_basis)
            if total_cost_basis != 0
            else None,
            "total_gain_loss": float(total_gain_loss)
            if total_gain_loss is not None
            else None,
            "total_gain_loss_pct": total_gain_loss_pct,
            "holdings": holdings,
        }

    # ------------------------------------------------------------------
    # Snapshots / History
    # ------------------------------------------------------------------

    async def get_history(
        self, portfolio_id: int, user_id: int
    ) -> list[PortfolioSnapshot]:
        """Get portfolio snapshots, newest first."""
        await self.get_portfolio(portfolio_id, user_id)

        result = await self.session.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.portfolio_id == portfolio_id)
            .order_by(PortfolioSnapshot.date.desc())
        )
        return list(result.scalars().all())

    async def create_snapshot(
        self, portfolio_id: int, user_id: int
    ) -> PortfolioSnapshot:
        """Create or update today's snapshot from current performance data."""
        performance = await self.get_performance(portfolio_id, user_id)

        total_value = Decimal(str(performance["total_value"] or 0))
        total_cost_basis = Decimal(str(performance["total_cost_basis"] or 0))
        total_gain_loss = Decimal(str(performance["total_gain_loss"] or 0))

        holdings_snapshot = [
            {
                "stock_id": h["stock_id"],
                "symbol": h["symbol"],
                "name": h["name"],
                "shares": h["shares"],
                "cost_basis_per_share": h["cost_basis_per_share"],
                "current_price": h["current_price"],
                "market_value": h["market_value"],
                "gain_loss": h["gain_loss"],
                "gain_loss_pct": h["gain_loss_pct"],
            }
            for h in performance["holdings"]
        ]

        today = date.today()

        # Check for existing snapshot today (upsert)
        result = await self.session.execute(
            select(PortfolioSnapshot).where(
                PortfolioSnapshot.portfolio_id == portfolio_id,
                PortfolioSnapshot.date == today,
            )
        )
        snapshot = result.scalar_one_or_none()

        if snapshot is not None:
            snapshot.total_value = total_value
            snapshot.total_cost_basis = total_cost_basis
            snapshot.total_gain_loss = total_gain_loss
            snapshot.holdings_snapshot = holdings_snapshot
        else:
            snapshot = PortfolioSnapshot(
                portfolio_id=portfolio_id,
                date=today,
                total_value=total_value,
                total_cost_basis=total_cost_basis,
                total_gain_loss=total_gain_loss,
                holdings_snapshot=holdings_snapshot,
            )
            self.session.add(snapshot)

        await self.session.flush()
        await self.session.commit()
        return snapshot
