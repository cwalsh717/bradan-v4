"""DCF valuation endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_session
from app.schemas.dcf import (
    DCFConstraintsResponse,
    DCFEligibilityError,
    DCFOverrides,
    DCFRunDetailResponse,
    DCFRunListResponse,
    DCFSaveRequest,
    DCFSummaryResponse,
    SensitivityResponse,
    SectorContextResponse,
)
from app.services.dcf_service import (
    DCFEligibilityError as ServiceEligibilityError,
    DCFService,
)

router = APIRouter(prefix="/api/dcf", tags=["dcf"])


def _get_user_id(x_user_id: Optional[str] = Header(None)) -> Optional[str]:
    """Extract user ID from header. In production this would come from Clerk JWT."""
    return x_user_id


def _require_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    """Require authenticated user via header."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return x_user_id


# ------------------------------------------------------------------
# GET /api/dcf/constraints — slider constraint rules
# ------------------------------------------------------------------


@router.get("/constraints")
async def get_constraints():
    """Return slider constraint rules (from code config, not DB)."""
    return DCFConstraintsResponse(
        data={
            "forecast_years": {"min": 5, "max": 10, "default": 10},
            "stable_growth_rate": {
                "min": -0.02,
                "max": "risk_free_rate",
                "default": "risk_free_rate - 0.01",
            },
            "stable_beta": {"min": 0.5, "max": 1.5, "default": 1.0},
            "stable_roc": {"min": 0.02, "max": 0.50, "default": "wacc"},
            "stable_debt_to_equity": {"min": 0, "max": 3.0, "default": "sector_avg"},
            "marginal_tax_rate": {"min": 0, "max": 0.50, "default": 0.25},
        }
    )


# ------------------------------------------------------------------
# GET /api/dcf/{symbol}/default — system-computed baseline valuation
# ------------------------------------------------------------------


@router.get("/{symbol}/default")
async def get_default_valuation(
    symbol: str,
    session: AsyncSession = Depends(get_session),
):
    """Compute or retrieve the default DCF valuation for a stock."""
    try:
        service = DCFService(session)
        result = service.compute_default(symbol)
        if hasattr(result, "__await__"):
            result = await result
    except ServiceEligibilityError as e:
        raise HTTPException(
            status_code=422,
            detail=DCFEligibilityError(reason=e.reason, detail=e.detail).model_dump(),
        )

    now = datetime.now(timezone.utc).isoformat()
    return {
        "data": result,
        "data_as_of": now,
        "next_refresh": None,
    }


# ------------------------------------------------------------------
# POST /api/dcf/{symbol}/compute — custom slider assumptions (ephemeral)
# ------------------------------------------------------------------


@router.post("/{symbol}/compute")
async def compute_custom(
    symbol: str,
    overrides: DCFOverrides,
    session: AsyncSession = Depends(get_session),
):
    """Run DCF with custom slider assumptions. Result is ephemeral (not saved)."""
    try:
        service = DCFService(session)
        result = await service.compute_custom(
            symbol=symbol,
            overrides=overrides.model_dump(exclude_none=True),
            scenario=overrides.scenario,
        )
    except ServiceEligibilityError as e:
        raise HTTPException(
            status_code=422,
            detail=DCFEligibilityError(reason=e.reason, detail=e.detail).model_dump(),
        )

    now = datetime.now(timezone.utc).isoformat()
    return {"data": result, "data_as_of": now}


# ------------------------------------------------------------------
# POST /api/dcf/{symbol}/save — auth: save custom run with name
# ------------------------------------------------------------------


@router.post("/{symbol}/save")
async def save_run(
    symbol: str,
    body: DCFSaveRequest,
    user_id: str = Depends(_require_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Save a custom DCF run with a name. Requires authentication."""
    try:
        service = DCFService(session)
        result = await service.save_run(
            symbol=symbol,
            user_id=user_id,
            run_name=body.run_name,
            overrides=body.overrides.model_dump(exclude_none=True),
        )
    except ServiceEligibilityError as e:
        raise HTTPException(
            status_code=422,
            detail=DCFEligibilityError(reason=e.reason, detail=e.detail).model_dump(),
        )

    return {"data": result}


# ------------------------------------------------------------------
# GET /api/dcf/{symbol}/runs — auth: list user's saved runs
# ------------------------------------------------------------------


@router.get("/{symbol}/runs")
async def list_runs(
    symbol: str,
    user_id: str = Depends(_require_user_id),
    session: AsyncSession = Depends(get_session),
):
    """List saved DCF runs for a stock. Requires authentication."""
    try:
        service = DCFService(session)
        runs = await service.list_runs(symbol, user_id)
    except ServiceEligibilityError as e:
        raise HTTPException(status_code=404, detail=e.detail)

    return DCFRunListResponse(data=runs)


# ------------------------------------------------------------------
# GET /api/dcf/{symbol}/runs/{run_id} — auth: get specific saved run
# ------------------------------------------------------------------


@router.get("/{symbol}/runs/{run_id}")
async def get_run(
    symbol: str,
    run_id: int,
    user_id: str = Depends(_require_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get a specific saved DCF run. Requires authentication."""
    try:
        service = DCFService(session)
        result = await service.get_run(symbol, run_id, user_id)
    except ServiceEligibilityError as e:
        raise HTTPException(status_code=404, detail=e.detail)

    return DCFRunDetailResponse(
        data=result,
        run_name=result.get("run_name", ""),
        run_id=run_id,
    )


# ------------------------------------------------------------------
# DELETE /api/dcf/{symbol}/runs/{run_id} — auth: delete saved run
# ------------------------------------------------------------------


@router.delete("/{symbol}/runs/{run_id}")
async def delete_run(
    symbol: str,
    run_id: int,
    user_id: str = Depends(_require_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Delete a saved DCF run. Requires authentication."""
    try:
        service = DCFService(session)
        deleted = await service.delete_run(symbol, run_id, user_id)
    except ServiceEligibilityError as e:
        raise HTTPException(status_code=404, detail=e.detail)

    if not deleted:
        raise HTTPException(status_code=404, detail="Run not found")

    return {"deleted": True}


# ------------------------------------------------------------------
# GET /api/dcf/{symbol}/sector-context — Damodaran industry data
# ------------------------------------------------------------------


@router.get("/{symbol}/sector-context")
async def get_sector_context(
    symbol: str,
    session: AsyncSession = Depends(get_session),
):
    """Get Damodaran industry data for slider context/guardrails."""
    try:
        service = DCFService(session)
        context = await service.get_sector_context(symbol)
    except ServiceEligibilityError as e:
        raise HTTPException(status_code=404, detail=e.detail)

    return SectorContextResponse(data=context)


# ------------------------------------------------------------------
# GET /api/dcf/{symbol}/sensitivity — WACC vs growth rate matrix
# ------------------------------------------------------------------


@router.get("/{symbol}/sensitivity")
async def get_sensitivity(
    symbol: str,
    session: AsyncSession = Depends(get_session),
):
    """Compute WACC vs growth rate sensitivity matrix."""
    try:
        service = DCFService(session)
        matrix = await service.get_sensitivity(symbol)
    except ServiceEligibilityError as e:
        raise HTTPException(
            status_code=422,
            detail=DCFEligibilityError(reason=e.reason, detail=e.detail).model_dump(),
        )

    return SensitivityResponse(data=matrix)


# ------------------------------------------------------------------
# GET /api/dcf/{symbol}/summary — plain-English valuation summary
# ------------------------------------------------------------------


@router.get("/{symbol}/summary")
async def get_summary(
    symbol: str,
    session: AsyncSession = Depends(get_session),
):
    """Generate plain-English valuation summary."""
    try:
        service = DCFService(session)
        summary = await service.get_summary(symbol)
    except ServiceEligibilityError as e:
        raise HTTPException(
            status_code=422,
            detail=DCFEligibilityError(reason=e.reason, detail=e.detail).model_dump(),
        )

    return DCFSummaryResponse(data=summary)


# ------------------------------------------------------------------
# GET /api/dcf/{symbol}/runs/{run_id}/export — PDF/CSV download
# ------------------------------------------------------------------


@router.get("/{symbol}/runs/{run_id}/export")
async def export_run(
    symbol: str,
    run_id: int,
    format: str = "csv",
    user_id: str = Depends(_require_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Export a saved DCF run as CSV. PDF support planned for Phase 5+ (Puppeteer)."""
    try:
        service = DCFService(session)
        result = await service.get_run(symbol, run_id, user_id)
    except ServiceEligibilityError as e:
        raise HTTPException(status_code=404, detail=e.detail)

    if format == "csv":
        import csv
        import io
        from fastapi.responses import StreamingResponse

        output = io.StringIO()
        writer = csv.writer(output)

        # Header info
        writer.writerow(["DCF Valuation Export"])
        writer.writerow(["Symbol", result.get("symbol", symbol)])
        writer.writerow(["Value per Share", result.get("value_per_share", "")])
        writer.writerow(["Scenario", result.get("scenario", "")])
        writer.writerow([])

        # Projections
        projections = result.get("projections", [])
        if projections:
            writer.writerow(
                ["Year", "Growth Rate", "EBIT After Tax", "FCFF", "WACC", "PV FCFF"]
            )
            for p in projections:
                writer.writerow(
                    [
                        p.get("year", ""),
                        f"{p.get('growth_rate', 0):.4f}",
                        f"{p.get('ebit_after_tax', 0):.2f}",
                        f"{p.get('fcff', 0):.2f}",
                        f"{p.get('wacc', 0):.4f}",
                        f"{p.get('pv_fcff', 0):.2f}",
                    ]
                )

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=dcf_{symbol}_{run_id}.csv"
            },
        )

    raise HTTPException(
        status_code=400, detail=f"Unsupported format: {format}. Use 'csv'."
    )
