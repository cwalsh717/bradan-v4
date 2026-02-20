from app.models import Base


EXPECTED_TABLES = {
    "country_risk_premiums",
    "damodaran_industries",
    "dashboard_tickers",
    "dcf_audit_log",
    "dcf_valuations",
    "default_spreads",
    "dividends",
    "earnings_calendar",
    "financial_statements",
    "fred_series",
    "glossary",
    "portfolio_holdings",
    "portfolio_snapshots",
    "portfolios",
    "price_history",
    "sector_mapping",
    "stock_splits",
    "stocks",
    "users",
}


def test_all_19_models_import():
    """All model modules import without error and register with Base."""
    from app.models.dashboard import DashboardTicker
    from app.models.stocks import (
        Stock, FinancialStatement, PriceHistory, Dividend, StockSplit, EarningsCalendar,
    )
    from app.models.dcf import (
        DamodaranIndustry, CountryRiskPremium, DefaultSpread,
        SectorMapping, DcfValuation, DcfAuditLog,
    )
    from app.models.users import User, Portfolio, PortfolioHolding, PortfolioSnapshot
    from app.models.shared import FredSeries, Glossary

    assert DashboardTicker.__tablename__ == "dashboard_tickers"
    assert Stock.__tablename__ == "stocks"
    assert DcfValuation.__tablename__ == "dcf_valuations"
    assert User.__tablename__ == "users"
    assert FredSeries.__tablename__ == "fred_series"


def test_base_metadata_has_19_tables():
    """Base.metadata.tables contains exactly 19 app tables."""
    table_names = set(Base.metadata.tables.keys())
    assert table_names == EXPECTED_TABLES


def test_stocks_table_columns():
    table = Base.metadata.tables["stocks"]
    col_names = {c.name for c in table.columns}
    expected = {"id", "symbol", "name", "exchange", "sector", "industry", "currency", "last_updated"}
    assert expected == col_names


def test_financial_statements_columns():
    table = Base.metadata.tables["financial_statements"]
    col_names = {c.name for c in table.columns}
    expected = {"id", "stock_id", "statement_type", "period", "fiscal_date", "data", "fetched_at"}
    assert expected == col_names


def test_dcf_valuations_columns():
    table = Base.metadata.tables["dcf_valuations"]
    col_names = {c.name for c in table.columns}
    expected = {
        "id", "stock_id", "damodaran_industry_id", "source_fiscal_date",
        "computed_at", "model_type", "is_default", "user_id", "run_name",
        "is_saved", "inputs", "outputs",
    }
    assert expected == col_names


def test_portfolio_holdings_columns():
    table = Base.metadata.tables["portfolio_holdings"]
    col_names = {c.name for c in table.columns}
    expected = {"id", "portfolio_id", "stock_id", "shares", "cost_basis_per_share", "added_at"}
    assert expected == col_names
