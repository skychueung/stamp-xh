"""Unified Model Registry for the Targeted Peptide Design Center (P4A).

This registry decouples model metadata from adapter implementations so that
new peptide design models can be registered behind a common interface without
changing the frontend or the main API contract.

Backwards compatibility: the P2/P3 Targeted Peptide Design Center endpoints
still use ``list_target_peptide_models`` and ``get_target_peptide_model``.
Those names are preserved and return entries containing both the legacy
fields (input_type, requires_structure, requires_gpu) and the new P4A
capability fields (supports_probe, supports_dry_run, ...).
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

SCIENTIFIC_BOUNDARY_NOTE = (
    "Targeted Peptide Design Center P4A registers models, adapter metadata, "
    "and empty or previously-generated artifacts. It does not run any model "
    "in this phase, does not generate new candidates, and does not claim "
    "experimental validation."
)

# Model statuses
MODEL_STATUS_AVAILABLE = "available"
MODEL_STATUS_NOT_CONNECTED = "not_connected"
MODEL_STATUS_PLANNED = "planned"
MODEL_STATUS_DISABLED = "disabled"
MODEL_STATUS_PARKED = "parked"
MODEL_STATUS_PENDING_PROBE = "pending_probe"
MODEL_STATUS_PENDING_REGISTRY = "pending_registry"
MODEL_STATUS_SMOKE_RERUN_VERIFIED = "smoke_rerun_verified"
MODEL_STATUS_CONTROLLED_SMOKE_VERIFIED = "controlled_smoke_verified"

# Model categories
CATEGORY_STRUCTURE_PREDICTION = "structure_prediction"
CATEGORY_PEPTIDE_DESIGN = "peptide_design"
CATEGORY_SEQUENCE_GENERATION = "sequence_generation"
CATEGORY_RANKING = "ranking"
CATEGORY_STRUCTURE_CONDITIONED_DESIGN = "structure_conditioned_design"
CATEGORY_FLOW_BASED_DESIGN = "flow_based_design"
CATEGORY_DIFFUSION_BASED_DESIGN = "diffusion_based_design"
CATEGORY_GRAPH_CONDITIONED_DESIGN = "graph_conditioned_design"
CATEGORY_HIERARCHICAL_DESIGN = "hierarchical_design"
CATEGORY_CLASSICAL_ML_DESIGN = "classical_ml_design"

# Output artifact types
ARTIFACT_PDB = "pdb"
ARTIFACT_METRICS_CSV = "metrics_csv"
ARTIFACT_LOGS = "logs"
ARTIFACT_MANIFEST = "manifest"
ARTIFACT_INPUT = "input"

# P33K product-group classification for UI governance (display-only)
_PRODUCT_GROUP_AVAILABLE_FIVE: frozenset[str] = frozenset({
    "pepmlm",
    "evobind2",
    "diffpepbuilder",
    "pepflow",
    "pephar",
})
_PRODUCT_GROUP_BLOCKED: frozenset[str] = frozenset({"ppflow"})
_PRODUCT_GROUP_BACKLOG: frozenset[str] = frozenset({"pepprclip", "pepglad", "rfpeptides"})


# P32A readiness metadata (display-only, does not overwrite canonical stage)
_READINESS_META: dict[str, dict[str, Any]] = {
    "evobind2": {
        "readiness_gate": "P3B_REAL_SMOKE_GO_WITH_NOTES / P3C_WORKER_HARDENING_ARTIFACT_UI_CLOSED",
        "readiness_level": "controlled_smoke_verified",
        "blocker_code": "REAL_RUN_GATE_CLOSED",
        "next_authorization": "NEW_EXPLICIT_AUTH_REQUIRED_FOR_ANY_FUTURE_EXECUTION",
        "evidence_ref": "EVOBIND2_P3B_REAL_SMOKE_RUN_CONTROLLED_EXECUTION_REPORT.md / EVOBIND2_P3C_WORKER_HARDENING_ARTIFACT_UI_AND_POST_RUN_AUDIT_REPORT.md",
        "last_verified_at": "2026-06-12T00:00:00+00:00",
        "evidence": {
            "availability": "partial",
            "stats": None,
        },
    },
    "pepmlm": {
        "readiness_gate": "P30B_SMOKE_RERUN_GO",
        "readiness_level": "smoke_rerun_verified",
        "blocker_code": "REAL_RUN_GATE_CLOSED",
        "next_authorization": "explicit gate open required",
        "evidence_ref": "STAMP_PEPMLM_SMOKE_RERUN_FIRST_REAL_MODEL_P30B_REPORT.md",
        "evidence": {
            "availability": "available",
            "stats": {"exit_code": 0, "candidate_count": 3},
        },
    },
    "pepprclip": {
        "readiness_gate": "P0_8MODEL",
        "readiness_level": "pending_probe",
        "blocker_code": "MINICLIP_CHECKPOINT_LICENSE_TOKEN",
        "next_authorization": "MiniCLIP checkpoint + HF token/license",
        "evidence_ref": "STAMP_P31D1_REGISTRY_LIVE_STATE_SYNC_REPORT.md",
    },
    "rfpeptides": {
        "readiness_gate": "P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED",
        "readiness_level": "pending_probe",
        "blocker_code": "REAL_RUN_GATE_CLOSED",
        "next_authorization": "NEW_EXPLICIT_AUTH_REQUIRED_FOR_ANY_FUTURE_EXECUTION",
        "evidence_ref": "STAMP_P33J_OUT_OF_SCOPE_ARTIFACT_CLASSIFICATION_MANIFEST.json / STAMP_P33I_P33H_DELIVERY_RECLASSIFICATION_REPORT.md",
        "last_verified_at": "2026-06-28T23:53:00+00:00",
    },
    "pepflow": {
        "readiness_gate": "P32B_THREE_MODEL_CONTROLLED_EXECUTION_DELIVERED",
        "readiness_level": "controlled_smoke_verified",
        "blocker_code": "REAL_RUN_GATE_CLOSED",
        "next_authorization": "NEW_EXPLICIT_AUTH_REQUIRED_FOR_ANY_FUTURE_EXECUTION",
        "evidence_ref": "STAMP_P32B_DELIVERY_MANIFEST.json",
        "last_verified_at": "2026-06-27T19:14:29+00:00",
        "evidence": {
            "availability": "partial",
            "stats": None,
        },
    },
    "pephar": {
        "readiness_gate": "P32B_THREE_MODEL_CONTROLLED_EXECUTION_DELIVERED",
        "readiness_level": "controlled_smoke_verified",
        "blocker_code": "REAL_RUN_GATE_CLOSED",
        "next_authorization": "NEW_EXPLICIT_AUTH_REQUIRED_FOR_ANY_FUTURE_EXECUTION",
        "evidence_ref": "STAMP_P32B_DELIVERY_MANIFEST.json",
        "last_verified_at": "2026-06-27T19:14:29+00:00",
        "evidence": {
            "availability": "partial",
            "stats": None,
        },
    },
    "diffpepbuilder": {
        "readiness_gate": "P32B_THREE_MODEL_CONTROLLED_EXECUTION_DELIVERED",
        "readiness_level": "controlled_smoke_verified",
        "blocker_code": "REAL_RUN_GATE_CLOSED",
        "next_authorization": "NEW_EXPLICIT_AUTH_REQUIRED_FOR_ANY_FUTURE_EXECUTION",
        "evidence_ref": "STAMP_P32B_DELIVERY_MANIFEST.json",
        "last_verified_at": "2026-06-27T19:14:29+00:00",
        "evidence": {
            "availability": "partial",
            "stats": None,
        },
    },
    "ppflow": {
        "readiness_gate": "P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS",
        "readiness_level": "controlled_smoke_verified",
        "blocker_code": "REAL_RUN_GATE_CLOSED",
        "next_authorization": "NEW_EXPLICIT_AUTH_REQUIRED_FOR_ANY_FUTURE_EXECUTION",
        "evidence_ref": "STAMP_P33O_PPFLOW_PATH_REPAIR_SUCCESS_REPORT.md / p33o_ppflow_path_repair_20260629_063127/manifest.json",
        "last_verified_at": "2026-06-29T06:41:17+08:00",
        "evidence": {
            "availability": "available",
            "stats": {
                "exit_code": 0,
                "elapsed_seconds": 588.4605281352997,
                "sample_dirs": 133,
                "file_count": 404,
                "artifact_bytes": 4408281,
            },
            "success_report": "reports/p33o_ppflow_repair/STAMP_P33O_PPFLOW_PATH_REPAIR_SUCCESS_REPORT.md",
            "execution_manifest": "reports/p33o_ppflow_repair/STAMP_P33O_PPFLOW_PATH_REPAIR_EXECUTION_MANIFEST.md",
            "result_manifest": "/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33o_ppflow_path_repair_20260629_063127/manifest.json",
            "status": "/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33o_ppflow_path_repair_20260629_063127/status.json",
            "artifact_dir": "/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33o_ppflow_path_repair_20260629_063127/",
            "sha256": {
                "success_report": "8f6519e85ce6f7936794ed5d580fe2c7ef52dadff6c6643770d19c0eb873f293",
                "execution_manifest": "1c3cfe85a35989f4deef44305186eb1683336c2900a9e5c43e24c8e0729ec307",
                "result_manifest": "6d14f2f56f927d5130099d88e3993534a8662b88e43394cbc36de93a5a006a00",
                "status": "3ffca90345575290cf9fccfbfb3997799631c7834e5f1a94c0e7f520c18628d8",
            },
            "exit_code": 0,
            "elapsed_seconds": 588.4605281352997,
            "sample_dirs": 133,
            "file_count": 404,
            "artifact_bytes": 4408281,
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        },
    },
    "pepglad": {
        "readiness_gate": "P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED",
        "readiness_level": "pending_probe",
        "blocker_code": "REAL_RUN_GATE_CLOSED",
        "next_authorization": "NEW_EXPLICIT_AUTH_REQUIRED_FOR_ANY_FUTURE_EXECUTION",
        "evidence_ref": "STAMP_P33J_OUT_OF_SCOPE_ARTIFACT_CLASSIFICATION_MANIFEST.json / STAMP_P33I_P33H_DELIVERY_RECLASSIFICATION_REPORT.md",
        "last_verified_at": "2026-06-28T23:53:00+00:00",
    },
}


def _derive_product_group(model_id: str) -> str:
    mid = model_id.lower().strip()
    if mid in _PRODUCT_GROUP_AVAILABLE_FIVE:
        return "available_five"
    if mid in _PRODUCT_GROUP_BLOCKED:
        return "blocked"
    if mid in _PRODUCT_GROUP_BACKLOG:
        return "backlog"
    return "unknown"


def _derive_ui_execution_state(product_group: str) -> str:
    if product_group == "available_five":
        return "closed_available"
    if product_group == "blocked":
        return "license_blocked"
    if product_group == "backlog":
        return "backlog"
    return "unknown"


def _derive_ui_selectable(product_group: str) -> bool:
    return product_group == "available_five"


def _derive_activation_requirements(model_id: str, product_group: str) -> str:
    mid = model_id.lower().strip()
    if product_group == "available_five":
        return "dev only; auth required; run_id + gate JSON required; GPU usage warning; never production 8001/8080"
    if mid == "ppflow":
        return "no upstream LICENSE / authorization unclear"
    if product_group == "backlog":
        return "not closed; roadmap only"
    return "explicit authorization required"


def _derive_delivery_status(model_id: str, product_group: str) -> str:
    mid = model_id.lower().strip()
    if product_group == "available_five":
        return "closed"
    if mid == "ppflow":
        return "blocked_license"
    if product_group == "backlog":
        return "backlog_pending"
    return "unknown"


def _enrich_readiness_fields(model: dict[str, object]) -> dict[str, object]:
    """Add display-only readiness and product-group fields without overwriting canonical stage."""
    meta = _READINESS_META.get(str(model.get("model_id", "")), {})
    enriched = dict(model)
    enriched["readiness_gate"] = meta.get("readiness_gate", model.get("stage", "P4A"))
    enriched["readiness_level"] = meta.get("readiness_level", model.get("status", "unknown"))
    enriched["execution_locked"] = not bool(model.get("real_run_enabled", False))
    enriched["blocker_code"] = meta.get("blocker_code", "UNKNOWN")
    enriched["next_authorization"] = meta.get("next_authorization", "explicit authorization required")
    enriched["last_verified_at"] = meta.get("last_verified_at", _iso_now())
    enriched["evidence_ref"] = meta.get("evidence_ref", "")
    enriched["evidence"] = meta.get("evidence", {})
    enriched["validation_status"] = model.get("validation_status", "NOT_EXPERIMENTALLY_VALIDATED")

    # P33K product-group UI governance fields (derived, but allow explicit per-entry override)
    model_id = str(model.get("model_id", ""))
    product_group = enriched.get("product_group") or _derive_product_group(model_id)
    enriched["product_group"] = product_group
    enriched["ui_selectable"] = enriched.get("ui_selectable", _derive_ui_selectable(product_group))
    enriched["ui_execution_state"] = enriched.get("ui_execution_state", _derive_ui_execution_state(product_group))
    enriched["activation_requirements"] = enriched.get(
        "activation_requirements", _derive_activation_requirements(model_id, product_group)
    )
    enriched["delivery_status"] = enriched.get("delivery_status", _derive_delivery_status(model_id, product_group))
    if product_group == "available_five":
        enriched.update(status="closed", status_reason="d18_authoritative_closed", readiness_level="closed", blocker_code=None)
    elif product_group == "blocked":
        enriched.update(status="blocked_license", status_reason="no upstream LICENSE / authorization unclear", readiness_level="blocked_license", blocker_code="LICENSE_BLOCKED", supports_probe=False, supports_dry_run=False, supports_real_run=False, real_run_enabled=False, execution_locked=True)
    elif product_group == "backlog":
        enriched.update(status="backlog", status_reason="not closed; roadmap only", readiness_level="backlog", blocker_code="NOT_CLOSED", supports_probe=False, supports_dry_run=False, supports_real_run=False, real_run_enabled=False, execution_locked=True)
    return enriched


def _evobind2_description() -> str:
    return (
        "EvoBind2 (controlled_smoke_verified): sequence-based blind peptide binder design. "
        "P3B real smoke run completed on GPU with mc_design.py; P3C worker hardening, artifact UI "
        "and post-run audit closed. Real execution remains gated."
    )


def _placeholder_description(name: str, status: str) -> str:
    return f"{name} ({status}); no runtime path yet in this phase."


_MODEL_REGISTRY: list[dict[str, object]] = [
    {
        # Legacy P2/P3 fields
        "model_id": "evobind2",
        "display_name": "EvoBind2",
        "category": f"{CATEGORY_STRUCTURE_PREDICTION} / {CATEGORY_PEPTIDE_DESIGN}",
        "input_type": "target_sequence_plus_structure",
        "status": MODEL_STATUS_CONTROLLED_SMOKE_VERIFIED,
        "status_reason": "p3b_real_smoke_verified_gate_closed",
        "stage": "P3B_CONTROLLED_SMOKE_OK",
        "description": _evobind2_description(),
        "requires_structure": True,
        "requires_gpu": True,
        "notes": (
            "P3B: real smoke run succeeded (job b8ab6d11-5762-4bdf-a9db-6d30602637fd); "
            "mc_design.py executed on GPU, produced unrelaxed_true.pdb and metrics.csv. "
            "P3C: worker hardened, artifact metadata/download endpoints hardened, frontend artifact UI added, "
            "post-run audit confirmed no residual processes and gate closed. "
            "All outputs NOT_EXPERIMENTALLY_VALIDATED. Real execution requires new explicit authorization."
        ),
        # P4A capability fields
        "supports_probe": True,
        "supports_dry_run": True,
        "supports_real_run": False,
        "supports_structure_output": True,
        "supports_sequence_output": False,
        "supports_ranking": False,
        "output_artifact_types": [ARTIFACT_PDB, ARTIFACT_METRICS_CSV, ARTIFACT_LOGS, ARTIFACT_MANIFEST, ARTIFACT_INPUT],
        "adapter_id": "evobind2",
        "real_run_enabled": False,
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "safety_note": (
            "EvoBind2 outputs are computational predictions only. "
            "NOT_EXPERIMENTALLY_VALIDATED. No Kd, MIC, MM-GBSA, ipTM, pLDDT, RMSD, or RMSF "
            "is an experimental measurement."
        ),
        "validation_policy": (
            "All EvoBind2 outputs must be labelled NOT_EXPERIMENTALLY_VALIDATED. "
            "Real execution requires explicit gate open, manual review, and must not be "
            "represented as experimental validation."
        ),
    },
    {
        "model_id": "pepmlm",
        "display_name": "PepMLM",
        "category": CATEGORY_SEQUENCE_GENERATION,
        "input_type": "target_sequence",
        "status": MODEL_STATUS_SMOKE_RERUN_VERIFIED,
        "status_reason": "p30b_smoke_rerun_verified_gate_closed",
        "stage": "P30B_SMOKE_RERUN_GO",
        "description": (
            "PepMLM masked-language-model peptide sequence generator. "
            "P30B smoke rerun verified on CUDA (RTX 4090) with 3 candidates; "
            "real-run gate remains CLOSED."
        ),
        "requires_structure": False,
        "requires_gpu": True,
        "notes": (
            "P30B smoke rerun verified: job ac90e622-492d-4697-a8fa-ce35b2d2bfc5 succeeded "
            "on CUDA RTX 4090, 3 candidates generated, gate CLOSED. "
            "P30D registered PepMLM to model-registry with smoke_rerun_verified probe. "
            "Real execution remains gated (gate CLOSED)."
        ),
        "supports_probe": True,
        "supports_dry_run": True,
        "supports_real_run": True,
        "supports_structure_output": False,
        "supports_sequence_output": True,
        "supports_ranking": False,
        "output_artifact_types": ["sequence_csv", "sequence_json", "logs", "manifest", "input"],
        "adapter_id": "pepmlm",
        "real_run_enabled": False,
        "safety_note": "PepMLM outputs are computational predictions only. NOT_EXPERIMENTALLY_VALIDATED. Generated candidates are model outputs, not experimentally validated peptides.",
        "validation_policy": "All PepMLM outputs must be labelled NOT_EXPERIMENTALLY_VALIDATED. Real execution requires explicit gate open, manual review, and must not be represented as experimental validation.",
    },
    {
        "model_id": "pepprclip",
        "display_name": "PepPrCLIP",
        "category": CATEGORY_RANKING,
        "input_type": "target_sequence_plus_candidates",
        "status": MODEL_STATUS_PENDING_PROBE,
        "status_reason": "pending_probe_miniclip_checkpoint_blocked",
        "stage": "P0_8MODEL",
        "description": (
            "PepPrCLIP (pending_probe): peptide-protein contrastive ranking / generation. "
            "Ranks candidate peptides against a target protein using ESM-2 650M embeddings "
            "and a MiniCLIP encoder."
        ),
        "requires_structure": False,
        "requires_gpu": True,
        "notes": (
            "Re-classified to pending_probe in STAMP_8_MODEL_TRACK_AFTER_PEPMLM_PARK_P0. "
            "Source and conda env are ready, ESM-2 loads from cache, but MiniCLIP checkpoint "
            "is not available (HuggingFace license/token required and outbound HTTPS unavailable). "
            "Real ranking remains gated."
        ),
        "supports_probe": True,
        "supports_dry_run": True,
        "supports_real_run": True,
        "supports_structure_output": False,
        "supports_sequence_output": False,
        "supports_ranking": True,
        "output_artifact_types": ["ranking_csv", "scores_json", "logs", "manifest", "input"],
        "adapter_id": "pepprclip",
        "real_run_enabled": False,
        "safety_note": "PepPrCLIP outputs are computational rankings only. NOT_EXPERIMENTALLY_VALIDATED. clip_score is not Kd, MIC, or experimental binding affinity.",
        "validation_policy": "All PepPrCLIP outputs must be labelled NOT_EXPERIMENTALLY_VALIDATED. Real execution requires explicit gate open, MiniCLIP checkpoint availability, manual review, and must not be represented as experimental validation.",
    },
    {
        "model_id": "rfpeptides",
        "display_name": "RFpeptides",
        "category": CATEGORY_STRUCTURE_CONDITIONED_DESIGN,
        "input_type": "target_sequence",
        "status": MODEL_STATUS_PENDING_PROBE,
        "status_reason": "p33i_out_of_scope_execution_evidence_preserved",
        "stage": "P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED",
        "description": "RFpeptides (pending_probe): RFdiffusion macrocyclic peptide binder design. The previous P33H controlled_smoke_verified status is reclassified because the success artifact 225850 depended on the out-of-scope PepGLAD execution chain and unauthorized e3nn/SE3Transformer source modifications. Preserved only as engineering/audit evidence.",
        "requires_structure": False,
        "requires_gpu": True,
        "notes": "P33I audit confirmed out-of-scope execution: RFpeptides was triggered after the unauthorized PepGLAD 225316 success and included unauthorized e3nn/SE3Transformer source patches. The 225850 artifact is preserved as out-of-scope engineering evidence only. All outputs NOT_EXPERIMENTALLY_VALIDATED. A new compliant controlled smoke requires fresh authorization and a new run_id.",
        "supports_probe": True,
        "supports_dry_run": True,
        "supports_real_run": False,
        "supports_structure_output": False,
        "supports_sequence_output": True,
        "supports_ranking": False,
        "output_artifact_types": [],
        "adapter_id": "rfpeptides",
        "real_run_enabled": False,
        "safety_note": "RFpeptides outputs are computational predictions only. NOT_EXPERIMENTALLY_VALIDATED. Generated sequences are model outputs, not experimentally validated peptides.",
        "validation_policy": "All RFpeptides outputs must be labelled NOT_EXPERIMENTALLY_VALIDATED. Real execution requires explicit gate open, manual review, and must not be represented as experimental validation.",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
    },
    {
        "model_id": "pepflow",
        "display_name": "PepFlow",
        "category": CATEGORY_FLOW_BASED_DESIGN,
        "input_type": "target_sequence_plus_structure",
        "status": MODEL_STATUS_CONTROLLED_SMOKE_VERIFIED,
        "status_reason": "p32b_controlled_smoke_verified",
        "stage": "P32B_CONTROLLED_SMOKE_OK",
        "description": "PepFlow (controlled_smoke_verified): full-atom multimodal flow-matching peptide design. P32B 3-step dummy sample completed; real execution remains gated.",
        "requires_structure": True,
        "requires_gpu": True,
        "notes": "P32B: 3-step dummy sample SUCCESS, exit code 0, manifest verified. All outputs NOT_EXPERIMENTALLY_VALIDATED. Real execution requires new explicit authorization.",
        "supports_probe": True,
        "supports_dry_run": True,
        "supports_real_run": False,
        "supports_structure_output": False,
        "supports_sequence_output": True,
        "supports_ranking": False,
        "output_artifact_types": [],
        "adapter_id": "pepflow",
        "real_run_enabled": False,
        "safety_note": "PepFlow outputs are computational predictions only. NOT_EXPERIMENTALLY_VALIDATED. Generated sequences are model outputs, not experimentally validated peptides.",
        "validation_policy": "All PepFlow outputs must be labelled NOT_EXPERIMENTALLY_VALIDATED. Real execution requires explicit gate open, manual review, and must not be represented as experimental validation.",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
    },
    {
        "model_id": "pepglad",
        "display_name": "PepGLAD",
        "category": CATEGORY_GRAPH_CONDITIONED_DESIGN,
        "input_type": "target_structure_plus_pocket",
        "status": MODEL_STATUS_PENDING_PROBE,
        "status_reason": "p33i_out_of_scope_execution_evidence_preserved",
        "stage": "P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED",
        "description": "PepGLAD (pending_probe): full-atom geometric latent diffusion peptide design. The previous P33H controlled_smoke_verified status is reclassified because the success artifact 225316 depended on an out-of-scope second retry and unauthorized OpenMM source modification. Preserved only as engineering/audit evidence.",
        "requires_structure": True,
        "requires_gpu": True,
        "notes": "P33I audit confirmed out-of-scope execution: 225039 consumed the single authorized retry and failed; 225316 was an unauthorized second retry depending on OpenMM source changes. The 225316 artifact is preserved as out-of-scope engineering evidence only. All outputs NOT_EXPERIMENTALLY_VALIDATED. A new compliant controlled smoke requires fresh authorization and a new run_id.",
        "supports_probe": True,
        "supports_dry_run": True,
        "supports_real_run": False,
        "supports_structure_output": True,
        "supports_sequence_output": True,
        "supports_ranking": False,
        "output_artifact_types": ["pdb", "sequence_csv", "scores_csv", "logs", "manifest", "input"],
        "adapter_id": "pepglad",
        "real_run_enabled": False,
        "safety_note": (
            "PepGLAD outputs are computational predictions only. "
            "NOT_EXPERIMENTALLY_VALIDATED. Generated peptide sequences and structures "
            "are model outputs, not experimentally validated binders."
        ),
        "validation_policy": (
            "All PepGLAD outputs must be labelled NOT_EXPERIMENTALLY_VALIDATED. "
            "Real execution requires explicit gate open, checkpoint validation, "
            "manual review, and must not be represented as experimental validation."
        ),
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
    },
    {
        "model_id": "diffpepbuilder",
        "display_name": "DiffPepBuilder",
        "category": CATEGORY_DIFFUSION_BASED_DESIGN,
        "input_type": "target_sequence_plus_structure",
        "status": MODEL_STATUS_CONTROLLED_SMOKE_VERIFIED,
        "status_reason": "p32b_controlled_smoke_verified",
        "stage": "P32B_CONTROLLED_SMOKE_OK",
        "description": "DiffPepBuilder (controlled_smoke_verified): diffusion-based peptide backbone and sequence design. P32B forward smoke completed; real execution remains gated.",
        "requires_structure": True,
        "requires_gpu": True,
        "notes": "P32B: forward controlled smoke SUCCESS, exit code 0, manifest verified. All outputs NOT_EXPERIMENTALLY_VALIDATED. Real execution requires new explicit authorization.",
        "supports_probe": True,
        "supports_dry_run": True,
        "supports_real_run": False,
        "supports_structure_output": False,
        "supports_sequence_output": True,
        "supports_ranking": False,
        "output_artifact_types": [],
        "adapter_id": "diffpepbuilder",
        "real_run_enabled": False,
        "safety_note": "DiffPepBuilder outputs are computational predictions only. NOT_EXPERIMENTALLY_VALIDATED. Generated sequences are model outputs, not experimentally validated peptides.",
        "validation_policy": "All DiffPepBuilder outputs must be labelled NOT_EXPERIMENTALLY_VALIDATED. Real execution requires explicit gate open, manual review, and must not be represented as experimental validation.",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
    },
    {
        "model_id": "ppflow",
        "display_name": "PPFlow",
        "category": CATEGORY_FLOW_BASED_DESIGN,
        "input_type": "target_sequence_plus_structure",
        "status": MODEL_STATUS_CONTROLLED_SMOKE_VERIFIED,
        "status_reason": "p33o_ppflow_path_repair_verified",
        "stage": "P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS",
        "description": "PPFlow (controlled_smoke_verified): torsional flow-matching peptide design. P33O invocation-path repair completed a controlled CPU execution (exit 0, 133 samples, 588.46s) with frozen assets; preserved as compliant success evidence. Real execution remains gated. NOT_EXPERIMENTALLY_VALIDATED.",
        "requires_structure": True,
        "requires_gpu": True,
        "notes": "P33O: invocation-path repair SUCCESS via P33G hardened runner, cwd=SOURCE_DIR, CPU, exit 0, 133 sample dirs, 404 files, 588.46s, 4,408,281 bytes. No source/checkpoint/config/scientific-param modification. P33G smoke evidence retained. P33N old gate retained as evidence. All outputs NOT_EXPERIMENTALLY_VALIDATED. Real execution requires new explicit authorization; execution_locked=true.",
        "supports_probe": True,
        "supports_dry_run": True,
        "supports_real_run": False,
        "supports_structure_output": False,
        "supports_sequence_output": True,
        "supports_ranking": False,
        "output_artifact_types": [],
        "adapter_id": "ppflow",
        "real_run_enabled": False,
        "safety_note": "PPFlow outputs are computational predictions only. NOT_EXPERIMENTALLY_VALIDATED. Real execution is unconditionally blocked in P29A.",
        "validation_policy": "Disabled placeholder; cannot produce scientific results in P4A. NOT_EXPERIMENTALLY_VALIDATED.",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
    },
    {
        "model_id": "pephar",
        "display_name": "PepHAR",
        "category": CATEGORY_HIERARCHICAL_DESIGN,
        "input_type": "target_sequence",
        "status": MODEL_STATUS_CONTROLLED_SMOKE_VERIFIED,
        "status_reason": "p32b_controlled_smoke_verified",
        "stage": "P32B_CONTROLLED_SMOKE_OK",
        "description": "PepHAR (controlled_smoke_verified): hotspot-driven autoregressive peptide design. P32B density and prediction variants completed; real execution remains gated.",
        "requires_structure": False,
        "requires_gpu": True,
        "notes": "P32B: density and prediction controlled smoke SUCCESS, exit code 0, manifests verified. All outputs NOT_EXPERIMENTALLY_VALIDATED. Real execution requires new explicit authorization.",
        "supports_probe": True,
        "supports_dry_run": True,
        "supports_real_run": False,
        "supports_structure_output": False,
        "supports_sequence_output": True,
        "supports_ranking": False,
        "output_artifact_types": [],
        "adapter_id": "pephar",
        "real_run_enabled": False,
        "safety_note": "PepHAR outputs are computational predictions only. NOT_EXPERIMENTALLY_VALIDATED. Generated sequences are model outputs, not experimentally validated peptides.",
        "validation_policy": "All PepHAR outputs must be labelled NOT_EXPERIMENTALLY_VALIDATED. Real execution requires explicit gate open, manual review, and must not be represented as experimental validation.",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
    },
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_target_peptide_models() -> list[dict[str, object]]:
    """Legacy name used by the P2/P3 Targeted Peptide Design Center."""
    return [_enrich_readiness_fields(deepcopy(m)) for m in _MODEL_REGISTRY]


def get_target_peptide_model(model_id: str) -> dict[str, object] | None:
    """Legacy name used by the P2/P3 Targeted Peptide Design Center."""
    normalized = model_id.lower().strip()
    for model in _MODEL_REGISTRY:
        if str(model["model_id"]).lower() == normalized:
            return _enrich_readiness_fields(deepcopy(model))
    return None


# Aliases for the new unified Model Registry API
list_models = list_target_peptide_models
get_model = get_target_peptide_model


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_default_safety_flags() -> dict[str, bool]:
    """Return the default safety flags for any model adapter operation."""
    return {
        "executed_model": False,
        "generated_candidates": False,
        "generated_structure": False,
        "generated_msa": False,
        "is_scientific_result": False,
        "computational_prediction_only": True,
    }


def build_model_probe_disabled_result(model_id: str, reason: str) -> dict[str, Any]:
    """Build a standardized disabled probe result for placeholder models."""
    model = get_model(model_id)
    display_name = str(model["display_name"]) if model else model_id
    return {
        "model_id": model_id,
        "display_name": display_name,
        "status": MODEL_STATUS_DISABLED,
        "message": reason,
        "probe_time": _iso_now(),
        "adapter_id": str(model["adapter_id"]) if model else f"{model_id}_placeholder",
        "safety_flags": build_default_safety_flags(),
        "detail": {},
        "scientific_boundary": SCIENTIFIC_BOUNDARY_NOTE,
    }
