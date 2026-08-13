"""Unified Model Registry Router (P4A/P5C).

Provides a model-agnostic API over the target peptide design adapters:
  - GET  /api/v1/models
  - GET  /api/v1/models/{model_id}
  - GET  /api/v1/models/{model_id}/probe
  - POST /api/v1/models/{model_id}/dry-run
  - POST /api/v1/models/{model_id}/submit
  - GET  /api/v1/models/{model_id}/jobs/{job_id}
  - GET  /api/v1/models/{model_id}/jobs/{job_id}/artifacts
  - GET  /api/v1/models/{model_id}/jobs/{job_id}/artifacts/{artifact_name}/download

Existing EvoBind2 endpoints (/api/v1/evobind2/*) are preserved.
No real model execution is performed unless the adapter-level real-run gate
is explicitly open; the public-demo gate remains closed by default.
"""

from __future__ import annotations

import hashlib
import logging
import os
import pathlib
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import ApiResponse
from app.schemas.model_registry import (
    ModelArtifactsResponse,
    ModelDetailResponse,
    ModelDryRunPayload,
    ModelDryRunResult,
    ModelProbeResult,
    ModelRegistryStatusEntry,
    ModelRegistryStatusResponse,
    ModelsListResponse,
)
from app.services.evobind2_job_service import (
    get_evobind2_job,
    resolve_evobind2_artifact_path,
)
from app.services.model_adapters import DiffPepBuilderAdapter, EvoBind2Adapter, PepGLADAdapter, PepHARAdapter, PepFlowAdapter, PepMLMAdapter, PepMLMRegistryAdapter, PepPrCLIPAdapter, PlaceholderAdapter, PPFlowAdapter, RFpeptidesAdapter
from app.services.pepmlm_job_service import (
    get_pepmlm_job,
    submit_pepmlm_job,
)
from app.services.target_peptide_model_registry import (
    SCIENTIFIC_BOUNDARY_NOTE,
    build_default_safety_flags,
    get_model,
    list_models,
)
from app.workers.pepmlm_worker import process_pepmlm_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/models", tags=["Model Registry"])
model_registry_status_router = APIRouter(
    prefix="/api/v1/model-registry", tags=["Model Registry Status"]
)


def _build_model_registry_status_response() -> ModelRegistryStatusResponse:
    """Build a compact status dashboard for the 8-model track."""
    models = list_models()
    entries: list[ModelRegistryStatusEntry] = []
    parked: list[str] = []
    pending_probe: list[str] = []
    pending_registry: list[str] = []
    for model in models:
        status = str(model.get("status", ""))
        entry = ModelRegistryStatusEntry(
            model_id=str(model["model_id"]),
            display_name=str(model["display_name"]),
            status=status,
            status_reason=model.get("status_reason"),
            stage=str(model.get("stage", "")),
            supports_probe=bool(model.get("supports_probe", False)),
            supports_dry_run=bool(model.get("supports_dry_run", False)),
            supports_real_run=bool(model.get("supports_real_run", False)),
            notes=model.get("notes"),
            product_group=str(model.get("product_group", "unknown")),
            ui_selectable=bool(model.get("ui_selectable", False)),
            ui_execution_state=str(model.get("ui_execution_state", "unknown")),
            activation_requirements=str(model.get("activation_requirements", "")),
            delivery_status=str(model.get("delivery_status", "")),
        )
        entries.append(entry)
        if status == "parked":
            parked.append(str(model["model_id"]))
        elif status == "pending_probe":
            pending_probe.append(str(model["model_id"]))
        elif status == "pending_registry":
            pending_registry.append(str(model["model_id"]))
    return ModelRegistryStatusResponse(
        models=entries,
        parked_models=parked,
        pending_probe_models=pending_probe,
        pending_registry_models=pending_registry,
        scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        count_total=len(entries),
        count_parked=len(parked),
        count_pending_probe=len(pending_probe),
        count_pending_registry=len(pending_registry),
    )


def _get_adapter(model_id: str) -> Any:
    """Return the appropriate adapter for a registered model."""
    model = get_model(model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' is not registered.",
        )
    adapter_id = str(model.get("adapter_id", ""))
    model_status = str(model.get("status", ""))
    # D19-A hard safety boundary: blocked/backlog entries are metadata-only.
    # Route them through the zero-execution placeholder before any concrete adapter.
    if str(model.get("product_group", "")) in {"blocked", "backlog"}:
        return PlaceholderAdapter(model_id)
    if model_id == "diffpepbuilder" or adapter_id == "diffpepbuilder":
        return DiffPepBuilderAdapter(model_id)
    if model_id == "ppflow" or adapter_id == "ppflow":
        return PPFlowAdapter(model_id)
    if model_id == "pepflow" or adapter_id == "pepflow":
        return PepFlowAdapter(model_id)
    if model_id == "pephar" or adapter_id == "pephar":
        return PepHARAdapter(model_id)
    # RFpeptides adapter is staging but safe (no execution); route before
    # the generic pending_registry placeholder so probe/dry-run details are preserved.
    if model_id == "rfpeptides" or adapter_id == "rfpeptides":
        return RFpeptidesAdapter(model_id)

    # Pending-registry skeleton models are explicitly routed through the
    # placeholder adapter so probe / dry-run return blocked without touching
    # any runtime. This overrides any previously-retained concrete adapter.
    if model_status == "pending_registry":
        return PlaceholderAdapter(model_id)
    if model_id == "evobind2" or adapter_id == "evobind2":
        return EvoBind2Adapter(model_id)
    if model_id == "pepmlm" or adapter_id == "pepmlm":
        return PepMLMRegistryAdapter(model_id)
    if model_id == "pepprclip" or adapter_id == "pepprclip":
        return PepPrCLIPAdapter(model_id)
    if model_id == "pepglad" or adapter_id == "pepglad":
        return PepGLADAdapter(model_id)
    return PlaceholderAdapter(model_id)


def _safe_model_id(model_id: str) -> str:
    """Validate that model_id does not contain path separators or traversal."""
    normalized = model_id.strip().replace(" ", "_").lower()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model ID cannot be empty.",
        )
    if ".." in normalized or "/" in normalized or "\\" in normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid model ID.",
        )
    return normalized


def _safe_artifact_name(artifact_name: str) -> str:
    """Validate artifact_name is a simple identifier.

    Rejects path separators and traversal so that download URLs can only
    address well-known artifact names registered in the adapter manifest.
    """
    normalized = artifact_name.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artifact name cannot be empty.",
        )
    if ".." in normalized or "/" in normalized or "\\" in normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid artifact name.",
        )
    return normalized


def _safe_job_id(job_id: str) -> str:
    """Reject traversal and path separators before an adapter sees a job id."""
    normalized = job_id.strip()
    if not normalized or ".." in normalized or "/" in normalized or "\\" in normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job ID.")
    return normalized


# ---------------------------------------------------------------------------
# P33Q: unified six-model evidence whitelist + safe download helpers
# ---------------------------------------------------------------------------

_STAMPUP_BASE = "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev"
_EVIDENCE_REPORTS_DIR = "/home/xh/kxc/stampup/reports"
_PPFLOW_EVIDENCE_REPORT_DIR = _STAMPUP_BASE + "/reports/p33o_ppflow_repair"
_PPFLOW_ARTIFACT_DIR = "/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33o_ppflow_path_repair_20260629_063127"
_P32B_ARTIFACT_DIR = "/mnt/sdb/kxc/stamp_models/artifacts/p32b_overnight/p32b_overnight_20260628_82705827"

# Per-model, per-evidence-id whitelist. Only real on-disk evidence files are
# listed; SHA256 is re-checked at download time. No client-supplied path is
# ever honored. `filename`/`media_type` are metadata for the non-file /evidence
# response; the server path is never exposed to the client.
_EVIDENCE_WHITELIST: dict[str, dict[str, dict[str, str]]] = {
    "ppflow": {
        "success_report": {
            "path": _PPFLOW_EVIDENCE_REPORT_DIR + "/STAMP_P33O_PPFLOW_PATH_REPAIR_SUCCESS_REPORT.md",
            "sha256": "8f6519e85ce6f7936794ed5d580fe2c7ef52dadff6c6643770d19c0eb873f293",
            "filename": "ppflow_success_report.md",
            "media_type": "text/markdown",
        },
        "execution_manifest": {
            "path": _PPFLOW_EVIDENCE_REPORT_DIR + "/STAMP_P33O_PPFLOW_PATH_REPAIR_EXECUTION_MANIFEST.md",
            "sha256": "1c3cfe85a35989f4deef44305186eb1683336c2900a9e5c43e24c8e0729ec307",
            "filename": "ppflow_execution_manifest.md",
            "media_type": "text/markdown",
        },
        "result_manifest": {
            "path": _PPFLOW_ARTIFACT_DIR + "/manifest.json",
            "sha256": "6d14f2f56f927d5130099d88e3993534a8662b88e43394cbc36de93a5a006a00",
            "filename": "ppflow_result_manifest.json",
            "media_type": "application/json",
        },
        "status": {
            "path": _PPFLOW_ARTIFACT_DIR + "/status.json",
            "sha256": "3ffca90345575290cf9fccfbfb3997799631c7834e5f1a94c0e7f520c18628d8",
            "filename": "ppflow_status.json",
            "media_type": "application/json",
        },
    },
    "pepmlm": {
        "success_report": {
            "path": _EVIDENCE_REPORTS_DIR + "/STAMP_PEPMLM_SMOKE_RERUN_FIRST_REAL_MODEL_P30B_REPORT.md",
            "sha256": "235cacd1e1dc2267177c446908bf81df6c22c29f23eae64f25aa90173060d96b",
            "filename": "pepmlm_success_report.md",
            "media_type": "text/markdown",
        },
        "status": {
            "path": _EVIDENCE_REPORTS_DIR + "/STAMP_PEPMLM_SMOKE_RERUN_FIRST_REAL_MODEL_P30B_STATUS.json",
            "sha256": "d334a3bf548c4b3d6fc23de04c2e858eef75c9b560c3eecb03eec7a3ad64f73f",
            "filename": "pepmlm_status.json",
            "media_type": "application/json",
        },
        "reasonix_review": {
            "path": _EVIDENCE_REPORTS_DIR + "/STAMP_PEPMLM_SMOKE_RERUN_FIRST_REAL_MODEL_P30B_REASONIX_REVIEW.md",
            "sha256": "aa253e3c11516961102db35dbb89139d4749dd9db4522d715f23971bf063ef9f",
            "filename": "pepmlm_reasonix_review.md",
            "media_type": "text/markdown",
        },
        "artifacts_index": {
            "path": _EVIDENCE_REPORTS_DIR + "/STAMP_PEPMLM_SMOKE_RERUN_FIRST_REAL_MODEL_P30B_ARTIFACTS.txt",
            "sha256": "57e8b6b92444449b1fe2c81d237d1bfb964458448a0661b10148e7ac30c2ed17",
            "filename": "pepmlm_artifacts_index.txt",
            "media_type": "text/plain",
        },
    },
    "evobind2": {
        "p3b_report": {
            "path": _EVIDENCE_REPORTS_DIR + "/EVOBIND2_P3B_REAL_SMOKE_RUN_CONTROLLED_EXECUTION_REPORT.md",
            "sha256": "01d5100ad74c0771314319a8a042fca9a62afd98e25a0556286376bf67d1d3e8",
            "filename": "evobind2_p3b_report.md",
            "media_type": "text/markdown",
        },
        "p3c_report": {
            "path": _EVIDENCE_REPORTS_DIR + "/EVOBIND2_P3C_WORKER_HARDENING_ARTIFACT_UI_AND_POST_RUN_AUDIT_REPORT.md",
            "sha256": "bb120103bca81069cdde25bd855e62c253c6fd7fc3c54e844e72b1f53bfa0390",
            "filename": "evobind2_p3c_report.md",
            "media_type": "text/markdown",
        },
    },
    "diffpepbuilder": {
        "delivery_manifest": {
            "path": _EVIDENCE_REPORTS_DIR + "/STAMP_P32B_DELIVERY_MANIFEST.json",
            "sha256": "c755ff61980a8dbeccfec66a5f4cf06275542d59839892cab092fc56a00b2c0c",
            "filename": "diffpepbuilder_delivery_manifest.json",
            "media_type": "application/json",
        },
        "result_manifest": {
            "path": _P32B_ARTIFACT_DIR + "/diffpepbuilder/manifest.json",
            "sha256": "ccc6a3e0b601dbe69b8e2b8d5f808ade6bfd30f1c9fc42adb7d701f328202581",
            "filename": "diffpepbuilder_result_manifest.json",
            "media_type": "application/json",
        },
    },
    "pepflow": {
        "delivery_manifest": {
            "path": _EVIDENCE_REPORTS_DIR + "/STAMP_P32B_DELIVERY_MANIFEST.json",
            "sha256": "c755ff61980a8dbeccfec66a5f4cf06275542d59839892cab092fc56a00b2c0c",
            "filename": "pepflow_delivery_manifest.json",
            "media_type": "application/json",
        },
        "result_manifest": {
            "path": _P32B_ARTIFACT_DIR + "/pepflow/manifest.json",
            "sha256": "fc76f5537d1cee88e3e446082d267ac690547861d5c207d0e2941341526708f6",
            "filename": "pepflow_result_manifest.json",
            "media_type": "application/json",
        },
    },
    "pephar": {
        "delivery_manifest": {
            "path": _EVIDENCE_REPORTS_DIR + "/STAMP_P32B_DELIVERY_MANIFEST.json",
            "sha256": "c755ff61980a8dbeccfec66a5f4cf06275542d59839892cab092fc56a00b2c0c",
            "filename": "pephar_delivery_manifest.json",
            "media_type": "application/json",
        },
        "result_manifest": {
            "path": _P32B_ARTIFACT_DIR + "/pephar_density/manifest.json",
            "sha256": "f6b25b80b023aa160241d0fb92d438ce2ffaf2bc5e97527fa5ff37e47ab98695",
            "filename": "pephar_result_manifest.json",
            "media_type": "application/json",
        },
    },
}

# Per-model containment roots. A resolved evidence path must lie within one of
# its model's roots (exact or nested). Symlinks escaping these roots are rejected.
_EVIDENCE_ALLOWED_ROOTS: dict[str, list[str]] = {
    "ppflow": [_PPFLOW_EVIDENCE_REPORT_DIR, _PPFLOW_ARTIFACT_DIR],
    "pepmlm": [_EVIDENCE_REPORTS_DIR],
    "evobind2": [_EVIDENCE_REPORTS_DIR],
    "diffpepbuilder": [_EVIDENCE_REPORTS_DIR, _P32B_ARTIFACT_DIR],
    "pepflow": [_EVIDENCE_REPORTS_DIR, _P32B_ARTIFACT_DIR],
    "pephar": [_EVIDENCE_REPORTS_DIR, _P32B_ARTIFACT_DIR],
}


def _safe_evidence_id(model_id: str, evidence_id: str) -> str:
    """Validate evidence_id is a simple identifier in this model's whitelist.

    Rejects path separators, traversal, absolute paths, and unknown ids.
    No arbitrary absolute path is ever accepted from the client.
    """
    normalized = evidence_id.strip()
    if not normalized or "/" in normalized or "\\" in normalized or ".." in normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid evidence id.",
        )
    model_whitelist = _EVIDENCE_WHITELIST.get(model_id, {})
    if normalized not in model_whitelist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence id not authorized for this model.",
        )
    return normalized


def _resolve_evidence(model_id: str, evidence_id: str) -> pathlib.Path:
    """Resolve a whitelisted evidence file for a model, enforcing containment,
    no symlinks, existence, and SHA256 match. Read-only: never writes."""
    entry = _EVIDENCE_WHITELIST[model_id][evidence_id]
    p = pathlib.Path(entry["path"]).resolve(strict=True)
    allowed_roots = [pathlib.Path(r).resolve(strict=True) for r in _EVIDENCE_ALLOWED_ROOTS.get(model_id, [])]
    contained = any(str(p) == str(r) or str(p).startswith(str(r) + os.sep) for r in allowed_roots)
    if not contained:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evidence path escapes whitelist root.",
        )
    if p.is_symlink():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Symlink evidence rejected.",
        )
    if not p.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file missing on disk.",
        )
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    if actual.lower() != str(entry["sha256"]).lower():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evidence SHA256 mismatch; download refused.",
        )
    return p


# ---------------------------------------------------------------------------
# GET /api/v1/models
# ---------------------------------------------------------------------------


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List all registered models",
    response_model=ApiResponse[ModelsListResponse],
)
async def list_models_endpoint() -> ApiResponse[ModelsListResponse]:
    """Return the unified registry of peptide design models."""
    models = list_models()
    return ApiResponse.success(
        data=ModelsListResponse(
            models=models,
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
            available_models=5,
            blocked_models=1,
            backlog_models=3,
            available_model_ids=["pepmlm", "diffpepbuilder", "pephar", "pepflow", "evobind2"],
            blocked_model_ids=["ppflow"],
            backlog_model_ids=["pepprclip", "rfpeptides", "pepglad"],
        ),
        message="Model registry returned",
    )


# ---------------------------------------------------------------------------
# GET /api/v1/models/{model_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{model_id}",
    status_code=status.HTTP_200_OK,
    summary="Get a single model's metadata and capabilities",
    response_model=ApiResponse[ModelDetailResponse],
)
async def get_model_endpoint(
    model_id: Annotated[str, Path(...)],
) -> ApiResponse[ModelDetailResponse]:
    """Return capabilities and safety metadata for one registered model."""
    normalized = _safe_model_id(model_id)
    adapter = _get_adapter(normalized)
    return ApiResponse.success(
        data=ModelDetailResponse(
            model=adapter.model_entry,
            safety_flags=build_default_safety_flags(),
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        ),
        message=f"Model '{normalized}' metadata returned",
    )


# ---------------------------------------------------------------------------
# GET /api/v1/models/{model_id}/probe
# ---------------------------------------------------------------------------


@router.get(
    "/{model_id}/probe",
    status_code=status.HTTP_200_OK,
    summary="Probe a registered model",
    response_model=ApiResponse[ModelProbeResult],
)
async def probe_model_endpoint(
    model_id: Annotated[str, Path(...)],
) -> ApiResponse[ModelProbeResult]:
    """Run a read-only probe for the requested model."""
    normalized = _safe_model_id(model_id)
    adapter = _get_adapter(normalized)
    result = adapter.probe()
    return ApiResponse.success(
        data=result,
        message=f"Model '{normalized}' probe completed",
    )


# ---------------------------------------------------------------------------
# POST /api/v1/models/{model_id}/dry-run
# ---------------------------------------------------------------------------


@router.post(
    "/{model_id}/dry-run",
    status_code=status.HTTP_200_OK,
    summary="Dry-run a registered model",
    response_model=ApiResponse[ModelDryRunResult],
)
async def dry_run_model_endpoint(
    model_id: Annotated[str, Path(...)],
    payload: ModelDryRunPayload,
) -> ApiResponse[ModelDryRunResult]:
    """Plan a run for the requested model without executing it."""
    normalized = _safe_model_id(model_id)
    adapter = _get_adapter(normalized)
    result = adapter.dry_run(payload)
    return ApiResponse.success(
        data=result,
        message=f"Model '{normalized}' dry-run completed",
    )


# ---------------------------------------------------------------------------
# POST /api/v1/models/{model_id}/submit
# ---------------------------------------------------------------------------


def _blocked_submit_result(model_id: str) -> dict[str, Any]:
    model = get_model(model_id)
    is_pending_registry = bool(model and str(model.get("status", "")) == "pending_registry")
    status_reason = ""
    if is_pending_registry:
        status_reason = str(
            model.get("status_reason", "pending_registry_skeleton_not_yet_implemented")
        )
    return {
        "model_id": model_id,
        "display_name": str(model["display_name"]) if model else model_id,
        "status": "BLOCKED",
        "message": "Real execution is disabled for this model in this phase.",
        "run_id": None,
        "artifacts": {},
        "expected_artifacts": {},
        "command_preview": None,
        "env_preview": {},
        "environment_summary": {},
        "blocked_reasons": [status_reason] if is_pending_registry else [],
        "safety_flags": build_default_safety_flags(),
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "scientific_boundary": SCIENTIFIC_BOUNDARY_NOTE,
        "available": False if is_pending_registry else None,
        "actionable": False if is_pending_registry else None,
        "dry_run_status": "blocked" if is_pending_registry else None,
        "reason": status_reason or None,
        "stage": "P1_SKELETON" if is_pending_registry else None,
        "runs_model": False if is_pending_registry else None,
        "generates_candidates": False if is_pending_registry else None,
        "experimental_validation": False if is_pending_registry else None,
    }


@router.post(
    "/{model_id}/submit",
    status_code=status.HTTP_200_OK,
    summary="Submit a real run for a registered model",
)
async def submit_model_endpoint(
    model_id: Annotated[str, Path(...)],
    payload: ModelDryRunPayload,
    sync: bool = False,
    db: Session = Depends(get_db),
) -> ApiResponse[Any]:
    """Submit a real run for the requested model.

    Only PepMLM is supported in P5C.  Set ``sync=true`` to block until the run
    completes (used for the controlled smoke run); otherwise a job record is
    created and returned for the worker to process asynchronously.
    """
    normalized = _safe_model_id(model_id)
    if normalized == "diffpepbuilder":
        result = _get_adapter(normalized).submit(payload)
        return ApiResponse.success(
            data=result,
            message="DiffPepBuilder submission is blocked in P17",
        )
    if normalized != "pepmlm":
        return ApiResponse.success(
            data=_blocked_submit_result(normalized),
            message=f"Real execution for model '{normalized}' is not enabled",
        )

    project_id = "p5c_smoke"
    job = submit_pepmlm_job(db, payload, project_id=project_id)

    if sync:
        process_pepmlm_job(db, job)
        db.refresh(job)
        adapter = PepMLMAdapter(normalized)
        artifacts_response = adapter.list_artifacts(str(job.id))
        return ApiResponse.success(
            data={
                "job_id": job.id,
                "status": job.status,
                "message": job.message or job.error_message,
                "run_id": str(job.id),
                "artifacts": artifacts_response.artifacts,
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                "safety_flags": {
                    "executed_model": job.status == "succeeded",
                    "generated_candidates": job.status == "succeeded",
                    "generated_structure": False,
                    "generated_msa": False,
                    "is_scientific_result": job.status == "succeeded",
                    "computational_prediction_only": True,
                },
            },
            message=f"PepMLM real run completed with status {job.status}",
        )

    return ApiResponse.success(
        data={"job_id": job.id, "status": job.status},
        message="PepMLM real run submitted",
    )


# ---------------------------------------------------------------------------
# GET /api/v1/models/{model_id}/jobs/{job_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{model_id}/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Get status of a model job",
)
async def get_model_job_status_endpoint(
    model_id: Annotated[str, Path(...)],
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[Any]:
    """Return the status and output of a submitted model job."""
    normalized = _safe_model_id(model_id)

    if normalized == "pepmlm":
        job = get_pepmlm_job(db, job_id)
    elif normalized == "evobind2":
        job = get_evobind2_job(db, job_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job status is not available for model '{normalized}'.",
        )

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found for model '{normalized}'.",
        )

    return ApiResponse.success(
        data={
            "job_id": job.id,
            "model_id": normalized,
            "status": job.status,
            "progress": job.progress,
            "message": job.message,
            "error_message": job.error_message,
            "error_json": job.error_json,
            "output_json": job.output_json,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        },
        message=f"Job '{job_id}' status returned",
    )


# ---------------------------------------------------------------------------
# GET /api/v1/models/{model_id}/jobs/{job_id}/artifacts
# ---------------------------------------------------------------------------


@router.get(
    "/{model_id}/jobs/{job_id}/artifacts",
    status_code=status.HTTP_200_OK,
    summary="List artifacts for a model job",
    response_model=ApiResponse[ModelArtifactsResponse],
)
async def list_model_artifacts_endpoint(
    model_id: Annotated[str, Path(...)],
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[ModelArtifactsResponse]:
    """List artifact metadata for a previously submitted job."""
    normalized_model = _safe_model_id(model_id)
    normalized_job = _safe_job_id(job_id)
    adapter = _get_adapter(normalized_model)
    result = adapter.list_artifacts(normalized_job)
    return ApiResponse.success(
        data=result,
        message=f"Artifacts for model '{normalized_model}' job '{job_id}' returned",
    )


# ---------------------------------------------------------------------------
# GET /api/v1/models/{model_id}/jobs/{job_id}/artifacts/{artifact_name}/download
# ---------------------------------------------------------------------------


@router.get(
    "/{model_id}/jobs/{job_id}/artifacts/{artifact_name}/download",
    status_code=status.HTTP_200_OK,
    summary="Download a single model artifact",
    response_class=FileResponse,
)
async def download_model_artifact_endpoint(
    model_id: Annotated[str, Path(...)],
    job_id: Annotated[str, Path(...)],
    artifact_name: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download a single artifact file for a model job."""
    normalized_model = _safe_model_id(model_id)
    normalized_artifact = _safe_artifact_name(artifact_name)

    adapter = _get_adapter(normalized_model)

    if isinstance(adapter, EvoBind2Adapter):
        job = get_evobind2_job(db, job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found for model '{normalized_model}'.",
            )

        artifact_path = resolve_evobind2_artifact_path(job, normalized_artifact)
        if artifact_path is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact '{normalized_artifact}' not found for job '{job_id}'.",
            )
    elif isinstance(adapter, PepMLMAdapter):
        artifact_path = adapter.download_artifact_path(job_id, normalized_artifact)
        if artifact_path is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact '{normalized_artifact}' not found for job '{job_id}'.",
            )
    elif isinstance(adapter, PepPrCLIPAdapter):
        artifact_path = adapter.download_artifact_path(job_id, normalized_artifact)
        if artifact_path is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact '{normalized_artifact}' not found for job '{job_id}'.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Download is not available for model '{normalized_model}'.",
        )

    if not artifact_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{normalized_artifact}' exists in manifest but file is missing on disk",
        )

    return FileResponse(
        path=str(artifact_path),
        filename=artifact_path.name,
        media_type="application/octet-stream",
    )


# ---------------------------------------------------------------------------
# P33Q: unified six-model structured evidence metadata + safe download
# GET /api/v1/models/{model_id}/evidence
# GET /api/v1/models/{model_id}/evidence/{evidence_id}/download
# ---------------------------------------------------------------------------


@router.get(
    "/{model_id}/evidence",
    status_code=status.HTTP_200_OK,
    summary="Return structured evidence metadata for a model (P33Q unified)",
)
async def get_model_evidence_endpoint(model_id: Annotated[str, Path(...)]):
    """Return structured (non-file) evidence metadata for any registered model.

    Unified six-model contract (P33Q): every registered model returns 200 with
    an availability flag and a per-model whitelist of downloadable evidence ids.
    Models without on-disk evidence return availability=unavailable and an empty
    downloadable_ids list; no evidence is ever forged. No file content is
    returned here; downloads go through the whitelisted endpoint below.
    """
    mid = _safe_model_id(model_id)
    models = {str(m.get("model_id", "")): m for m in list_models()}
    if mid not in models:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found.")
    model = models[mid]
    ev = model.get("evidence", {}) or {}
    availability = str(
        ev.get("availability") or ("available" if mid in _EVIDENCE_WHITELIST else "unavailable")
    )
    stats = ev.get("stats")
    whitelist = _EVIDENCE_WHITELIST.get(mid, {})
    downloadable_ids = list(whitelist.keys())
    artifacts = []
    for eid, entry in whitelist.items():
        try:
            bytes_size = os.path.getsize(entry["path"])
        except OSError:
            bytes_size = None
        artifacts.append({
            "id": eid,
            "filename": entry.get("filename", eid),
            "media_type": entry.get("media_type", "application/octet-stream"),
            "sha256": entry["sha256"],
            "bytes": bytes_size,
        })
    return {
        "code": 200,
        "message": f"{mid} evidence metadata",
        "data": {
            "model_id": mid,
            "stage": model.get("stage"),
            "validation_status": model.get("validation_status", "NOT_EXPERIMENTALLY_VALIDATED"),
            "execution_locked": model.get("execution_locked", True),
            "real_run_enabled": model.get("real_run_enabled", False),
            "supports_real_run": model.get("supports_real_run", False),
            "evidence_ref": model.get("evidence_ref", ""),
            "availability": availability,
            "stats": stats,
            "downloadable_ids": downloadable_ids,
            "artifacts": artifacts,
        },
    }


@router.get(
    "/{model_id}/evidence/{evidence_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download a whitelisted evidence file (SHA256-verified, P33Q unified)",
    response_class=FileResponse,
)
async def download_model_evidence_endpoint(
    model_id: Annotated[str, Path(...)],
    evidence_id: Annotated[str, Path(...)],
):
    """Download a single whitelisted, SHA256-verified evidence file.

    Only evidence ids registered in the per-model whitelist are authorized.
    Arbitrary absolute paths, traversal, and symlinks are rejected; the on-disk
    SHA256 is re-checked before serving. No model execution, gate, or checkpoint
    load occurs.
    """
    mid = _safe_model_id(model_id)
    if mid not in _EVIDENCE_WHITELIST:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No evidence download for this model.",
        )
    eid = _safe_evidence_id(mid, evidence_id)
    entry = _EVIDENCE_WHITELIST[mid][eid]
    path = _resolve_evidence(mid, eid)
    return FileResponse(
        path=str(path),
        filename=entry.get("filename", f"{mid}_{eid}"),
        media_type=entry.get("media_type", "application/octet-stream"),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/model-registry
# GET /api/v1/model-registry/status
# ---------------------------------------------------------------------------


@model_registry_status_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List all registered models (registry alias)",
    response_model=ApiResponse[ModelsListResponse],
)
async def model_registry_alias_endpoint() -> ApiResponse[ModelsListResponse]:
    """Alias for GET /api/v1/models."""
    return ApiResponse.success(
        data=ModelsListResponse(
            models=list_models(),
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        ),
        message="Model registry returned",
    )


@model_registry_status_router.get(
    "/status",
    status_code=status.HTTP_200_OK,
    summary="Get compact 8-model track status dashboard",
    response_model=ApiResponse[ModelRegistryStatusResponse],
)
async def model_registry_status_endpoint() -> ApiResponse[ModelRegistryStatusResponse]:
    """Return a compact status table for the 8-model track."""
    return ApiResponse.success(
        data=_build_model_registry_status_response(),
        message="Model registry status returned",
    )
