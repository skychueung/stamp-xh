"""Filesystem-backed skeleton service for Targeted Peptide Design jobs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.schemas.target_peptide_design import (
    TargetPeptideDesignCandidatesResponse,
    TargetPeptideDesignJobCreate,
    TargetPeptideDesignJobResponse,
)
from app.services.target_peptide_model_registry import (
    SCIENTIFIC_BOUNDARY_NOTE,
    get_target_peptide_model,
    list_target_peptide_models,
)

JOB_NOTE = "No real model was executed in P2."
EMPTY_CANDIDATE_NOTE = "No real model was executed in P2."


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utcnow().isoformat()


def get_target_peptide_design_root() -> Path:
    return Path(settings.stamp_data_dir).expanduser().resolve() / "target_peptide_design"


def get_target_peptide_design_jobs_root() -> Path:
    return get_target_peptide_design_root() / "jobs"


def ensure_job_artifact_dir(job_id: str) -> Path:
    job_dir = get_target_peptide_design_jobs_root() / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_job_status_payload(
    *,
    job_id: str,
    request: TargetPeptideDesignJobCreate,
    model_info: dict[str, object],
    status: str,
    message: str,
    artifact_dir: Path,
    created_at: str,
    updated_at: str,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "target_name": request.target_name,
        "target_sequence": request.target_sequence,
        "model_id": request.model_id,
        "peptide_length": request.peptide_length,
        "num_candidates": request.num_candidates,
        "status": status,
        "message": message,
        "artifact_dir": str(artifact_dir),
        "notes": request.notes,
        "model_info": model_info,
        "created_at": created_at,
        "updated_at": updated_at,
        "scientific_boundary": SCIENTIFIC_BOUNDARY_NOTE,
    }


def create_target_peptide_job(request: TargetPeptideDesignJobCreate) -> TargetPeptideDesignJobResponse:
    model_info = get_target_peptide_model(request.model_id)
    if model_info is None:
        raise ValueError(f"Unknown model_id '{request.model_id}'")

    job_id = str(uuid4())
    created_at = _iso_now()
    updated_at = created_at
    job_dir = ensure_job_artifact_dir(job_id)

    if request.model_id == "PepMLM":
        status = "CONFIG_REQUIRED"
        message = "PepMLM is registered but not configured in the P2 skeleton."
    else:
        status = "PLANNED"
        message = "Job registered in the P2 skeleton; no model was executed."

    request_payload = request.model_dump(mode="json")
    _write_json(job_dir / "request.json", request_payload)
    _write_json(job_dir / "model_status.json", model_info)

    job_payload = build_job_status_payload(
        job_id=job_id,
        request=request,
        model_info=model_info,
        status=status,
        message=message,
        artifact_dir=job_dir,
        created_at=created_at,
        updated_at=updated_at,
    )
    _write_json(job_dir / "job_status.json", job_payload)
    _write_json(
        job_dir / "candidates.json",
        {
            "job_id": job_id,
            "candidates": [],
            "note": EMPTY_CANDIDATE_NOTE,
            "scientific_boundary": SCIENTIFIC_BOUNDARY_NOTE,
        },
    )

    return TargetPeptideDesignJobResponse.model_validate(job_payload)


def get_target_peptide_job(job_id: str) -> TargetPeptideDesignJobResponse | None:
    job_path = get_target_peptide_design_jobs_root() / job_id / "job_status.json"
    if not job_path.exists():
        return None
    return TargetPeptideDesignJobResponse.model_validate(_load_json(job_path))


def get_target_peptide_job_candidates(
    job_id: str,
) -> TargetPeptideDesignCandidatesResponse | None:
    candidates_path = get_target_peptide_design_jobs_root() / job_id / "candidates.json"
    if not candidates_path.exists():
        return None
    return TargetPeptideDesignCandidatesResponse.model_validate(_load_json(candidates_path))


def list_target_peptide_models_payload() -> dict[str, Any]:
    models = list_target_peptide_models()
    return {
        "models": models,
        "scientific_boundary": SCIENTIFIC_BOUNDARY_NOTE,
    }
