"""
STAMP Platform — Pipeline Orchestrator Service (v1.6 P0)

Automates the front-half pipeline:
  TargetProtein → EpitopeScreening → PeptideGeneration → PeptideOptimization
  → STAMP Assembly → Batch Draft

Rules:
- Every step writes to DB and artifact files.
- No fabricated structure metrics (pLDDT, ipTM, RMSD, RMSF, Rg, ΔG).
- No fake AI generation — baseline methods are explicitly labeled.
- SUCCEEDED only when real records/files exist.
- BLOCKED when dependencies missing.
"""

from __future__ import annotations

import json
import logging
import os
import traceback
import threading
import zipfile
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import InvalidSequenceError
from app.models.orm import (
    BatchComputation,
    BatchComputationItem,
    EpitopeCandidate,
    EpitopeScan,
    PipelineRun,
    PipelineStep,
    StampCandidate,
    StampGenerationRun,
    TargetProtein,
)
from app.services.biophys import (
    calculate_pi,
)
from app.services.sequence_validator import (
    compute_gravy,
    compute_net_charge,
    validate_sequence,
)
from app.services.pipeline_artifacts import (
    initialize_run_artifacts,
    mark_manifest_status,
    reset_step_state,
    run_root,
    sequence_sha256,
    update_step_state,
)

logger = logging.getLogger("stamp")

_pipeline_log_lock = threading.Lock()

VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")
LINKER_LIBRARY = ["GGGGS", "EAAAKEAAAK", "RKRR", "AAY", "GSG"]

STEP_ORDER = [
    "TARGET_INPUT",
    "EPITOPE_SCREENING",
    "PEPTIDE_GENERATION",
    "PEPTIDE_OPTIMIZATION",
    "STAMP_ASSEMBLY",
    "STRUCTURE_VALIDATION_READY",
    "FINAL_RANKING",
    "REPORT_EXPORT",
]

STEP_METHODS: dict[str, str] = {
    "TARGET_INPUT": "sequence_validation_and_summary_v1",
    "EPITOPE_SCREENING": "sequence_sliding_window_heuristic_v1",
    "PEPTIDE_GENERATION": "deterministic_targeting_peptide_baseline_v1",
    "PEPTIDE_OPTIMIZATION": "sequence_physicochemical_filter_v1",
    "STAMP_ASSEMBLY": "rule_based_stamp_assembly_v1",
    "STRUCTURE_VALIDATION_READY": "structure_validation_readiness_v1",
    "FINAL_RANKING": "rule_based_sequence_level_final_ranking_v1",
    "REPORT_EXPORT": "pipeline_report_export_v1",
}

STEP_BOUNDARIES: dict[str, str] = {
    "TARGET_INPUT": "Sequence validation only; no structural prediction.",
    "EPITOPE_SCREENING": "Computational sequence-level epitope prioritization only; not experimentally validated.",
    "PEPTIDE_GENERATION": "Deterministic baseline generation; not deep learning unless explicitly labeled.",
    "PEPTIDE_OPTIMIZATION": "Sequence physicochemical filters; not experimental toxicity/activity predictions.",
    "STAMP_ASSEMBLY": "Rule-based concatenation; no experimental validation of assembled construct.",
    "STRUCTURE_VALIDATION_READY": "Candidates are ready for downstream structure prediction and docking. No structural modelling metrics are claimed at this stage.",
    "FINAL_RANKING": "Sequence-level computational prioritization only. Not experimentally validated. No structural score, MD metric, or binding free energy is claimed in this stage.",
    "REPORT_EXPORT": "Pipeline summary export. All metrics are sequence-level computational estimates.",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _artifact_dir(run_id: str) -> str:
    return str(run_root(run_id))


def _step_dir(run_id: str, step_name: str) -> str:
    # Keep legacy step paths readable while all new state lives below steps/.
    path = os.path.join(_artifact_dir(run_id), "steps", step_name.lower(), "artifacts")
    os.makedirs(path, exist_ok=True)
    return path


def _pipeline_log_path(run_id: str) -> str:
    """Return the durable, per-run execution log path."""
    return os.path.join(_artifact_dir(run_id), "logs.jsonl")


def _append_pipeline_log(
    run_id: str,
    level: str,
    message: str,
    *,
    step: str | None = None,
    model_id: str | None = None,
    request_id: str | None = None,
    exception_trace: str | None = None,
) -> None:
    """Append one structured line to the run log without breaking execution."""
    record = {
        "timestamp": _utc_now().isoformat(),
        "level": level.upper(),
        "run_id": run_id,
        "step": step,
        "model_id": model_id,
        "request_id": request_id or run_id,
        "message": message,
        "exception_trace": exception_trace,
    }
    try:
        with _pipeline_log_lock:
            with open(_pipeline_log_path(run_id), "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        logger.exception("Failed to write pipeline log for run %s", run_id)


def read_pipeline_log(run_id: str, tail: int = 500) -> list[dict[str, Any]]:
    """Read the newest structured execution log records for a pipeline run."""
    path = _pipeline_log_path(run_id)
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()
    records: list[dict[str, Any]] = []
    for line in lines[-max(1, tail):]:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            records.append({"timestamp": None, "level": "INFO", "run_id": run_id, "step": None, "message": line})
    return records


def _write_json(path: str, data: dict | list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def _write_csv(path: str, headers: list[str], rows: list[list[Any]]) -> None:
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def _update_step(
    step: PipelineStep,
    status: str,
    output_json: dict | None = None,
    error_message: str | None = None,
) -> None:
    previous_started_at = step.started_at
    attempt_data = dict(step.input_json or {})
    if status == "RUNNING" and previous_started_at is None:
        attempt_data["attempt"] = int(attempt_data.get("attempt", 0)) + 1
        step.input_json = attempt_data
    step.status = status
    if status == "RUNNING" and step.started_at is None:
        step.started_at = _utc_now()
    if status in ("SUCCEEDED", "FAILED", "BLOCKED"):
        step.finished_at = _utc_now()
    if output_json is not None:
        step.output_json = output_json
    if error_message is not None:
        step.error_message = error_message
    update_step_state(
        step.pipeline_run_id,
        step.step_name,
        status,
        attempt=int(attempt_data.get("attempt", 0)),
        input_hash=str(attempt_data.get("input_hash", "")),
        error=error_message,
        artifacts=(output_json or {}).get("artifact_files") if output_json else None,
        started_at=step.started_at.isoformat() if step.started_at else None,
        finished_at=step.finished_at.isoformat() if step.finished_at else None,
    )


def _update_run(
    run: PipelineRun,
    status: str | None = None,
    current_step: str | None = None,
    output_json: dict | None = None,
    error_message: str | None = None,
) -> None:
    if status is not None:
        run.status = status
    if current_step is not None:
        run.current_step = current_step
    if output_json is not None:
        run.output_json = output_json
    if error_message is not None:
        run.error_message = error_message
    run.updated_at = _utc_now()


def create_pipeline_run(
    db: Session,
    project_id: str | None,
    target_name: str,
    target_sequence: str,
    created_by: str | None = None,
) -> PipelineRun:
    """Create a new PipelineRun with all steps initialized to PENDING."""
    run = PipelineRun(
        project_id=project_id,
        target_name=target_name,
        target_sequence=target_sequence.upper().strip(),
        status="PENDING",
        current_step="TARGET_INPUT",
        created_by=created_by,
    )
    db.add(run)
    db.flush()

    input_hash = sequence_sha256(run.target_sequence)
    initialize_run_artifacts(
        run.id,
        target_name=run.target_name,
        target_sequence=run.target_sequence,
        project_id=run.project_id,
        created_by=created_by,
    )

    for i, step_name in enumerate(STEP_ORDER):
        step = PipelineStep(
            pipeline_run_id=run.id,
            step_name=step_name,
            step_order=i,
            status="PENDING",
            method=STEP_METHODS.get(step_name),
            scientific_boundary_note=STEP_BOUNDARIES.get(step_name),
            input_json={"input_hash": input_hash, "attempt": 0},
        )
        db.add(step)

    db.commit()
    db.refresh(run)
    return run


def get_pipeline_status(db: Session, run_id: str) -> dict[str, Any]:
    """Get full pipeline status with step details."""
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise ValueError(f"PipelineRun {run_id} not found")

    steps = (
        db.query(PipelineStep)
        .filter(PipelineStep.pipeline_run_id == run_id)
        .order_by(PipelineStep.step_order)
        .all()
    )

    def _fmt(dt: datetime | None) -> str | None:
        return dt.isoformat() if dt else None

    return {
        "run_id": run.id,
        "target_name": run.target_name,
        "status": run.status,
        "current_step": run.current_step,
        "error_message": run.error_message,
        "created_at": _fmt(run.created_at),
        "updated_at": _fmt(run.updated_at),
        "steps": [
            {
                "step_name": s.step_name,
                "status": s.status,
                "started_at": _fmt(s.started_at),
                "finished_at": _fmt(s.finished_at),
                "method": s.method,
                "output_summary": _step_output_summary(s),
            }
            for s in steps
        ],
    }


def _step_output_summary(step: PipelineStep) -> dict[str, Any]:
    out = step.output_json or {}
    summary: dict[str, Any] = {}
    if "record_count" in out:
        summary["record_count"] = out["record_count"]
    if "artifact_files" in out:
        summary["artifact_files"] = out["artifact_files"]
    if "top_candidate_count" in out:
        summary["top_candidate_count"] = out["top_candidate_count"]
    # Expose full arrays for frontend result tables
    for key in ("candidates", "peptides", "optimized_peptides", "stamp_candidates", "batch_items", "target_protein", "final_ranking", "manifest"):
        if key in out:
            summary[key] = out[key]
    return summary


def run_target_input_step(db: Session, run: PipelineRun) -> bool:
    """Validate sequence, compute summary, create TargetProtein record."""
    step = _get_step(db, run.id, "TARGET_INPUT")
    _update_step(step, "RUNNING")
    db.commit()

    seq = run.target_sequence.strip().upper()
    try:
        cleaned = validate_sequence(seq)
    except InvalidSequenceError as exc:
        _update_step(step, "FAILED", error_message=str(exc))
        _update_run(run, status="FAILED", error_message=str(exc))
        db.commit()
        return False

    length = len(cleaned)
    aa_counts = {aa: cleaned.count(aa) for aa in VALID_AA if aa in cleaned}
    net_charge = compute_net_charge(cleaned)
    gravy = compute_gravy(cleaned)
    mw_approx = sum({
        "A": 89, "C": 121, "D": 133, "E": 147, "F": 165,
        "G": 75, "H": 155, "I": 131, "K": 146, "L": 131,
        "M": 149, "N": 132, "P": 115, "Q": 146, "R": 174,
        "S": 105, "T": 119, "V": 117, "W": 204, "Y": 181,
    }.get(aa, 110) for aa in cleaned)

    # Ensure a project exists (required by target_proteins NOT NULL constraint)
    project_id = run.project_id
    if project_id is None:
        from app.models.orm import Project
        proj = Project(name=f"Pipeline-{run.id[:8]}")
        db.add(proj)
        db.flush()
        project_id = proj.id
        run.project_id = project_id

    # Stable, idempotent target identity. A retry reuses the project target.
    stable_hash = sequence_sha256(cleaned)
    tp = db.query(TargetProtein).filter(
        TargetProtein.project_id == project_id,
        TargetProtein.sequence_hash == stable_hash,
    ).first()
    if tp is None:
        tp = TargetProtein(
            project_id=project_id,
            name=run.target_name,
            sequence=cleaned,
            sequence_hash=stable_hash,
            length=length,
            metadata_json={
                "aa_counts": aa_counts,
                "net_charge": round(net_charge, 2),
                "gravy": gravy,
                "mw_approx_da": mw_approx,
            },
        )
        db.add(tp)
        db.flush()

    artifact_dir = _step_dir(run.id, "TARGET_INPUT")
    summary = {
        "target_protein_id": tp.id,
        "sequence_length": length,
        "aa_composition": aa_counts,
        "net_charge": round(net_charge, 2),
        "gravy": gravy,
        "mw_approx_da": mw_approx,
        "method": STEP_METHODS["TARGET_INPUT"],
        "scientific_boundary_note": STEP_BOUNDARIES["TARGET_INPUT"],
    }
    _write_json(os.path.join(artifact_dir, "target_summary.json"), summary)

    _update_step(
        step,
        "SUCCEEDED",
        output_json={
            "target_protein_id": tp.id,
            "record_count": 1,
            "artifact_files": ["target_summary.json"],
        },
    )
    _update_run(run, current_step="EPITOPE_SCREENING")
    db.commit()
    return True


def run_epitope_screening_step(
    db: Session,
    run: PipelineRun,
    top_k: int = 20,
    window_sizes: list[int] | None = None,
) -> bool:
    """Sliding-window epitope screening baseline."""
    step = _get_step(db, run.id, "EPITOPE_SCREENING")
    _update_step(step, "RUNNING")
    db.commit()

    seq = run.target_sequence.strip().upper()
    windows = window_sizes or [9, 12, 15]

    candidates: list[dict[str, Any]] = []
    for wsize in windows:
        for start in range(0, len(seq) - wsize + 1):
            window = seq[start:start + wsize]
            if any(aa not in VALID_AA for aa in window):
                continue
            net_charge = compute_net_charge(window)
            gravy = compute_gravy(window)
            cys = window.count("C")
            aromatic = sum(window.count(aa) for aa in "FWY")
            basic = sum(window.count(aa) for aa in "KRH")
            acidic = sum(window.count(aa) for aa in "DE")

            # Instability proxy: too many proline or too charged
            instability = 0.0
            if window.count("P") > 2:
                instability += 0.3
            if abs(net_charge) > 4:
                instability += 0.2

            # Priority score (higher = better epitope candidate)
            priority = (
                0.25 * max(0, 1 - abs(net_charge) / 4)
                + 0.25 * max(0, 1 - abs(gravy))
                + 0.20 * (1 if cys == 0 else 0.5)
                + 0.15 * (aromatic / wsize)
                + 0.15 * max(0, 1 - instability)
            )

            candidates.append({
                "start": start,
                "end": start + wsize - 1,
                "sequence": window,
                "length": wsize,
                "net_charge": round(net_charge, 2),
                "hydrophobic_ratio": round((gravy + 4.5) / 9.0, 3),  # normalize roughly
                "aromatic_count": aromatic,
                "basic_count": basic,
                "acidic_count": acidic,
                "cys_count": cys,
                "instability_proxy": round(instability, 3),
                "conservation": "NOT_AVAILABLE",
                "surface_accessibility": "NOT_AVAILABLE",
                "priority_score": round(priority, 4),
            })

    if not candidates:
        _update_step(step, "FAILED", error_message="No valid epitope candidates found.")
        _update_run(run, status="FAILED")
        db.commit()
        return False

    candidates.sort(key=lambda x: x["priority_score"], reverse=True)
    top_candidates = candidates[:top_k]

    # Persist EpitopeScan
    scan = EpitopeScan(
        project_id=run.project_id,
        target_protein_id=_get_target_protein_id(db, run),
        algorithm="sequence_sliding_window_heuristic_v1",
        algorithm_version="1.0",
        status="COMPLETED",
        parameters={"window_sizes": windows, "top_k": top_k},
        started_at=_utc_now(),
        finished_at=_utc_now(),
    )
    db.add(scan)
    db.flush()

    # Persist EpitopeCandidate records
    for i, c in enumerate(top_candidates):
        ec = EpitopeCandidate(
            scan_id=scan.id,
            start=c["start"],
            end=c["end"],
            sequence=c["sequence"],
            net_charge=c["net_charge"],
            hydrophobicity=c["hydrophobic_ratio"],
            pi=calculate_pi(c["sequence"]) if hasattr(calculate_pi, '__call__') else None,
            cys_count=c["cys_count"],
            metrics={
                "aromatic_count": c["aromatic_count"],
                "basic_count": c["basic_count"],
                "acidic_count": c["acidic_count"],
                "instability_proxy": c["instability_proxy"],
                "conservation": c["conservation"],
                "surface_accessibility": c["surface_accessibility"],
            },
            ranking_score=c["priority_score"],
            filter_status="PASS",
        )
        db.add(ec)
        top_candidates[i]["candidate_id"] = ec.id

    db.flush()

    # Artifacts
    artifact_dir = _step_dir(run.id, "EPITOPE_SCREENING")
    _write_json(os.path.join(artifact_dir, "epitope_candidates.json"), {
        "scan_id": scan.id,
        "method": STEP_METHODS["EPITOPE_SCREENING"],
        "scientific_boundary_note": STEP_BOUNDARIES["EPITOPE_SCREENING"],
        "candidates": top_candidates,
    })
    _write_csv(
        os.path.join(artifact_dir, "epitope_candidates.csv"),
        ["rank", "start", "end", "sequence", "length", "net_charge", "hydrophobic_ratio",
         "aromatic_count", "basic_count", "acidic_count", "cys_count", "priority_score"],
        [[i + 1, c["start"], c["end"], c["sequence"], c["length"], c["net_charge"],
          c["hydrophobic_ratio"], c["aromatic_count"], c["basic_count"],
          c["acidic_count"], c["cys_count"], c["priority_score"]]
         for i, c in enumerate(top_candidates)],
    )

    _update_step(
        step,
        "SUCCEEDED",
        output_json={
            "scan_id": scan.id,
            "record_count": len(top_candidates),
            "artifact_files": ["epitope_candidates.json", "epitope_candidates.csv"],
            "candidates": top_candidates[:20],
        },
    )
    _update_run(run, current_step="PEPTIDE_GENERATION")
    db.commit()
    return True


def run_peptide_generation_step(
    db: Session,
    run: PipelineRun,
    peptides_per_epitope: int = 5,
) -> bool:
    """Deterministic targeting peptide baseline generation."""
    step = _get_step(db, run.id, "PEPTIDE_GENERATION")
    _update_step(step, "RUNNING")
    db.commit()

    # Fetch top epitope candidates from this run
    scan_id = _get_scan_id(db, run)
    if not scan_id:
        _update_step(step, "FAILED", error_message="No epitope scan found.")
        _update_run(run, status="FAILED")
        db.commit()
        return False

    epitopes = (
        db.query(EpitopeCandidate)
        .filter(EpitopeCandidate.scan_id == scan_id)
        .order_by(EpitopeCandidate.ranking_score.desc())
        .limit(20)
        .all()
    )

    if not epitopes:
        _update_step(step, "FAILED", error_message="No epitope candidates available.")
        _update_run(run, status="FAILED")
        db.commit()
        return False

    selected_models = list(((run.output_json or {}).get("request") or {}).get("selected_models") or [])
    model_execution: dict[str, Any] | None = None
    if selected_models:
        from app.services.production_model_registry import production_registry

        try:
            probes = [production_registry.get(model_id).probe() for model_id in selected_models]
        except KeyError:
            _update_step(step, "BLOCKED", error_message="Unknown selected model")
            _update_run(run, status="BLOCKED", current_step="PEPTIDE_GENERATION")
            db.commit()
            return False
        from app.services.unified_model_runtime import process_model_job
        model_results = []
        for model_id, probe in zip(selected_models, probes):
            if probe["state"] != "ready":
                model_results.append({
                    "job_id": None,
                    "model_id": model_id,
                    "status": "BLOCKED",
                    "result": None,
                    "error": {"error_code": "MODEL_RUNTIME_NOT_READY", "probe": probe},
                })
                _append_pipeline_log(
                    run.id, "WARNING", f"{model_id} skipped: runtime state={probe['state']}.",
                    step="PEPTIDE_GENERATION", model_id=model_id,
                )
                continue
            model_job = production_registry.get(model_id).submit(
                db,
                {
                    "target_sequence": run.target_sequence,
                    "peptide_length": 12,
                    # Keep interactive pipeline runs bounded while still returning
                    # enough candidates for cross-model ranking and top-N output.
                    "num_candidates": min(10, max(1, peptides_per_epitope * len(epitopes))),
                    "seed": int(sequence_sha256(run.target_sequence)[:8], 16),
                    "device": os.environ.get("STAMP_PEPMLM_DEVICE", "cuda"),
                },
                project_id=run.project_id or "pipeline_models",
                run_id=f"pipeline_{run.id}",
            )
            process_model_job(db, model_job)
            db.refresh(model_job)
            model_results.append({
                "job_id": model_job.id,
                "model_id": model_id,
                "status": model_job.status,
                "result": model_job.output_json,
                "error": model_job.error_json,
            })
        succeeded_models = [item for item in model_results if item["status"] == "SUCCEEDED"]
        failed_models = [item for item in model_results if item["status"] != "SUCCEEDED"]
        if not succeeded_models:
            _update_step(step, "BLOCKED", output_json={"model_results": model_results},
                         error_message="No selected model job succeeded")
            _update_run(run, status="BLOCKED", current_step="PEPTIDE_GENERATION")
            db.commit()
            return False
        model_execution = {
            "model_ids": selected_models,
            "status": "PARTIAL" if failed_models else "SUCCEEDED",
            "jobs": model_results,
            "provenance": "real_model",
            "warnings": [{"model_id": item["model_id"], "status": item["status"], "error": item["error"]}
                         for item in failed_models],
        }

    all_peptides: list[dict[str, Any]] = []
    generation_run = StampGenerationRun(
        project_id=run.project_id,
        epitope_id=epitopes[0].id,
        generator_name="unified_five_model_runtime" if model_execution else "deterministic_targeting_peptide_baseline_v1",
        generator_version="2.0" if model_execution else "1.0",
        status="COMPLETED",
        started_at=_utc_now(),
        finished_at=_utc_now(),
    )
    db.add(generation_run)
    db.flush()

    if model_execution:
        for model_job in model_execution["jobs"]:
            if model_job["status"] != "SUCCEEDED":
                continue
            result = model_job.get("result") or {}
            for candidate in result.get("candidates") or []:
                sequence = str(candidate.get("sequence", "")).upper()
                if not sequence or any(aa not in VALID_AA for aa in sequence):
                    continue
                gravy = compute_gravy(sequence)
                all_peptides.append({
                    "sequence": sequence,
                    "length": len(sequence),
                    "net_charge": round(compute_net_charge(sequence), 2),
                    "hydrophobic_ratio": round((gravy + 4.5) / 9.0, 3),
                    "source_epitope_id": epitopes[0].id,
                    "source_epitope_sequence": epitopes[0].sequence.upper(),
                    "generation_method": "unified_five_model_runtime",
                    "source_model": model_job["model_id"],
                    "source_job_id": model_job["job_id"],
                    "source_candidate_id": candidate.get("candidate_id"),
                    "score": candidate.get("score"),
                    "structure_path": candidate.get("structure_path"),
                    "pass_basic_filters": True,
                    "warning_flags": [],
                    "provenance": "real_model",
                })

    for epitope in ([] if model_execution else epitopes):
        epi_seq = epitope.sequence.upper()
        epi_charge = compute_net_charge(epi_seq)
        charge_sign = "positive" if epi_charge > 0.5 else "negative" if epi_charge < -0.5 else "neutral"

        pool_size = peptides_per_epitope
        for idx in range(pool_size):
            # Deterministic variations based on epitope charge complementarity
            if charge_sign == "positive":
                candidate = _generate_complementary_peptide(epi_seq, prefer_negative=True, idx=idx)
            elif charge_sign == "negative":
                candidate = _generate_complementary_peptide(epi_seq, prefer_positive=True, idx=idx)
            else:
                candidate = _generate_complementary_peptide(epi_seq, balanced=True, idx=idx)

            if not candidate:
                continue

            length = len(candidate)
            net_charge = compute_net_charge(candidate)
            gravy = compute_gravy(candidate)
            hydrophobic_ratio = round((gravy + 4.5) / 9.0, 3)

            # Basic filters
            pass_filters = True
            warning_flags: list[str] = []
            if length < 12 or length > 25:
                pass_filters = False
                warning_flags.append("length_out_of_range")
            if net_charge <= 0:
                pass_filters = False
                warning_flags.append("non_positive_charge")
            if hydrophobic_ratio < 0.35 or hydrophobic_ratio > 0.70:
                warning_flags.append("hydrophobicity_extreme")
            if any(aa not in VALID_AA for aa in candidate):
                pass_filters = False
                warning_flags.append("invalid_aa")
            # Check long hydrophobic stretches
            max_stretch = 0
            cur = 0
            for aa in candidate:
                if aa in "VILFMWY":
                    cur += 1
                    max_stretch = max(max_stretch, cur)
                else:
                    cur = 0
            if max_stretch > 5:
                warning_flags.append("long_hydrophobic_stretch")
            # Check repeats
            if any(candidate[i:i+4] == candidate[i+4:i+8] for i in range(len(candidate) - 7)):
                warning_flags.append("tandem_repeat")

            peptide_record = {
                "sequence": candidate,
                "length": length,
                "net_charge": round(net_charge, 2),
                "hydrophobic_ratio": hydrophobic_ratio,
                "source_epitope_id": epitope.id,
                "source_epitope_sequence": epi_seq,
                "generation_method": STEP_METHODS["PEPTIDE_GENERATION"],
                "pass_basic_filters": pass_filters,
                "warning_flags": warning_flags,
            }
            all_peptides.append(peptide_record)

    if not all_peptides:
        _update_step(step, "FAILED", error_message="No peptides generated.")
        _update_run(run, status="FAILED")
        db.commit()
        return False

    # Artifacts
    artifact_dir = _step_dir(run.id, "PEPTIDE_GENERATION")
    _write_json(os.path.join(artifact_dir, "generated_peptides.json"), {
        "generation_run_id": generation_run.id,
        "method": STEP_METHODS["PEPTIDE_GENERATION"],
        "scientific_boundary_note": STEP_BOUNDARIES["PEPTIDE_GENERATION"],
        "peptides": all_peptides,
        "model_execution": model_execution,
    })
    _write_csv(
        os.path.join(artifact_dir, "generated_peptides.csv"),
        ["sequence", "length", "net_charge", "hydrophobic_ratio",
         "source_epitope_id", "pass_basic_filters", "warning_flags"],
        [[p["sequence"], p["length"], p["net_charge"], p["hydrophobic_ratio"],
          p["source_epitope_id"], p["pass_basic_filters"],
          ";".join(p["warning_flags"])] for p in all_peptides],
    )

    _update_step(
        step,
        "SUCCEEDED",
        output_json={
            "generation_run_id": generation_run.id,
            "record_count": len(all_peptides),
            "artifact_files": ["generated_peptides.json", "generated_peptides.csv"],
            "peptides": all_peptides[:50],
            "model_execution": model_execution,
        },
    )
    _update_run(run, current_step="PEPTIDE_OPTIMIZATION")
    db.commit()
    return True


def _generate_complementary_peptide(
    epitope_seq: str,
    prefer_negative: bool = False,
    prefer_positive: bool = False,
    balanced: bool = False,
    idx: int = 0,
) -> str | None:
    """Generate a targeting peptide candidate from an epitope using deterministic rules."""
    import random
    deterministic_seed = int(sequence_sha256(f"{epitope_seq}:{idx}")[:16], 16)
    random.seed(deterministic_seed)

    positive_pool = list("KKRRHH")
    negative_pool = list("DDEE")
    neutral_hydro = list("VILFMYW")
    neutral_polar = list("STNQGPA")

    length = random.randint(12, 20)
    peptide: list[str] = []

    for i in range(length):
        if prefer_negative and i % 3 == 0:
            peptide.append(random.choice(negative_pool))
        elif prefer_positive and i % 3 == 0:
            peptide.append(random.choice(positive_pool))
        elif balanced:
            if i % 2 == 0:
                peptide.append(random.choice(neutral_polar + positive_pool[:2]))
            else:
                peptide.append(random.choice(neutral_hydro + negative_pool[:2]))
        else:
            peptide.append(random.choice(neutral_polar + neutral_hydro))

    return "".join(peptide)


def run_peptide_optimization_step(
    db: Session,
    run: PipelineRun,
    top_k: int = 50,
) -> bool:
    """Physicochemical filter and rank generated peptides.

    Implements ranked_with_warnings mechanism:
    - strict_pass=true peptides are prioritized.
    - If no strict_pass, the best warning candidates are retained
      (never crash the pipeline).
    """
    step = _get_step(db, run.id, "PEPTIDE_OPTIMIZATION")
    _update_step(step, "RUNNING")
    db.commit()

    gen_dir = _step_dir(run.id, "PEPTIDE_GENERATION")
    gen_path = os.path.join(gen_dir, "generated_peptides.json")
    if not os.path.exists(gen_path):
        _update_step(step, "FAILED", error_message="Generated peptides artifact missing.")
        _update_run(run, status="FAILED")
        db.commit()
        return False

    with open(gen_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    peptides = data.get("peptides", [])

    all_evaluated: list[dict[str, Any]] = []
    for p in peptides:
        seq = p["sequence"].upper()
        warning_flags: list[str] = []

        # Fatal: invalid amino acid
        if any(aa not in VALID_AA for aa in seq):
            continue

        length = len(seq)
        # Fatal: extreme length (outside 8-50)
        if length < 8 or length > 50:
            continue

        net_charge = compute_net_charge(seq)
        gravy = compute_gravy(seq)
        hydrophobic_ratio = round((gravy + 4.5) / 9.0, 3)
        aromatic = sum(seq.count(aa) for aa in "FWY") / length
        basic = sum(seq.count(aa) for aa in "KRH") / length
        acidic = sum(seq.count(aa) for aa in "DE") / length
        cys = seq.count("C")
        pro = seq.count("P")

        # Aggregation risk proxy
        agg_risk = "low"
        if hydrophobic_ratio > 0.60 and length > 20:
            agg_risk = "high"
            warning_flags.append("high_aggregation_risk")
        elif hydrophobic_ratio > 0.55:
            agg_risk = "medium"
            warning_flags.append("medium_aggregation_risk")

        # Synthesis risk proxy
        synth_risk = "low"
        if cys > 2:
            synth_risk = "high"
            warning_flags.append("high_synthesis_risk")
        elif pro > 3:
            synth_risk = "medium"
            warning_flags.append("medium_synthesis_risk")

        # Strict filter checks
        strict_pass = True
        if length < 12 or length > 35:
            strict_pass = False
            warning_flags.append("length_out_of_range")
        if net_charge <= 0:
            strict_pass = False
            warning_flags.append("non_positive_charge")
        if hydrophobic_ratio < 0.35 or hydrophobic_ratio > 0.70:
            strict_pass = False
            warning_flags.append("hydrophobicity_out_of_range")
        if agg_risk == "high":
            strict_pass = False
            warning_flags.append("aggregation_risk_high")
        if synth_risk == "high":
            strict_pass = False
            warning_flags.append("synthesis_risk_high")

        # Solubility proxy
        solubility_proxy = round(
            0.4 * (net_charge / 10)
            + 0.3 * (1 - hydrophobic_ratio)
            + 0.3 * (1 if length <= 25 else 0.5),
            3,
        )

        # Hemolysis risk proxy
        hemo_risk = "low"
        if hydrophobic_ratio > 0.60 and basic > 0.3:
            hemo_risk = "medium"
            warning_flags.append("hemolysis_risk_medium")

        rank_score = (
            0.25 * solubility_proxy
            + 0.25 * (1 if agg_risk == "low" else 0.5 if agg_risk == "medium" else 0)
            + 0.20 * (net_charge / 10)
            + 0.15 * (1 - abs(gravy))
            + 0.15 * (1 if synth_risk == "low" else 0.5)
        )

        all_evaluated.append({
            "sequence": seq,
            "length": length,
            "net_charge": round(net_charge, 2),
            "hydrophobic_ratio": hydrophobic_ratio,
            "aromatic_ratio": round(aromatic, 3),
            "basic_ratio": round(basic, 3),
            "acidic_ratio": round(acidic, 3),
            "predicted_solubility_proxy": solubility_proxy,
            "aggregation_risk_proxy": agg_risk,
            "hemolysis_risk_proxy": hemo_risk,
            "synthesis_risk_proxy": synth_risk,
            "cysteine_count": cys,
            "proline_count": pro,
            "rank_score": round(rank_score, 4),
            "source_epitope_id": p.get("source_epitope_id"),
            "generation_method": p.get("generation_method"),
            "strict_pass": strict_pass,
            "warning_flags": warning_flags,
        })

    # Sort all by rank_score descending
    all_evaluated.sort(key=lambda x: x["rank_score"], reverse=True)

    # Separate strict vs warning
    strict_peptides = [p for p in all_evaluated if p["strict_pass"]]
    warning_peptides = [p for p in all_evaluated if not p["strict_pass"]]

    # Build final list: strict first, then best warnings
    if strict_peptides:
        top_optimized = strict_peptides[:top_k]
    else:
        # No strict pass — keep top warning candidates so pipeline doesn't crash
        top_optimized = warning_peptides[:top_k] if warning_peptides else all_evaluated[:top_k]

    if not top_optimized:
        _update_step(step, "FAILED", error_message="No peptides available for optimization.")
        _update_run(run, status="FAILED")
        db.commit()
        return False

    # Clean up internal flags before writing output
    output_peptides = []
    for p in top_optimized:
        out = {k: v for k, v in p.items() if k not in ("strict_pass",)}
        output_peptides.append(out)

    artifact_dir = _step_dir(run.id, "PEPTIDE_OPTIMIZATION")
    _write_json(os.path.join(artifact_dir, "optimized_peptides.json"), {
        "method": STEP_METHODS["PEPTIDE_OPTIMIZATION"],
        "scientific_boundary_note": STEP_BOUNDARIES["PEPTIDE_OPTIMIZATION"],
        "strict_pass_count": len(strict_peptides),
        "warning_count": len(warning_peptides),
        "peptides": output_peptides,
    })
    _write_csv(
        os.path.join(artifact_dir, "optimized_peptides.csv"),
        ["rank", "sequence", "length", "net_charge", "hydrophobic_ratio",
         "solubility_proxy", "aggregation_risk", "hemolysis_risk",
         "synthesis_risk", "cysteine_count", "rank_score", "warning_flags"],
        [[i + 1, p["sequence"], p["length"], p["net_charge"], p["hydrophobic_ratio"],
          p["predicted_solubility_proxy"], p["aggregation_risk_proxy"],
          p["hemolysis_risk_proxy"], p["synthesis_risk_proxy"],
          p["cysteine_count"], p["rank_score"], ";".join(p["warning_flags"])]
         for i, p in enumerate(output_peptides)],
    )

    _update_step(
        step,
        "SUCCEEDED",
        output_json={
            "record_count": len(output_peptides),
            "strict_pass_count": len(strict_peptides),
            "artifact_files": ["optimized_peptides.json", "optimized_peptides.csv"],
            "optimized_peptides": output_peptides[:50],
        },
    )
    _update_run(run, current_step="STAMP_ASSEMBLY")
    db.commit()
    return True


def run_stamp_assembly_step(
    db: Session,
    run: PipelineRun,
    top_k: int = 100,
) -> bool:
    """Assemble STAMP candidates from optimized peptides + linkers + functional peptides."""
    step = _get_step(db, run.id, "STAMP_ASSEMBLY")
    _update_step(step, "RUNNING")
    db.commit()

    opt_dir = _step_dir(run.id, "PEPTIDE_OPTIMIZATION")
    opt_path = os.path.join(opt_dir, "optimized_peptides.json")
    if not os.path.exists(opt_path):
        _update_step(step, "FAILED", error_message="Optimized peptides artifact missing.")
        _update_run(run, status="FAILED")
        db.commit()
        return False

    with open(opt_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    peptides = data.get("peptides", [])[:top_k]

    # Load functional peptides from existing data if available
    func_peptides = _load_functional_peptides()
    if not func_peptides:
        # Fallback: use a minimal curated set, explicitly labeled as unvalidated
        func_peptides = [
            {"name": "P4_curated", "sequence": "RKKRWWIRVR", "source": "curated_fallback_unvalidated"},
            {"name": "E14_curated", "sequence": "GLFDVIKKVAAVIGGL", "source": "curated_fallback_unvalidated"},
            {"name": "LL37_fragment", "sequence": "LLGDFFRKSKEKIGKEFKRIVQRIKDF", "source": "curated_fallback_unvalidated"},
        ]

    stamp_candidates: list[dict[str, Any]] = []
    for p in peptides:
        tp = p["sequence"]
        for linker in LINKER_LIBRARY:
            for fp in func_peptides:
                full = f"{tp}{linker}{fp['sequence']}"
                total_len = len(full)
                net_charge = compute_net_charge(full)
                gravy = compute_gravy(full)
                hydrophobic_ratio = round((gravy + 4.5) / 9.0, 3)

                pass_length = 30 <= total_len <= 80
                pass_charge = net_charge > 0
                pass_hydro = 0.30 <= hydrophobic_ratio <= 0.75

                rank_score = (
                    0.3 * (1 if pass_length else 0)
                    + 0.3 * (1 if pass_charge else 0)
                    + 0.2 * (1 if pass_hydro else 0)
                    + 0.2 * p.get("rank_score", 0)
                )

                stamp_candidates.append({
                    "stamp_sequence": full,
                    "targeting_peptide": tp,
                    "linker": linker,
                    "functional_peptide": fp["sequence"],
                    "functional_peptide_name": fp.get("name", "unknown"),
                    "functional_peptide_source": fp.get("source", "unknown"),
                    "total_length": total_len,
                    "net_charge": round(net_charge, 2),
                    "hydrophobic_ratio": hydrophobic_ratio,
                    "linker_type": _linker_type(linker),
                    "assembly_method": STEP_METHODS["STAMP_ASSEMBLY"],
                    "pass_length": pass_length,
                    "pass_charge": pass_charge,
                    "pass_hydrophobicity": pass_hydro,
                    "rank_score": round(rank_score, 4),
                    "source_peptide_rank_score": p.get("rank_score"),
                })

    stamp_candidates.sort(key=lambda x: x["rank_score"], reverse=True)
    top_stamp = stamp_candidates[:top_k]

    # Persist to DB
    generation_run_id = _get_generation_run_id(db, run)
    for sc in top_stamp:
        stamp = StampCandidate(
            project_id=run.project_id,
            epitope_id=sc.get("source_epitope_id") or _get_first_epitope_id(db, run),
            generation_run_id=generation_run_id,
            targeting_peptide_seq=sc["targeting_peptide"],
            linker_seq=sc["linker"],
            full_sequence=sc["stamp_sequence"],
            composite_score=sc["rank_score"],
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            metrics={
                "functional_peptide_name": sc["functional_peptide_name"],
                "functional_peptide_source": sc["functional_peptide_source"],
                "linker_type": sc["linker_type"],
                "pass_length": sc["pass_length"],
                "pass_charge": sc["pass_charge"],
                "pass_hydrophobicity": sc["pass_hydrophobicity"],
                "total_length": sc["total_length"],
                "net_charge": sc["net_charge"],
                "hydrophobic_ratio": sc["hydrophobic_ratio"],
            },
        )
        db.add(stamp)
        db.flush()
        sc["stamp_candidate_id"] = stamp.id

    artifact_dir = _step_dir(run.id, "STAMP_ASSEMBLY")
    _write_json(os.path.join(artifact_dir, "stamp_candidates.json"), {
        "method": STEP_METHODS["STAMP_ASSEMBLY"],
        "scientific_boundary_note": STEP_BOUNDARIES["STAMP_ASSEMBLY"],
        "candidates": top_stamp,
    })
    _write_csv(
        os.path.join(artifact_dir, "stamp_candidates.csv"),
        ["rank", "stamp_sequence", "targeting_peptide", "linker", "functional_peptide",
         "total_length", "net_charge", "hydrophobic_ratio", "pass_length", "pass_charge",
         "pass_hydrophobicity", "rank_score"],
        [[i + 1, s["stamp_sequence"], s["targeting_peptide"], s["linker"],
          s["functional_peptide"], s["total_length"], s["net_charge"],
          s["hydrophobic_ratio"], s["pass_length"], s["pass_charge"],
          s["pass_hydrophobicity"], s["rank_score"]]
         for i, s in enumerate(top_stamp)],
    )

    _update_step(
        step,
        "SUCCEEDED",
        output_json={
            "record_count": len(top_stamp),
            "artifact_files": ["stamp_candidates.json", "stamp_candidates.csv"],
            "stamp_candidates": top_stamp[:50],
        },
    )
    _update_run(run, current_step="STRUCTURE_VALIDATION_READY")
    db.commit()
    return True


def run_structure_validation_ready_step(db: Session, run: PipelineRun) -> bool:
    """Mark STAMP candidates as ready for downstream structure prediction.
    Does NOT generate fake PDB, pLDDT, ipTM, or docking scores."""
    step = _get_step(db, run.id, "STRUCTURE_VALIDATION_READY")
    _update_step(step, "RUNNING")
    db.commit()

    stamp_dir = _step_dir(run.id, "STAMP_ASSEMBLY")
    stamp_path = os.path.join(stamp_dir, "stamp_candidates.json")
    if not os.path.exists(stamp_path):
        _update_step(step, "FAILED", error_message="STAMP candidates artifact missing.")
        _update_run(run, status="FAILED")
        db.commit()
        return False

    with open(stamp_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    candidates = data.get("candidates", [])
    if not candidates:
        _update_step(step, "FAILED", error_message="No STAMP candidates available.")
        _update_run(run, status="FAILED")
        db.commit()
        return False

    manifest = {
        "pipeline_run_id": run.id,
        "target_name": run.target_name,
        "candidate_count": len(candidates),
        "status": "READY_FOR_VALIDATION",
        "note": "Candidates are ready for downstream structure prediction and docking. No structural modelling metrics are claimed at this stage.",
        "candidates": [
            {
                "stamp_candidate_id": c.get("stamp_candidate_id"),
                "stamp_sequence": c["stamp_sequence"],
                "targeting_peptide": c["targeting_peptide"],
                "linker": c["linker"],
                "functional_peptide": c["functional_peptide"],
                "total_length": c["total_length"],
                "net_charge": c["net_charge"],
            }
            for c in candidates[:20]
        ],
    }

    artifact_dir = _step_dir(run.id, "STRUCTURE_VALIDATION_READY")
    _write_json(os.path.join(artifact_dir, "structure_validation_manifest.json"), manifest)

    _update_step(
        step,
        "SUCCEEDED",
        output_json={
            "record_count": len(candidates),
            "artifact_files": ["structure_validation_manifest.json"],
            "manifest": manifest,
        },
    )
    _update_run(run, current_step="FINAL_RANKING")
    db.commit()
    return True


def run_final_ranking_step(db: Session, run: PipelineRun, top_k: int = 50) -> bool:
    """Compute final ranking of STAMP candidates using sequence-level composite scoring.

    No structural scores (pLDDT, ipTM, docking_score, delta_G) are used.
    """
    step = _get_step(db, run.id, "FINAL_RANKING")
    _update_step(step, "RUNNING")
    db.commit()

    stamp_dir = _step_dir(run.id, "STAMP_ASSEMBLY")
    stamp_path = os.path.join(stamp_dir, "stamp_candidates.json")
    if not os.path.exists(stamp_path):
        _update_step(step, "FAILED", error_message="STAMP candidates artifact missing.")
        _update_run(run, status="FAILED")
        db.commit()
        return False

    with open(stamp_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    candidates = data.get("candidates", [])
    if not candidates:
        _update_step(step, "FAILED", error_message="No STAMP candidates to rank.")
        _update_run(run, status="FAILED")
        db.commit()
        return False

    # Load epitope data for source epitope scores
    epitope_dir = _step_dir(run.id, "EPITOPE_SCREENING")
    epitope_path = os.path.join(epitope_dir, "epitope_candidates.json")
    epitope_map: dict[str, dict] = {}
    if os.path.exists(epitope_path):
        with open(epitope_path, "r", encoding="utf-8") as f:
            e_data = json.load(f)
        for c in e_data.get("candidates", []):
            epitope_map[c.get("sequence", "")] = c

    # Load optimized peptide data
    opt_dir = _step_dir(run.id, "PEPTIDE_OPTIMIZATION")
    opt_path = os.path.join(opt_dir, "optimized_peptides.json")
    peptide_map: dict[str, dict] = {}
    if os.path.exists(opt_path):
        with open(opt_path, "r", encoding="utf-8") as f:
            p_data = json.load(f)
        for p in p_data.get("peptides", []):
            peptide_map[p.get("sequence", "")] = p

    ranked: list[dict[str, Any]] = []
    for i, c in enumerate(candidates):
        # Sub-scores (normalized to ~0-1)
        epitope_priority = c.get("source_peptide_rank_score", 0.5)
        peptide_filter = min(1.0, max(0.0, c.get("source_peptide_rank_score", 0.5)))
        stamp_assembly = min(1.0, max(0.0, c.get("rank_score", 0)))

        total_len = c["total_length"]
        net_charge = c["net_charge"]
        hydro = c["hydrophobic_ratio"]

        # Physicochemical score
        len_score = max(0.0, 1.0 - abs(total_len - 35) / 30)
        charge_score = max(0.0, 1.0 - abs(abs(net_charge) - 5) / 10)
        hydro_score = max(0.0, 1.0 - abs(hydro - 0.5) / 0.3)
        physico_score = (len_score + charge_score + hydro_score) / 3

        # Penalties
        penalties = 0.0
        warnings: list[str] = []
        if not c.get("pass_length", True):
            penalties += 0.1
            warnings.append("length_out_of_range")
        if not c.get("pass_charge", True):
            penalties += 0.1
            warnings.append("charge_out_of_range")
        if not c.get("pass_hydrophobicity", True):
            penalties += 0.1
            warnings.append("hydrophobicity_out_of_range")
        if net_charge < 0:
            penalties += 0.2
            warnings.append("low_charge")

        final_rank_score = (
            0.20 * epitope_priority
            + 0.20 * peptide_filter
            + 0.25 * stamp_assembly
            + 0.25 * physico_score
            + 0.10 * (1.0 if not warnings else 0.5)
            - penalties
        )
        final_rank_score = round(max(0.0, min(1.0, final_rank_score)), 4)

        # Find source epitope info
        tp_seq = c["targeting_peptide"]
        source_epi = peptide_map.get(tp_seq, {})
        epi_seq = source_epi.get("source_epitope_id", "")
        epi_info = epitope_map.get(epi_seq, {})

        ranked.append({
            "rank": i + 1,
            "stamp_candidate_id": c.get("stamp_candidate_id"),
            "stamp_sequence": c["stamp_sequence"],
            "targeting_peptide": c["targeting_peptide"],
            "linker": c["linker"],
            "functional_peptide": c["functional_peptide"],
            "functional_peptide_name": c.get("functional_peptide_name", "unknown"),
            "source_epitope_sequence": epi_seq,
            "epitope_start": epi_info.get("start"),
            "epitope_end": epi_info.get("end"),
            "total_length": total_len,
            "net_charge": net_charge,
            "hydrophobic_ratio": hydro,
            "epitope_priority_score": round(epitope_priority, 4),
            "peptide_filter_score": round(peptide_filter, 4),
            "stamp_assembly_score": round(stamp_assembly, 4),
            "physicochemical_score": round(physico_score, 4),
            "final_rank_score": final_rank_score,
            "warnings": warnings,
            "method": STEP_METHODS["FINAL_RANKING"],
            "scientific_boundary_note": STEP_BOUNDARIES["FINAL_RANKING"],
        })

    ranked.sort(key=lambda x: x["final_rank_score"], reverse=True)
    # Re-assign ranks after sorting
    for i, r in enumerate(ranked):
        r["rank"] = i + 1

    top_ranked = ranked[:top_k]

    artifact_dir = _step_dir(run.id, "FINAL_RANKING")
    _write_json(os.path.join(artifact_dir, "final_ranking.json"), {
        "method": STEP_METHODS["FINAL_RANKING"],
        "scientific_boundary_note": STEP_BOUNDARIES["FINAL_RANKING"],
        "total_candidates": len(ranked),
        "candidates": top_ranked,
    })
    _write_csv(
        os.path.join(artifact_dir, "final_ranking.csv"),
        ["rank", "stamp_candidate_id", "stamp_sequence", "targeting_peptide", "linker",
         "functional_peptide", "total_length", "net_charge", "hydrophobic_ratio",
         "epitope_priority_score", "peptide_filter_score", "stamp_assembly_score",
         "physicochemical_score", "final_rank_score", "warnings"],
        [[r["rank"], r["stamp_candidate_id"], r["stamp_sequence"], r["targeting_peptide"],
          r["linker"], r["functional_peptide"], r["total_length"], r["net_charge"],
          r["hydrophobic_ratio"], r["epitope_priority_score"], r["peptide_filter_score"],
          r["stamp_assembly_score"], r["physicochemical_score"], r["final_rank_score"],
          ";".join(r["warnings"])]
         for r in top_ranked],
    )
    _write_json(os.path.join(artifact_dir, "final_ranking_summary.json"), {
        "total_candidates": len(ranked),
        "top_candidate_count": len(top_ranked),
        "method": STEP_METHODS["FINAL_RANKING"],
    })

    _update_step(
        step,
        "SUCCEEDED",
        output_json={
            "record_count": len(top_ranked),
            "artifact_files": ["final_ranking.json", "final_ranking.csv", "final_ranking_summary.json"],
            "final_ranking": top_ranked[:20],
        },
    )
    _update_run(run, current_step="REPORT_EXPORT")
    db.commit()
    return True


def generate_pipeline_report(db: Session, run: PipelineRun) -> bool:
    """Generate pipeline_report.json and pipeline_report.md."""
    step = _get_step(db, run.id, "REPORT_EXPORT")
    _update_step(step, "RUNNING")
    db.commit()

    # Collect stats from steps
    steps = (
        db.query(PipelineStep)
        .filter(PipelineStep.pipeline_run_id == run.id)
        .order_by(PipelineStep.step_order)
        .all()
    )

    step_stats = []
    for s in steps:
        out = s.output_json or {}
        step_stats.append({
            "step_name": s.step_name,
            "status": s.status,
            "method": s.method,
            "record_count": out.get("record_count", 0),
            "scientific_boundary_note": s.scientific_boundary_note,
        })

    # Load final ranking top 10
    final_ranking_path = os.path.join(_step_dir(run.id, "FINAL_RANKING"), "final_ranking.json")
    top_candidates = []
    if os.path.exists(final_ranking_path):
        with open(final_ranking_path, "r", encoding="utf-8") as f:
            fr_data = json.load(f)
        top_candidates = fr_data.get("candidates", [])[:10]

    report_data = {
        "pipeline_run_id": run.id,
        "target_name": run.target_name,
        "target_sequence_length": len(run.target_sequence),
        "status": run.status,
        "current_step": run.current_step,
        "steps": step_stats,
        "top_candidates": top_candidates,
        "scientific_boundary_note": "All metrics are sequence-level computational estimates. Not experimentally validated.",
        "generated_at": _utc_now().isoformat(),
    }

    artifact_dir = _step_dir(run.id, "REPORT_EXPORT")
    _write_json(os.path.join(artifact_dir, "pipeline_report.json"), report_data)

    # Generate markdown report
    md_lines = [
        f"# Pipeline Report — {run.target_name}",
        "",
        f"- **Run ID:** `{run.id}`",
        f"- **Target Sequence Length:** {len(run.target_sequence)} aa",
        f"- **Status:** {run.status}",
        f"- **Generated At:** {report_data['generated_at']}",
        "",
        "## Step Summary",
        "",
        "| Step | Status | Records | Method |",
        "|------|--------|---------|--------|",
    ]
    for st in step_stats:
        md_lines.append(f"| {st['step_name']} | {st['status']} | {st['record_count']} | {st['method']} |")

    md_lines.extend([
        "",
        "## Top 10 Final Ranked Candidates",
        "",
        "| Rank | STAMP Sequence | Targeting Peptide | Linker | Functional | Length | Charge | Score |",
        "|------|----------------|-------------------|--------|------------|--------|--------|-------|",
    ])
    for c in top_candidates:
        md_lines.append(
            f"| {c.get('rank', '-')} | `{c.get('stamp_sequence', '-')}` | "
            f"{c.get('targeting_peptide', '-')} | {c.get('linker', '-')} | "
            f"{c.get('functional_peptide', '-')} | {c.get('total_length', '-')} | "
            f"{c.get('net_charge', '-')} | {c.get('final_rank_score', '-')} |"
        )

    md_lines.extend([
        "",
        "## Scientific Boundary",
        "",
        report_data["scientific_boundary_note"],
        "",
        "> **Warning:** These are computational prioritizations only. "
        "No experimental validation of antimicrobial activity, binding affinity, or toxicity has been performed.",
    ])

    with open(os.path.join(artifact_dir, "pipeline_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    _update_step(
        step,
        "SUCCEEDED",
        output_json={
            "record_count": len(top_candidates),
            "artifact_files": ["pipeline_report.json", "pipeline_report.md"],
        },
    )
    _update_run(run, status="SUCCEEDED", current_step="FRONT_PIPELINE_TO_FINAL_RANKING_READY")
    db.commit()
    return True


def create_batch_draft_step(db: Session, run: PipelineRun) -> bool:
    """Create a BatchComputation draft from top STAMP candidates."""
    step = _get_step(db, run.id, "BATCH_DRAFT")
    _update_step(step, "RUNNING")
    db.commit()

    stamp_dir = _step_dir(run.id, "STAMP_ASSEMBLY")
    stamp_path = os.path.join(stamp_dir, "stamp_candidates.json")
    if not os.path.exists(stamp_path):
        _update_step(step, "FAILED", error_message="STAMP candidates artifact missing.")
        _update_run(run, status="FAILED")
        db.commit()
        return False

    with open(stamp_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    candidates = data.get("candidates", [])[:50]  # Draft top 50

    # Create BatchComputation record
    batch = BatchComputation(
        project_id=run.project_id,
        name=f"Pipeline-{run.id[:8]}-BatchDraft",
        job_type="MIXED",
        status="PENDING",
        input_json={
            "pipeline_run_id": run.id,
            "candidate_count": len(candidates),
            "next_recommended_action": "FLEXPEPDOCK",
        },
        artifact_dir=f"data/pipeline_runs/{run.id}/batch_draft",
    )
    db.add(batch)
    db.flush()

    # Create items
    for c in candidates:
        item = BatchComputationItem(
            batch_id=batch.id,
            project_id=run.project_id,
            candidate_id=c.get("stamp_candidate_id"),
            job_type="FLEXPEPDOCK",
            status="PENDING",
            input_json={
                "stamp_sequence": c["stamp_sequence"],
                "targeting_peptide": c["targeting_peptide"],
                "linker": c["linker"],
                "functional_peptide": c["functional_peptide"],
            },
            artifact_dir=f"data/pipeline_runs/{run.id}/batch_draft/{c.get('stamp_candidate_id', 'unknown')}",
        )
        db.add(item)

    db.flush()

    batch_dir = _step_dir(run.id, "BATCH_DRAFT")
    _write_json(os.path.join(batch_dir, "batch_draft.json"), {
        "batch_id": batch.id,
        "method": STEP_METHODS["BATCH_DRAFT"],
        "scientific_boundary_note": STEP_BOUNDARIES["BATCH_DRAFT"],
        "candidate_count": len(candidates),
        "next_recommended_action": "FLEXPEPDOCK",
        "items": [
            {
                "candidate_id": c.get("stamp_candidate_id"),
                "stamp_sequence": c["stamp_sequence"],
                "status": "PENDING",
            }
            for c in candidates
        ],
    })

    _update_step(
        step,
        "SUCCEEDED",
        output_json={
            "batch_id": batch.id,
            "record_count": len(candidates),
            "artifact_files": ["batch_draft.json"],
            "batch_items": [
                {
                    "candidate_id": c.get("stamp_candidate_id"),
                    "stamp_sequence": c["stamp_sequence"],
                    "status": "PENDING",
                }
                for c in candidates
            ],
        },
    )
    _update_run(run, current_step="STRUCTURE_VALIDATION_READY", status="SUCCEEDED")
    db.commit()
    return True


def run_pipeline_once(
    db: Session,
    run_id: str,
    top_epitopes: int = 20,
    peptides_per_epitope: int = 5,
    top_stamp_candidates: int = 100,
) -> PipelineRun:
    """Execute all pipeline steps sequentially."""
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise ValueError(f"PipelineRun {run_id} not found")

    if run.status == "SUCCEEDED":
        logger.info("PipelineRun %s already SUCCEEDED; skipping.", run_id)
        _append_pipeline_log(run_id, "INFO", "Run already succeeded; no duplicate execution was started.")
        return run

    _append_pipeline_log(run_id, "INFO", "Pipeline execution started.")
    mark_manifest_status(run_id, "RUNNING")
    _update_run(run, status="RUNNING")
    db.commit()

    steps_to_run = [
        ("TARGET_INPUT", lambda: run_target_input_step(db, run)),
        ("EPITOPE_SCREENING", lambda: run_epitope_screening_step(db, run, top_k=top_epitopes)),
        ("PEPTIDE_GENERATION", lambda: run_peptide_generation_step(db, run, peptides_per_epitope=peptides_per_epitope)),
        ("PEPTIDE_OPTIMIZATION", lambda: run_peptide_optimization_step(db, run)),
        ("STAMP_ASSEMBLY", lambda: run_stamp_assembly_step(db, run, top_k=top_stamp_candidates)),
        ("STRUCTURE_VALIDATION_READY", lambda: run_structure_validation_ready_step(db, run)),
        ("FINAL_RANKING", lambda: run_final_ranking_step(db, run)),
        ("REPORT_EXPORT", lambda: generate_pipeline_report(db, run)),
    ]

    for step_name, step_func in steps_to_run:
        db.refresh(run)
        queue_metadata = dict((run.output_json or {}).get("queue") or {})
        if queue_metadata.get("cancel_requested"):
            step = _get_step(db, run.id, step_name)
            if step.status not in {"SUCCEEDED", "CANCELLED"}:
                _update_step(step, "CANCELLED", error_message="Run cancellation requested")
            _update_run(run, status="CANCELLED", current_step=step_name)
            db.commit()
            _append_pipeline_log(run_id, "INFO", "Pipeline execution cancelled.", step=step_name)
            mark_manifest_status(run_id, "CANCELLED")
            return run
        # Skip steps already succeeded
        step = _get_step(db, run.id, step_name)
        if step.status == "SUCCEEDED":
            logger.info("Step %s already succeeded; skipping.", step_name)
            _append_pipeline_log(run_id, "INFO", "Step already succeeded; skipped.", step=step_name)
            continue

        logger.info("Running pipeline step: %s for run %s", step_name, run_id)
        _append_pipeline_log(run_id, "INFO", "Step started.", step=step_name)
        try:
            ok = step_func()
        except Exception as exc:
            logger.exception("Step %s failed for run %s: %s", step_name, run_id, exc)
            _append_pipeline_log(
                run_id,
                "ERROR",
                f"{type(exc).__name__}: {exc}",
                step=step_name,
                exception_trace=traceback.format_exc(),
            )
            # A database exception leaves SQLAlchemy's transaction unusable.
            # Roll it back before persisting the visible FAILED state.
            db.rollback()
            run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            step = _get_step(db, run_id, step_name)
            _update_step(step, "FAILED", error_message=f"[{step_name}] {type(exc).__name__}: {exc}")
            _update_run(run, status="FAILED", current_step=step_name, error_message=f"{type(exc).__name__}: {exc}")
            db.commit()
            mark_manifest_status(run_id, "FAILED")
            return run

        if not ok:
            db.refresh(run)
            logger.error("Step %s returned False for run %s", step_name, run_id)
            _append_pipeline_log(run_id, "ERROR", step.error_message or "Step returned False.", step=step_name)
            if run.status != "BLOCKED":
                _update_run(run, status="FAILED", current_step=step_name)
            db.commit()
            mark_manifest_status(run_id, run.status)
            return run

        db.refresh(run)
        _append_pipeline_log(run_id, "INFO", "Step succeeded.", step=step_name)

    # Mark completion
    _update_run(run, status="SUCCEEDED", current_step="FRONT_PIPELINE_TO_FINAL_RANKING_READY")
    db.commit()
    db.refresh(run)
    logger.info("PipelineRun %s completed successfully.", run_id)
    _append_pipeline_log(run_id, "INFO", "Pipeline execution completed successfully.")
    mark_manifest_status(run_id, "SUCCEEDED")
    return run


def retry_pipeline_from_step(db: Session, run_id: str, from_step: str) -> PipelineRun:
    """Retry a pipeline from a specific step, resetting that step and all subsequent steps."""
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise ValueError(f"PipelineRun {run_id} not found")

    if from_step not in STEP_ORDER:
        raise ValueError(f"Invalid step name: {from_step}")

    reset = False
    for step in (
        db.query(PipelineStep)
        .filter(PipelineStep.pipeline_run_id == run_id)
        .order_by(PipelineStep.step_order)
        .all()
    ):
        if step.step_name == from_step:
            reset = True
        if reset:
            step.status = "PENDING"
            step.started_at = None
            step.finished_at = None
            step.output_json = {}
            step.error_message = None
            step.input_json = {
                **dict(step.input_json or {}),
                "attempt": int((step.input_json or {}).get("attempt", 0)),
            }
            reset_step_state(
                run_id,
                step.step_name,
                attempt=int(step.input_json.get("attempt", 0)),
                input_hash=str(step.input_json.get("input_hash", "")),
            )

    _update_run(run, status="PENDING", current_step=from_step, error_message=None)
    mark_manifest_status(run_id, "PENDING")
    db.commit()
    db.refresh(run)
    _append_pipeline_log(run_id, "INFO", "Retry requested; this step and following steps were reset.", step=from_step)
    return run


def list_pipeline_artifacts(run_id: str) -> list[dict[str, Any]]:
    """List all artifact files for a pipeline run."""
    base = _artifact_dir(run_id)
    files: list[dict[str, Any]] = []
    for root, _, filenames in os.walk(base):
        for name in filenames:
            path = os.path.join(root, name)
            rel = os.path.relpath(path, base)
            files.append({
                "path": rel,
                "size_bytes": os.path.getsize(path),
            })
    return files


def create_pipeline_zip(run_id: str, zip_path: str | None = None) -> str:
    """Zip all pipeline artifacts."""
    base = _artifact_dir(run_id)
    if zip_path is None:
        zip_path = os.path.join(base, f"pipeline_{run_id}_artifacts.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, filenames in os.walk(base):
            for name in filenames:
                if name.endswith(".zip"):
                    continue
                path = os.path.join(root, name)
                rel = os.path.relpath(path, base)
                zf.write(path, rel)
    return zip_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_step(db: Session, run_id: str, step_name: str) -> PipelineStep:
    step = (
        db.query(PipelineStep)
        .filter(PipelineStep.pipeline_run_id == run_id, PipelineStep.step_name == step_name)
        .first()
    )
    if not step:
        raise ValueError(f"Step {step_name} not found for run {run_id}")
    return step


def _get_target_protein_id(db: Session, run: PipelineRun) -> str | None:
    tp = db.query(TargetProtein).filter(
        TargetProtein.project_id == run.project_id,
        TargetProtein.sequence == run.target_sequence,
    ).order_by(TargetProtein.created_at.desc()).first()
    return tp.id if tp else None


def _get_scan_id(db: Session, run: PipelineRun) -> str | None:
    tp_id = _get_target_protein_id(db, run)
    if not tp_id:
        return None
    scan = db.query(EpitopeScan).filter(
        EpitopeScan.project_id == run.project_id,
        EpitopeScan.target_protein_id == tp_id,
    ).order_by(EpitopeScan.created_at.desc()).first()
    return scan.id if scan else None


def _get_generation_run_id(db: Session, run: PipelineRun) -> str | None:
    gr = db.query(StampGenerationRun).filter(
        StampGenerationRun.project_id == run.project_id,
    ).order_by(StampGenerationRun.created_at.desc()).first()
    return gr.id if gr else None


def _get_first_epitope_id(db: Session, run: PipelineRun) -> str | None:
    scan_id = _get_scan_id(db, run)
    if not scan_id:
        return None
    ec = db.query(EpitopeCandidate).filter(
        EpitopeCandidate.scan_id == scan_id,
    ).order_by(EpitopeCandidate.ranking_score.desc()).first()
    return ec.id if ec else None


def _linker_type(linker: str) -> str:
    if linker in ("EAAAKEAAAK", "AAY"):
        return "rigid"
    if linker in ("RKRR",):
        return "cleavable"
    return "flexible"


def _load_functional_peptides() -> list[dict[str, Any]]:
    """Load real AMP / functional peptide library from project data."""
    data_dir = os.environ.get("STAMP_DATA_DIR", "data")
    candidates_path = os.path.join(data_dir, "real_amp_candidates.json")
    if os.path.exists(candidates_path):
        try:
            with open(candidates_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [
                {"name": d.get("name", f"amp_{i}"), "sequence": d["sequence"], "source": "real_amp_library"}
                for i, d in enumerate(data)
                if "sequence" in d
            ]
        except (json.JSONDecodeError, OSError):
            pass
    return []
