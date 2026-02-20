from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models import Base


class DamodaranIndustry(Base):
    __tablename__ = "damodaran_industries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    industry_name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    num_firms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    unlevered_beta: Mapped[Optional[str]] = mapped_column(Numeric(8, 4), nullable=True)
    avg_effective_tax_rate: Mapped[Optional[str]] = mapped_column(Numeric(8, 4), nullable=True)
    avg_debt_to_equity: Mapped[Optional[str]] = mapped_column(Numeric(8, 4), nullable=True)
    avg_operating_margin: Mapped[Optional[str]] = mapped_column(Numeric(8, 4), nullable=True)
    avg_roc: Mapped[Optional[str]] = mapped_column(Numeric(8, 4), nullable=True)
    avg_reinvestment_rate: Mapped[Optional[str]] = mapped_column(Numeric(8, 4), nullable=True)
    cost_of_capital: Mapped[Optional[str]] = mapped_column(Numeric(8, 4), nullable=True)
    fundamental_growth_rate: Mapped[Optional[str]] = mapped_column(Numeric(8, 4), nullable=True)
    updated_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)


class CountryRiskPremium(Base):
    __tablename__ = "country_risk_premiums"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    moody_rating: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    default_spread: Mapped[Optional[str]] = mapped_column(Numeric(8, 4), nullable=True)
    equity_risk_premium: Mapped[Optional[str]] = mapped_column(Numeric(8, 4), nullable=True)
    country_risk_premium: Mapped[Optional[str]] = mapped_column(Numeric(8, 4), nullable=True)
    updated_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)


class DefaultSpread(Base):
    __tablename__ = "default_spreads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rating: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    spread_over_treasury: Mapped[str] = mapped_column(Numeric(8, 4), nullable=False)
    updated_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)


class SectorMapping(Base):
    __tablename__ = "sector_mapping"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    twelvedata_sector: Mapped[str] = mapped_column(String(100), nullable=False)
    twelvedata_industry: Mapped[str] = mapped_column(String(100), nullable=False)
    damodaran_industry_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("damodaran_industries.id"), nullable=True)
    match_confidence: Mapped[Optional[str]] = mapped_column(Numeric(5, 2), nullable=True)
    manually_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("twelvedata_sector", "twelvedata_industry", name="uq_sector_mapping_composite"),
        Index("ix_sector_mapping_composite", "twelvedata_sector", "twelvedata_industry"),
    )


class DcfValuation(Base):
    __tablename__ = "dcf_valuations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stocks.id"), nullable=False)
    damodaran_industry_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("damodaran_industries.id"), nullable=True)
    source_fiscal_date: Mapped[Optional[str]] = mapped_column(Date, nullable=True)
    computed_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    model_type: Mapped[str] = mapped_column(String(10), nullable=False, default="fcff")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    run_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    outputs: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        Index("ix_dcf_valuations_stock_default", "stock_id", "is_default"),
        Index("ix_dcf_valuations_stock_user", "stock_id", "user_id"),
        Index("ix_dcf_valuations_user_saved", "user_id", "is_saved"),
    )


class DcfAuditLog(Base):
    __tablename__ = "dcf_audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dcf_valuation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dcf_valuations.id"), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
