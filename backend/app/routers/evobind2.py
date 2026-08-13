"""EvoBind2 Router — Dry-run and Probe API (v0.2-probe).

Provides:
  - POST /dry-run  : plans an EvoBind2 run without executing it
  - GET  /probe    : read-only environment probe (no subprocess model execution)

No subprocess calls that run EvoBind2, HHblits searches, AlphaFold2 forward
passes, or generate MSA/candidate/PDB outputs.  The probe endpoint is safe to
expose even in public-demo mode because it only checks paths and runs
help/version/import commands in the isolated conda environment.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, status

from app.models.schemas import ApiResponse
from app.schemas.evobind2 import (
    EvoBind2DryRunRequest,
    EvoBind2DryRunResponse,
    EvoBind2ProbeResponse,
)
from app.services.compute_wrappers.evobind2_wrapper import (
    EvoBind2Input,
    dry_run_plan,
    probe,
)

logger = logging.getLogger("stamp")

router = APIRouter(prefix="/api/v1/evobind2", tags=["EvoBind2"])


# ---------------------------------------------------------------------------
# GET /api/v1/evobind2/probe
# ---------------------------------------------------------------------------


@router.get(
    "/probe",
    response_model=ApiResponse[EvoBind2ProbeResponse],
    status_code=status.HTTP_200_OK,
    summary="Probe EvoBind2 environment readiness",
)
async def evobind2_probe() -> ApiResponse[EvoBind2ProbeResponse]:
    """Read-only probe of the EvoBind2 execution environment.

    This endpoint does NOT:
      - run EvoBind2 / mc_design.py design flow
      - run HHblits database searches
      - run AlphaFold2 forward passes
      - generate MSA, candidate peptides, PDB, or scientific metrics

    It only verifies that source code, conda environment, AF2 parameters,
    HHblits binary, UniRef30 database, and JAX/GPU resources are present.
    """
    result = probe()
    response = EvoBind2ProbeResponse(**result)

    if result["status"] == "UNAVAILABLE":
        return ApiResponse.error(
            code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message="EvoBind2 environment is unavailable",
            data=response.model_dump(),
        )

    return ApiResponse.success(
        data=response,
        message="EvoBind2 probe completed without running the model",
    )


# ---------------------------------------------------------------------------
# POST /api/v1/evobind2/dry-run
# ---------------------------------------------------------------------------


@router.post(
    "/dry-run",
    response_model=ApiResponse[EvoBind2DryRunResponse],
    status_code=status.HTTP_200_OK,
    summary="Dry-run an EvoBind2 predict-only job",
)
async def evobind2_dry_run(body: EvoBind2DryRunRequest) -> ApiResponse[EvoBind2DryRunResponse]:
    """Plan an EvoBind2 run without executing it.

    Returns the command preview, environment variables, artifact paths,
    and safety flags.  No subprocess is spawned and no GPU job is run.
    """
    # Convert schema request to wrapper input
    inp = EvoBind2Input(
        run_id=body.run_id,
        receptor_fasta=body.receptor_fasta,
        peptide_length=body.peptide_length,
        mode=body.mode,
        peptide_sequence=body.peptide_sequence,
        model_name=body.model_name,
        max_recycles=body.max_recycles,
        num_iterations=body.num_iterations,
        use_gpu=body.use_gpu,
        selected_gpu=body.selected_gpu,
        msa_mode=body.msa_mode,
        receptor_msa_a3m=body.receptor_msa_a3m,
    )

    # Plan (never executes)
    plan = dry_run_plan(inp)

    # Map wrapper output to schema response
    response = EvoBind2DryRunResponse(
        run_id=plan.run_id,
        status=plan.status,
        mode=plan.mode,
        model_name=plan.model_name,
        used_gpu=plan.used_gpu,
        selected_gpu=plan.selected_gpu,
        runtime_seconds=plan.runtime_seconds,
        artifacts=plan.artifacts,
        safety_flags=plan.safety_flags,
        command_preview=plan.command_preview,
        env_preview=plan.env_preview,
        error_message=plan.error_message,
    )

    if plan.status == "BLOCKED":
        return ApiResponse.error(
            code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message=plan.error_message or "EvoBind2 run blocked",
            data=response.model_dump(),
        )

    return ApiResponse.success(
        data=response,
        message="EvoBind2 dry-run planned — no commands were executed",
    )
