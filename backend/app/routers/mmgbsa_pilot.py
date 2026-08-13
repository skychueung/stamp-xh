"""MM-GBSA Pilot Router (v1.5 P3).

Provides probe, validation, dry-run, and smoke endpoints for MM-GBSA pilot jobs.
Does NOT execute full MM-GBSA production runs.

Scientific boundaries:
- probe returns BLOCKED if environment is missing.
- dry_run returns command list only, never executes.
- smoke runs gmx_MMPBSA --version only, never runs real calculation.
- No fabricated ΔG values at any endpoint.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import ApiResponse
from app.services.md_environment_probe import probe_md_environment
from app.services.mmgbsa_pilot_runner import (
    check_environment,
    create_workdir,
    dry_run,
    smoke_run,
    validate_input,
)

logger = logging.getLogger("stamp")

router = APIRouter(prefix="/api/v1/mmgbsa-pilot", tags=["MM-GBSA Pilot"])


# ---------------------------------------------------------------------------
# GET /api/v1/mmgbsa-pilot/probe
# ---------------------------------------------------------------------------

@router.get(
    "/probe",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Probe MM-GBSA environment readiness",
)
async def mmgbsa_probe_get() -> ApiResponse[dict]:
    """Return MM-GBSA environment status.

    If gmx_MMPBSA is missing, returns BLOCKED with reasons.
    If available, returns AVAILABLE with version info.
    """
    report = probe_md_environment()
    data = report.to_dict()
    status_str = data.get("status", "unknown")
    message = (
        "MM-GBSA environment ready"
        if status_str == "AVAILABLE"
        else f"MM-GBSA environment blocked: {', '.join(data.get('blocking_reasons') or [])}"
    )
    return ApiResponse.success(data=data, message=message)


# ---------------------------------------------------------------------------
# POST /api/v1/mmgbsa-pilot/probe
# ---------------------------------------------------------------------------

@router.post(
    "/probe",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Probe MM-GBSA environment (POST variant)",
)
async def mmgbsa_probe_post() -> ApiResponse[dict]:
    """Same as GET /probe but accepts POST for compatibility."""
    return await mmgbsa_probe_get()


# ---------------------------------------------------------------------------
# POST /api/v1/mmgbsa-pilot/validate-input
# ---------------------------------------------------------------------------

class ValidateInputRequest:
    topology: str
    trajectory: str
    index: str
    mdp: Optional[str] = None
    ligand_mask: Optional[str] = ":1-10"
    receptor_mask: Optional[str] = ":11-100"
    frames: Optional[int] = None


@router.post(
    "/validate-input",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Validate MM-GBSA input files",
)
async def mmgbsa_validate_input(body: dict) -> ApiResponse[dict]:
    """Validate that topology, trajectory, and index files exist and are readable."""
    ok, err = validate_input(body)
    if not ok:
        return ApiResponse.error(
            code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message=f"Validation failed: {err}",
            data={"valid": False, "reason": err},
        )
    return ApiResponse.success(
        data={"valid": True, "inputs": body},
        message="Input validation passed",
    )


# ---------------------------------------------------------------------------
# POST /api/v1/mmgbsa-pilot/create-workdir
# ---------------------------------------------------------------------------

@router.post(
    "/create-workdir",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Create MM-GBSA working directory",
)
async def mmgbsa_create_workdir(body: dict) -> ApiResponse[dict]:
    """Create the scaffold working directory for an MM-GBSA job."""
    batch_id = body.get("batch_id", "test-batch")
    item_id = body.get("item_id", "test-item")
    workdir = create_workdir(batch_id, item_id)
    return ApiResponse.success(
        data={
            "batch_id": batch_id,
            "item_id": item_id,
            "workdir": workdir,
            "subdirs": ["inputs", "topology", "trajectory", "analysis", "logs", "artifacts"],
        },
        message="Workdir created",
    )


# ---------------------------------------------------------------------------
# POST /api/v1/mmgbsa-pilot/dry-run
# ---------------------------------------------------------------------------

@router.post(
    "/dry-run",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Dry-run MM-GBSA execution",
)
async def mmgbsa_dry_run(body: dict) -> ApiResponse[dict]:
    """Return the commands that would be executed without running them."""
    batch_id = body.get("batch_id", "test-batch")
    item_id = body.get("item_id", "test-item")
    input_json = body.get("input_json", body)

    result = dry_run(batch_id, item_id, input_json)
    return ApiResponse.success(
        data=result,
        message="Dry-run complete — no commands were executed",
    )


# ---------------------------------------------------------------------------
# POST /api/v1/mmgbsa-pilot/smoke
# ---------------------------------------------------------------------------

@router.post(
    "/smoke",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="MM-GBSA smoke test",
)
async def mmgbsa_smoke() -> ApiResponse[dict]:
    """Run a minimal smoke test: gmx_MMPBSA --version.

    Returns success if the tool responds, BLOCKED if environment is missing.
    """
    success, error = smoke_run()
    if success:
        return ApiResponse.success(
            data={"smoke_test": "passed", "tool": "gmx_MMPBSA"},
            message="MM-GBSA smoke test passed",
        )
    return ApiResponse.error(
        code=status.HTTP_503_SERVICE_UNAVAILABLE,
        message=f"MM-GBSA smoke test failed: {error}",
        data={"smoke_test": "failed", "reason": error},
    )
