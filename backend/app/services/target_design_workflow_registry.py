"""Target-design workflow dry-run planner (P7A/P7C).

Plans a multi-model workflow:

    PepMLM -> PepPrCLIP -> EvoBind2 -> Molstar

without executing any model.  Prior real artifacts (P5C PepMLM, P3B EvoBind2)
may be referenced as examples but are never re-run.

P7C adds:
  - Persisting the latest dry-run result for report export.
  - Whitelisted artifact download via the workflow router.
  - JSON / Markdown dry-run report generation.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.schemas.model_registry import (
    ModelDryRunPayload,
    ModelSafetyFlags,
    TargetDesignWorkflowPayload,
    TargetDesignWorkflowResult,
    WorkflowArtifactReference,
    WorkflowStep,
)
from app.services.model_adapters.evobind2_adapter import EvoBind2Adapter
from app.services.model_adapters.pepmlm_adapter import PepMLMAdapter
from app.services.model_adapters.pepprclip_adapter import (
    PEPPRCLIP_CHECKPOINT,
    PepPrCLIPAdapter,
)
from app.services.target_peptide_model_registry import (
    SCIENTIFIC_BOUNDARY_NOTE,
    build_default_safety_flags,
)

WORKFLOW_ID_PREFIX = "target_design_dryrun"
WORKFLOW_ARTIFACT_ROOT = Path(
    "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/artifacts/workflows"
)
LATEST_DRY_RUN_CACHE = WORKFLOW_ARTIFACT_ROOT / "latest_dry_run.json"

# Prior real artifacts that can be referenced but are never re-run.
P5C_PEPMLM_JOB_ID = "db47863a-501b-435a-840c-254376798251"
P3B_EVOBIND2_JOB_ID = "b8ab6d11-5762-4bdf-a9db-6d30602637fd"
P3B_EVOBIND2_PDB_REL = (
    "data_dev/artifacts/evobind2/b8ab6d11-5762-4bdf-a9db-6d30602637fd/output/unrelaxed_true.pdb"
)

# Whitelist of artifact references that may be downloaded through the workflow
# router.  Each key is a URL-safe artifact_ref; the value is the absolute file
# path that must live under /home/xh/kxc/stampup.
DOWNLOADABLE_ARTIFACTS: dict[str, Path] = {
    "p5c-candidates-csv": Path(
        "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/"
        f"data_dev/artifacts/pepmlm/{P5C_PEPMLM_JOB_ID}/output/candidate_sequences.csv"
    ),
    "p5c-candidates-json": Path(
        "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/"
        f"data_dev/artifacts/pepmlm/{P5C_PEPMLM_JOB_ID}/output/candidate_sequences.json"
    ),
    "p3b-pdb": Path(
        "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/"
        + P3B_EVOBIND2_PDB_REL
    ),
}

DOWNLOADABLE_ARTIFACT_FILENAMES: dict[str, str] = {
    "p5c-candidates-csv": "P5C_candidate_sequences.csv",
    "p5c-candidates-json": "P5C_candidate_sequences.json",
    "p3b-pdb": "P3B_unrelaxed_true.pdb",
}

ALLOWED_DOWNLOAD_ROOTS = (
    Path("/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/artifacts"),
    Path("/home/xh/kxc/stampup/reports"),
    WORKFLOW_ARTIFACT_ROOT,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_safety_flags() -> ModelSafetyFlags:
    return ModelSafetyFlags(**build_default_safety_flags())


def _step_from_adapter_result(
    step_id: str,
    name: str,
    model_id: str,
    adapter_result: object,
    extra_message: str = "",
    blocked_reason: Optional[str] = None,
) -> WorkflowStep:
    msg = str(adapter_result.message or f"{name} dry-run planned.")
    if extra_message:
        msg = f"{msg} {extra_message}".strip()
    return WorkflowStep(
        step_id=step_id,
        name=name,
        model_id=model_id,
        status=str(adapter_result.status),
        message=msg,
        command_preview=adapter_result.command_preview,
        env_preview=dict(adapter_result.env_preview),
        artifacts=dict(adapter_result.artifacts),
        expected_artifacts=dict(adapter_result.artifacts),
        blocked_reason=blocked_reason,
    )


def _path_within_allowed_roots(path: Path) -> bool:
    """Return True if *path* is under one of the allowed download roots."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in ALLOWED_DOWNLOAD_ROOTS:
        try:
            if resolved == root.resolve() or root.resolve() in resolved.parents:
                return True
        except OSError:
            continue
    return False


def persist_latest_workflow_result(result: TargetDesignWorkflowResult) -> None:
    """Persist the most recent dry-run result so export endpoints can serve it."""
    WORKFLOW_ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    # Write as JSON so it can be re-loaded by Pydantic.
    LATEST_DRY_RUN_CACHE.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )


def load_workflow_result(workflow_id: str) -> TargetDesignWorkflowResult | None:
    """Load a cached workflow result.

    Supports the special workflow_id ``latest`` to retrieve the most recently
    persisted dry-run result.
    """
    if workflow_id == "latest":
        if not LATEST_DRY_RUN_CACHE.exists():
            return None
        data = json.loads(LATEST_DRY_RUN_CACHE.read_text(encoding="utf-8"))
        return TargetDesignWorkflowResult.model_validate(data)

    if not LATEST_DRY_RUN_CACHE.exists():
        return None
    data = json.loads(LATEST_DRY_RUN_CACHE.read_text(encoding="utf-8"))
    if data.get("workflow_id") != workflow_id:
        return None
    return TargetDesignWorkflowResult.model_validate(data)


def generate_workflow_json_report(result: TargetDesignWorkflowResult) -> dict[str, object]:
    """Generate a structured JSON report from a workflow dry-run result."""
    return {
        "workflow_id": result.workflow_id,
        "workflow_type": result.workflow_type,
        "created_at": _now(),
        "dry_run": True,
        "target_sequence_summary": {
            "length": len(result.prior_artifacts_referenced.get("target_sequence", "")),
            "preview": (result.prior_artifacts_referenced.get("target_sequence", "")[:60] + "...")
            if len(result.prior_artifacts_referenced.get("target_sequence", "")) > 60
            else result.prior_artifacts_referenced.get("target_sequence", ""),
        },
        "generator_model": "pepmlm",
        "ranker_model": "pepprclip",
        "structure_model": "evobind2",
        "status": result.status,
        "message": result.message,
        "steps": [
            {
                "step_id": step.step_id,
                "name": step.name,
                "model_id": step.model_id,
                "status": step.status,
                "message": step.message,
                "blocked_reason": step.blocked_reason,
                "command_preview": step.command_preview,
                "expected_artifacts": step.expected_artifacts,
            }
            for step in result.steps
        ],
        "artifact_references": [
            {
                "label": ref.label,
                "model_id": ref.model_id,
                "job_id": ref.job_id,
                "artifact_name": ref.artifact_name,
                "artifact_path": ref.artifact_path,
                "status": ref.status,
                "reason": ref.reason,
                "validation_status": ref.validation_status,
                "download_url": ref.download_url,
            }
            for ref in result.artifact_references
        ],
        "expected_artifacts": result.expected_artifacts,
        "blocked_reasons": result.blocked_reasons,
        "safety_flags": result.safety_flags.model_dump(),
        "scientific_boundary": result.scientific_boundary,
        "validation_status": result.validation_status,
        "report_disclaimer": (
            "This is a workflow dry-run report. No model was executed. "
            "No peptide candidates, ranking scores, or structures were generated."
        ),
    }


def generate_workflow_markdown_report(result: TargetDesignWorkflowResult) -> str:
    """Generate a Markdown report from a workflow dry-run result."""
    target_sequence = result.prior_artifacts_referenced.get("target_sequence", "")
    lines: list[str] = [
        "# Target-Design Workflow Dry-Run Report",
        "",
        "**Report ID:** `{workflow_id}`".format(workflow_id=result.workflow_id),
        f"**Generated at:** {_now()}",
        "**Dry run:** `true`",
        "",
        "## Target sequence summary",
        "",
        f"- Length: {len(target_sequence)}",
        f"- Preview: `{target_sequence[:80]}{'...' if len(target_sequence) > 80 else ''}`",
        "",
        "## Workflow configuration",
        "",
        "| Key | Value |",
        "|---|---|",
        "| generator_model | pepmlm |",
        "| ranker_model | pepprclip |",
        "| structure_model | evobind2 |",
        f"| status | {result.status} |",
        "",
        "## Steps",
        "",
        "| # | Step | Model | Status | Blocked reason |",
        "|---|---|---|---|---|",
    ]
    for step in result.steps:
        blocked = step.blocked_reason or "—"
        lines.append(
            f"| {step.step_id} | {step.name} | {step.model_id} | {step.status} | {blocked} |"
        )

    lines.extend([
        "",
        "## Artifact references",
        "",
        "| Label | Model | Artifact | Status | Download |",
        "|---|---|---|---|---|",
    ])
    for ref in result.artifact_references:
        download = "Available" if ref.download_url and ref.status == "Exists" else ref.status
        lines.append(
            f"| {ref.label} | {ref.model_id} | {ref.artifact_name} | {ref.status} | {download} |"
        )

    lines.extend([
        "",
        "## Expected artifacts",
        "",
        "| Key | Path |",
        "|---|---|",
    ])
    for key, value in result.expected_artifacts.items():
        lines.append(f"| {key} | {value or '—'} |")

    lines.extend([
        "",
        "## Blocked reasons",
        "",
    ])
    if result.blocked_reasons:
        for reason in result.blocked_reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Safety flags",
        "",
    ])
    flags = result.safety_flags.model_dump()
    for key, value in flags.items():
        lines.append(f"- {key}: {value}")

    lines.extend([
        "",
        "## Scientific boundary",
        "",
        result.scientific_boundary,
        "",
        "- No Kd, MIC, MM-GBSA, ipTM, pLDDT, RMSD, or RMSF is reported.",
        "- No experimental validation has been performed.",
        "- Ranking scores are not binding affinities.",
        "",
        "## Disclaimer",
        "",
        "This report is generated from a workflow dry-run. No model was executed, "
        "no new peptide candidates were generated, no real ranking was produced, "
        "and no new structure was generated.",
        "",
    ])
    return "\n".join(lines)


def resolve_workflow_artifact_path(artifact_ref: str) -> Path | None:
    """Resolve a whitelisted artifact_ref to an absolute file path.

    Returns ``None`` if the ref is unknown, not on the whitelist, or would
    escape the allowed download roots.
    """
    ref = artifact_ref.strip()
    if not ref:
        return None
    if ".." in ref or "/" in ref or "\\" in ref:
        return None
    path = DOWNLOADABLE_ARTIFACTS.get(ref)
    if path is None:
        return None
    if not path.exists():
        return None
    if not _path_within_allowed_roots(path):
        return None
    return path


def build_target_design_dry_run(
    payload: TargetDesignWorkflowPayload,
) -> TargetDesignWorkflowResult:
    """Return a dry-run plan for the full target-design workflow."""
    workflow_id = f"{WORKFLOW_ID_PREFIX}_{uuid.uuid4().hex[:12]}"
    blocked_reasons: list[str] = []

    # Stash the raw target sequence so report export can show a summary.
    target_sequence = payload.target_sequence

    prior_artifacts_referenced: dict[str, Optional[str]] = {
        "target_sequence": target_sequence,
        "pepmlm_p5c_job_id": P5C_PEPMLM_JOB_ID,
        "pepmlm_p5c_artifact_root": (
            "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/"
            f"data_dev/artifacts/pepmlm/{P5C_PEPMLM_JOB_ID}"
        ),
        "evobind2_p3b_job_id": P3B_EVOBIND2_JOB_ID,
        "evobind2_p3b_pdb_relative": P3B_EVOBIND2_PDB_REL,
        "evobind2_p3b_pdb_absolute": (
            "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/"
            + P3B_EVOBIND2_PDB_REL
        ),
    }

    if payload.generator_model != "pepmlm":
        blocked_reasons.append(
            f"Generator model '{payload.generator_model}' is not supported in P7A; "
            "only pepmlm is supported."
        )
    if payload.ranker_model != "pepprclip":
        blocked_reasons.append(
            f"Ranker model '{payload.ranker_model}' is not supported in P7A; "
            "only pepprclip is supported."
        )
    if payload.structure_model != "evobind2":
        blocked_reasons.append(
            f"Structure model '{payload.structure_model}' is not supported in P7A; "
            "only evobind2 is supported."
        )

    steps: list[WorkflowStep] = []

    # Step 1: PepMLM candidate generation (dry-run only)
    pepmlm_payload = ModelDryRunPayload(
        target_sequence=payload.target_sequence,
        peptide_length=payload.peptide_length,
        num_candidates=payload.num_candidates,
        dry_run=True,
    )
    pepmlm_result = PepMLMAdapter("pepmlm").dry_run(pepmlm_payload)
    steps.append(
        _step_from_adapter_result(
            "step_1", "PepMLM candidate generation", "pepmlm", pepmlm_result
        )
    )

    # Step 2: PepPrCLIP ranking (dry-run only)
    placeholder_candidates = ["AAAAAA", "GGGGGG", "KKKKKK"]
    pepprclip_payload = ModelDryRunPayload(
        target_sequence=payload.target_sequence,
        candidate_peptides=placeholder_candidates,
        top_k=payload.top_k,
        dry_run=True,
    )
    pepprclip_result = PepPrCLIPAdapter("pepprclip").dry_run(pepprclip_payload)
    checkpoint_missing = not PEPPRCLIP_CHECKPOINT.exists()
    pepprclip_extra = ""
    pepprclip_blocked_reason: Optional[str] = None
    if checkpoint_missing:
        pepprclip_extra = "MiniCLIP checkpoint is missing; real ranking remains gated."
        pepprclip_blocked_reason = (
            "BLOCKED_LICENSE_OR_TOKEN_REQUIRED: MiniCLIP checkpoint missing"
        )
        blocked_reasons.append("MiniCLIP checkpoint missing")
    steps.append(
        _step_from_adapter_result(
            "step_2",
            "PepPrCLIP ranking",
            "pepprclip",
            pepprclip_result,
            pepprclip_extra,
            pepprclip_blocked_reason,
        )
    )

    # Step 3: EvoBind2 structure prediction (dry-run only)
    evobind2_payload = ModelDryRunPayload(
        target_sequence=payload.target_sequence,
        peptide_length=payload.peptide_length,
        model_name="model_1_ptm",
        max_recycles=1,
        num_iterations=1,
        dry_run=True,
    )
    evobind2_result = EvoBind2Adapter("evobind2").dry_run(evobind2_payload)
    steps.append(
        _step_from_adapter_result(
            "step_3",
            "EvoBind2 structure prediction",
            "evobind2",
            evobind2_result,
            "Real execution is gated.",
        )
    )

    # Step 4: Molstar visualization (no model execution)
    molstar_artifacts = {
        "pdb_url": (
            f"/api/v1/models/evobind2/jobs/{P3B_EVOBIND2_JOB_ID}/"
            "artifacts/unrelaxed_true.pdb/download"
        ),
        "viewer_path": "/target-design",
    }
    steps.append(
        WorkflowStep(
            step_id="step_4",
            name="Molstar visualization",
            model_id="molstar",
            status="READY",
            message=(
                "Molstar viewer can load the referenced EvoBind2 P3B PDB artifact "
                "(dry-run only; no new structure generated)."
            ),
            command_preview=None,
            env_preview={},
            artifacts=molstar_artifacts,
        )
    )

    expected_artifacts: dict[str, Optional[str]] = {
        "pepmlm/output/candidate_sequences.csv": pepmlm_result.artifacts.get(
            "output/candidate_sequences.csv"
        ),
        "pepmlm/output/candidate_sequences.json": pepmlm_result.artifacts.get(
            "output/candidate_sequences.json"
        ),
        "pepprclip/output/ranking.csv": pepprclip_result.artifacts.get("output/ranking.csv"),
        "pepprclip/output/scores.json": pepprclip_result.artifacts.get("output/scores.json"),
        "evobind2/output/unrelaxed_true.pdb": evobind2_result.artifacts.get("pdb"),
        "manifest/workflow_lineage.json": str(
            WORKFLOW_ARTIFACT_ROOT / workflow_id / "manifest" / "workflow_lineage.json"
        ),
        "logs/workflow.log": str(WORKFLOW_ARTIFACT_ROOT / workflow_id / "logs" / "workflow.log"),
    }

    p5c_root = prior_artifacts_referenced["pepmlm_p5c_artifact_root"]
    p3b_pdb_abs = prior_artifacts_referenced["evobind2_p3b_pdb_absolute"]
    artifact_references = [
        WorkflowArtifactReference(
            label="P5C PepMLM candidates CSV",
            model_id="pepmlm",
            job_id=P5C_PEPMLM_JOB_ID,
            artifact_name="candidate_sequences.csv",
            artifact_path=f"{p5c_root}/output/candidate_sequences.csv",
            status="Exists",
            reason="Historical P5C artifact reference; not regenerated in P7B.",
            download_url="/api/v1/workflows/target-design/artifacts/p5c-candidates-csv/download",
        ),
        WorkflowArtifactReference(
            label="P5C PepMLM candidates JSON",
            model_id="pepmlm",
            job_id=P5C_PEPMLM_JOB_ID,
            artifact_name="candidate_sequences.json",
            artifact_path=f"{p5c_root}/output/candidate_sequences.json",
            status="Exists",
            reason="Historical P5C artifact reference; not regenerated in P7B.",
            download_url="/api/v1/workflows/target-design/artifacts/p5c-candidates-json/download",
        ),
        WorkflowArtifactReference(
            label="P6B/P7A PepPrCLIP ranking CSV",
            model_id="pepprclip",
            artifact_name="ranking.csv",
            artifact_path=expected_artifacts["pepprclip/output/ranking.csv"],
            status="Blocked",
            reason="MiniCLIP checkpoint missing / BLOCKED_LICENSE_OR_TOKEN_REQUIRED; ranking.csv not generated.",
        ),
        WorkflowArtifactReference(
            label="P6B/P7A PepPrCLIP scores JSON",
            model_id="pepprclip",
            artifact_name="scores.json",
            artifact_path=expected_artifacts["pepprclip/output/scores.json"],
            status="Blocked",
            reason="MiniCLIP checkpoint missing / BLOCKED_LICENSE_OR_TOKEN_REQUIRED; scores.json not generated.",
        ),
        WorkflowArtifactReference(
            label="P3B EvoBind2 PDB",
            model_id="evobind2",
            job_id=P3B_EVOBIND2_JOB_ID,
            artifact_name="unrelaxed_true.pdb",
            artifact_path=p3b_pdb_abs,
            status="Exists",
            reason="Historical P3B artifact reference; Molstar can load this PDB.",
            download_url="/api/v1/workflows/target-design/artifacts/p3b-pdb/download",
        ),
        WorkflowArtifactReference(
            label="Workflow lineage manifest",
            model_id="workflow",
            artifact_name="workflow_lineage.json",
            artifact_path=expected_artifacts["manifest/workflow_lineage.json"],
            status="Expected",
            reason="Dry-run plan only; manifest path is previewed but not written.",
        ),
    ]

    status = "READY" if not blocked_reasons else "BLOCKED_WITH_NOTES"
    message = "Target-design workflow dry-run skeleton is ready."
    if blocked_reasons:
        message += " Blocked notes: " + "; ".join(blocked_reasons)

    result = TargetDesignWorkflowResult(
        workflow_id=workflow_id,
        workflow_type="target-design",
        status=status,
        message=message,
        steps=steps,
        expected_artifacts=expected_artifacts,
        safety_flags=_base_safety_flags(),
        validation_status="NOT_EXPERIMENTALLY_VALIDATED",
        scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        blocked_reasons=blocked_reasons,
        prior_artifacts_referenced=prior_artifacts_referenced,
        artifact_references=artifact_references,
    )

    # Persist the latest dry-run result for report export endpoints.
    try:
        persist_latest_workflow_result(result)
    except OSError:
        # Persistence is best-effort; dry-run itself must still succeed.
        pass

    return result
