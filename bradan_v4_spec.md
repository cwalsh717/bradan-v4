# Bradán v4 — Backend Specification

## Project Overview

Bradán v4 is a stock research and valuation tool built as a portfolio project. It is not a brokerage competitor or trading companion — it is a research tool that maximizes actionable insight from premium market data APIs.

**Target audience:** Non-finance professionals (self-rated 4/10 financial literacy, with occasional 6/10 viewers). The backend is professional-grade; the frontend translates complexity into clarity.

**Core value proposition:** An on-demand DCF valuation engine grounded in Aswath Damodaran's framework, paired with a clean market dashboard and stock profile page.

---

## Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Backend | FastAPI (Python) | Async-native for websockets/API calls, readable for portfolio reviewers |
| Frontend | Next.js (React) | Industry standard, good Clerk integration |
| Database | PostgreSQL | Relational data model, strong JSONB support, Railway-native |
| Auth | Clerk (free tier) | Managed auth service, 10k MAU free, JWT verification on FastAPI |
| Hosting | Railway (3 services) | App, DB, and frontend as separate services (deployed) |
| Market Data | Twelve Data Pro tier ($230/mo) | Websockets (1,500 symbols), full financial statements, max history |
| Economic Data | FRED API | Risk-free rates, treasury yields, credit spreads |
| Valuation Framework | Damodaran (NYU) | 6 static reference datasets, updated annually |
| Charting | Recharts | React-native, composable, works with SSR/client components |
| Frontend Testing | Vitest + React Testing Library | Fast, ESM-native, jsdom environment |

---

## Architecture

### Service Topology (Railway)

- **Service 1:** FastAPI backend (Python)
- **Service 2:** PostgreSQL database (separate container — survives app redeploys)
- **Service 3:** Next.js frontend

### Data Flow

- **Twelve Data Websocket → FastAPI → Frontend clients:** Backend maintains one persistent websocket connection to Twelve Data. Fans out to all connected browser clients via FastAPI websocket endpoints.
- **Twelve Data REST → FastAPI → PostgreSQL:** Financial statements, price history, dividends, splits fetched on demand and cached in Postgres.
- **FRED API → PostgreSQL:** Daily fetch for treasury yields, credit spreads. Stored with history for sparklines.
- **Damodaran static files → PostgreSQL:** Annual manual/scripted refresh of industry reference data.
- **PostgreSQL → FastAPI → Frontend:** All cached data served from DB. Ratios, TTM, P&L computed on the fly — never stored.
- **CORS:** Backend allows requests from the Railway frontend domain via `CORSMiddleware`.

---

## Access Model

| Page | Auth Required | Notes |
|------|---------------|-------|
| Landing / Macro Dashboard | No | Public — good for LinkedIn traffic |
| Stock Profile | No | Public |
| DCF Model (default) | No | Public — system-computed valuation |
| DCF Model (save custom runs) | Yes | Clerk auth required to save |
| Portfolio Builder | Yes | Clerk auth required |
| Power Demand Dashboard | N/A | Placeholder — no data source yet |

---

## Database Schema (19 Tables)

### Domain 1: Dashboard

```
dashboard_tickers
├── id (PK)
├── category (text) — "equities", "rates", "credit", "currencies", "commodities", "critical_minerals", "crypto", "futures"
├── display_name (text) — "S&P 500 (SPY)"
├── symbol (text) — "SPY", "DGS10", "ES"
├── data_source (text) — "twelvedata_ws", "fred_daily"
├── display_format (text) — "price", "percentage"
├── display_order (int) — sort within category
├── is_active (bool) — toggle without deleting
```

**~28 tickers:** SPY, QQQ, IWM, VIXY, UKX, EWJ, FEZ, EWH, DGS2, DGS10, SPREAD_2S10S, BAMLC0A0CM, BAMLH0A0HYM2, UUP, USO, UNG, GLD, CPER, URA, LIT, REMX, BTC/USD, ETH/USD, ES, NQ, CL, GC

### Domain 2: Stock Profile

```
stocks
├── id (PK)
├── symbol (text, unique)
├── name (text)
├── exchange (text)
├── sector (text) — Twelve Data classification
├── industry (text) — Twelve Data classification
├── currency (text)
├── last_updated (timestamp)

financial_statements
├── id (PK)
├── stock_id (FK → stocks)
├── statement_type (text) — "income", "balance_sheet", "cash_flow"
├── period (text) — "annual", "quarterly"
├── fiscal_date (date)
├── data (jsonb) — full statement
├── fetched_at (timestamp)

price_history
├── id (PK)
├── stock_id (FK → stocks)
├── date (date)
├── open (decimal)
├── high (decimal)
├── low (decimal)
├── close (decimal)
├── volume (bigint)
├── fetched_at (timestamp)
├── UNIQUE(stock_id, date)

dividends
├── id (PK)
├── stock_id (FK → stocks)
├── ex_date (date)
├── amount (decimal)
├── fetched_at (timestamp)

stock_splits
├── id (PK)
├── stock_id (FK → stocks)
├── date (date)
├── ratio_from (int)
├── ratio_to (int)

earnings_calendar
├── id (PK)
├── stock_id (FK → stocks)
├── report_date (date)
├── fiscal_quarter (text)
├── confirmed (bool)
├── fetched_at (timestamp)
```

**Notes:**
- Price history stores daily candles only. Weekly/monthly computed on the fly from daily data.
- Max available history fetched on first request, then append-only.
- No stock_quotes table — all live pricing via websocket in-memory.
- TTM (trailing twelve months) computed from latest 4 quarterly records in financial_statements, not stored separately.

### Domain 3: DCF Model

```
damodaran_industries
├── id (PK)
├── industry_name (text) — 94 industry groups
├── num_firms (int)
├── unlevered_beta (decimal)
├── avg_effective_tax_rate (decimal)
├── avg_debt_to_equity (decimal)
├── avg_operating_margin (decimal)
├── avg_roc (decimal)
├── avg_reinvestment_rate (decimal)
├── cost_of_capital (decimal)
├── fundamental_growth_rate (decimal)
├── updated_at (timestamp)

country_risk_premiums
├── id (PK)
├── country (text)
├── moody_rating (text)
├── default_spread (decimal)
├── equity_risk_premium (decimal)
├── country_risk_premium (decimal)
├── updated_at (timestamp)

default_spreads
├── id (PK)
├── rating (text) — "AAA", "AA", "A", etc.
├── spread_over_treasury (decimal)
├── updated_at (timestamp)

sector_mapping
├── id (PK)
├── twelvedata_sector (text)
├── twelvedata_industry (text)
├── damodaran_industry_id (FK → damodaran_industries)
├── match_confidence (decimal)
├── manually_verified (bool)

dcf_valuations
├── id (PK)
├── stock_id (FK → stocks)
├── damodaran_industry_id (FK → damodaran_industries)
├── source_fiscal_date (date) — ties valuation to exact data used
├── computed_at (timestamp)
├── model_type (text) — "fcff" or "fcfe"
├── is_default (bool)
├── user_id (text, nullable) — Clerk ID for custom runs
├── run_name (text, nullable)
├── is_saved (bool)
├── inputs (jsonb) — all assumptions and computed inputs
├── outputs (jsonb) — all results

dcf_audit_log
├── id (PK)
├── dcf_valuation_id (FK → dcf_valuations)
├── event (text) — "computed", "input_override", "data_refresh"
├── details (jsonb)
├── created_at (timestamp)
```

**Sector Mapping Thresholds:**
- Above 85% confidence: shown as matched
- 60–85%: warning badge, DCF still runs
- Below 60%: DCF blocked, "Industry classification uncertain"
- `manually_verified = true` overrides confidence score permanently

**DCF Input Constraints:**
Stored in code/config, not database. These are Damodaran's valuation rules:
- Terminal growth rate capped at risk-free rate
- Beta moves toward 1 in stable growth
- Growth tied to reinvestment and return on capital
- Reinvestment rate = growth / ROC

### Domain 4: Users & Portfolios

```
users
├── id (PK)
├── clerk_id (text, unique)
├── email (text)
├── display_name (text, nullable)
├── created_at (timestamp)
├── last_login (timestamp)

portfolios
├── id (PK)
├── user_id (FK → users)
├── name (text)
├── mode (text) — "watchlist" or "full"
├── created_at (timestamp)
├── updated_at (timestamp)

portfolio_holdings
├── id (PK)
├── portfolio_id (FK → portfolios)
├── stock_id (FK → stocks)
├── shares (decimal, nullable) — null in watchlist mode
├── cost_basis_per_share (decimal, nullable) — null in watchlist mode
├── added_at (timestamp)

portfolio_snapshots
├── id (PK)
├── portfolio_id (FK → portfolios)
├── date (date)
├── total_value (decimal)
├── total_cost_basis (decimal)
├── total_gain_loss (decimal)
├── holdings_snapshot (jsonb)
```

**Portfolio Behavior:**
- Two modes toggled per portfolio: watchlist (just tracks stocks) and full (tracks P&L)
- Single entry per stock per portfolio — user enters total shares and average cost basis
- No lot-by-lot tracking
- Toggling watchlist → full: stocks carry over with "needs details" state
- Toggling full → watchlist: lot data preserved, just hidden
- Deleting all position data for a stock keeps the stock visible with "no positions" state
- P&L computed on the fly from holdings + live websocket prices
- Snapshots computed on-demand when user views portfolio history (v1 — no background job)

### Shared

```
fred_series
├── id (PK)
├── series_id (text) — "DGS10", "DGS2", "BAMLC0A0CM", etc.
├── value (decimal)
├── observation_date (date)
├── fetched_at (timestamp)
├── UNIQUE(series_id, observation_date)

glossary
├── id (PK)
├── technical_term (text, unique) — "wacc"
├── display_label (text) — "Cost of Running the Business"
├── technical_label (text) — "WACC"
├── tooltip (text) — plain English explanation
├── category (text) — "dcf", "ratios", "profile"
├── learn_more_url (text, nullable)
```

**Glossary Delivery:** Stored in DB as source of truth. Served via GET /api/glossary endpoint. Frontend also bundles a client-side glossary lookup (26 entries in `frontend/src/lib/glossary.ts`) used by the GlossaryTooltip component for instant hover tooltips without network requests. DB remains canonical; client-side entries are a performance optimization.

---

## Caching Strategy

| Data Type | Strategy | Invalidation |
|-----------|----------|-------------|
| Dashboard prices (Twelve Data WS symbols) | In-memory Python dict | Continuous websocket stream |
| Stock profile live price | In-memory, dynamic WS subscribe/unsubscribe | 60-second timeout on no frontend heartbeat |
| Price history | Postgres, append-only | Fetch gap since last stored date on request |
| Financial statements | Postgres | Earnings calendar driven — refresh when known report date passes |
| Dividends | Postgres | Refresh with financial statements |
| Stock splits | Postgres | Refresh with financial statements |
| Earnings calendar | Postgres | Periodic check from Twelve Data |
| FRED series (rates, spreads) | Postgres, append daily | One fetch per day |
| Damodaran reference tables | Postgres | Annual manual/scripted refresh |
| DCF default valuation | Postgres | Re-compute if underlying data refreshed since last run |
| All ratios, margins, growth rates | Computed on the fly | Never stored |
| Weekly/monthly candles | Computed on the fly from daily | Never stored |
| TTM financials | Computed from latest 4 quarters | Never stored |

**Websocket Budget:**
- Pro tier: 1,500 symbols, 3 connections
- Dashboard: ~28 persistent subscriptions
- Stock profiles: dynamic subscribe on page open, unsubscribe on leave
- Cleanup loop every 30 seconds for orphaned subscriptions
- Comfortable headroom for concurrent users

**API Credit Conservation:**
- Price history: 1 credit per stock on first fetch, 1 credit per append (only when viewed)
- Financial statements: ~300 credits per stock (income + balance + cash flow), cached until next earnings
- Fetch daily candles only — compute weekly/monthly
- Pre-seed S&P 500 + Nasdaq 100 before launch to avoid cold start credit spikes

---

## API Endpoints (~32)

### Dashboard
```
GET  /api/dashboard/config          — Active dashboard tickers with categories
WS   /api/dashboard/stream          — Live prices for all dashboard tickers
```

### Stock Profile
```
GET  /api/stocks/{symbol}/profile       — Company info
GET  /api/stocks/{symbol}/financials    — Statements (params: period=annual|quarterly|ttm)
GET  /api/stocks/{symbol}/ratios        — Computed from financials on the fly
GET  /api/stocks/{symbol}/price-history — OHLCV (params: start_date, end_date)
GET  /api/stocks/{symbol}/dividends     — Dividend history
GET  /api/stocks/{symbol}/splits        — Split history
GET  /api/stocks/{symbol}/peers         — Same Damodaran industry, basic metrics
WS   /api/stocks/{symbol}/stream        — Live price for profile page
```

### DCF Model
```
GET  /api/dcf/{symbol}/default          — System-computed baseline valuation
POST /api/dcf/{symbol}/compute          — Run with custom slider assumptions (ephemeral)
POST /api/dcf/{symbol}/save             — Auth: save custom run with name
GET  /api/dcf/{symbol}/runs             — Auth: list user's saved runs
GET  /api/dcf/{symbol}/runs/{run_id}    — Auth: get specific saved run
DELETE /api/dcf/{symbol}/runs/{run_id}  — Auth: delete saved run
GET  /api/dcf/{symbol}/sector-context   — Damodaran industry data for sliders/guardrails
GET  /api/dcf/{symbol}/sensitivity      — WACC vs growth rate matrix
GET  /api/dcf/{symbol}/runs/{id}/export — Download valuation as PDF/CSV
GET  /api/dcf/{symbol}/summary          — Plain-English valuation summary
GET  /api/dcf/constraints               — Slider constraint rules (from code config)
```

### Users & Portfolios
```
POST /api/auth/sync                         — Create/update local user from Clerk JWT
GET  /api/portfolios                        — Auth: list portfolios
POST /api/portfolios                        — Auth: create portfolio
PATCH /api/portfolios/{id}                  — Auth: update name or toggle mode
DELETE /api/portfolios/{id}                 — Auth: delete portfolio
GET  /api/portfolios/{id}/holdings          — Auth: holdings with live prices
POST /api/portfolios/{id}/holdings          — Auth: add stock (+ optional shares/cost basis)
DELETE /api/portfolios/{id}/holdings/{id}   — Auth: remove holding
GET  /api/portfolios/{id}/performance       — Auth: computed P&L summary
GET  /api/portfolios/{id}/history           — Auth: portfolio value over time (snapshots)
```

### Utility
```
GET  /api/search?q={query}     — Stock search (local DB first, Twelve Data fallback)
GET  /api/rates/risk-free      — Current 10-year Treasury from fred_series
GET  /api/glossary             — All glossary entries ordered by category and term
GET  /api/health               — System status: DB, WS, FRED, cache staleness
GET  /api/system/rate-status   — Twelve Data credit usage monitoring
```

### Response Envelope
All cached data endpoints include:
```json
{
  "data": { ... },
  "data_as_of": "2025-10-15T00:00:00Z",
  "next_refresh": "2026-01-24T00:00:00Z"
}
```

---

## DCF Engine — Damodaran Methodology

### Approach
- **Firm valuation (FCFF)** as the default model type
- **TTM (trailing twelve months)** as the base financial period
- Discount rate: WACC computed from cost of equity (CAPM) + cost of debt
- Growth: tied to reinvestment rate × return on capital
- Terminal value: stable growth model with growth capped at risk-free rate
- Terminal ROC converges toward cost of capital
- See also: dcf_methodology.md for implementation detail, edge cases, transition mechanics, and SAP validation case.

### Key Formulas
- **Cost of Equity** = Risk-free Rate + Levered Beta × Equity Risk Premium + Country Risk Premium
- **Levered Beta** = Unlevered Beta × (1 + (1 - tax rate) × D/E)
- **WACC** = Cost of Equity × (E/(D+E)) + Cost of Debt × (1-t) × (D/(D+E))
- **FCFF** = EBIT(1-t) - Reinvestment
- **Reinvestment Rate** = (CapEx - Depreciation + ΔWorking Capital) / EBIT(1-t)
- **Expected Growth** = Reinvestment Rate × Return on Capital
- **Terminal Value** = FCFF_terminal / (WACC - stable growth rate)
- **Equity Value** = Enterprise Value + Cash - Debt - Minority Interests
- **Value per Share** = Equity Value / Shares Outstanding

### Data Sources per Input
| Input | Source |
|-------|--------|
| Risk-free rate | FRED (DGS10) |
| Equity risk premium | Damodaran country_risk_premiums |
| Unlevered beta | Damodaran damodaran_industries (sector average) |
| Tax rate | Computed from financial_statements (TTM) |
| D/E ratio | Computed from financial_statements (latest balance sheet) |
| EBIT, revenue, CapEx, depreciation, working capital | financial_statements (TTM) |
| Cost of debt | Risk-free rate + default spread (from company's implied rating) |
| Shares outstanding | Twelve Data stock profile |

### Slider Guardrails
- Each adjustable input shows: computed value, sector average (from damodaran_industries), hard limits
- Preset scenarios: Conservative / Moderate / Optimistic (maps to specific assumption bundles)
- Soft warnings when user moves beyond 1.5× sector range
- Hard caps enforced: terminal growth ≤ risk-free rate, beta floors/ceilings

### Progressive Disclosure (Frontend Contract)
- **Level 1 (Headline):** Value per share, current price, implied upside/downside, verdict
- **Level 2 (Overview):** Key assumptions as plain-language cards, scenario presets, peer context
- **Level 3 (Full Model):** Year-by-year projections, all sliders, sensitivity matrix, export

---

## Search Behavior

- **Local first:** Query `stocks` table for symbol/name match
- **Fallback:** Hit Twelve Data symbol search endpoint
- **Results include:** `cached: bool` flag — tells frontend if data is ready or needs initial loading
- **On selection of uncached stock:** Create `stocks` record, begin async data fetch

---

## Pre-seed Strategy

Manual script run before launch:
- S&P 500 + Nasdaq 100 (~600 stocks)
- Fetch: profile, financial statements, max price history, dividends, splits, earnings calendar
- Stagger across minutes to stay within 610 credits/minute
- Populates `stocks`, `financial_statements`, `price_history`, `dividends`, `stock_splits`, `earnings_calendar`

---

## Twelve Data API Corrections (Discovered in Deployment)

These corrections apply to the actual Twelve Data API responses vs what was originally assumed:

- **Stock splits:** Returns `from_factor` / `to_factor` fields, plus `description` like "2-for-1". Original assumption of `ratio_from` / `ratio_to` was wrong — the service parses both formats.
- **Earnings calendar:** Returns `{earnings: {date: [...]}}` nested structure, not a flat list.
- **Search endpoint:** Now returns the standard response envelope (`data`, `data_as_of`, `next_refresh`) so `apiGet()` can unwrap consistently.
- **Date fields:** SQLAlchemy returns `datetime.date` objects; Pydantic schemas must use `date` type, not `str`. Affects `PriceHistoryResponse`, `DividendResponse`, `SplitResponse`, `FinancialStatementResponse`.
- **Pre-seeded stubs:** Stocks inserted by the pre-seed script have `last_updated=None` (profile data only). The stock router detects this and triggers a full data fetch on first view.

---

## Error Handling Principles

- **DCF eligibility** checked at request time by querying financial_statements and price_history — no stored status table
- **Partial fetch failures** (e.g., got income statement but balance sheet timed out): serve what's available, mark incomplete, retry on next request
- **Twelve Data down:** Serve cached data with stale indicator. Dashboard shows last known prices. Profile pages work from cache.
- **FRED down:** Use last stored value from fred_series
- **Sector mapping miss (<60%):** Block DCF, show clear message
- **Internal rate limiting:** Queue/throttle Twelve Data REST calls to stay within 610 credits/minute

---

## Build Order

### Phase 1: Foundation
- PostgreSQL on Railway — all 19 tables
- FastAPI project structure + health endpoint
- Twelve Data API client module
- FRED API client module
- Basic stock search

### Phase 2: Data Layer
- Stock profile data pipeline (fetch + cache: profile, financials, price history, dividends, splits, earnings calendar)
- Validate schema against real Twelve Data API responses
- TTM computation logic
- FRED daily fetch and storage

### Phase 3: Dashboard
- Seed dashboard_tickers table
- Twelve Data websocket connection (backend)
- FRED daily fetch for rates/spreads
- FastAPI websocket endpoint for frontend fan-out
- Dynamic subscribe/unsubscribe for stock profiles

### Phase 4: DCF Engine
- Damodaran static file ingestion (6 datasets)
- Sector fuzzy mapping + manual override system
- DCF computation module (FCFF model)
- Default valuation endpoint
- Custom run compute/save/list/delete
- Sensitivity table
- Summary endpoint
- Export (PDF/CSV)
- Audit logging

### Phase 5: Frontend Shell
- Next.js project on Railway
- Clerk auth integration
- Page routing (dashboard, stock profile, DCF, portfolio)
- Basic layouts

### Phase 6: Frontend Pages
- Dashboard with live websocket prices
- Stock profile with charts, financials, ratios
- DCF page with progressive disclosure (3 levels)
- Glossary tooltip integration

### Phase 7: Portfolio
- Auth-gated routes
- Portfolio CRUD
- Holdings management (watchlist + full mode)
- P&L computation
- Portfolio history snapshots

### Phase 8: Polish
- Pre-seed script (S&P 500 + Nasdaq 100)
- Error states and loading indicators
- Data freshness indicators
- Rate limit monitoring
- Final QA pass

---

## Testing Standards

- **Every phase must include tests.** No untested code ships.
- **Test stack:** pytest + pytest-asyncio + httpx AsyncClient + pytest-cov
- Mock all external APIs (Twelve Data, FRED) — never hit real APIs in test suite
- Test both success and error paths
- Unit tests for all service modules and computation logic
- Integration tests for all API endpoints
- The PM subagent enforces this on every phase

---

## Project Infrastructure

### Repository
- Private GitHub repo: `bradan-v4`
- Monorepo: backend/ and frontend/ in same repo
- `CLAUDE.md` in repo root — auto-read by Claude Code every session
- `bradan_v4_spec.md` in repo root — single source of truth

### Subagents (Claude Code)
Three subagents in `.claude/agents/`:
- `backend.md` — backend implementation specialist
- `frontend.md` — frontend implementation specialist
- `pm.md` — enforces spec compliance, testing, build order, quality gates

### Development Workflow
1. Plan phase in Claude Code using `/phase-plan N`
2. Review and approve the plan
3. Execute — sub-agents build, hooks auto-format, `/check` gates quality
4. After each phase completes, update `bradan_v4_spec.md`: mark completion log, add any discoveries (schema changes, edge cases found, API response corrections, new decisions)
5. Commit spec + code together
6. Debrief in claude.ai project if needed for next phase planning

### Spec Update Rules
- The spec is a living document updated after every phase
- Implementation discoveries get written back into the spec
- Schema changes must be reflected in the spec before the phase is marked complete
- The completion log must be updated with sub-phase detail (see Phase 1 for reference)

### MCP Servers (Active)
- **PostgreSQL (dbhub)** — Direct database access to Railway Postgres via MCP
- **Puppeteer** — Browser automation for visual testing and DCF PDF export rendering

---

## Completion Log

- [x] Phase 1a: Project skeleton (FastAPI, folder structure, health check, Dockerfile)
- [x] Phase 1b: Database models and Alembic migration (19 tables)
- [x] Phase 1c: API clients (Twelve Data 9 methods, FRED 2 methods), search endpoint, full Phase 1 test suite (33 tests)
- [x] Phase 2a: Stock data pipeline service (StockDataService — fetch + upsert profile, financials, price history, dividends, splits, earnings calendar; append-only price history; partial failure resilience)
- [x] Phase 2b: FRED data service (FredDataService — fetch/upsert 4 tracked series, daily incremental update, 1-year backfill)
- [x] Phase 2c: TTM computation module (TTMService — sum 4 quarterly income/cash_flow, latest quarter balance sheet, graceful degradation)
- [x] Phase 2d: Stock profile REST endpoints (5 endpoints: profile, financials with annual/quarterly/ttm, price-history, dividends, splits; response envelope; auto-fetch on uncached stock; earnings-driven next_refresh)
- [x] Phase 2e: FRED rate endpoint (GET /api/rates/risk-free — DGS10 from fred_series, 503 on missing data)
- [x] Phase 2f: Phase 2 test suite (69 new tests, 102 total; Pydantic schemas fixed for Python 3.9 compatibility)
- [x] Phase 3a: Seed dashboard_tickers table (27 tickers across 8 categories, idempotent check-then-insert/update)
- [x] Phase 3b: Twelve Data WebSocket manager (persistent upstream connection, in-memory price dict, subscribe/unsubscribe, auto-reconnect with exponential backoff, 30s cleanup loop for stale profile symbols)
- [x] Phase 3c: FRED daily scheduler (FredScheduler — daily fetch + in-memory cache, computed SPREAD_2S10S = DGS10 - DGS2)
- [x] Phase 3d: Dashboard endpoints (GET /api/dashboard/config with category grouping, WS /api/dashboard/stream fan-out from ws_manager + fred_scheduler)
- [x] Phase 3e: Stock profile WebSocket (WS /api/stocks/{symbol}/stream — dynamic subscribe, 30s heartbeat, 60s TTL cleanup)
- [x] Phase 3f: App lifecycle wiring (startup: seed tickers, start ws_manager + subscribe dashboard symbols, start fred_scheduler; shutdown: stop all)
- [x] Phase 3g: Phase 3 test suite (20 new tests, 122 total; websockets.asyncio type annotation fixed for Python 3.9)
- [x] Phase 4a: Damodaran seed service (seed_damodaran_data — 15 default_spreads, 13 country_risk_premiums, 25 damodaran_industries; idempotent check-then-insert/update)
- [x] Phase 4b: DCF computation engine (dcf_engine.py — pure two-stage FCFF model, CAPM, WACC, synthetic ratings, linear transitions, terminal value, equity bridge, sensitivity matrix, scenario presets; SAP validation case)
- [x] Phase 4c: Sector mapping service (SectorMappingService — fuzzy SequenceMatcher matching, financial company detection, confidence scoring, manual override)
- [x] Phase 4d: DCF Pydantic schemas (DCFOverrides, DCFResult, SensitivityMatrix, DCFSaveRequest, SectorContext, DCFConstraints, eligibility error)
- [x] Phase 4e: DCF orchestration service (DCFService — compute_default, compute_custom, save/list/get/delete runs, sensitivity, sector-context, summary; TTM extraction, country risk lookup, audit logging)
- [x] Phase 4f: DCF router (11 endpoints: constraints, default, compute, save, runs CRUD, sector-context, sensitivity, summary, CSV export; auth via X-User-Id header)
- [x] Phase 4g: App lifecycle wiring (Damodaran seed on startup, DCF router included)
- [x] Phase 4h: Phase 4 test suite (92 new tests — 60 engine + 32 service/endpoint/seed/mapping, 214 total)
- [x] Phase 5a: Next.js project setup (App Router, TypeScript, Tailwind CSS v4, eslint, project structure under frontend/)
- [x] Phase 5b: Clerk auth integration (ClerkProvider, SignIn/SignUp pages, middleware route protection, auth-gated /portfolio route)
- [x] Phase 5c: Page routing and layouts (RootLayout with Header, dashboard /, stock profile /stocks/[symbol], DCF /dcf/[symbol], portfolio /portfolio, sign-in/sign-up)
- [x] Phase 5d: API client module (apiGet/apiFetch with NEXT_PUBLIC_API_URL, response envelope unwrap, error handling)
- [x] Phase 5e: WebSocket hook (useWebSocket — auto-connect/disconnect, reconnect with backoff, JSON parsing, connection state)
- [x] Phase 5f: Phase 5 test suite (23 tests — Vitest + React Testing Library + jsdom; layout, header, pages, API client, WS hook)
- [x] Phase 6a: Backend computed ratios service (compute_ratios — 17 ratios across 5 categories: profitability, liquidity, leverage, valuation, efficiency; pure function, graceful None handling)
- [x] Phase 6b: Backend ratios + peers endpoints (GET /api/stocks/{symbol}/ratios — TTM-based on-the-fly computation; GET /api/stocks/{symbol}/peers — same Damodaran industry lookup)
- [x] Phase 6c: Backend glossary seed (seed_glossary — 31 entries across 3 categories: dcf/ratios/profile; idempotent check-then-insert/update; GET /api/glossary endpoint)
- [x] Phase 6d: Frontend formatting utilities (7 functions: formatCurrency, formatPercent, formatLargeNumber, formatChange, changeColor, formatDate, formatRatio; null-safe "—" fallback)
- [x] Phase 6e: Frontend search bar (SearchBar — debounced 300ms, min 2 chars, apiGet /api/search, dropdown with keyboard nav, router.push on select; integrated into Header)
- [x] Phase 6f: Frontend glossary tooltips (GlossaryTooltip — hover tooltip with display_label + plain-English tooltip, auto-positions above/below; 26 client-side entries + DB-backed API)
- [x] Phase 6g: Dashboard page (live WS prices via /api/dashboard/stream, 8 category sections, TickerCard with format switching price/percentage, CategorySection grid, loading skeletons, disconnected banner)
- [x] Phase 6h: Stock profile page (6 parallel data fetches + WS /api/stocks/{symbol}/stream, PriceChart via Recharts AreaChart, tabbed layout: Financials/Ratios/Dividends, FinancialsTable, RatiosGrid with GlossaryTooltip, PeerList with links)
- [x] Phase 6i: DCF page with progressive disclosure (3 levels: Headline → Overview → Full Model; Headline: value vs price, upside/downside, verdict badge; AssumptionCards with GlossaryTooltip; ScenarioSelector 3 presets; EquityBridge waterfall; ProjectionTable year-by-year; SensitivityTable heatmap green/red; CSV export link)
- [x] Phase 6j: Phase 6 test suite (108 new tests — 24 backend: ratios unit+endpoint, peers, glossary seed+endpoint; 84 frontend: format 35, SearchBar 5, GlossaryTooltip 7, dashboard 5, stock-profile 9, DCF 16, existing pages updated 7; 338 total: 238 backend + 100 frontend)
- [x] Phase 7a: Backend Clerk JWT auth (auth.py — get_current_user dependency, HS256 JWT decode, DB user lookup; CLERK_SECRET_KEY config; pyjwt[crypto] dependency)
- [x] Phase 7b: Backend auth sync endpoint (POST /api/auth/sync — upsert local user from Clerk JWT, extract clerk_id/email/display_name from claims)
- [x] Phase 7c: Backend portfolio schemas (7 Pydantic models — PortfolioCreate/Update, HoldingCreate, PortfolioResponse, HoldingResponse, PerformanceSummary, SnapshotResponse; mode validator watchlist/full)
- [x] Phase 7d: Backend portfolio service (PortfolioService — 11 methods: list/create/get/update/delete portfolios, list/add/remove holdings with live WS prices, get_performance on-the-fly P&L, get_history/create_snapshot; ownership enforcement, IntegrityError→409)
- [x] Phase 7e: Backend portfolio router (9 auth-gated endpoints: GET/POST/PATCH/DELETE portfolios, GET/POST/DELETE holdings, GET performance, GET history; holdings count via grouped COUNT query)
- [x] Phase 7f: Frontend portfolio types + auth fetch (Portfolio/Holding/PerformanceSummary/PortfolioSnapshot types; authFetch with Bearer token for non-envelope endpoints; useAuthSync hook)
- [x] Phase 7g: Frontend portfolio pages (list page: create/delete/list portfolios; detail page /portfolio/[id]: performance summary cards in full mode, holdings table with symbol links, add/remove holdings; portfolio layout with auth sync)
- [x] Phase 7h: Phase 7 test suite (36 new tests — 26 backend: 5 auth sync + 21 portfolio endpoints/CRUD/holdings/performance/history/auth-guard/ownership; 10 frontend: list page 5 + detail page 5; 374 total: 264 backend + 110 frontend)
- [x] Phase 8a: Pre-seed script (preseed.py — S&P 500 + Nasdaq 100 symbols, staggered batches respecting 610 credits/min, preseed_single.py for single-stock API validation)
- [x] Phase 8b: Rate limit monitoring (TwelveDataRateLimiter class — sliding window credit tracking; GET /api/system/rate-status endpoint)
- [x] Phase 8c: Frontend polish components (ErrorState, FreshnessIndicator with relative timestamps, LoadingSkeleton; formatRelativeTime + formatTimestamp utilities)
- [x] Phase 8d: Phase 8 test suite (41 new tests — 16 backend: preseed + rate limits; 25 frontend: ErrorState + FreshnessIndicator + LoadingSkeleton + format utils; 415 total)
- [x] Phase 8e: Railway deployment (railway.toml + .dockerignore for both services, .env.production for frontend, CORS middleware on backend)
- [x] Phase 8f: Live API shape fixes (Twelve Data split parsing uses from_factor/to_factor; earnings calendar returns {earnings:{date:[...]}}; search endpoint returns standard envelope; Pydantic date type coercion for price-history/financials/dividends; pre-seeded stubs trigger data fetch on first view; 416 total tests: 280 backend + 136 frontend)
