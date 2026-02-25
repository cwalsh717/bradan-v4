from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stocks import FinancialStatement

STATEMENT_TYPES = ("income", "balance_sheet", "cash_flow")
FLOW_STATEMENTS = ("income", "cash_flow")


class TTMService:
    """Compute trailing-twelve-month financials from the latest 4 quarterly records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def compute_ttm(self, stock_id: int) -> Optional[dict]:
        """
        Build a TTM snapshot for a stock.

        - Income and cash flow: sum numeric fields across the latest 4 quarters.
        - Balance sheet: use only the most recent quarter (point-in-time).
        - Returns None if no quarterly data exists for any statement type.
        """
        result: dict = {}
        quarters_used = 0
        period_start = None
        period_end = None

        for stmt_type in STATEMENT_TYPES:
            statements = await self._fetch_quarters(stock_id, stmt_type)

            if not statements:
                continue

            # Track overall quarter counts and date range from income statements
            # (income is the most representative), but fall back to whatever is available.
            if stmt_type == "income" or quarters_used == 0:
                quarters_used = len(statements)
                # statements are ordered desc; last element is the earliest quarter.
                period_end = str(statements[0].fiscal_date)
                period_start = str(statements[-1].fiscal_date)

            data_dicts = [s.data for s in statements]

            if stmt_type in FLOW_STATEMENTS:
                result[stmt_type] = self._sum_numeric_fields(data_dicts)
            else:
                # Balance sheet: point-in-time snapshot, use most recent quarter only.
                result[stmt_type] = dict(data_dicts[0])

        if not result:
            return None

        result["quarters_used"] = quarters_used
        result["period_start"] = period_start
        result["period_end"] = period_end

        return result

    async def _fetch_quarters(
        self, stock_id: int, statement_type: str, limit: int = 4
    ) -> list[FinancialStatement]:
        """Return the latest `limit` quarterly records for the given statement type."""
        stmt = (
            select(FinancialStatement)
            .where(
                FinancialStatement.stock_id == stock_id,
                FinancialStatement.statement_type == statement_type,
                FinancialStatement.period == "quarterly",
            )
            .order_by(FinancialStatement.fiscal_date.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _sum_numeric_fields(statements: list[dict]) -> dict:
        """
        Aggregate a list of JSONB data dicts.

        - Numeric values (int, float, or numeric strings) are summed.
        - None/null is treated as 0 for summation purposes.
        - Non-numeric fields take their value from the most recent statement (index 0).
        """
        if not statements:
            return {}

        # Collect all keys across every quarter.
        all_keys: list[str] = []
        seen: set[str] = set()
        for d in statements:
            for k in d:
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)

        result: dict = {}

        for key in all_keys:
            values = [d.get(key) for d in statements]

            # Determine whether this field is numeric by checking if *any* quarter
            # has a value that can be interpreted as a number.
            is_numeric = any(_to_float(v) is not None for v in values if v is not None)

            if is_numeric:
                total = 0.0
                for v in values:
                    parsed = _to_float(v)
                    if parsed is not None:
                        total += parsed
                # Preserve int type when there is no fractional component.
                result[key] = int(total) if total == int(total) else total
            else:
                # Non-numeric: take from most recent quarter.
                result[key] = values[0]

        return result


def _to_float(value) -> Optional[float]:
    """Convert a value to float if possible, return None otherwise."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
