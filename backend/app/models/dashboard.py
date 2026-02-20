from sqlalchemy import BigInteger, Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class DashboardTicker(Base):
    __tablename__ = "dashboard_tickers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    data_source: Mapped[str] = mapped_column(String(30), nullable=False)
    display_format: Mapped[str] = mapped_column(String(20), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_dashboard_tickers_category_order", "category", "display_order"),
        Index("ix_dashboard_tickers_is_active", "is_active"),
    )
