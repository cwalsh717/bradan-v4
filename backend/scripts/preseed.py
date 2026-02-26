"""Pre-seed script: bulk-insert S&P 500 + Nasdaq 100 stock stubs.

Creates Stock rows (symbol + placeholder name) so the search endpoint
works immediately on first boot.  Full profile data is fetched on-demand
by StockDataService.fetch_full_profile().

Usage:
    cd backend && python -m scripts.preseed
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.stocks import Stock

logger = logging.getLogger(__name__)

# fmt: off
# Deduplicated S&P 500 + Nasdaq 100 constituents (as of early 2026).
# ~530 unique symbols.  Running the script twice is safe (idempotent).
PRESEED_SYMBOLS: tuple[str, ...] = (
    "A", "AAPL", "ABBV", "ABNB", "ABT", "ACGL", "ACN", "ADBE", "ADI", "ADM",
    "ADP", "ADSK", "AEE", "AEP", "AES", "AFL", "AIG", "AIZ", "AJG", "AKAM",
    "ALB", "ALGN", "ALL", "ALLE", "AMAT", "AMCR", "AMD", "AME", "AMGN", "AMP",
    "AMT", "AMZN", "ANET", "ANSS", "AON", "AOS", "APA", "APD", "APH", "APTV",
    "ARE", "ARM", "ASML", "ATVI", "AVGO", "AVY", "AXP", "AZO",
    "BA", "BAC", "BAX", "BBWI", "BBY", "BDX", "BEN", "BF.B", "BG", "BIIB",
    "BIO", "BK", "BKNG", "BKR", "BLK", "BMY", "BR", "BRK.B", "BRO", "BSX",
    "BWA", "BXP",
    "C", "CAG", "CAH", "CARR", "CAT", "CB", "CBOE", "CBRE", "CCI", "CCL",
    "CDNS", "CDW", "CE", "CEG", "CF", "CFG", "CHD", "CHRW", "CHTR", "CI",
    "CINF", "CL", "CLX", "CMA", "CMCSA", "CME", "CMG", "CMI", "CMS", "CNC",
    "CNP", "COF", "COO", "COP", "COST", "CPAY", "CPB", "CPRT", "CPT", "CRL",
    "CRM", "CRWD", "CSCO", "CSGP", "CSX", "CTAS", "CTLT", "CTRA", "CTSH",
    "CTVA", "CVS", "CVX", "CZR",
    "D", "DAL", "DASH", "DD", "DE", "DECK", "DFS", "DG", "DGX", "DHI", "DHR",
    "DIS", "DISH", "DLTR", "DOV", "DOW", "DPZ", "DRI", "DTE", "DUK", "DVA",
    "DVN", "DXCM",
    "EA", "EBAY", "ECL", "ED", "EFX", "EIX", "EL", "EMN", "EMR", "ENPH",
    "EOG", "EPAM", "EQIX", "EQR", "EQT", "ES", "ESS", "ETN", "ETR", "EVRG",
    "EW", "EXC", "EXPD", "EXPE", "EXR",
    "F", "FANG", "FAST", "FBIN", "FCX", "FDS", "FDX", "FE", "FFIV", "FI",
    "FISV", "FITB", "FLT", "FMC", "FOX", "FOXA", "FRT", "FSLR", "FTNT",
    "FTV",
    "GILD", "GIS", "GL", "GLW", "GM", "GNRC", "GOOG", "GOOGL", "GPC", "GPN",
    "GRMN", "GS", "GWW",
    "HAL", "HAS", "HBAN", "HCA", "HD", "HOLX", "HON", "HPE", "HPQ", "HRL",
    "HSIC", "HST", "HSY", "HUBB", "HUM", "HWM",
    "IBM", "ICE", "IDXX", "IEX", "IFF", "ILMN", "INCY", "INTC", "INTU", "INVH",
    "IP", "IPG", "IQV", "IR", "IRM", "ISRG", "IT", "ITW", "IVZ",
    "J", "JBHT", "JCI", "JKHY", "JNJ", "JNPR", "JPM",
    "K", "KDP", "KEY", "KEYS", "KHC", "KIM", "KLAC", "KMB", "KMI", "KMX",
    "KO", "KR",
    "L", "LDOS", "LEN", "LH", "LHX", "LIN", "LKQ", "LLY", "LMT", "LNT",
    "LOW", "LRCX", "LULU", "LUV", "LVS", "LW", "LYB", "LYV",
    "MA", "MAA", "MAR", "MAS", "MCD", "MCHP", "MCK", "MCO", "MDLZ", "MDT",
    "MELI", "MET", "META", "MGM", "MHK", "MKC", "MKTX", "MLM", "MMC", "MMM",
    "MNST", "MO", "MOH", "MOS", "MPC", "MPWR", "MRK", "MRNA", "MRVL", "MS",
    "MSCI", "MSFT", "MSI", "MTB", "MTCH", "MTD", "MU", "NCLH",
    "NDAQ", "NDSN", "NEE", "NEM", "NFLX", "NI", "NKE", "NOC", "NOW", "NRG",
    "NSC", "NTAP", "NTRS", "NUE", "NVDA", "NVR", "NWL", "NWS", "NWSA",
    "O", "ODFL", "OGN", "OKE", "OMC", "ON", "ORCL", "ORLY", "OTIS", "OXY",
    "PANW", "PARA", "PAYC", "PAYX", "PCAR", "PCG", "PDD", "PEAK", "PEG",
    "PEP", "PFE", "PFG", "PG", "PGR", "PH", "PHM", "PKG", "PLD", "PM",
    "PNC", "PNR", "PNW", "PODD", "POOL", "PPG", "PPL", "PRU", "PSA", "PSX",
    "PTC", "PVH", "PWR", "PXD", "PYPL",
    "QCOM", "QRVO",
    "RCL", "RE", "REG", "REGN", "RF", "RHI", "RJF", "RL", "RMD", "ROK",
    "ROL", "ROP", "ROST", "RSG", "RTX",
    "SBAC", "SBNY", "SBUX", "SCHW", "SEE", "SHW", "SIVB", "SJM", "SLB",
    "SMCI", "SNA", "SNPS", "SO", "SPG", "SPGI", "SRE", "STE", "STLD", "STT",
    "STX", "STZ", "SWK", "SWKS", "SYF", "SYK", "SYY",
    "T", "TAP", "TDG", "TDY", "TEAM", "TECH", "TEL", "TER", "TFC", "TFX",
    "TGT", "TJX", "TMO", "TMUS", "TPR", "TRGP", "TRMB", "TROW", "TRV",
    "TSCO", "TSLA", "TSN", "TT", "TTWO", "TXN", "TXT", "TYL",
    "UAL", "UDR", "UHS", "ULTA", "UNH", "UNP", "UPS", "URI", "USB",
    "V", "VFC", "VICI", "VLO", "VLTO", "VMC", "VRSK", "VRSN", "VRTX", "VTR",
    "VTRS", "VZ",
    "WAB", "WAT", "WBA", "WBD", "WDC", "WEC", "WELL", "WFC", "WHR", "WM",
    "WMB", "WMT", "WRB", "WRK", "WST", "WTW", "WY", "WYNN",
    "XEL", "XOM", "XRAY", "XYL",
    "YUM",
    "ZBH", "ZBRA", "ZION", "ZTS",
)
# fmt: on


async def preseed_tickers(session: AsyncSession) -> dict:
    """Insert stock stubs for all pre-seed symbols.  Idempotent.

    Returns a summary dict with inserted/skipped/total counts.
    """
    result = await session.execute(select(Stock.symbol))
    existing = {row for row in result.scalars().all()}

    inserted = 0
    skipped = 0

    for symbol in PRESEED_SYMBOLS:
        if symbol in existing:
            skipped += 1
        else:
            session.add(Stock(symbol=symbol, name=symbol))
            inserted += 1

    await session.commit()

    logger.info("Pre-seed: %d inserted, %d skipped, %d total",
                inserted, skipped, len(PRESEED_SYMBOLS))
    return {"inserted": inserted, "skipped": skipped, "total": len(PRESEED_SYMBOLS)}


async def main():
    logging.basicConfig(level=logging.INFO)
    async with async_session() as session:
        result = await preseed_tickers(session)
        print(f"Pre-seed complete: {result}")


if __name__ == "__main__":
    asyncio.run(main())
