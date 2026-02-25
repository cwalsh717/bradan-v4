"""Sector fuzzy mapping service: bridges Twelve Data sector/industry names to Damodaran industry groups."""

import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dcf import DamodaranIndustry, SectorMapping
from app.models.stocks import Stock

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Financial company detection sets
# ---------------------------------------------------------------------------

FINANCIAL_SECTORS: set[str] = {"financial services", "financials", "financial"}

FINANCIAL_INDUSTRIES: set[str] = {
    "banks",
    "banking",
    "regional banks",
    "diversified banks",
    "insurance",
    "life insurance",
    "property insurance",
    "reits",
    "reit",
    "real estate investment trust",
    "asset management",
    "capital markets",
    "investment banking",
    "mortgage finance",
    "consumer finance",
    "financial data",
    "financial exchanges",
}

HIGH_CONFIDENCE_THRESHOLD = 0.85
MEDIUM_CONFIDENCE_THRESHOLD = 0.60


@dataclass
class SectorMappingResult:
    """Result of a sector-to-Damodaran-industry mapping lookup."""

    damodaran_industry_id: int
    industry_name: str
    confidence: float
    confidence_level: str  # "high", "medium", "low"
    manually_verified: bool
    is_eligible: bool
    rejection_reason: Optional[str]  # "financial_firm", "low_confidence", None

    unlevered_beta: Decimal
    avg_effective_tax_rate: Decimal
    avg_debt_to_equity: Decimal
    avg_operating_margin: Decimal
    avg_roc: Decimal
    cost_of_capital: Decimal


def _normalise(text: str) -> str:
    """Lowercase, strip, remove parenthetical content."""
    text = text.lower().strip()
    text = re.sub(r"\s*\([^)]*\)", "", text)
    return text.strip()


def _score_pair(candidate: str, reference: str) -> float:
    """Similarity score between 0 and 1 for two normalised strings."""
    if candidate == reference:
        return 1.0
    if candidate in reference or reference in candidate:
        shorter = min(len(candidate), len(reference))
        longer = max(len(candidate), len(reference))
        if longer > 0:
            return 0.80 + 0.15 * (shorter / longer)
    return SequenceMatcher(None, candidate, reference).ratio()


class SectorMappingService:
    """Maps Twelve Data sector/industry to Damodaran industry groups."""

    async def get_mapping(
        self, session: AsyncSession, stock: Stock
    ) -> SectorMappingResult:
        """Get the Damodaran industry mapping for a stock."""
        td_sector = stock.sector or ""
        td_industry = stock.industry or ""
        is_financial = self.is_financial_company(td_sector, td_industry)

        # Look up existing mapping
        existing = await self._find_existing_mapping(session, td_sector, td_industry)
        if existing is not None:
            mapping_row, dam_industry = existing
            return self._build_result(
                dam_industry=dam_industry,
                confidence=float(mapping_row.match_confidence or 0),
                manually_verified=mapping_row.manually_verified,
                is_financial=is_financial,
            )

        # No sector/industry info — zero-confidence fallback
        if not td_sector and not td_industry:
            result = await session.execute(
                select(DamodaranIndustry).order_by(DamodaranIndustry.id).limit(1)
            )
            fallback = result.scalar_one_or_none()
            if fallback is None:
                raise ValueError("No Damodaran industries in database.")
            return self._build_result(
                dam_industry=fallback,
                confidence=0.0,
                manually_verified=False,
                is_financial=is_financial,
            )

        damodaran_id, confidence = await self.fuzzy_match(
            session, td_sector, td_industry
        )

        new_mapping = SectorMapping(
            twelvedata_sector=td_sector,
            twelvedata_industry=td_industry,
            damodaran_industry_id=damodaran_id,
            match_confidence=Decimal(str(round(confidence, 2))),
            manually_verified=False,
        )
        session.add(new_mapping)
        await session.commit()

        dam_result = await session.execute(
            select(DamodaranIndustry).where(DamodaranIndustry.id == damodaran_id)
        )
        dam_industry = dam_result.scalar_one()

        return self._build_result(
            dam_industry=dam_industry,
            confidence=confidence,
            manually_verified=False,
            is_financial=is_financial,
        )

    async def fuzzy_match(
        self, session: AsyncSession, td_sector: str, td_industry: str
    ) -> tuple[int, float]:
        """Find best Damodaran industry match. Returns (id, confidence)."""
        result = await session.execute(select(DamodaranIndustry))
        all_industries = result.scalars().all()
        if not all_industries:
            raise ValueError("No Damodaran industries in database.")

        norm_sector = _normalise(td_sector)
        norm_industry = _normalise(td_industry)

        best_id: int = all_industries[0].id
        best_score: float = 0.0

        for dam in all_industries:
            norm_dam = _normalise(dam.industry_name)
            direct_score = _score_pair(norm_industry, norm_dam)
            sector_score = _score_pair(norm_sector, norm_dam) if norm_sector else 0.0
            industry_score = (
                _score_pair(norm_industry, norm_dam) if norm_industry else 0.0
            )
            weighted_score = sector_score * 0.3 + industry_score * 0.7
            score = max(direct_score, weighted_score)

            if score > best_score:
                best_score = score
                best_id = dam.id

        return best_id, round(best_score, 4)

    async def set_manual_override(
        self,
        session: AsyncSession,
        stock_sector: str,
        stock_industry: str,
        damodaran_industry_id: int,
    ) -> SectorMapping:
        """Manually set the mapping. Sets manually_verified=True."""
        result = await session.execute(
            select(SectorMapping).where(
                SectorMapping.twelvedata_sector == stock_sector,
                SectorMapping.twelvedata_industry == stock_industry,
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.damodaran_industry_id = damodaran_industry_id
            existing.match_confidence = Decimal("1.00")
            existing.manually_verified = True
            session.add(existing)
        else:
            existing = SectorMapping(
                twelvedata_sector=stock_sector,
                twelvedata_industry=stock_industry,
                damodaran_industry_id=damodaran_industry_id,
                match_confidence=Decimal("1.00"),
                manually_verified=True,
            )
            session.add(existing)

        await session.commit()
        await session.refresh(existing)
        return existing

    def is_financial_company(self, sector: str, industry: str) -> bool:
        """Check if the company is a financial firm (not supported for FCFF DCF)."""
        norm_sector = (sector or "").lower().strip()
        norm_industry = (industry or "").lower().strip()

        if norm_sector in FINANCIAL_SECTORS:
            return True
        if norm_industry in FINANCIAL_INDUSTRIES:
            return True
        for fi in FINANCIAL_INDUSTRIES:
            if fi in norm_industry:
                return True
        return False

    async def _find_existing_mapping(
        self, session: AsyncSession, td_sector: str, td_industry: str
    ) -> Optional[tuple[SectorMapping, DamodaranIndustry]]:
        """Look up existing sector_mapping row joined with Damodaran industry."""
        result = await session.execute(
            select(SectorMapping, DamodaranIndustry)
            .join(
                DamodaranIndustry,
                SectorMapping.damodaran_industry_id == DamodaranIndustry.id,
            )
            .where(
                SectorMapping.twelvedata_sector == td_sector,
                SectorMapping.twelvedata_industry == td_industry,
            )
        )
        row = result.one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    @staticmethod
    def _build_result(
        *,
        dam_industry: DamodaranIndustry,
        confidence: float,
        manually_verified: bool,
        is_financial: bool,
    ) -> SectorMappingResult:
        if confidence >= HIGH_CONFIDENCE_THRESHOLD:
            confidence_level = "high"
        elif confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
            confidence_level = "medium"
        else:
            confidence_level = "low"

        rejection_reason: Optional[str] = None
        is_eligible = True

        if is_financial:
            is_eligible = False
            rejection_reason = "financial_firm"
        elif confidence < MEDIUM_CONFIDENCE_THRESHOLD and not manually_verified:
            is_eligible = False
            rejection_reason = "low_confidence"

        if manually_verified and not is_financial:
            is_eligible = True
            rejection_reason = None

        def _dec(val: object) -> Decimal:
            if val is None:
                return Decimal("0")
            return Decimal(str(val))

        return SectorMappingResult(
            damodaran_industry_id=dam_industry.id,
            industry_name=dam_industry.industry_name,
            confidence=confidence,
            confidence_level=confidence_level,
            manually_verified=manually_verified,
            is_eligible=is_eligible,
            rejection_reason=rejection_reason,
            unlevered_beta=_dec(dam_industry.unlevered_beta),
            avg_effective_tax_rate=_dec(dam_industry.avg_effective_tax_rate),
            avg_debt_to_equity=_dec(dam_industry.avg_debt_to_equity),
            avg_operating_margin=_dec(dam_industry.avg_operating_margin),
            avg_roc=_dec(dam_industry.avg_roc),
            cost_of_capital=_dec(dam_industry.cost_of_capital),
        )


sector_mapping_service = SectorMappingService()
