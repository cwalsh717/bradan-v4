# Bradán v4

## What This Is
Stock research and DCF valuation tool. FastAPI backend, Next.js frontend, PostgreSQL on Railway.

## Source of Truth
Read `bradan_v4_spec.md` for all schema, endpoints, formulas, and build order. Do not deviate from it.

## Commands
- Dev server: `cd backend && uvicorn app.main:app --reload`
- Tests: `cd backend && pytest tests/ -v`
- Single test: `cd backend && pytest tests/test_file.py -k test_name`
- Lint: `cd backend && ruff check .`
- Format: `cd backend && ruff format .`
- Migrations: `cd backend && alembic upgrade head`

## Rules
- IMPORTANT: Run `pytest` before any commit. No untested code ships.
- IMPORTANT: Mock all external APIs (Twelve Data, FRED) in tests. Never hit real APIs.
- Compute don't store: ratios, TTM, weekly/monthly candles, P&L are computed on the fly.
- All live pricing via websocket. No REST polling for prices.
- Use plan mode for any task with more than one moving part.
- For multi-file tasks, use sub-agents to keep the main context window clean.

## Structure
- `backend/` — FastAPI app, services, models, tests
- `frontend/` — Next.js app (Phase 5+)
- `.claude/agents/` — sub-agent definitions
- `.claude/commands/` — slash commands for workflow
