from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models import Base


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    exchange: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    last_updated: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_stocks_sector_industry", "sector", "industry"),
    )


class FinancialStatement(Base):
    __tablename__ = "financial_statements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stocks.id"), nullable=False, index=True)
    statement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    fiscal_date: Mapped[str] = mapped_column(Date, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("stock_id", "statement_type", "period", "fiscal_date", name="uq_financial_statements_composite"),
        Index("ix_financial_statements_composite", "stock_id", "statement_type", "period", "fiscal_date"),
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stocks.id"), nullable=False)
    date: Mapped[str] = mapped_column(Date, nullable=False)
    open: Mapped[str] = mapped_column(Numeric(14, 4), nullable=False)
    high: Mapped[str] = mapped_column(Numeric(14, 4), nullable=False)
    low: Mapped[str] = mapped_column(Numeric(14, 4), nullable=False)
    close: Mapped[str] = mapped_column(Numeric(14, 4), nullable=False)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    fetched_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_price_history_stock_date"),
        Index("ix_price_history_stock_date", "stock_id", "date"),
    )


class Dividend(Base):
    __tablename__ = "dividends"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stocks.id"), nullable=False)
    ex_date: Mapped[str] = mapped_column(Date, nullable=False)
    amount: Mapped[str] = mapped_column(Numeric(12, 6), nullable=False)
    fetched_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_dividends_stock_ex_date", "stock_id", "ex_date"),
    )


class StockSplit(Base):
    __tablename__ = "stock_splits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stocks.id"), nullable=False)
    date: Mapped[str] = mapped_column(Date, nullable=False)
    ratio_from: Mapped[int] = mapped_column(Integer, nullable=False)
    ratio_to: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_stock_splits_stock_date", "stock_id", "date"),
    )


class EarningsCalendar(Base):
    __tablename__ = "earnings_calendar"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stocks.id"), nullable=False)
    report_date: Mapped[str] = mapped_column(Date, nullable=False)
    fiscal_quarter: Mapped[str] = mapped_column(String(10), nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fetched_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_earnings_calendar_stock_report_date", "stock_id", "report_date"),
    )
