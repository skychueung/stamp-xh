"""STAMP Platform — Complex Batch Queue (v0.10-P6l).

Top-N candidate selection, batch FASTA generation, manifest creation,
and batch interface_quality import for complex structure prediction.

Flow:
  1. Select top N stamp_candidates by composite_score.
  2. Generate ColabFold-compatible FASTA for each (target + peptide).
  3. Build batch manifest JSON.
  4. (Server-side) Run ColabFold batch.
  5. Parse batch outputs.
  6. Run interface parser + pDockQ calculator + persist for each.

Current stage: BATCH_COMPLEX_PREDICTION_QUEUE.
NO FoldX, NO FlexPepDock, NO delta_G, NO docking_score.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.crud.projects import get_project
from app.crud.stamp_candidates import (
    get_stamp_candidate,
    list_stamp_candidates_by_project,
    update_stamp_candidate,
)
from app.models.orm import TargetProtein
from app.schemas import StampCandidateUpdate
from app.services.complex_interface_parser import parse_complex_interface
from app.services.complex_prediction_input import build_multimer_fasta
from app.services.pdockq_calculator import PDockQError, build_interface_quality

logger = logging.getLogger(__name__)

REQUIRED_VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
REQUIRED_PREDICTION_STATUS = "COMPUTATIONAL_COMPLEX_BATCH_PREDICTION_INPUT_ONLY"


class ComplexBatchError(ValueError):
    """Raised when batch queue preparation or import fails."""

    pass


# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------


def select_top_candidates_for_complex_batch(
    db: Session,
    project_id: str,
    *,
    top_n: int = 3,
    target_sequence: str | None = None,
) -> dict[str, Any]:
    """Select top N stamp candidates for complex batch prediction.

    Args:
        db: Database session.
        project_id: Project ID.
        top_n: Number of candidates to select.
        target_sequence: Optional target protein sequence. If not provided,
            the first target protein of the project is used.

    Returns:
        Dict with keys: project_id, target_sequence, candidates (list).
        Each candidate dict has: candidate_id, rank, peptide_sequence,
        composite_score, full_sequence, candidate_name.

    Raises:
        ComplexBatchError: If project not found, no candidates, or
            target sequence cannot be resolved.
    """
    project = get_project(db, project_id)
    if project is None:
        raise ComplexBatchError(f"Project '{project_id}' not found")

    # Resolve target sequence
    resolved_target = target_sequence
    if not resolved_target:
        # Get first target protein for the project
        first_target = (
            db.query(TargetProtein)
            .filter(TargetProtein.project_id == project_id)
            .first()
        )
        if first_target:
            resolved_target = first_target.sequence

    if not resolved_target:
        raise ComplexBatchError(
            f"No target_sequence provided and project '{project_id}' has no target proteins"
        )

    # Fetch all candidates for the project, sorted by composite_score DESC
    all_candidates = list_stamp_candidates_by_project(db, project_id, limit=1000)
    if not all_candidates:
        raise ComplexBatchError(f"Project '{project_id}' has no stamp candidates")

    # Sort by composite_score descending (None scores go to the end)
    scored = [(c, c.composite_score if c.composite_score is not None else float("-inf")) for c in all_candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    top_candidates = scored[:top_n]

    candidates_list = []
    for rank, (cand, score) in enumerate(top_candidates, start=1):
        candidates_list.append({
            "candidate_id": cand.id,
            "rank": rank,
            "peptide_sequence": cand.targeting_peptide_seq,
            "composite_score": score if score != float("-inf") else None,
            "full_sequence": cand.full_sequence,
            "candidate_name": f"candidate_{cand.id[:8]}",
        })

    return {
        "project_id": project_id,
        "target_sequence": resolved_target,
        "top_n": len(candidates_list),
        "candidates": candidates_list,
    }


# ---------------------------------------------------------------------------
# Batch FASTA generation
# ---------------------------------------------------------------------------


def prepare_batch_fastas(
    candidates: list[dict[str, Any]],
    target_sequence: str,
    output_dir: str,
) -> list[dict[str, Any]]:
    """Generate ColabFold-compatible FASTA files for each candidate.

    Args:
        candidates: List of candidate dicts from select_top_candidates_for_complex_batch.
        target_sequence: Target protein sequence.
        output_dir: Directory to write FASTA files.

    Returns:
        List of candidate dicts enriched with 'fasta_file' and 'fasta_path'.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for cand in candidates:
        peptide_seq = cand["peptide_sequence"]
        fasta_filename = f"candidate_{cand['candidate_id']}_complex.fasta"
        fasta_path = out_dir / fasta_filename

        fasta_content = build_multimer_fasta(
            target_sequence=target_sequence,
            peptide_sequence=peptide_seq,
            target_chain_id="A",
            peptide_chain_id="B",
            target_name="target",
            peptide_name=cand["candidate_name"],
        )

        fasta_path.write_text(fasta_content, encoding="utf-8")

        results.append({
            **cand,
            "fasta_file": fasta_filename,
            "fasta_path": str(fasta_path),
        })

    return results


# ---------------------------------------------------------------------------
# Batch manifest
# ---------------------------------------------------------------------------


def build_batch_manifest(
    project_id: str,
    candidates: list[dict[str, Any]],
    target_sequence: str,
    fasta_dir: str,
    top_n: int,
) -> dict[str, Any]:
    """Build a batch manifest describing the complex prediction batch.

    Args:
        project_id: Project ID.
        candidates: Enriched candidate list (with fasta_file).
        target_sequence: Target protein sequence.
        fasta_dir: Directory containing FASTA files.
        top_n: Number of candidates in batch.

    Returns:
        Manifest dict.
    """
    manifest_candidates = []
    for cand in candidates:
        manifest_candidates.append({
            "candidate_id": cand["candidate_id"],
            "rank": cand["rank"],
            "fasta_file": cand["fasta_file"],
            "target_chain_id": "A",
            "peptide_chain_id": "B",
            "sequence_format": "colabfold_colon_separated_complex",
            "peptide_sequence": cand["peptide_sequence"],
            "forbidden_metrics": {
                "delta_G": None,
                "docking_score": None,
            },
        })

    return {
        "batch_id": f"p6l_project_{project_id}_top{top_n}",
        "project_id": project_id,
        "top_n": top_n,
        "stage": "complex_batch_input_preparation",
        "prediction_status": REQUIRED_PREDICTION_STATUS,
        "validation_status": REQUIRED_VALIDATION_STATUS,
        "metrics_are_real": False,
        "target_sequence_length": len(target_sequence),
        "candidates": manifest_candidates,
        "forbidden_metrics": {
            "delta_G": None,
            "docking_score": None,
        },
    }


# ---------------------------------------------------------------------------
# Batch output parsing
# ---------------------------------------------------------------------------


def parse_batch_outputs(
    batch_output_dir: str,
) -> list[dict[str, Any]]:
    """Parse all ColabFold complex outputs in a batch output directory.

    Expects directory structure:
        batch_output_dir/
          candidate_<id>/
            ...ColabFold output files...

    Args:
        batch_output_dir: Root directory containing per-candidate subdirs.

    Returns:
        List of parse results, one per candidate subdir found.
    """
    from app.services.complex_prediction_parser import parse_complex_output

    out_dir = Path(batch_output_dir)
    if not out_dir.exists():
        raise ComplexBatchError(f"Batch output directory not found: {batch_output_dir}")

    results = []
    for subdir in sorted(out_dir.iterdir()):
        if not subdir.is_dir():
            continue
        candidate_id = subdir.name
        try:
            report = parse_complex_output(str(subdir))
            results.append({
                "candidate_id": candidate_id,
                "success": True,
                "report": report,
            })
        except Exception as exc:
            logger.warning("Failed to parse output for %s: %s", candidate_id, exc)
            results.append({
                "candidate_id": candidate_id,
                "success": False,
                "error": str(exc),
            })

    return results


# ---------------------------------------------------------------------------
# Batch interface_quality import
# ---------------------------------------------------------------------------


def import_batch_interface_quality(
    db: Session,
    batch_output_dir: str,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Import interface_quality for all candidates in a batch output directory.

    For each candidate with valid complex output:
      1. Parse PDB with complex_interface_parser (P6i).
      2. Compute pDockQ with pdockq_calculator (P6j).
      3. Persist to stamp_candidate.metrics['interface_quality'].

    Args:
        db: Database session.
        batch_output_dir: Root directory with per-candidate ColabFold outputs.
        overwrite: If True, overwrite existing interface_quality; if False, skip.

    Returns:
        Summary dict with success_count, fail_count, skipped_count, details.
    """
    out_dir = Path(batch_output_dir)
    if not out_dir.exists():
        raise ComplexBatchError(f"Batch output directory not found: {batch_output_dir}")

    success_count = 0
    fail_count = 0
    skipped_count = 0
    details = []

    for subdir in sorted(out_dir.iterdir()):
        if not subdir.is_dir():
            continue
        candidate_id = subdir.name

        # Strip candidate_ prefix if present
        if candidate_id.startswith("candidate_"):
            candidate_id = candidate_id[len("candidate_"):]

        candidate = get_stamp_candidate(db, candidate_id)
        if candidate is None:
            logger.warning("Candidate '%s' not found in DB, skipping", candidate_id)
            details.append({
                "candidate_id": candidate_id,
                "status": "FAILED",
                "reason": "Candidate not found in DB",
            })
            fail_count += 1
            continue

        # Skip if already has interface_quality and overwrite=False
        existing_metrics = candidate.metrics or {}
        if not overwrite and "interface_quality" in existing_metrics:
            logger.info("Candidate '%s' already has interface_quality, skipping", candidate_id)
            details.append({
                "candidate_id": candidate_id,
                "status": "SKIPPED",
                "reason": "interface_quality already exists",
            })
            skipped_count += 1
            continue

        # Find PDB and PAE files
        pdb_files = list(subdir.glob("*_unrelaxed_*.pdb"))
        if not pdb_files:
            logger.warning("No PDB found for candidate '%s', skipping", candidate_id)
            details.append({
                "candidate_id": candidate_id,
                "status": "FAILED",
                "reason": "No PDB file found",
            })
            fail_count += 1
            continue

        pdb_path = str(pdb_files[0])

        pae_files = list(subdir.glob("*_predicted_aligned_error_*.json"))
        pae_path = str(pae_files[0]) if pae_files else None

        try:
            # Step 1: Parse interface (P6i)
            parser_result = parse_complex_interface(
                pdb_path,
                pae_json_path=pae_path,
            )

            if not parser_result.get("has_chain_A") or not parser_result.get("has_chain_B"):
                details.append({
                    "candidate_id": candidate_id,
                    "status": "FAILED",
                    "reason": "Missing chain A or chain B in PDB",
                })
                fail_count += 1
                continue

            # Step 2: Build interface quality with pDockQ (P6j)
            interface_quality = build_interface_quality(
                parser_result,
                input_complex_structure_file=pdb_path,
            )

            # Step 3: Validate no forbidden metrics leaked in
            forbidden = interface_quality.get("forbidden_metrics", {})
            if forbidden.get("delta_G") is not None or forbidden.get("docking_score") is not None:
                raise ValueError("Forbidden metrics contain non-null values")

            # Step 4: Persist
            updated_metrics = {**existing_metrics, "interface_quality": interface_quality}
            update_stamp_candidate(
                db,
                candidate,
                StampCandidateUpdate(metrics=updated_metrics),
            )

            success_count += 1
            details.append({
                "candidate_id": candidate_id,
                "status": "SUCCESS",
                "pdockq": interface_quality.get("pdockq"),
                "interface_contact_count": interface_quality.get("input_features", {}).get("interface_contact_count"),
            })

        except (PDockQError, ValueError, Exception) as exc:
            logger.warning("Failed to import interface_quality for %s: %s", candidate_id, exc)
            details.append({
                "candidate_id": candidate_id,
                "status": "FAILED",
                "reason": str(exc),
            })
            fail_count += 1

    return {
        "batch_output_dir": batch_output_dir,
        "success_count": success_count,
        "fail_count": fail_count,
        "skipped_count": skipped_count,
        "total": success_count + fail_count + skipped_count,
        "details": details,
    }
