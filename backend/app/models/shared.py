from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models import Base


class FredSeries(Base):
    __tablename__ = "fred_series"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[str] = mapped_column(Numeric(12, 6), nullable=False)
    observation_date: Mapped[str] = mapped_column(Date, nullable=False)
    fetched_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("series_id", "observation_date", name="uq_fred_series_composite"),
        Index("ix_fred_series_composite", "series_id", "observation_date"),
    )


class Glossary(Base):
    __tablename__ = "glossary"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    technical_term: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_label: Mapped[str] = mapped_column(String(200), nullable=False)
    technical_label: Mapped[str] = mapped_column(String(50), nullable=False)
    tooltip: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    learn_more_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
