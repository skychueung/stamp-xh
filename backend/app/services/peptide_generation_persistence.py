"""STAMP Platform — Peptide Generation Persistence Adapter (P5-lite P3).

Connects the rule-based targeting peptide generator
(app.services.targeting_peptide_generator) to the database persistence layer.
Reads an epitope sequence from the DB, runs the generator, creates a
stamp_generation_runs record, persists all targeting peptide candidates to
stamp_candidates, and manages run lifecycle (PENDING -> RUNNING -> COMPLETED/FAILED).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.crud.stamp_candidates import (
    create_stamp_candidates_bulk,
    create_stamp_generation_run,
    mark_stamp_generation_run_completed,
    mark_stamp_generation_run_failed,
    mark_stamp_generation_run_running,
)
from app.models.orm import EpitopeCandidate, EpitopeScan
from app.models.targeting_peptide import SourceEpitope
from app.schemas import (
    PeptideGenerationRunRequest,
    PeptideGenerationRunResponse,
    StampCandidateCreate,
    StampCandidateResponse,
    StampGenerationRunCreate,
)
from app.services.targeting_peptide_generator import generate_targeting_peptides

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_float(val: Any) -> Optional[float]:
    """Safely convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_str(val: Any) -> Optional[str]:
    """Safely convert a value to str, returning None if input is None."""
    if val is None:
        return None
    return str(val)


def _safe_int(val: Any) -> Optional[int]:
    """Safely convert a value to int, returning None on failure."""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


def map_generated_peptide_to_stamp_candidate_create(
    generation_run_id: str,
    epitope_id: str,
    project_id: str,
    raw_candidate: dict[str, Any],
    linker_seq: str = "GGGGS",
) -> StampCandidateCreate:
    """Map a raw targeting peptide candidate to StampCandidateCreate.

    This function does NOT fabricate any experimental data:
      - validation_status is always NOT_EXPERIMENTALLY_VALIDATED
      - No MIC / MBC / hemolysis / toxicity / ipTM / pDockQ / ΔG / docking_score
      - All original generator metrics are preserved in the metrics JSON field

    Field mapping:
      - sequence -> targeting_peptide_seq
      - linker_seq -> linker_seq (from request)
      - full_sequence -> targeting_peptide_seq + linker_seq (if no full_sequence)
      - ranking_score -> composite_score (falls back to 'score')
    """
    # Build metrics dict from raw fields, preserving everything for traceability
    metrics = dict(raw_candidate)

    targeting_seq = _safe_str(raw_candidate.get("sequence")) or ""
    # Assemble full_sequence safely
    full_sequence = targeting_seq + linker_seq

    # Map ranking_score -> composite_score
    composite_score = _safe_float(
        raw_candidate.get("ranking_score", raw_candidate.get("score"))
    )

    return StampCandidateCreate(
        project_id=project_id,
        epitope_id=epitope_id,
        generation_run_id=generation_run_id,
        targeting_peptide_seq=targeting_seq,
        linker_seq=linker_seq,
        full_sequence=full_sequence,
        composite_score=composite_score,
        validation_status="NOT_EXPERIMENTALLY_VALIDATED",
        metrics=metrics if metrics else {},
    )


# ---------------------------------------------------------------------------
# Core workflow
# ---------------------------------------------------------------------------


def run_peptide_generation_and_persist(
    db: Session, request: PeptideGenerationRunRequest
) -> PeptideGenerationRunResponse:
    """Run targeting peptide generation against a DB epitope and persist results.

    Workflow:
      1. Validate epitope_id exists
      2. Validate project_id matches epitope's scan.project_id
      3. Create stamp_generation_runs record (status=PENDING)
      4. Mark RUNNING
      5. Call generate_targeting_peptides() with epitope sequence
      6. Map candidates to StampCandidateCreate and bulk insert
      7. Mark COMPLETED
      8. Return PeptideGenerationRunResponse

    On any error: mark FAILED, re-raise as StampException.

    Args:
        db: SQLAlchemy session.
        request: Peptide generation run request with project_id, epitope_id, params.

    Returns:
        PeptideGenerationRunResponse with generation_run_id, status, candidates.

    Raises:
        StampException: 404 if epitope not found, 400 if project mismatch,
                        500 for generation computation errors.
    """
    from app.core.exceptions import StampException

    # --- 1. Validate epitope exists ---
    epitope = db.query(EpitopeCandidate).filter(EpitopeCandidate.id == request.epitope_id).first()
    if epitope is None:
        raise StampException(
            status_code=404,
            detail=f"Epitope '{request.epitope_id}' not found",
            error_code="EPITOPE_NOT_FOUND",
        )

    # --- 2. Validate project_id matches the epitope's scan project ---
    scan = db.query(EpitopeScan).filter(EpitopeScan.id == epitope.scan_id).first()
    if scan is None or scan.project_id != request.project_id:
        raise StampException(
            status_code=400,
            detail=(
                f"Project ID mismatch: epitope belongs to "
                f"project '{scan.project_id if scan else 'unknown'}', not '{request.project_id}'"
            ),
            error_code="PROJECT_ID_MISMATCH",
        )

    # --- 3. Create generation run record ---
    run_in = StampGenerationRunCreate(
        project_id=request.project_id,
        epitope_id=request.epitope_id,
        generator_name=request.generator_name,
        generator_version=request.generator_version,
        parameters={
            "top_k": request.top_k,
            "linker_seq": request.linker_seq,
            **(request.parameters or {}),
        },
        status="PENDING",
    )
    run = create_stamp_generation_run(db, run_in)
    run_id = run.id
    logger.info(
        "Created peptide generation run %s for epitope %s", run_id, request.epitope_id
    )

    try:
        # --- 4. Mark RUNNING ---
        mark_stamp_generation_run_running(db, run_id)
        logger.info("Generation run %s marked RUNNING", run_id)

        # --- 5. Build source epitope and run generator ---
        source_epitope = SourceEpitope(
            candidate_id=epitope.id,
            sequence=epitope.sequence,
            start=getattr(epitope, "start", 1),
            end=getattr(epitope, "end", len(epitope.sequence)),
            target_name=getattr(scan, "target_name", "Unknown"),
            species=getattr(scan, "species", "Unknown"),
        )

        generation_result = generate_targeting_peptides(
            source_epitope=source_epitope,
            requested_count=request.top_k,
        )

        raw_candidates = generation_result.get("candidates", [])
        logger.info(
            "Generation run %s completed with %d candidates", run_id, len(raw_candidates)
        )

        # --- 6. Map and persist candidates ---
        if raw_candidates:
            candidate_creates = [
                map_generated_peptide_to_stamp_candidate_create(
                    generation_run_id=run_id,
                    epitope_id=request.epitope_id,
                    project_id=request.project_id,
                    raw_candidate=rc,
                    linker_seq=request.linker_seq,
                )
                for rc in raw_candidates
            ]
            create_stamp_candidates_bulk(db, candidate_creates)
            logger.info(
                "Persisted %d stamp candidates for run %s", len(candidate_creates), run_id
            )

        # --- 7. Mark COMPLETED ---
        mark_stamp_generation_run_completed(db, run_id)

        # Build response candidates (top_k only; generator already returns top_k)
        persisted = []
        if raw_candidates:
            # Query back from DB to get IDs and timestamps
            from app.crud.stamp_candidates import list_stamp_candidates_by_generation_run

            db_candidates = list_stamp_candidates_by_generation_run(db, run_id)
            persisted = [
                StampCandidateResponse(
                    id=c.id,
                    project_id=c.project_id,
                    epitope_id=c.epitope_id,
                    generation_run_id=c.generation_run_id,
                    targeting_peptide_seq=c.targeting_peptide_seq,
                    linker_seq=c.linker_seq,
                    full_sequence=c.full_sequence,
                    composite_score=c.composite_score,
                    validation_status=c.validation_status,
                    metrics=c.metrics,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                )
                for c in db_candidates
            ]

        return PeptideGenerationRunResponse(
            generation_run_id=run_id,
            project_id=request.project_id,
            epitope_id=request.epitope_id,
            status="COMPLETED",
            candidate_count=len(persisted),
            top_candidates=persisted,
            error_message=None,
        )

    except StampException as exc:
        # Re-raise StampExceptions as-is (expected validation errors)
        # But still mark the run as FAILED
        mark_stamp_generation_run_failed(db, run_id, exc.detail)
        raise
    except Exception as exc:
        # --- Mark FAILED on any unexpected error ---
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        logger.exception("Generation run %s failed: %s", run_id, error_msg)
        mark_stamp_generation_run_failed(db, run_id, error_msg)
        raise StampException(
            status_code=500,
            detail=f"Peptide generation failed: {error_msg}",
            error_code="PEPTIDE_GENERATION_FAILED",
        ) from exc
