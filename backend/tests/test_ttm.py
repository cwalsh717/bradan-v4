from datetime import date
from unittest.mock import AsyncMock, MagicMock


from app.services.ttm import TTMService, _to_float


def _make_session():
    """Create a mock AsyncSession."""
    return AsyncMock()


def _make_statement(fiscal_date, data: dict):
    """Create a mock FinancialStatement with .fiscal_date and .data attributes."""
    stmt = MagicMock()
    stmt.fiscal_date = fiscal_date
    stmt.data = data
    return stmt


def _mock_fetch_quarters(income=None, balance_sheet=None, cash_flow=None):
    """Return an AsyncMock side_effect for _fetch_quarters that maps statement_type to data."""
    mapping = {
        "income": income or [],
        "balance_sheet": balance_sheet or [],
        "cash_flow": cash_flow or [],
    }

    async def _side_effect(stock_id, statement_type, limit=4):
        return mapping.get(statement_type, [])

    return _side_effect


# ---------- _to_float ----------


async def test_to_float_int():
    assert _to_float(5) == 5.0


async def test_to_float_float():
    assert _to_float(3.14) == 3.14


async def test_to_float_numeric_string():
    assert _to_float("1234") == 1234.0


async def test_to_float_non_numeric_string():
    assert _to_float("hello") is None


async def test_to_float_none():
    assert _to_float(None) is None


# ---------- _sum_numeric_fields ----------


async def test_sum_numeric_fields_with_numeric_strings():
    """Twelve Data returns numbers as strings; they should be summed."""
    service = TTMService(_make_session())
    dicts = [
        {"revenue": "1000", "currency": "USD"},
        {"revenue": "2000", "currency": "USD"},
        {"revenue": "3000", "currency": "USD"},
        {"revenue": "4000", "currency": "USD"},
    ]
    result = service._sum_numeric_fields(dicts)
    assert result["revenue"] == 10000
    # Non-numeric field should take value from first dict (most recent)
    assert result["currency"] == "USD"


async def test_sum_numeric_fields_with_int_values():
    """Integer values should be summed correctly."""
    service = TTMService(_make_session())
    dicts = [
        {"net_income": 100, "eps": 1.5},
        {"net_income": 200, "eps": 2.0},
    ]
    result = service._sum_numeric_fields(dicts)
    assert result["net_income"] == 300
    assert result["eps"] == 3.5


async def test_sum_numeric_fields_with_mixed_types():
    """Mix of int, float, and string numeric values."""
    service = TTMService(_make_session())
    dicts = [
        {"revenue": 1000},
        {"revenue": "2000"},
        {"revenue": 3000.5},
    ]
    result = service._sum_numeric_fields(dicts)
    assert result["revenue"] == 6000.5


async def test_sum_numeric_fields_with_none_values():
    """None values should be treated as 0 for summation."""
    service = TTMService(_make_session())
    dicts = [
        {"revenue": "1000", "special_charge": None},
        {"revenue": "2000", "special_charge": "500"},
    ]
    result = service._sum_numeric_fields(dicts)
    assert result["revenue"] == 3000
    # special_charge: one None, one "500" -- "500" is numeric, so sum is 500
    assert result["special_charge"] == 500


async def test_sum_numeric_fields_empty():
    """Empty list returns empty dict."""
    service = TTMService(_make_session())
    result = service._sum_numeric_fields([])
    assert result == {}


# ---------- compute_ttm ----------


async def test_compute_ttm_with_4_quarters():
    """Full TTM: income and cash_flow summed, balance_sheet latest only."""
    session = _make_session()
    service = TTMService(session)

    income_stmts = [
        _make_statement(
            date(2024, 6, 30),
            {"revenue": "4000", "net_income": "400", "currency": "USD"},
        ),
        _make_statement(
            date(2024, 3, 31),
            {"revenue": "3000", "net_income": "300", "currency": "USD"},
        ),
        _make_statement(
            date(2023, 12, 31),
            {"revenue": "2000", "net_income": "200", "currency": "USD"},
        ),
        _make_statement(
            date(2023, 9, 30),
            {"revenue": "1000", "net_income": "100", "currency": "USD"},
        ),
    ]

    bs_stmts = [
        _make_statement(
            date(2024, 6, 30), {"total_assets": "50000", "total_debt": "10000"}
        ),
        _make_statement(
            date(2024, 3, 31), {"total_assets": "48000", "total_debt": "9500"}
        ),
        _make_statement(
            date(2023, 12, 31), {"total_assets": "46000", "total_debt": "9000"}
        ),
        _make_statement(
            date(2023, 9, 30), {"total_assets": "44000", "total_debt": "8500"}
        ),
    ]

    cf_stmts = [
        _make_statement(
            date(2024, 6, 30), {"operating_cash_flow": "500", "capex": "-100"}
        ),
        _make_statement(
            date(2024, 3, 31), {"operating_cash_flow": "400", "capex": "-80"}
        ),
        _make_statement(
            date(2023, 12, 31), {"operating_cash_flow": "300", "capex": "-60"}
        ),
        _make_statement(
            date(2023, 9, 30), {"operating_cash_flow": "200", "capex": "-40"}
        ),
    ]

    service._fetch_quarters = AsyncMock(
        side_effect=_mock_fetch_quarters(
            income=income_stmts,
            balance_sheet=bs_stmts,
            cash_flow=cf_stmts,
        )
    )

    result = await service.compute_ttm(stock_id=1)

    assert result is not None

    # Income: summed
    assert result["income"]["revenue"] == 10000
    assert result["income"]["net_income"] == 1000
    assert result["income"]["currency"] == "USD"  # non-numeric: most recent

    # Balance sheet: latest quarter only (index 0)
    assert result["balance_sheet"]["total_assets"] == "50000"
    assert result["balance_sheet"]["total_debt"] == "10000"

    # Cash flow: summed
    assert result["cash_flow"]["operating_cash_flow"] == 1400
    assert result["cash_flow"]["capex"] == -280

    # Metadata
    assert result["quarters_used"] == 4
    assert result["period_start"] == "2023-09-30"
    assert result["period_end"] == "2024-06-30"


async def test_compute_ttm_fewer_than_4_quarters():
    """When only 2 quarters exist, quarters_used reflects that."""
    session = _make_session()
    service = TTMService(session)

    income_stmts = [
        _make_statement(date(2024, 6, 30), {"revenue": "4000"}),
        _make_statement(date(2024, 3, 31), {"revenue": "3000"}),
    ]

    service._fetch_quarters = AsyncMock(
        side_effect=_mock_fetch_quarters(income=income_stmts)
    )

    result = await service.compute_ttm(stock_id=1)

    assert result is not None
    assert result["quarters_used"] == 2
    assert result["income"]["revenue"] == 7000
    assert result["period_start"] == "2024-03-31"
    assert result["period_end"] == "2024-06-30"


async def test_compute_ttm_no_data_returns_none():
    """When no quarterly data exists, compute_ttm returns None."""
    session = _make_session()
    service = TTMService(session)

    service._fetch_quarters = AsyncMock(side_effect=_mock_fetch_quarters())

    result = await service.compute_ttm(stock_id=1)

    assert result is None


async def test_balance_sheet_uses_latest_quarter_only():
    """Balance sheet data should come from index 0 only, not be summed."""
    session = _make_session()
    service = TTMService(session)

    bs_stmts = [
        _make_statement(date(2024, 6, 30), {"total_assets": "50000", "cash": "5000"}),
        _make_statement(date(2024, 3, 31), {"total_assets": "48000", "cash": "4000"}),
        _make_statement(date(2023, 12, 31), {"total_assets": "46000", "cash": "3000"}),
        _make_statement(date(2023, 9, 30), {"total_assets": "44000", "cash": "2000"}),
    ]

    service._fetch_quarters = AsyncMock(
        side_effect=_mock_fetch_quarters(balance_sheet=bs_stmts)
    )

    result = await service.compute_ttm(stock_id=1)

    assert result is not None
    # Should be the exact dict from the first (most recent) statement, not summed
    assert result["balance_sheet"]["total_assets"] == "50000"
    assert result["balance_sheet"]["cash"] == "5000"
    # Verify these are NOT the summed values (188000 and 14000)
    assert result["balance_sheet"]["total_assets"] != "188000"
