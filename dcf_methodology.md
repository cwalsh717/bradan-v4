# DCF Methodology Reference — Damodaran FCFF Valuation

This document supplements `bradan_v4_spec.md` with implementation-level detail for the DCF engine. Source: Aswath Damodaran's DCF Valuation course (Sessions 1–24).

---

## 1. Model Structure: Two-Stage FCFF

The engine uses a **two-stage firm valuation (FCFF)** model:
- **Stage 1 (High Growth):** 5–10 year explicit forecast period. Growth, reinvestment, beta, debt ratio, and ROC transition linearly from current values to stable-state values.
- **Stage 2 (Terminal/Stable Growth):** Perpetuity via the Gordon Growth model.

Year-by-year projection: for each year in the high-growth period, compute EBIT(1-t), reinvestment, and FCFF. Discount each year's FCFF at the WACC for that year (WACC changes as beta and debt ratio transition).

```
Value of Operating Assets = Σ [FCFF_t / (1 + WACC_t)^t]  +  Terminal Value / (1 + WACC_n)^n
```

---

## 2. Current Cash Flow Construction (Base Year)

### FCFF Formula
```
FCFF = EBIT(1-t) - Reinvestment
Reinvestment = (CapEx - Depreciation) + ΔWorking Capital
```

### Getting EBIT Right
Before computing, adjust EBIT for:
1. **R&D capitalization** (optional/future): R&D is an operating expense in GAAP but is really a capital expense. Capitalizing it increases EBIT but also increases invested capital. For v4, use reported EBIT without R&D adjustment (note: this is a known simplification).
2. **One-time/non-recurring items**: If TTM EBIT includes extraordinary charges, the model should still use reported figures (user can override via sliders).
3. **Negative EBIT**: If EBIT(1-t) is negative, the company is not DCF-eligible in our system. Return a clear "insufficient data" response. Do NOT attempt to project negative cash flows forward.

### TTM Computation
- Sum the latest 4 quarterly income statements for: revenue, EBIT, CapEx, depreciation, interest expense, tax provision
- Sum the latest 4 quarterly cash flow statements for: CapEx, depreciation
- Use the **most recent quarter's** balance sheet for: total debt, cash, working capital, shares outstanding, book value of equity

### Key Ratios from Base Year
```
Tax Rate = Tax Provision / Pre-tax Income (from TTM; floor at 0%, cap at marginal rate ~25% for US)
Return on Capital (ROC) = EBIT(1-t) / (BV of Equity + BV of Debt - Cash)
Reinvestment Rate = Reinvestment / EBIT(1-t)
```

If effective tax rate < 0 or > 50%, use marginal tax rate (default 25% for US companies).

---

## 3. Cost of Equity (CAPM)

```
Cost of Equity = Risk-free Rate + Levered Beta × Equity Risk Premium + Country Risk Premium
```

### Risk-free Rate
- Source: FRED DGS10 (10-year US Treasury yield)
- This also serves as the ceiling for the stable growth rate

### Beta
- **Unlevered (asset) beta**: From `damodaran_industries` table, sector average
- **Levered beta** = Unlevered Beta × (1 + (1 - tax rate) × (D/E))
- D/E = market debt / market equity (use book debt as proxy for market debt; market cap for equity)
- In **stable growth**: beta converges toward 1.0 (the market average)

### Equity Risk Premium
- Source: `country_risk_premiums` table
- For US companies: use the base mature market premium (~5–6%, from Damodaran's annual update)
- For non-US: mature market premium + country risk premium

### Transition During High-Growth Period
Beta moves linearly from current levered beta to stable beta (1.0) over the forecast period. Each year recalculate:
```
beta_year_t = current_beta + (stable_beta - current_beta) × (t / n)
```

---

## 4. Cost of Debt

```
Pre-tax Cost of Debt = Risk-free Rate + Default Spread
After-tax Cost of Debt = Pre-tax Cost of Debt × (1 - tax rate)
```

### Synthetic Rating via Interest Coverage
If no actual bond rating is available, estimate from interest coverage ratio:

```
Interest Coverage Ratio = EBIT / Interest Expense
```

| Coverage Ratio | Rating | Spread (approx) |
|---|---|---|
| > 8.50 | AAA | 0.75% |
| 6.50–8.50 | AA | 1.00% |
| 5.50–6.50 | A+ | 1.50% |
| 4.25–5.50 | A | 1.80% |
| 3.00–4.25 | A- | 2.00% |
| 2.50–3.00 | BBB | 2.25% |
| 2.25–2.50 | BB+ | 2.75% |
| 2.00–2.25 | BB | 3.50% |
| 1.75–2.00 | B+ | 4.75% |
| 1.50–1.75 | B | 6.50% |
| 1.25–1.50 | B- | 8.00% |
| 0.80–1.25 | CCC | 10.00% |
| 0.65–0.80 | CC | 11.50% |
| 0.20–0.65 | C | 12.70% |
| < 0.20 | D | 15.00% |

Use `default_spreads` table in database (these values are the seed data). The lookup maps coverage ratio → rating → spread.

### Edge Case: Zero or Negative Interest Expense
If interest expense is zero or negative, assign AAA rating (company has no/negligible debt).

---

## 5. WACC (Weighted Average Cost of Capital)

```
WACC = Cost of Equity × (E / (D+E)) + Cost of Debt × (1-t) × (D / (D+E))
```

- **Weights must be market values**, not book values
- E = market cap (shares outstanding × current price)
- D = book value of total debt (reasonable proxy for market value for most firms)

### Transition During High-Growth Period
Debt ratio moves linearly from current to target stable debt ratio:
```
debt_ratio_year_t = current_D/(D+E) + (stable_debt_ratio - current_D/(D+E)) × (t / n)
```
In stable growth, use either sector average debt ratio or an optimal capital structure estimate. Default: sector average from `damodaran_industries`.

---

## 6. Growth Rate Estimation

```
Expected Growth in EBIT(1-t) = Reinvestment Rate × Return on Capital
```

This is the **fundamental growth equation** — growth is a function of how much you reinvest and how well you invest.

### High-Growth Period
- Use company's current reinvestment rate and ROC to compute initial growth
- If reinvestment rate > 100% (company investing more than it earns), growth is being funded by external capital — flag this but still compute
- If ROC < WACC, the company is destroying value with its reinvestments — flag this

### Transition to Stable Growth
Growth rate decreases linearly from high-growth rate to stable growth rate:
```
growth_year_t = high_growth + (stable_growth - high_growth) × (t / n)
```

### Stable Growth Rate
- **Cannot exceed the risk-free rate** (hard cap). Rationale: risk-free rate ≈ nominal GDP growth rate in the long run
- Can be negative (implies firm shrinks over time)
- Default: risk-free rate (optimistic) or risk-free rate - 1% (moderate)
- User can adjust via slider within [−2%, risk-free rate] range

---

## 7. Terminal Value

```
Terminal Value = FCFF_n+1 / (WACC_stable - g_stable)
```

Where:
```
FCFF_n+1 = EBIT_n+1 × (1-t) × (1 - Reinvestment Rate_stable)
Reinvestment Rate_stable = g_stable / ROC_stable
```

### Critical: ROC in Stable Growth
- **Default assumption**: ROC converges to WACC (excess returns = 0). This means terminal value is **invariant to growth rate** — the right default for most firms.
- If ROC_stable > WACC_stable: firm earns perpetual excess returns (only justified for firms with durable competitive advantages). Terminal value increases with growth.
- If ROC_stable < WACC_stable: firm destroys value in perpetuity. Terminal value decreases with growth.

```
# When ROC = WACC (default):
Reinvestment Rate_stable = g / WACC
# Terminal value simplifies — growth doesn't matter because extra growth
# requires extra reinvestment that earns exactly the cost of capital
```

### Terminal Value as % of Total Value
Terminal value typically represents 60–80%+ of total firm value. This is normal and expected — it reflects that most returns from stocks come from long-term price appreciation. This is NOT a flaw in DCF.

---

## 8. Equity Bridge (Operating Assets → Equity Value per Share)

```
Enterprise Value = PV of FCFFs + PV of Terminal Value
Equity Value = Enterprise Value + Cash - Total Debt - Minority Interests - Preferred Stock
Value per Share = Equity Value / Shares Outstanding
```

### What to Add
- **Cash and marketable securities**: from latest balance sheet (use total cash + short-term investments)

### What to Subtract
- **Total debt**: short-term + long-term debt from balance sheet
- **Minority interests**: if reported (rare for most US companies; set to 0 if not available)
- **Preferred stock**: if any (set to 0 if not available)
- **Employee stock options**: ideally value as options and subtract (v4 simplification: ignore, note as limitation)

---

## 9. Sensitivity Analysis

Generate a matrix: **WACC vs. Terminal Growth Rate**

- WACC range: computed WACC ± 2%, in 0.5% increments (9 columns)
- Growth range: 0% to risk-free rate, in 0.5% increments (variable rows)
- Each cell = implied Value per Share

This is the `GET /api/dcf/{symbol}/sensitivity` endpoint.

---

## 10. Scenario Presets

### Conservative
- Growth: sector average reinvestment rate × sector average ROC
- Beta: current (no improvement assumed)
- Debt ratio: current (no optimization)
- Terminal ROC = WACC (no excess returns)
- Terminal growth = risk-free rate - 2%

### Moderate (Default)
- Growth: company's current reinvestment rate × current ROC
- Beta: transitions to 1.0
- Debt ratio: transitions to sector average
- Terminal ROC = WACC
- Terminal growth = risk-free rate - 1%

### Optimistic
- Growth: company's current reinvestment rate × current ROC (or higher if justified)
- Beta: transitions to 0.8–1.0
- Debt ratio: transitions toward optimal
- Terminal ROC = 1.5× WACC (sustained competitive advantage)
- Terminal growth = risk-free rate

---

## 11. DCF Eligibility Rules

A stock is **NOT eligible** for DCF if:
- No income statement data (cannot compute EBIT)
- No balance sheet data (cannot compute invested capital, debt, cash)
- EBIT is negative for TTM (v4 does not handle negative earnings companies)
- No price data (cannot compute market cap for WACC weights)
- Sector mapping confidence < 60% (cannot look up beta, industry averages)
- Financial company (banks, insurance, REITs) — FCFF model is inappropriate for these; they need FCFE model. v4 should check SIC/industry and return "financial firms not supported" message.

---

## 12. Implementation Checklist for Claude Code

The DCF engine should be built as a pure computation module (`backend/app/services/dcf_engine.py`) that:

1. **Takes inputs** (either computed defaults or user overrides) as a typed dataclass/Pydantic model
2. **Returns outputs** as a structured result (year-by-year projections, terminal value, equity bridge, value per share, sensitivity matrix)
3. **Has zero database access** — it receives data, computes, returns results. The router/service layer handles DB queries and passes data in.
4. **Is fully testable** with hardcoded inputs → expected outputs (use the SAP example from session 10 as a validation case)

### SAP Validation Case (from Damodaran Session 10)
Use this to validate the engine produces correct numbers:
```
Inputs:
  EBIT(1-t) = 1,414M EUR
  Reinvestment = 812M EUR (CapEx 831 - Depr + WC change -19)
  Reinvestment Rate = 57.42%
  ROC = 19.93%
  Growth = 57.42% × 19.93% = 11.44%
  Risk-free = 3.41%
  Unlevered beta = 1.25
  Current D/E ≈ 1.4%
  Levered beta = 1.26
  ERP = 4.25% (4% mature + 0.25% country)
  Cost of equity = 3.41% + 1.26 × 4.25% = 8.77%
  Cost of debt after-tax = 2.39%
  WACC = 8.77%(0.986) + 2.39%(0.014) = 8.68%
  
  Stable: g=3.41%, beta=1.0, D/E=20%, ROC=6.62%, WACC=6.62%

Expected Output:
  Operating Assets Value ≈ 31,615M EUR
  + Cash 3,018 - Debt 558 - Pension 305 - Minority 55
  Equity Value ≈ 34,656M (adjusted)
  - Options 180
  Value/Share ≈ 106.12 EUR
  (Actual trading price: 122 EUR)
```

### Test Strategy
- Unit test the engine with the SAP case above
- Unit test each sub-computation independently (WACC calc, beta levering, terminal value, equity bridge)
- Test edge cases: zero debt, very high debt, negative working capital change, growth > risk-free (should cap)
- Test that slider overrides actually change the output
- Test sensitivity matrix dimensions and that center cell matches base case
