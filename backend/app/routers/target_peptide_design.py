"""Targeted Peptide Design Center API skeleton."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import ApiResponse
from app.schemas.target_peptide_design import (
    TargetPeptideDesignCandidatesResponse,
    TargetPeptideDesignJobCreate,
    TargetPeptideDesignJobResponse,
    TargetPeptideDesignModelProbeResult,
    TargetPeptideDesignModelProbesResponse,
    TargetPeptideDesignModelsResponse,
)
from app.services.target_peptide_design_service import (
    create_target_peptide_job,
    get_target_peptide_job,
    get_target_peptide_job_candidates,
    list_target_peptide_models_payload,
)
from app.services.target_peptide_model_probe import (
    get_target_peptide_model_probe,
    get_target_peptide_model_probes,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/target-peptide-design", tags=["Targeted Peptide Design"])


@router.get(
    "/models",
    status_code=status.HTTP_200_OK,
    summary="List target peptide design models",
    response_model=ApiResponse[TargetPeptideDesignModelsResponse],
)
async def list_models() -> ApiResponse[TargetPeptideDesignModelsResponse]:
    return ApiResponse.success(
        data=TargetPeptideDesignModelsResponse.model_validate(
            list_target_peptide_models_payload()
        )
    )


@router.get(
    "/models/probe",
    status_code=status.HTTP_200_OK,
    summary="Probe all target peptide design models",
    response_model=ApiResponse[TargetPeptideDesignModelProbesResponse],
)
async def list_model_probes() -> ApiResponse[TargetPeptideDesignModelProbesResponse]:
    return ApiResponse.success(
        data=get_target_peptide_model_probes()
    )


@router.get(
    "/models/{model_id}/probe",
    status_code=status.HTTP_200_OK,
    summary="Probe a target peptide design model",
    response_model=ApiResponse[TargetPeptideDesignModelProbeResult],
)
async def get_model_probe(model_id: str) -> ApiResponse[TargetPeptideDesignModelProbeResult]:
    try:
        probe = get_target_peptide_model_probe(model_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ApiResponse.success(data=probe)


@router.post(
    "/jobs",
    status_code=status.HTTP_201_CREATED,
    summary="Create a target peptide design job skeleton",
    response_model=ApiResponse[TargetPeptideDesignJobResponse],
)
async def create_job(
    request: TargetPeptideDesignJobCreate,
) -> ApiResponse[TargetPeptideDesignJobResponse]:
    try:
        job = create_target_peptide_job(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ApiResponse.success(data=job)


@router.get(
    "/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Get a target peptide design job by ID",
    response_model=ApiResponse[TargetPeptideDesignJobResponse],
)
async def get_job(job_id: str) -> ApiResponse[TargetPeptideDesignJobResponse]:
    job = get_target_peptide_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target peptide design job '{job_id}' not found",
        )
    return ApiResponse.success(data=job)


@router.get(
    "/jobs/{job_id}/candidates",
    status_code=status.HTTP_200_OK,
    summary="Get target peptide design job candidates",
    response_model=ApiResponse[TargetPeptideDesignCandidatesResponse],
)
async def get_candidates(
    job_id: str,
) -> ApiResponse[TargetPeptideDesignCandidatesResponse]:
    candidates = get_target_peptide_job_candidates(job_id)
    if candidates is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target peptide design job '{job_id}' not found",
        )
    return ApiResponse.success(data=candidates)
