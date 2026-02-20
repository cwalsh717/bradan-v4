from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stocks import Stock
from app.services.twelvedata import TwelveDataClient


class SearchService:
    """Stock search: local DB first, Twelve Data fallback."""

    def __init__(self, twelvedata: TwelveDataClient):
        self.twelvedata = twelvedata

    async def search(self, query: str, db: AsyncSession) -> List[dict]:
        """
        1. Query stocks table for symbol or name match (ILIKE)
        2. If less than 5 results, also hit Twelve Data symbol_search
        3. Merge results, deduplicate by symbol
        4. Return unified results with 'cached' bool flag
        """
        pattern = f"%{query}%"
        stmt = (
            select(Stock)
            .where(Stock.symbol.ilike(pattern) | Stock.name.ilike(pattern))
            .limit(10)
        )
        result = await db.execute(stmt)
        db_stocks = result.scalars().all()

        results = {}
        for s in db_stocks:
            results[s.symbol.upper()] = {
                "symbol": s.symbol,
                "name": s.name,
                "exchange": s.exchange or "",
                "type": "Common Stock",
                "currency": s.currency or "USD",
                "cached": True,
            }

        if len(results) < 5:
            try:
                api_results = await self.twelvedata.symbol_search(query)
                for item in api_results:
                    sym = item.get("symbol", "").upper()
                    if sym and sym not in results:
                        results[sym] = {
                            "symbol": item.get("symbol", ""),
                            "name": item.get("instrument_name", ""),
                            "exchange": item.get("exchange", ""),
                            "type": item.get("instrument_type", ""),
                            "currency": item.get("currency", "USD"),
                            "cached": False,
                        }
            except Exception:
                pass  # serve what we have from DB

        return list(results.values())[:10]
