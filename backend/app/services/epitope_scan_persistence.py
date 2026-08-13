"""STAMP Platform -- Epitope Scan Persistence Adapter (P5-lite P2).

Connects the biophysical epitope scanner (app.services.epitope_scanner)
to the database persistence layer. Runs a real scan against a target
protein sequence stored in the DB, creates an epitope_scans record,
persists all candidate epitopes to epitope_candidates, and manages
scan lifecycle (PENDING -> RUNNING -> COMPLETED/FAILED).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.crud.epitopes import (
    create_epitope_candidates_bulk,
    create_epitope_scan,
    mark_epitope_scan_completed,
    mark_epitope_scan_failed,
    mark_epitope_scan_running,
)
from app.crud.target_proteins import get_target_protein
from app.models.epitope import EpitopeScanFilters
from app.schemas import (
    EpitopeCandidateCreate,
    EpitopeScanCandidateItem,
    EpitopeScanCreate,
    EpitopeScanRunRequest,
    EpitopeScanRunResponse,
)
from app.services.epitope_scanner import scan_epitopes

logger = logging.getLogger(__name__)


def _safe_float(val: Any) -> Optional[float]:
    """Safely convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    """Safely convert a value to int, returning None on failure."""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _safe_str(val: Any) -> Optional[str]:
    """Safely convert a value to str, returning None if input is None."""
    if val is None:
        return None
    return str(val)


def map_scan_result_to_candidate_create(
    scan_id: str, raw_candidate: dict[str, Any]
) -> EpitopeCandidateCreate:
    """Map a raw candidate dict (from scan_epitopes) to EpitopeCandidateCreate.

    This function does NOT fabricate any data:
      - surface_exposure_score is kept as None (not computed by scan_epitopes)
      - No experimental validation fields are set
      - All original metrics are preserved in the metrics JSON field

    Field mapping:
      - start -> start
      - end -> end
      - sequence -> sequence
      - net_charge -> net_charge
      - GRAVY -> hydrophobicity
      - pI -> pi
      - cys_count -> cys_count
      - ranking_score -> ranking_score (falls back to 'score' if present)
      - filter_status -> filter_status
      - All other raw fields -> stored in metrics dict
    """
    # Build metrics dict from raw fields, preserving everything for traceability
    metrics = dict(raw_candidate)

    # Extract surface_exposure_score if present (it won't be from scan_epitopes)
    surface_exposure = _safe_float(raw_candidate.get("surface_exposure_score"))

    return EpitopeCandidateCreate(
        scan_id=scan_id,
        start=_safe_int(raw_candidate.get("start")) or 0,
        end=_safe_int(raw_candidate.get("end")) or 0,
        sequence=_safe_str(raw_candidate.get("sequence")) or "",
        net_charge=_safe_float(raw_candidate.get("net_charge")),
        hydrophobicity=_safe_float(raw_candidate.get("GRAVY")),
        pi=_safe_float(raw_candidate.get("pI")),
        cys_count=_safe_int(raw_candidate.get("cys_count")),
        surface_exposure_score=surface_exposure,  # Always None from scan_epitopes
        ranking_score=_safe_float(
            raw_candidate.get("ranking_score", raw_candidate.get("score"))
        ),
        filter_status=_safe_str(raw_candidate.get("filter_status")) or "PASS",
        metrics=metrics if metrics else None,
    )


def run_epitope_scan_and_persist(
    db: Session, request: EpitopeScanRunRequest
) -> EpitopeScanRunResponse:
    """Run a full epitope scan against a DB target protein and persist results.

    Workflow:
      1. Validate target_protein_id exists
      2. Validate project_id matches target_protein.project_id
      3. Create epitope_scans record (status=PENDING)
      4. Mark RUNNING
      5. Call scan_epitopes() with target protein sequence
      6. Map candidates to EpitopeCandidateCreate and bulk insert
      7. Mark COMPLETED
      8. Return EpitopeScanRunResponse

    On any error: mark FAILED, re-raise as StampException.

    Args:
        db: SQLAlchemy session.
        request: Scan run request with project_id, target_protein_id, params.

    Returns:
        EpitopeScanRunResponse with scan_id, status, candidates.

    Raises:
        StampException: 404 if target protein not found, 400 if project mismatch,
                        500 for scan computation errors.
    """
    from app.core.exceptions import StampException

    # --- 1. Validate target protein exists ---
    target_protein = get_target_protein(db, request.target_protein_id)
    if target_protein is None:
        raise StampException(
            status_code=404,
            detail=f"Target protein '{request.target_protein_id}' not found",
            error_code="TARGET_PROTEIN_NOT_FOUND",
        )

    # --- 2. Validate project_id matches ---
    if target_protein.project_id != request.project_id:
        raise StampException(
            status_code=400,
            detail=(
                f"Project ID mismatch: target protein belongs to "
                f"project '{target_protein.project_id}', not '{request.project_id}'"
            ),
            error_code="PROJECT_ID_MISMATCH",
        )

    # --- 3. Create scan record ---
    scan_in = EpitopeScanCreate(
        project_id=request.project_id,
        target_protein_id=request.target_protein_id,
        algorithm=request.algorithm,
        algorithm_version=request.algorithm_version,
        parameters={
            "window_size": request.window_size,
            "top_k": request.top_k,
            "filters": request.filters,
        },
        status="PENDING",
    )
    scan = create_epitope_scan(db, scan_in)
    scan_id = scan.id
    logger.info("Created epitope scan %s for target %s", scan_id, request.target_protein_id)

    try:
        # --- 4. Mark RUNNING ---
        mark_epitope_scan_running(db, scan_id)
        logger.info("Scan %s marked RUNNING", scan_id)

        # --- 5. Build filters if provided ---
        filters = None
        if request.filters:
            try:
                filters = EpitopeScanFilters(**request.filters)
            except Exception as filt_exc:
                logger.warning("Invalid filters provided, using defaults: %s", filt_exc)

        # --- 6. Run the actual scan ---
        scan_result = scan_epitopes(
            sequence=target_protein.sequence,
            target_name=target_protein.name,
            species=getattr(target_protein, "organism", None) or "Unknown",
            window_size=request.window_size,
            top_k=request.top_k,
            filters=filters,
        )

        raw_candidates = scan_result.get("candidates", [])
        logger.info(
            "Scan %s completed with %d candidates", scan_id, len(raw_candidates)
        )

        # --- 7. Map and persist candidates ---
        if raw_candidates:
            candidate_creates = [
                map_scan_result_to_candidate_create(scan_id, rc)
                for rc in raw_candidates
            ]
            create_epitope_candidates_bulk(db, candidate_creates)
            logger.info("Persisted %d candidates for scan %s", len(candidate_creates), scan_id)

        # --- 8. Mark COMPLETED ---
        mark_epitope_scan_completed(db, scan_id)

        # Build response candidates
        top_candidates = [
            EpitopeScanCandidateItem(
                candidate_id=rc.get("candidate_id", f"{scan_id}_{i}"),
                start=rc.get("start", 0),
                end=rc.get("end", 0),
                sequence=rc.get("sequence", ""),
                length=rc.get("length", 0),
                net_charge=rc.get("net_charge"),
                pi=rc.get("pI"),
                hydrophobicity=rc.get("GRAVY"),
                cys_count=rc.get("cys_count"),
                surface_exposure_score=rc.get("surface_exposure_score"),  # None
                ranking_score=rc.get("ranking_score", rc.get("score")),
                filter_status=rc.get("filter_status", "PASS"),
                recommendation_reason=rc.get("recommendation_reason"),
                risk_notes=rc.get("risk_notes"),
                disulfide_risk=rc.get("disulfide_risk"),
            )
            for i, rc in enumerate(raw_candidates)
        ]

        return EpitopeScanRunResponse(
            scan_id=scan_id,
            project_id=request.project_id,
            target_protein_id=request.target_protein_id,
            status="COMPLETED",
            candidate_count=len(top_candidates),
            top_candidates=top_candidates,
            error_message=None,
        )

    except StampException as exc:
        # Re-raise StampExceptions as-is (they're expected validation errors)
        # But still mark the scan as FAILED
        scan_failed = mark_epitope_scan_failed(db, scan_id, exc.detail)
        if scan_failed:
            db.commit()
        raise
    except Exception as exc:
        # --- Mark FAILED on any unexpected error ---
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        logger.exception("Scan %s failed: %s", scan_id, error_msg)
        mark_epitope_scan_failed(db, scan_id, error_msg)
        raise StampException(
            status_code=500,
            detail=f"Epitope scan failed: {error_msg}",
            error_code="EPITOPE_SCAN_FAILED",
        ) from exc
