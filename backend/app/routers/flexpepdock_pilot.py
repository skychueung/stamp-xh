"""FlexPepDock Pilot Router (v1.5 P1).

Minimal skeleton for FlexPepDock pilot endpoints.
Does NOT run actual docking in P1 — only probes the environment,
validates inputs, and returns AVAILABLE / BLOCKED status.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import ApiResponse
from app.services.flexpepdock_environment_probe import probe_flexpepdock_environment
from app.services.flexpepdock_runner import (
    create_workdir,
    dry_run,
    smoke_run,
    validate_input,
)

logger = logging.getLogger("stamp")

router = APIRouter(prefix="/api/v1/flexpepdock-pilot", tags=["FlexPepDock Pilot"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class FlexPepDockProbeResponse(BaseModel):
    status: str
    rosetta_env_script_exists: bool
    flexpepdock_available: bool
    rosetta_scripts_available: bool
    rosetta_db_available: bool
    rosetta_root: Optional[str]
    blocking_reasons: list[str]


class FlexPepDockValidateRequest(BaseModel):
    input_json: dict


class FlexPepDockValidateResponse(BaseModel):
    ok: bool
    error: Optional[str]


class FlexPepDockCreateWorkdirRequest(BaseModel):
    batch_id: str
    item_id: str


class FlexPepDockCreateWorkdirResponse(BaseModel):
    workdir: str


class FlexPepDockDryRunRequest(BaseModel):
    batch_id: str
    item_id: str
    input_json: dict


class FlexPepDockDryRunResponse(BaseModel):
    workdir: str
    command: str
    receptor_pdb: str
    peptide_pdb: str
    peptide_fasta: str
    receptor_chain: str
    peptide_chain: str
    dry_run: bool


class FlexPepDockSmokeResponse(BaseModel):
    success: bool
    error: Optional[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/probe", response_model=ApiResponse[FlexPepDockProbeResponse])
def probe_flexpepdock(
    db: Session = Depends(get_db),
):
    """Probe the server environment for FlexPepDock readiness.

    Returns BLOCKED if critical Rosetta/FlexPepDock dependencies are missing.
    Returns AVAILABLE if all critical dependencies are present.
    """
    report = probe_flexpepdock_environment()
    return ApiResponse.success(data=report.to_dict())


@router.post("/validate-input", response_model=ApiResponse[FlexPepDockValidateResponse])
def validate_flexpepdock_input(
    body: FlexPepDockValidateRequest,
    db: Session = Depends(get_db),
):
    """Validate FlexPepDock input parameters.

    Checks receptor_pdb, peptide_pdb/peptide_fasta, and chain IDs.
    """
    ok, err = validate_input(body.input_json)
    return ApiResponse.success(data={"ok": ok, "error": err})


@router.post("/create-workdir", response_model=ApiResponse[FlexPepDockCreateWorkdirResponse])
def create_flexpepdock_workdir(
    body: FlexPepDockCreateWorkdirRequest,
    db: Session = Depends(get_db),
):
    """Create the working directory scaffold for a FlexPepDock job."""
    workdir = create_workdir(body.batch_id, body.item_id)
    return ApiResponse.success(data={"workdir": workdir})


@router.post("/dry-run", response_model=ApiResponse[FlexPepDockDryRunResponse])
def dry_run_flexpepdock(
    body: FlexPepDockDryRunRequest,
    db: Session = Depends(get_db),
):
    """Log the commands that would be executed without running them."""
    result = dry_run(body.batch_id, body.item_id, body.input_json)
    return ApiResponse.success(data=result)


@router.post("/smoke", response_model=ApiResponse[FlexPepDockSmokeResponse])
def smoke_flexpepdock(
    db: Session = Depends(get_db),
):
    """Run a minimal smoke test (FlexPepDocking -help).

    Returns success=True if the binary responds to -help.
    """
    success, error = smoke_run()
    return ApiResponse.success(data={"success": success, "error": error})
