"""Batch compute runner for ColabFold / FoldX / MMGBSA / FlexPepDock.

v1.5-md-computation-pilot

This module provides the task management framework. For FLEXPEPDOCK,
real docking execution is performed synchronously in dispatch_batch_item.
Other job types defer execution to server-side runners or local subprocesses.

Scientific boundaries:
- No fabricated metrics (pLDDT, ipTM, RMSD, RMSF, ΔG, MM-GBSA, docking_score).
- SUCCEEDED only when real output files exist and parse successfully.
- BLOCKED when command/env missing.
- FAILED when input files missing or command returns non-zero.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.orm import BatchComputationItem
from app.services.batch_dir_service import ensure_item_dir, get_item_log_path

logger = logging.getLogger("stamp")

VALID_JOB_TYPES = {"COLABFOLD", "FOLDX", "MMGBSA", "FLEXPEPDOCK"}


def validate_job_params(job_type: str, input_json: dict) -> tuple[bool, Optional[str]]:
    """Validate job parameters before dispatch.

    Returns:
        (ok, error_message)
    """
    if job_type not in VALID_JOB_TYPES:
        return False, f"job_type must be one of {sorted(VALID_JOB_TYPES)}"

    if job_type == "FLEXPEPDOCK":
        receptor_pdb = input_json.get("receptor_pdb")
        if not receptor_pdb:
            return False, "receptor_pdb is required for FLEXPEPDOCK"
        if not Path(receptor_pdb).exists():
            return False, f"receptor_pdb not found: {receptor_pdb}"
        peptide_pdb = input_json.get("peptide_pdb")
        peptide_fasta = input_json.get("peptide_fasta")
        if not peptide_pdb and not peptide_fasta:
            return False, "Either peptide_pdb or peptide_fasta is required for FLEXPEPDOCK"
        return True, None

    sequence = input_json.get("sequence")
    if not sequence or len(sequence) < 5:
        return False, "sequence must be at least 5 residues"

    return True, None


def check_command_available(command: str) -> bool:
    """Check if a system command is available."""
    return shutil.which(command) is not None


def check_input_files(input_paths: list[str]) -> tuple[bool, Optional[str]]:
    """Check if all required input files exist.

    Returns:
        (ok, missing_file)
    """
    for p in input_paths:
        if not Path(p).exists():
            return False, p
    return True, None


def dispatch_batch_item(
    db: Session,
    item: BatchComputationItem,
) -> BatchComputationItem:
    """Dispatch a single batch item.

    State machine:
        PENDING -> validate params -> check command -> check inputs -> RUNNING -> execute -> SUCCEEDED/FAILED
        If command missing -> BLOCKED
        If inputs missing -> FAILED
        If validation fails -> FAILED (or 422 at API layer)
    """
    # 1. Validate params
    ok, err = validate_job_params(item.job_type, item.input_json or {})
    if not ok:
        item.status = "FAILED"
        item.error_message = err
        item.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(item)
        return item

    # 2. Ensure directory and logs
    ensure_item_dir(item.batch_id, item.id, item.job_type)
    from app.services.runner_logger import ensure_log_dir
    ensure_log_dir(item.batch_id, item.id, item.job_type)

    # 3. Check command / environment availability
    if item.job_type == "FLEXPEPDOCK":
        from app.services.flexpepdock_environment_probe import ROSETTA_ENV_SCRIPT
        if not Path(ROSETTA_ENV_SCRIPT).exists():
            item.status = "BLOCKED"
            item.error_message = (
                f"Rosetta env script not found: {ROSETTA_ENV_SCRIPT}. "
                "Source or install Rosetta."
            )
            item.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(item)
            logger.warning("Batch item %s BLOCKED: Rosetta env missing", item.id)
            return item
    else:
        command_map = {
            "COLABFOLD": "colabfold_batch",
            "FOLDX": "foldx",
            "MMGBSA": "gmx_MMPBSA",
        }
        cmd = command_map.get(item.job_type)
        if cmd and not check_command_available(cmd):
            item.status = "BLOCKED"
            item.error_message = (
                f"Command '{cmd}' not found in PATH. Install required software."
            )
            item.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(item)
            logger.warning("Batch item %s BLOCKED: command %s missing", item.id, cmd)
            return item

    # 4. Check input files
    input_paths = item.input_json.get("input_paths", []) if item.input_json else []
    ok, missing = check_input_files(input_paths)
    if not ok:
        item.status = "FAILED"
        item.error_message = f"Missing input file: {missing}"
        item.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(item)
        logger.warning("Batch item %s FAILED: missing input %s", item.id, missing)
        return item

    # 5. Execute (FLEXPEPDOCK runs real docking in P2; others remain deferred)
    if item.job_type == "FLEXPEPDOCK":
        from app.services.flexpepdock_runner import run_single_docking

        item.status = "RUNNING"
        item.started_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(item)
        logger.info("Batch item %s marked RUNNING (FlexPepDock real execution)", item.id)

        status, error, output = run_single_docking(
            str(item.batch_id),
            str(item.id),
            item.input_json or {},
        )

        if status == "SUCCEEDED":
            item = finalize_batch_item(db, item, success=True, output_json=output)
        elif status == "FAILED":
            item.status = "FAILED"
            item.error_message = error or "FlexPepDock execution failed"
            item.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(item)
        elif status == "BLOCKED":
            item.status = "BLOCKED"
            item.error_message = error or "FlexPepDock blocked"
            item.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(item)

        logger.info(
            "Batch item %s finished with status=%s (job_type=%s)",
            item.id, item.status, item.job_type,
        )
        return item

    # 5b. Non-FLEXPEPDOCK jobs: mark RUNNING (execution deferred)
    item.status = "RUNNING"
    item.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    logger.info("Batch item %s marked RUNNING (job_type=%s, execution deferred)", item.id, item.job_type)
    return item


def finalize_batch_item(
    db: Session,
    item: BatchComputationItem,
    *,
    success: bool,
    output_json: Optional[dict] = None,
    error_message: Optional[str] = None,
) -> BatchComputationItem:
    """Finalize a batch item after attempted execution.

    Guards:
        - If success=True but no real output files -> downgrade to FAILED.
        - Never write fabricated metrics.
    """
    if success:
        # Verify real artifacts exist before marking SUCCEEDED
        artifact_dir = Path(item.artifact_dir) if item.artifact_dir else None
        has_artifacts = False
        if artifact_dir and artifact_dir.exists():
            has_artifacts = any(artifact_dir.iterdir())

        if not has_artifacts:
            item.status = "FAILED"
            item.error_message = "No real artifacts found in output directory."
            item.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(item)
            logger.warning("Batch item %s FAILED: artifact directory empty", item.id)
            return item

        item.status = "SUCCEEDED"
        item.output_json = output_json or {}
    else:
        item.status = "FAILED"
        item.error_message = error_message or "Unknown failure"

    item.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


def compute_batch_status_from_items(items: list[BatchComputationItem]) -> str:
    """Derive an aggregate batch status from a list of item statuses.

    Minimal helper introduced to satisfy ``test_flexpepdock_batch.py``
    without changing the existing dispatch/finalize logic. Status precedence:
    RUNNING > PENDING > terminal states.
    """
    if not items:
        return "PENDING"

    statuses = {getattr(item, "status", None) for item in items}
    statuses.discard(None)

    if "RUNNING" in statuses:
        return "RUNNING"
    if statuses == {"SUCCEEDED"}:
        return "SUCCEEDED"
    if statuses <= {"FAILED", "BLOCKED"}:
        return "FAILED"
    if statuses == {"PENDING"}:
        return "PENDING"
    return "PARTIAL"
