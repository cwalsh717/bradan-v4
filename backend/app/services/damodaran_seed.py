"""Seed service for Damodaran reference data (DCF valuation inputs).

Seeds three tables:
  - default_spreads       (15 rows -- synthetic rating -> spread)
  - country_risk_premiums (13 rows -- key countries)
  - damodaran_industries  (25 rows -- most common industries for v1)

All rates and percentages are stored as decimals (4.60 % = 0.0460).
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dcf import CountryRiskPremium, DamodaranIndustry, DefaultSpread

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Default spreads -- synthetic-rating table (Damodaran Jan 2025)
# ---------------------------------------------------------------------------
DEFAULT_SPREADS: list[tuple[str, Decimal]] = [
    ("AAA", Decimal("0.0075")),
    ("AA", Decimal("0.0100")),
    ("A+", Decimal("0.0150")),
    ("A", Decimal("0.0180")),
    ("A-", Decimal("0.0200")),
    ("BBB", Decimal("0.0225")),
    ("BB+", Decimal("0.0275")),
    ("BB", Decimal("0.0350")),
    ("B+", Decimal("0.0475")),
    ("B", Decimal("0.0650")),
    ("B-", Decimal("0.0800")),
    ("CCC", Decimal("0.1000")),
    ("CC", Decimal("0.1150")),
    ("C", Decimal("0.1270")),
    ("D", Decimal("0.1500")),
]

# ---------------------------------------------------------------------------
# 2. Country risk premiums -- key countries (Damodaran Jan 2025, approx)
# ---------------------------------------------------------------------------
COUNTRY_RISK_PREMIUMS: list[tuple[str, str, Decimal, Decimal, Decimal]] = [
    ("United States", "Aaa", Decimal("0.0000"), Decimal("0.0460"), Decimal("0.0000")),
    ("United Kingdom", "Aa3", Decimal("0.0058"), Decimal("0.0518"), Decimal("0.0058")),
    ("Germany", "Aaa", Decimal("0.0000"), Decimal("0.0460"), Decimal("0.0000")),
    ("Japan", "A1", Decimal("0.0068"), Decimal("0.0528"), Decimal("0.0068")),
    ("Canada", "Aaa", Decimal("0.0000"), Decimal("0.0460"), Decimal("0.0000")),
    ("France", "Aa2", Decimal("0.0046"), Decimal("0.0506"), Decimal("0.0046")),
    ("Australia", "Aaa", Decimal("0.0000"), Decimal("0.0460"), Decimal("0.0000")),
    ("China", "A1", Decimal("0.0068"), Decimal("0.0528"), Decimal("0.0068")),
    ("India", "Baa3", Decimal("0.0162"), Decimal("0.0622"), Decimal("0.0162")),
    ("Brazil", "Ba1", Decimal("0.0217"), Decimal("0.0677"), Decimal("0.0217")),
    ("South Korea", "Aa2", Decimal("0.0046"), Decimal("0.0506"), Decimal("0.0046")),
    ("Switzerland", "Aaa", Decimal("0.0000"), Decimal("0.0460"), Decimal("0.0000")),
    ("Ireland", "A1", Decimal("0.0068"), Decimal("0.0528"), Decimal("0.0068")),
]

# ---------------------------------------------------------------------------
# 3. Damodaran industries -- common industries for v1 (Damodaran Jan 2025)
# ---------------------------------------------------------------------------
# (industry_name, num_firms, unlevered_beta, avg_effective_tax_rate,
#  avg_debt_to_equity, avg_operating_margin, avg_roc,
#  avg_reinvestment_rate, cost_of_capital, fundamental_growth_rate)
DAMODARAN_INDUSTRIES: list[
    tuple[
        str, int, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal
    ]
] = [
    # fmt: off
    (
        "Software (System & Application)",
        393,
        Decimal("1.2200"),
        Decimal("0.0600"),
        Decimal("0.0600"),
        Decimal("0.2100"),
        Decimal("0.3000"),
        Decimal("0.3500"),
        Decimal("0.1000"),
        Decimal("0.1050"),
    ),
    (
        "Semiconductor",
        80,
        Decimal("1.4000"),
        Decimal("0.0900"),
        Decimal("0.0500"),
        Decimal("0.2600"),
        Decimal("0.2200"),
        Decimal("0.4000"),
        Decimal("0.1100"),
        Decimal("0.0880"),
    ),
    (
        "Computer Services",
        130,
        Decimal("1.1500"),
        Decimal("0.1000"),
        Decimal("0.1200"),
        Decimal("0.1200"),
        Decimal("0.1800"),
        Decimal("0.4000"),
        Decimal("0.1000"),
        Decimal("0.0720"),
    ),
    (
        "Internet/E-Commerce",
        48,
        Decimal("1.3200"),
        Decimal("0.0800"),
        Decimal("0.0400"),
        Decimal("0.1500"),
        Decimal("0.1500"),
        Decimal("0.5000"),
        Decimal("0.1100"),
        Decimal("0.0750"),
    ),
    (
        "Retail (General)",
        18,
        Decimal("0.8800"),
        Decimal("0.2200"),
        Decimal("0.2500"),
        Decimal("0.0700"),
        Decimal("0.1500"),
        Decimal("0.5000"),
        Decimal("0.0900"),
        Decimal("0.0750"),
    ),
    (
        "Retail (Online)",
        63,
        Decimal("1.2800"),
        Decimal("0.0800"),
        Decimal("0.0800"),
        Decimal("0.0800"),
        Decimal("0.1400"),
        Decimal("0.5500"),
        Decimal("0.1000"),
        Decimal("0.0770"),
    ),
    (
        "Auto & Truck",
        26,
        Decimal("1.0200"),
        Decimal("0.1000"),
        Decimal("0.4200"),
        Decimal("0.0800"),
        Decimal("0.1000"),
        Decimal("0.6000"),
        Decimal("0.0900"),
        Decimal("0.0600"),
    ),
    (
        "Pharmaceuticals",
        280,
        Decimal("1.1000"),
        Decimal("0.0400"),
        Decimal("0.0800"),
        Decimal("0.1800"),
        Decimal("0.1200"),
        Decimal("0.4500"),
        Decimal("0.0900"),
        Decimal("0.0540"),
    ),
    (
        "Biotechnology",
        598,
        Decimal("1.3000"),
        Decimal("0.0100"),
        Decimal("0.1500"),
        Decimal("-0.5000"),
        Decimal("-0.1000"),
        Decimal("0.8000"),
        Decimal("0.1000"),
        Decimal("-0.0800"),
    ),
    (
        "Oil/Gas (Production)",
        200,
        Decimal("1.1500"),
        Decimal("0.0800"),
        Decimal("0.3000"),
        Decimal("0.3000"),
        Decimal("0.1200"),
        Decimal("0.5000"),
        Decimal("0.0900"),
        Decimal("0.0600"),
    ),
    (
        "Utilities (General)",
        18,
        Decimal("0.3500"),
        Decimal("0.1200"),
        Decimal("1.1000"),
        Decimal("0.2000"),
        Decimal("0.0600"),
        Decimal("0.6000"),
        Decimal("0.0500"),
        Decimal("0.0360"),
    ),
    (
        "Banks (Regional)",
        590,
        Decimal("0.4500"),
        Decimal("0.1800"),
        Decimal("0.7000"),
        Decimal("0.3500"),
        Decimal("0.0800"),
        Decimal("0.6000"),
        Decimal("0.0600"),
        Decimal("0.0480"),
    ),
    (
        "Insurance (General)",
        50,
        Decimal("0.6500"),
        Decimal("0.1500"),
        Decimal("0.4000"),
        Decimal("0.1000"),
        Decimal("0.0800"),
        Decimal("0.5000"),
        Decimal("0.0700"),
        Decimal("0.0400"),
    ),
    (
        "Telecom Services",
        55,
        Decimal("0.6500"),
        Decimal("0.1200"),
        Decimal("0.8000"),
        Decimal("0.2000"),
        Decimal("0.0900"),
        Decimal("0.5500"),
        Decimal("0.0600"),
        Decimal("0.0495"),
    ),
    (
        "Entertainment",
        110,
        Decimal("1.1000"),
        Decimal("0.0500"),
        Decimal("0.2000"),
        Decimal("0.1000"),
        Decimal("0.0800"),
        Decimal("0.5000"),
        Decimal("0.0900"),
        Decimal("0.0400"),
    ),
    (
        "Healthcare Services",
        107,
        Decimal("0.9500"),
        Decimal("0.1000"),
        Decimal("0.3500"),
        Decimal("0.0800"),
        Decimal("0.1000"),
        Decimal("0.5000"),
        Decimal("0.0800"),
        Decimal("0.0500"),
    ),
    (
        "Aerospace/Defense",
        77,
        Decimal("1.0500"),
        Decimal("0.1200"),
        Decimal("0.2500"),
        Decimal("0.1200"),
        Decimal("0.1500"),
        Decimal("0.4500"),
        Decimal("0.0900"),
        Decimal("0.0675"),
    ),
    (
        "Food Processing",
        92,
        Decimal("0.6500"),
        Decimal("0.1400"),
        Decimal("0.3000"),
        Decimal("0.1200"),
        Decimal("0.1200"),
        Decimal("0.5000"),
        Decimal("0.0700"),
        Decimal("0.0600"),
    ),
    (
        "Beverage (Alcoholic)",
        25,
        Decimal("0.7000"),
        Decimal("0.1500"),
        Decimal("0.2000"),
        Decimal("0.1800"),
        Decimal("0.1400"),
        Decimal("0.4500"),
        Decimal("0.0700"),
        Decimal("0.0630"),
    ),
    (
        "Real Estate (General)",
        12,
        Decimal("0.5500"),
        Decimal("0.0800"),
        Decimal("0.5000"),
        Decimal("0.2500"),
        Decimal("0.0500"),
        Decimal("0.5000"),
        Decimal("0.0600"),
        Decimal("0.0250"),
    ),
    (
        "Transportation",
        35,
        Decimal("0.8000"),
        Decimal("0.1500"),
        Decimal("0.5500"),
        Decimal("0.1200"),
        Decimal("0.1000"),
        Decimal("0.5500"),
        Decimal("0.0700"),
        Decimal("0.0550"),
    ),
    (
        "Mining (Diversified)",
        85,
        Decimal("1.0000"),
        Decimal("0.1200"),
        Decimal("0.2000"),
        Decimal("0.1800"),
        Decimal("0.1000"),
        Decimal("0.5000"),
        Decimal("0.0900"),
        Decimal("0.0500"),
    ),
    (
        "Electric Utilities",
        55,
        Decimal("0.3800"),
        Decimal("0.1000"),
        Decimal("1.0000"),
        Decimal("0.2200"),
        Decimal("0.0700"),
        Decimal("0.5500"),
        Decimal("0.0500"),
        Decimal("0.0385"),
    ),
    (
        "Advertising",
        50,
        Decimal("1.0800"),
        Decimal("0.0800"),
        Decimal("0.1500"),
        Decimal("0.1000"),
        Decimal("0.1200"),
        Decimal("0.5000"),
        Decimal("0.0900"),
        Decimal("0.0600"),
    ),
    (
        "Chemical (Specialty)",
        90,
        Decimal("1.0200"),
        Decimal("0.1400"),
        Decimal("0.2200"),
        Decimal("0.1400"),
        Decimal("0.1200"),
        Decimal("0.5000"),
        Decimal("0.0900"),
        Decimal("0.0600"),
    ),
    # fmt: on
]


async def seed_damodaran_data(session: AsyncSession) -> dict[str, int]:
    """Seed Damodaran reference data. Idempotent check-then-insert/update."""
    now = datetime.now(timezone.utc)
    counts: dict[str, int] = {}

    # -- default_spreads ---------------------------------------------------
    result = await session.execute(select(DefaultSpread))
    existing_spreads = {row.rating: row for row in result.scalars().all()}

    inserted = updated = 0
    for rating, spread in DEFAULT_SPREADS:
        if rating in existing_spreads:
            row = existing_spreads[rating]
            row.spread_over_treasury = spread
            row.updated_at = now
            updated += 1
        else:
            session.add(
                DefaultSpread(
                    rating=rating,
                    spread_over_treasury=spread,
                    updated_at=now,
                )
            )
            inserted += 1
    counts["default_spreads"] = inserted + updated
    logger.info("default_spreads seeded: %d inserted, %d updated", inserted, updated)

    # -- country_risk_premiums ---------------------------------------------
    result = await session.execute(select(CountryRiskPremium))
    existing_countries = {row.country: row for row in result.scalars().all()}

    inserted = updated = 0
    for country, moody, ds, erp, crp in COUNTRY_RISK_PREMIUMS:
        if country in existing_countries:
            row = existing_countries[country]
            row.moody_rating = moody
            row.default_spread = ds
            row.equity_risk_premium = erp
            row.country_risk_premium = crp
            row.updated_at = now
            updated += 1
        else:
            session.add(
                CountryRiskPremium(
                    country=country,
                    moody_rating=moody,
                    default_spread=ds,
                    equity_risk_premium=erp,
                    country_risk_premium=crp,
                    updated_at=now,
                )
            )
            inserted += 1
    counts["country_risk_premiums"] = inserted + updated
    logger.info(
        "country_risk_premiums seeded: %d inserted, %d updated", inserted, updated
    )

    # -- damodaran_industries ----------------------------------------------
    result = await session.execute(select(DamodaranIndustry))
    existing_industries = {row.industry_name: row for row in result.scalars().all()}

    inserted = updated = 0
    for (
        name,
        num_firms,
        beta,
        tax,
        de,
        margin,
        roc,
        reinvest,
        coc,
        growth,
    ) in DAMODARAN_INDUSTRIES:
        if name in existing_industries:
            row = existing_industries[name]
            row.num_firms = num_firms
            row.unlevered_beta = beta
            row.avg_effective_tax_rate = tax
            row.avg_debt_to_equity = de
            row.avg_operating_margin = margin
            row.avg_roc = roc
            row.avg_reinvestment_rate = reinvest
            row.cost_of_capital = coc
            row.fundamental_growth_rate = growth
            row.updated_at = now
            updated += 1
        else:
            session.add(
                DamodaranIndustry(
                    industry_name=name,
                    num_firms=num_firms,
                    unlevered_beta=beta,
                    avg_effective_tax_rate=tax,
                    avg_debt_to_equity=de,
                    avg_operating_margin=margin,
                    avg_roc=roc,
                    avg_reinvestment_rate=reinvest,
                    cost_of_capital=coc,
                    fundamental_growth_rate=growth,
                    updated_at=now,
                )
            )
            inserted += 1
    counts["damodaran_industries"] = inserted + updated
    logger.info(
        "damodaran_industries seeded: %d inserted, %d updated", inserted, updated
    )

    await session.commit()
    logger.info("Damodaran seed complete: %s", counts)
    return counts
