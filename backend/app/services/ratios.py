"""Compute financial ratios on-the-fly from TTM income + latest balance sheet.

All ratios are computed — never stored. Missing inputs yield None for that ratio.
"""

from typing import Any, Optional


def _safe_get(data: dict, *keys) -> Optional[float]:
    """Try multiple keys in order, returning the first numeric value found."""
    for key in keys:
        val = data.get(key)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return None


def compute_ratios(
    ttm: dict,
    current_price: Optional[float] = None,
    shares_outstanding: Optional[float] = None,
) -> dict[str, Optional[float]]:
    """Compute financial ratios from TTM data.

    Parameters
    ----------
    ttm : dict
        TTM snapshot with "income", "balance_sheet", and optionally "cash_flow" dicts.
    current_price : float or None
        Current stock price (for valuation ratios). None => valuation ratios are null.
    shares_outstanding : float or None
        Shares outstanding override. If None, pulled from balance_sheet.

    Returns
    -------
    dict[str, Optional[float]]
        Flat dict of ratio name -> value (or None if not computable).
    """
    income: dict[str, Any] = ttm.get("income", {})
    balance: dict[str, Any] = ttm.get("balance_sheet", {})
    cash_flow: dict[str, Any] = ttm.get("cash_flow", {})

    # --- Extract raw inputs ---
    revenue = _safe_get(income, "revenue", "total_revenue")
    gross_profit = _safe_get(income, "gross_profit")
    operating_income = _safe_get(income, "operating_income", "ebit")
    net_income = _safe_get(
        income, "net_income", "net_income_applicable_to_common_shares"
    )
    interest_expense = _safe_get(income, "interest_expense")
    cost_of_revenue = _safe_get(income, "cost_of_revenue", "cost_of_goods_sold")

    total_assets = _safe_get(balance, "total_assets")
    total_equity = _safe_get(
        balance,
        "total_shareholders_equity",
        "stockholders_equity",
        "total_equity",
    )
    total_debt = _safe_get(balance, "total_debt")
    if total_debt is None:
        short = _safe_get(balance, "short_term_debt") or 0
        long = _safe_get(balance, "long_term_debt") or 0
        if short or long:
            total_debt = short + long

    current_assets = _safe_get(balance, "current_assets")
    current_liabilities = _safe_get(balance, "current_liabilities")
    inventory = _safe_get(balance, "inventory")
    cash = _safe_get(
        balance,
        "cash_and_cash_equivalents",
        "cash_and_short_term_investments",
    )

    shares = shares_outstanding
    if shares is None:
        shares = _safe_get(
            balance,
            "shares_outstanding",
            "common_shares_outstanding",
        )

    # Derived: gross profit from revenue - COGS if not directly available
    if gross_profit is None and revenue is not None and cost_of_revenue is not None:
        gross_profit = revenue - cost_of_revenue

    # EBITDA: operating income + depreciation/amortisation
    depreciation = _safe_get(
        cash_flow,
        "depreciation_and_amortization",
        "depreciation",
    )
    ebitda: Optional[float] = None
    if operating_income is not None and depreciation is not None:
        ebitda = operating_income + depreciation
    elif operating_income is not None:
        ebitda = operating_income  # fallback without D&A

    # --- Profitability ---
    gross_margin = _div(gross_profit, revenue)
    operating_margin = _div(operating_income, revenue)
    net_margin = _div(net_income, revenue)
    roe = _div(net_income, total_equity)
    roa = _div(net_income, total_assets)

    # ROIC = EBIT*(1-t) / (total_debt + equity - cash)
    roic: Optional[float] = None
    if operating_income is not None and total_equity is not None:
        # Approximate tax rate from income data
        pretax = _safe_get(income, "income_before_tax", "pretax_income")
        tax_expense = _safe_get(income, "income_tax_expense", "tax_provision")
        tax_rate = 0.0
        if pretax and tax_expense and pretax > 0:
            tax_rate = tax_expense / pretax
        nopat = operating_income * (1 - tax_rate)
        invested_capital = (total_equity or 0) + (total_debt or 0) - (cash or 0)
        if invested_capital > 0:
            roic = nopat / invested_capital

    # --- Liquidity ---
    current_ratio = _div(current_assets, current_liabilities)
    quick_ratio: Optional[float] = None
    if current_assets is not None and current_liabilities is not None:
        inv = inventory or 0
        if current_liabilities > 0:
            quick_ratio = (current_assets - inv) / current_liabilities

    # --- Leverage ---
    debt_to_equity = _div(total_debt, total_equity)
    debt_to_assets = _div(total_debt, total_assets)
    interest_coverage: Optional[float] = None
    if (
        operating_income is not None
        and interest_expense is not None
        and interest_expense > 0
    ):
        interest_coverage = operating_income / interest_expense

    # --- Valuation (need price + shares) ---
    market_cap: Optional[float] = None
    if current_price is not None and shares is not None and shares > 0:
        market_cap = current_price * shares

    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    ev_to_ebitda: Optional[float] = None

    if market_cap is not None:
        if net_income is not None and net_income > 0:
            pe_ratio = market_cap / net_income
        if total_equity is not None and total_equity > 0:
            pb_ratio = market_cap / total_equity
        if revenue is not None and revenue > 0:
            ps_ratio = market_cap / revenue
        if ebitda is not None and ebitda > 0:
            ev = market_cap + (total_debt or 0) - (cash or 0)
            ev_to_ebitda = ev / ebitda

    # --- Efficiency ---
    asset_turnover = _div(revenue, total_assets)
    inventory_turnover: Optional[float] = None
    if cost_of_revenue is not None and inventory is not None and inventory > 0:
        inventory_turnover = cost_of_revenue / inventory

    # --- Round all values ---
    def _round(v: Optional[float], decimals: int = 4) -> Optional[float]:
        if v is None:
            return None
        return round(v, decimals)

    return {
        # Profitability
        "gross_margin": _round(gross_margin),
        "operating_margin": _round(operating_margin),
        "net_margin": _round(net_margin),
        "roe": _round(roe),
        "roa": _round(roa),
        "roic": _round(roic),
        # Liquidity
        "current_ratio": _round(current_ratio),
        "quick_ratio": _round(quick_ratio),
        # Leverage
        "debt_to_equity": _round(debt_to_equity),
        "debt_to_assets": _round(debt_to_assets),
        "interest_coverage": _round(interest_coverage),
        # Valuation
        "pe_ratio": _round(pe_ratio, 2),
        "pb_ratio": _round(pb_ratio, 2),
        "ps_ratio": _round(ps_ratio, 2),
        "ev_to_ebitda": _round(ev_to_ebitda, 2),
        # Efficiency
        "asset_turnover": _round(asset_turnover),
        "inventory_turnover": _round(inventory_turnover),
    }


def _div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Safe division: returns None if either input is None or denominator is zero."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator
