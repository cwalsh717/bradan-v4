from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    clerk_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_login: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="watchlist")
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stocks.id"), nullable=False)
    shares: Mapped[Optional[str]] = mapped_column(Numeric(14, 6), nullable=True)
    cost_basis_per_share: Mapped[Optional[str]] = mapped_column(Numeric(14, 4), nullable=True)
    added_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("portfolio_id", "stock_id", name="uq_portfolio_holdings_composite"),
        Index("ix_portfolio_holdings_portfolio_stock", "portfolio_id", "stock_id"),
    )


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[str] = mapped_column(Date, nullable=False)
    total_value: Mapped[str] = mapped_column(Numeric(16, 2), nullable=False)
    total_cost_basis: Mapped[str] = mapped_column(Numeric(16, 2), nullable=False)
    total_gain_loss: Mapped[str] = mapped_column(Numeric(16, 2), nullable=False)
    holdings_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("portfolio_id", "date", name="uq_portfolio_snapshots_composite"),
        Index("ix_portfolio_snapshots_portfolio_date", "portfolio_id", "date"),
    )
