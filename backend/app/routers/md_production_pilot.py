"""MD Production Pilot Router (v1.5 P2).

Endpoints:
  GET  /api/v1/md-pilot/probe      → enhanced env probe
  POST /api/v1/md-pilot/validate-input → validate input PDB
  POST /api/v1/md-pilot/create-workdir → create workdir scaffold
  POST /api/v1/md-pilot/dry-run    → log commands without execution
  POST /api/v1/md-pilot/smoke      → run gmx -h smoke test
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import ApiResponse
from app.services.md_environment_probe import probe_md_environment
from app.services.md_pilot_runner import (
    create_workdir,
    dry_run,
    smoke_run,
    validate_input,
)

logger = logging.getLogger("stamp")

router = APIRouter(prefix="/api/v1/md-pilot", tags=["MD Production Pilot"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MdPilotProbeRequest(BaseModel):
    input_pdb_path: Optional[str] = None


class MdPilotProbeData(BaseModel):
    status: str
    stamp_md_env_available: bool
    gromacs_available: bool
    gromacs_version: Optional[str]
    gpu_available: bool
    gpu_info: Optional[list[dict]]
    mdanalysis_available: bool
    openmm_available: bool
    parmed_available: bool
    amber_available: bool
    mmgbsa_available: bool
    mmgbsa_version: Optional[str]
    platform_version: str
    input_pdb_valid: bool
    input_pdb_path: Optional[str]
    blocking_reasons: list[str]
    next_actions: list[str]

    class Config:
        from_attributes = True


class MdPilotValidateRequest(BaseModel):
    input_json: dict


class MdPilotValidateData(BaseModel):
    ok: bool
    error: Optional[str]


class MdPilotCreateWorkdirRequest(BaseModel):
    batch_id: str
    item_id: str


class MdPilotCreateWorkdirData(BaseModel):
    workdir: str


class MdPilotDryRunRequest(BaseModel):
    batch_id: str
    item_id: str
    input_json: dict


class MdPilotDryRunData(BaseModel):
    workdir: str
    commands: list[str]
    input_pdb: str
    forcefield: str
    water_model: str
    box_type: str
    ion_conc: float
    dry_run: bool


class MdPilotSmokeData(BaseModel):
    success: bool
    error: Optional[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/probe", response_model=ApiResponse[MdPilotProbeData])
def probe_md_get(
    input_pdb_path: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Probe the server environment for MD readiness.

    Returns BLOCKED if critical MD tools (GROMACS, stamp-md env, MDAnalysis) are missing.
    Returns AVAILABLE if all critical dependencies are present.
    """
    report = probe_md_environment(input_pdb_path=input_pdb_path)
    return ApiResponse.success(data=report.to_dict())


@router.post("/probe", response_model=ApiResponse[MdPilotProbeData])
def probe_md_post(
    body: MdPilotProbeRequest,
    db: Session = Depends(get_db),
):
    """POST variant of MD environment probe."""
    report = probe_md_environment(input_pdb_path=body.input_pdb_path)
    return ApiResponse.success(data=report.to_dict())


@router.post("/validate-input", response_model=ApiResponse[MdPilotValidateData])
def validate_md_input(
    body: MdPilotValidateRequest,
    db: Session = Depends(get_db),
):
    """Validate MD pilot input parameters.

    Checks input_pdb existence and minimal PDB format.
    """
    ok, err = validate_input(body.input_json)
    return ApiResponse.success(data={"ok": ok, "error": err})


@router.post("/create-workdir", response_model=ApiResponse[MdPilotCreateWorkdirData])
def create_md_workdir(
    body: MdPilotCreateWorkdirRequest,
    db: Session = Depends(get_db),
):
    """Create the working directory scaffold for an MD pilot job."""
    workdir = create_workdir(body.batch_id, body.item_id)
    return ApiResponse.success(data={"workdir": workdir})


@router.post("/dry-run", response_model=ApiResponse[MdPilotDryRunData])
def dry_run_md(
    body: MdPilotDryRunRequest,
    db: Session = Depends(get_db),
):
    """Log the commands that would be executed without running them."""
    result = dry_run(body.batch_id, body.item_id, body.input_json)
    return ApiResponse.success(data=result)


@router.post("/smoke", response_model=ApiResponse[MdPilotSmokeData])
def smoke_md(
    db: Session = Depends(get_db),
):
    """Run a minimal smoke test (gmx -h inside stamp-md conda env).

    Returns success=True if gmx responds.
    """
    success, error = smoke_run()
    return ApiResponse.success(data={"success": success, "error": error})
