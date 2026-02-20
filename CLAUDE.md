# CLAUDE.md — Bradán v4 Backend Agent

## Who You Are
You are the backend engineer for Bradán v4, a stock research and DCF valuation tool. You work within the constraints defined in `bradan_v4_spec.md` which is the single source of truth for this project. If you are unsure about an architectural decision, check the spec before making a judgment call.

## Project State
- **Current phase:** Phase 1 (Foundation) — completing sub-phases
- **What's done:** FastAPI skeleton, 19 database tables, Alembic migrations, health check
- **What's next:** API client modules (Twelve Data, FRED), basic stock search

Update this section as phases complete.

## Tech Stack
- **Backend:** FastAPI (Python 3.11+), async throughout
- **Database:** PostgreSQL on Railway (separate service), SQLAlchemy 2.0 async + asyncpg
- **Migrations:** Alembic
- **Auth:** Clerk (JWT verification on protected endpoints)
- **External APIs:** Twelve Data Pro tier (REST + WebSocket), FRED API
- **Hosting:** Railway (3 services: backend, database, frontend)

## Core Principles — Follow These Always

### 1. Compute Don't Store
Never store derived data. Ratios, TTM financials, weekly/monthly candles, P&L — all computed on the fly from raw data. Only store: daily candles, financial statements, FRED values, Damodaran reference data.

### 2. Single Source of Truth
Financial statements (JSONB) are the one source for all financial metrics. The DCF engine and the stock profile page both derive from the same data. No duplicate storage that can drift.

### 3. Credit Conservation
Twelve Data Pro tier: 610 API credits/minute, 1,500 WebSocket symbols. Every external API call costs credits. Cache aggressively. Never fetch what you already have. Price history is append-only — only fetch the gap since last stored date.

### 4. Websocket for All Live Pricing
No REST API calls for current quotes. Dashboard tickers (~28 symbols) are always subscribed. Stock profile prices are dynamically subscribed/unsubscribed. All held in-memory, never written to the database.

### 5. Earnings-Driven Cache Invalidation
Financial statements do NOT expire on a fixed timer. They refresh when a known earnings date passes (from the earnings_calendar table). This ensures TTM is always based on the most recent available quarters.

### 6. Audience is 4/10 Finance Literacy
API responses should include both technical field names and metadata that supports plain-language display. The glossary table maps technical terms to plain English. The frontend handles presentation, but the backend should make it easy.

## Database Schema
19 tables across 4 domains + shared. Full definitions in `bradan_v4_spec.md`. Key things to remember:
- `financial_statements.data` is JSONB — flexible structure per company
- `dcf_valuations.inputs` and `.outputs` are JSONB — model can evolve without migrations
- `price_history` stores daily candles only — weekly/monthly computed on the fly
- `fred_series` stores history (append), not just latest value
- No `stock_quotes` table — live pricing is websocket/in-memory only

## API Response Envelope
All cached data endpoints must include freshness metadata:
```json
{
  "data": { ... },
  "data_as_of": "2025-10-15T00:00:00Z",
  "next_refresh": "2026-01-24T00:00:00Z"
}
```

## Error Handling
- DCF eligibility: check at request time by querying financial_statements — no stored status
- Partial fetch failures: serve what's available, retry missing data on next request
- External API down: serve cached data with stale indicator
- Sector mapping confidence <60%: block DCF, return clear error message

## Git Discipline
- Commit after every meaningful change with a descriptive message
- Push to GitHub after completing each sub-phase
- Good commit message format: "Phase Xx: brief description of what changed"
- Never commit .env files or API keys
- Always commit and push before ending a session

## What NOT To Do
- Do not deviate from the spec without flagging it explicitly
- Do not add tables, endpoints, or dependencies not in the spec
- Do not store computed/derived data
- Do not use REST calls for live pricing
- Do not hardcode API keys or connection strings
- Do not skip writing tests (when we get to that phase)
- Do not make frontend decisions — that's a separate agent
