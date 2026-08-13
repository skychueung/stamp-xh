"""STAMP Platform — STAMP Assembly Persistence Adapter (P5-lite P4).

Connects the heuristic final-ranking service to the database persistence layer.
Reads stamp candidates from a generation run, assembles full STAMP sequences
(targeting_peptide + linker + killing_peptide), computes biophysical properties,
runs final heuristic ranking, and updates the database.

Scientific-integrity rules:
  - NO fabricated experimental data (MIC, MBC, hemolysis, toxicity).
  - NO structural modelling metrics (ipTM, pDockQ, docking_score, delta_G).
  - metrics only gains keys "assembly" and "final_ranking"; existing keys preserved.
  - validation_status remains "NOT_EXPERIMENTALLY_VALIDATED".
  - Core stamp_assembler.py and final_ranking.py algorithms are NOT modified.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.crud.stamp_candidates import (
    get_stamp_generation_run,
    list_stamp_candidates_by_generation_run,
    update_stamp_candidates_bulk,
)
from app.models.orm import StampCandidate
from app.schemas import (
    StampAssemblyFailedCandidate,
    StampAssemblyRankedCandidate,
    StampAssemblyRunRequest,
    StampAssemblyRunResponse,
    StampCandidateUpdate,
)
from app.services.biophys import (
    calculate_gravy,
    calculate_net_charge,
    calculate_pi,
    count_cys,
)
from app.services.final_ranking import compute_final_ranking

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


def _safe_int(val: Any) -> Optional[int]:
    """Safely convert a value to int, returning None on failure."""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Core workflow
# ---------------------------------------------------------------------------


def run_stamp_assembly_and_persist(
    db: Session, request: StampAssemblyRunRequest
) -> StampAssemblyRunResponse:
    """Run STAMP assembly and final ranking for a generation run.

    Workflow:
      1. Validate generation_run_id exists.
      2. Validate project_id matches generation_run.project_id.
      3. Fetch all stamp candidates for this generation_run.
      4. For each candidate:
         - If force=False and already has assembly + ranking metrics, skip.
         - Assemble full_sequence = targeting_peptide_seq + linker_seq + killing_peptide_seq.
         - Compute biophysical properties.
         - Call final_ranking to get composite_score.
         - Update DB record.
      5. Return StampAssemblyRunResponse.

    Args:
        db: SQLAlchemy session.
        request: Assembly run request with project_id, generation_run_id, linker,
            killing peptide, and force flag.

    Returns:
        StampAssemblyRunResponse with counts and ranked/failed candidate lists.

    Raises:
        StampException: 404 if generation run not found, 400 if project mismatch.
    """
    from app.core.exceptions import StampException

    # --- 1. Validate generation run exists ---
    run = get_stamp_generation_run(db, request.generation_run_id)
    if run is None:
        raise StampException(
            status_code=404,
            detail=f"Generation run '{request.generation_run_id}' not found",
            error_code="GENERATION_RUN_NOT_FOUND",
        )

    # --- 2. Validate project_id matches ---
    if run.project_id != request.project_id:
        raise StampException(
            status_code=400,
            detail=(
                f"Project ID mismatch: generation run belongs to "
                f"project '{run.project_id}', not '{request.project_id}'"
            ),
            error_code="PROJECT_ID_MISMATCH",
        )

    # --- 3. Fetch candidates ---
    candidates = list_stamp_candidates_by_generation_run(
        db, request.generation_run_id, skip=0, limit=500
    )
    logger.info(
        "STAMP assembly run: fetched %d candidates for generation run %s",
        len(candidates),
        request.generation_run_id,
    )

    if not candidates:
        logger.info("No candidates found for generation run %s", request.generation_run_id)
        return StampAssemblyRunResponse(
            project_id=request.project_id,
            generation_run_id=request.generation_run_id,
            status="COMPLETED",
            processed_count=0,
            skipped_count=0,
            failed_count=0,
            ranked_candidates=[],
            failed_candidates=[],
            error_message=None,
        )

    # --- 4. Assemble and rank ---
    assembly_results: List[Dict[str, Any]] = []
    failed_candidates: List[StampAssemblyFailedCandidate] = []
    skipped_count = 0
    processed_count = 0

    db_updates: List[Tuple[StampCandidate, StampCandidateUpdate]] = []

    for candidate in candidates:
        try:
            # Idempotency check
            if not request.force and _is_already_processed(candidate):
                logger.debug("Candidate %s already processed; skipping", candidate.id)
                skipped_count += 1
                continue

            # Assemble single candidate
            assembly_result = _assemble_single_candidate(candidate, request)
            assembly_results.append(assembly_result)
            processed_count += 1
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {str(exc)}"
            logger.exception("Assembly failed for candidate %s: %s", candidate.id, error_msg)
            failed_candidates.append(
                StampAssemblyFailedCandidate(
                    candidate_id=candidate.id,
                    error_message=error_msg,
                )
            )

    # --- 5. Run final ranking on successfully assembled candidates ---
    ranked_list: List[StampAssemblyRankedCandidate] = []
    if assembly_results:
        try:
            ranking_response = _rank_candidates(assembly_results)
            ranked_raw = ranking_response.get("ranked_candidates", [])

            # Map ranking results back to DB update objects and response items
            for rank, rc in enumerate(ranked_raw[: request.top_k], start=1):
                candidate_id = rc["candidate_id"]
                composite_score = _safe_float(rc.get("composite_score"))
                full_sequence = rc.get("full_sequence", "")
                targeting_peptide_seq = rc.get("targeting_peptide", {}).get("sequence", "")

                # Find original candidate for DB update
                candidate = next(
                    (c for c in candidates if c.id == candidate_id), None
                )
                if candidate is None:
                    logger.warning(
                        "Ranked candidate %s not found in original candidate list; skipping DB update",
                        candidate_id,
                    )
                    continue

                # Build merged metrics
                merged_metrics = _merge_metrics(
                    candidate.metrics,
                    next(
                        (ar for ar in assembly_results if ar["candidate_id"] == candidate_id),
                        {},
                    ),
                    rc,
                )

                update_obj = StampCandidateUpdate(
                    full_sequence=full_sequence,
                    linker_seq=request.linker_seq,
                    composite_score=composite_score,
                    validation_status="NOT_EXPERIMENTALLY_VALIDATED",
                    metrics=merged_metrics,
                )
                db_updates.append((candidate, update_obj))

                ranked_list.append(
                    StampAssemblyRankedCandidate(
                        rank=rank,
                        candidate_id=candidate_id,
                        targeting_peptide_seq=targeting_peptide_seq,
                        full_sequence=full_sequence,
                        composite_score=composite_score,
                        validation_status="NOT_EXPERIMENTALLY_VALIDATED",
                    )
                )
        except Exception as exc:
            error_msg = f"Final ranking failed: {type(exc).__name__}: {str(exc)}"
            logger.exception("Final ranking failed for generation run %s", request.generation_run_id)
            # Mark all processed as failed since ranking could not complete
            for ar in assembly_results:
                failed_candidates.append(
                    StampAssemblyFailedCandidate(
                        candidate_id=ar["candidate_id"],
                        error_message=error_msg,
                    )
                )
            processed_count = 0
            ranked_list = []

    # --- 6. Persist updates ---
    if db_updates:
        try:
            update_stamp_candidates_bulk(db, db_updates)
            logger.info(
                "Persisted %d candidate updates for generation run %s",
                len(db_updates),
                request.generation_run_id,
            )
        except Exception as exc:
            error_msg = f"Bulk update failed: {type(exc).__name__}: {str(exc)}"
            logger.exception(error_msg)
            # Do not raise; record in response
            failed_candidates.extend(
                [
                    StampAssemblyFailedCandidate(
                        candidate_id=c.id,
                        error_message=error_msg,
                    )
                    for c, _ in db_updates
                ]
            )

    # --- 7. Determine status ---
    if failed_candidates and not ranked_list and processed_count == 0:
        status = "FAILED"
    elif failed_candidates:
        status = "COMPLETED_WITH_ERRORS"
    else:
        status = "COMPLETED"

    return StampAssemblyRunResponse(
        project_id=request.project_id,
        generation_run_id=request.generation_run_id,
        status=status,
        processed_count=processed_count,
        skipped_count=skipped_count,
        failed_count=len(failed_candidates),
        ranked_candidates=ranked_list,
        failed_candidates=failed_candidates,
        error_message=None if status != "FAILED" else (failed_candidates[0].error_message if failed_candidates else None),
    )


# ---------------------------------------------------------------------------
# Single-candidate assembly
# ---------------------------------------------------------------------------


def _assemble_single_candidate(
    candidate: StampCandidate, request: StampAssemblyRunRequest
) -> Dict[str, Any]:
    """Assemble a single STAMP candidate.

    Concatenates targeting_peptide_seq + linker_seq + killing_peptide_seq and
    computes biophysical properties using the biophys module.

    Args:
        candidate: StampCandidate ORM object from the database.
        request: StampAssemblyRunRequest containing linker and killing peptide.

    Returns:
        Assembly result dict suitable for _rank_candidates input.

    Raises:
        ValueError: If targeting_peptide_seq is empty or None.
    """
    tp_seq = (candidate.targeting_peptide_seq or "").upper().strip()
    linker_seq = (request.linker_seq or "").upper().strip()
    kp_seq = (request.killing_peptide_seq or "").upper().strip()

    if not tp_seq:
        raise ValueError(f"Candidate {candidate.id} has empty targeting_peptide_seq")
    if not linker_seq:
        raise ValueError("Request linker_seq is empty")
    if not kp_seq:
        raise ValueError("Request killing_peptide_seq is empty")

    full_sequence = tp_seq + linker_seq + kp_seq
    length = len(full_sequence)
    net_charge = calculate_net_charge(full_sequence)
    pi = calculate_pi(full_sequence)
    gravy = calculate_gravy(full_sequence)
    cys = count_cys(full_sequence)

    return {
        "candidate_id": candidate.id,
        "full_sequence": full_sequence,
        "targeting_peptide": {
            "name": candidate.id,
            "sequence": tp_seq,
            "length": len(tp_seq),
        },
        "linker": {
            "sequence": linker_seq,
            "length": len(linker_seq),
        },
        "amp": {
            "name": "killing_peptide",
            "sequence": kp_seq,
            "length": len(kp_seq),
        },
        "length": length,
        "net_charge": net_charge,
        "pI": pi,
        "GRAVY": gravy,
        "cys_count": cys,
        "mode": "REAL_STAMP_ASSEMBLY_V0_7",
        "created_at": None,
    }


# ---------------------------------------------------------------------------
# Ranking adapter
# ---------------------------------------------------------------------------


def _rank_candidates(
    assembly_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Rank assembled candidates using final_ranking.

    Constructs the exact dict shape expected by compute_final_ranking and
    delegates scoring to it.

    Args:
        assembly_results: List of assembly result dicts from _assemble_single_candidate.

    Returns:
        Dict returned by compute_final_ranking containing ranked_candidates.
    """
    return compute_final_ranking(assembly_results)


# ---------------------------------------------------------------------------
# Metrics merging
# ---------------------------------------------------------------------------


def _merge_metrics(
    existing: Optional[Dict[str, Any]],
    assembly_result: Dict[str, Any],
    ranking_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge metrics preserving existing content.

    Adds metrics["assembly"] and metrics["final_ranking"] while keeping all
    previously stored keys intact.

    Args:
        existing: Current metrics dict from the DB record (may be None).
        assembly_result: Dict returned by _assemble_single_candidate.
        ranking_result: Dict returned by compute_final_ranking (single candidate slice).

    Returns:
        New metrics dict with assembly and final_ranking keys added.
    """
    merged: Dict[str, Any] = dict(existing) if existing else {}

    # Assembly metrics: biophysical properties of the full assembled sequence
    merged["assembly"] = {
        "full_sequence": assembly_result.get("full_sequence"),
        "length": assembly_result.get("length"),
        "net_charge": assembly_result.get("net_charge"),
        "pI": assembly_result.get("pI"),
        "GRAVY": assembly_result.get("GRAVY"),
        "cys_count": assembly_result.get("cys_count"),
        "targeting_peptide_seq": assembly_result.get("targeting_peptide", {}).get("sequence"),
        "linker_seq": assembly_result.get("linker", {}).get("sequence"),
        "killing_peptide_seq": assembly_result.get("amp", {}).get("sequence"),
        "mode": assembly_result.get("mode", "REAL_STAMP_ASSEMBLY_V0_7"),
    }

    # Final ranking metrics: heuristic composite score and sub-scores if available
    merged["final_ranking"] = {
        "composite_score": ranking_result.get("composite_score"),
        "mode": ranking_result.get("mode", "HEURISTIC_FINAL_RANKING_V0_7"),
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
    }

    return merged


# ---------------------------------------------------------------------------
# Idempotency check
# ---------------------------------------------------------------------------


def _is_already_processed(candidate: StampCandidate) -> bool:
    """Check if candidate already has assembly and ranking metrics.

    Args:
        candidate: StampCandidate ORM object.

    Returns:
        True if metrics contains both 'assembly' and 'final_ranking' keys
        and the composite_score column is populated.
    """
    metrics = candidate.metrics or {}
    return (
        "assembly" in metrics
        and "final_ranking" in metrics
        and candidate.composite_score is not None
    )
