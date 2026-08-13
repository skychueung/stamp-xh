"""P33U D23 Dev Run Console router (additive; extends D22).

D23 scope: wire the D22 SmokeRunnerAdapter into the formal registry adapter
contract via a new additive ``submit_dev_smoke`` method on BaseModelAdapter
(overridden by DiffPepBuilderAdapter + PepHARAdapter), reached through a new
registry dispatch module ``app.services.p33u.dev_smoke_dispatch``. The Run
Console router no longer calls bare helpers / scripts directly for
DiffPepBuilder / PepHAR smoke — it calls ``dispatch_dev_smoke(model_id, job,
job_dir, seed)``, which looks up the registry adapter and invokes
``adapter.submit_dev_smoke``. The default ``adapter.submit()`` stays BLOCKED
(read-only P31B / P31C / P30D); PepMLM's real-run submit() path is untouched.
D22 PepHAR verification run (p33u_model_3ff8c7253966412c, seed=12345) is ingested
to P33T dev DB as dev_smoke_candidate with source_round=P33U_D22.

D23 changes over D22:
  - New ``app/services/p33u/dev_smoke_dispatch.py``: registry dispatch entry
    point (dispatch_dev_smoke). Single place the router calls for dev smoke.
  - BaseModelAdapter.submit_dev_smoke (additive; default not supported).
  - DiffPepBuilderAdapter / PepHARAdapter override submit_dev_smoke → delegate
    to SmokeRunnerAdapter (full provenance: script/config/checkpoint SHA + env
    + seed). Default submit() stays BLOCKED.
  - Router _run_model_thread: diffpepbuilder / pephar branches now call
    dispatch_dev_smoke(...) instead of the removed _run_diffpepbuilder_smoke /
    _run_pephar_smoke helpers. PepMLM / PepFlow / EvoBind2 / PPFlow branches
    unchanged.
  - /smoke-candidates: optional source_round query param (filter P33U_D21 /
    P33U_D22).
  - /jobs/{id}/artifacts: surfaces provenance (adapter_id,
    adapter_formal_path, dispatch_contract, source_round, seed, script /
    config / checkpoint SHA, gate_json_path).
  - Round bumped P33U_D22 -> P33U_D23.

P33U D21 / D22 history preserved below.

D21 scope: open the remaining model real-run gates. DiffPepBuilder and PepHAR
get dev-only minimal REAL-run smoke on GPU1 (reusing the D10-proven paths
D10-2 / D10-3). EvoBind2 stays blocked with evidence (conda env 'evobind'
absent; license still ALLOWED CC BY-NC 4.0). PepFlow parser smoke is upgraded
to decode raw token indices to an AA alphabet via PepFlow's own
restypes_with_x. Additive over D20G — does not modify p33s.py / p33t.py logic,
does not touch prod 8001/8080, never invokes PPFlow, never modifies
/home/xh/stamp. All outputs tagged NOT_EXPERIMENTALLY_VALIDATED /
COMPUTATIONAL_PREDICTION_ONLY.

D21 changes over D20G:
  - DiffPepBuilder: console_status real_run_enabled -> real_run_minimal_smoke;
    real_run_enabled=True. New _run_diffpepbuilder_smoke() helper invokes
    experiments/run_inference.py via Hydra (min_length=12, max_length=12,
    samples_per_length=3) on cuda:1, reusing D10 processed receptor. REAL
    forward pass producing real 12aa PDBs. Adapter submit() stays blocked by
    design (P17); smoke bypasses the adapter (subprocess invoke) like PepFlow.
  - PepHAR: console_status -> real_run_minimal_smoke; real_run_enabled=True.
    New _run_pephar_smoke() helper invokes p33u_d21_pephar_smoke.py (D10-3
    sample_remapped approach) under CUDA_VISIBLE_DEVICES=1 (cuda:0=GPU1), 3
    samples 12aa. REAL forward pass producing real 12aa PDBs + rmsd/recovery.
  - EvoBind2: console_status -> safety_gate_not_enabled_with_evidence. License
    still ALLOWED (CC BY-NC 4.0). Real-run NOT enabled because conda env
    'evobind' (jax+tf+AF2) is ABSENT from all conda env dirs (created in D10,
    no longer present); README forbids unauthorized env creation. NOT a license
    block.
  - PepFlow: parser smoke upgraded — raw token indices decoded to AA via
    restypes_with_x from PepFlow's data/residue_constants.py (verified at
    runtime against the source file). Still artifact-only (no forward pass, no
    new candidates).
  - PPFlow: stays disabled / blocked_license. API rejects run; never loads
    checkpoint; never occupies GPU.
  - Round bumped P33U_D20G -> P33U_D21.

Endpoints (prefix /api/v1/p33u):
  GET  /run/console-matrix        five-model + scorer runnability matrix
  POST /run/model                 dev-only model run (PepMLM / DiffPepBuilder /
                                  PepHAR real; PepFlow parser smoke; EvoBind2
                                  safety-gate blocked; PPFlow license blocked)
  POST /run/scorer                candidate-level scorer run
  GET  /jobs                      list recent jobs
  GET  /jobs/{job_id}             unified job status + provenance + gate JSON
  GET  /jobs/{job_id}/logs        log content
  GET  /jobs/{job_id}/artifacts   artifact list with SHA256
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.p33s import scorers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/p33u", tags=["p33u-d23-registry-submit-contract-integration"])

VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
PREDICTION_TAG = "COMPUTATIONAL_PREDICTION_ONLY"
ROUND_TAG = "P33U_D29"

# ---------------------------------------------------------------------------
# Fixed paths and matrix (mirror D19B / registry truth)
# ---------------------------------------------------------------------------

JOB_STORE_ROOT = Path("/mnt/sdb/kxc/p33u_d20a_work/jobs")
D19_INPUTS = Path("/mnt/sdb/kxc/p33u_d19_work/inputs")
D19_SMOKE = Path("/mnt/sdb/kxc/p33u_d19_work/smoke_tests")
D19_SCORING_RUNS = Path("/mnt/sdb/kxc/p33u_d19_work/scoring_runs")
D26_MATRIX_JSON = Path("/mnt/sdb/kxc/p33u_d26_work/d26_scoring_matrix.json")
VINA_SMOKE_SCRIPT = D19_SMOKE / "vina" / "vina_smoke_v4.py"
OPENMM_SMOKE_SCRIPT = D19_SMOKE / "openmm" / "openmm_smoke.py"
MMPBSA_SMOKE_SCRIPT = D19_SMOKE / "mmpbsa" / "mmpbsa_3file.py"
COLABFOLD_BIN = Path("/home/xh/micromamba/envs/localcolabfold/bin/colabfold_batch")
AMBERHOME_DIR = "/mnt/sdb/kxc/stamp_models/envs/p33s_scorers_py310"
PEPMLM_GATE_FILE = Path("/home/xh/kxc/stampup/models_dev/pepmlm/.real_run_enabled")
PEPMLM_MODEL_PATH = "/home/xh/kxc/stampup/models_dev/pepmlm/ChatterjeeLab_PepMLM-650M"

# PepFlow parser-smoke inputs (existing D7 real-run artifact; read-only).
PEPFLOW_CASE0_PT = Path(
    "/mnt/sdb/kxc/stamp_models/artifacts/p33u_lane_d/p33u_d7_20260703_2100/"
    "pepflow/p33u_pepflow_579c0bfffcab41f1/outputs/case0.pt"
)
PEPFLOW_PROVENANCE = Path(
    "/mnt/sdb/kxc/stamp_models/artifacts/p33u_lane_d/p33u_d7_20260703_2100/"
    "pepflow/p33u_pepflow_579c0bfffcab41f1/provenance.json"
)
PEPFLOW_ENV_PYTHON = Path("/mnt/sdb/kxc/stamp_models/envs/pepflow_py310/bin/python")
# D21: parser smoke upgraded with vocab decode (restypes_with_x from PepFlow's
# own data/residue_constants.py). Additive — D20G script left in place.
PEPFLOW_PARSER_SCRIPT = Path(
    "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/"
    "backend/scripts/p33u_d21_pepflow_parser_smoke.py"
)

# D21: dev-only minimal real-run smoke runners for DiffPepBuilder + PepHAR.
# Both reuse the D10-proven GPU1 paths (D10-2 / D10-3 gates). Additive — adapter
# submit() stays blocked by design; these bypass the adapter like the PepFlow
# parser smoke (subprocess invoke of the real runner script on GPU1).
DIFFPEPBUILDER_SMOKE_SCRIPT = Path(
    "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/"
    "backend/scripts/p33u_d21_diffpepbuilder_smoke.sh"
)
DIFFPEPBUILDER_ENV_PYTHON = Path("/mnt/sdb/kxc/stamp_models/envs/diffpepbuilder_py39/bin/python")
PEPHAR_SMOKE_SCRIPT = Path(
    "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/"
    "backend/scripts/p33u_d21_pephar_smoke.py"
)
PEPHAR_ENV_PYTHON = Path("/mnt/sdb/kxc/stamp_models/envs/pephar_py310/bin/python")
# D21 work root for smoke outputs (kept under the D20A work tree's parent so
# /mnt/sdb has space; D8-D20G bundles untouched).
D21_WORK_ROOT = Path("/mnt/sdb/kxc/p33u_d21_work")
D21_JOB_STORE_ROOT = D21_WORK_ROOT / "jobs"

# Five available closed-loop models (per goal). PPFlow is license-blocked.
AVAILABLE_MODELS = ("pepmlm", "diffpepbuilder", "pephar", "pepflow", "evobind2")
BLOCKED_MODELS = {"ppflow": "blocked_license: no upstream PPFlow LICENSE; never invoked per goal"}
BACKLOG_MODELS = {
    "pepprclip": "backlog: not closed; roadmap only",
    "rfpeptides": "backlog: not closed; roadmap only",
    "pepglad": "backlog: not closed; roadmap only",
}

# Scorers: 5 available (D19B verified), 3 blocked.
AVAILABLE_SCORERS = ("prodigy", "vina", "openmm", "mmgbsa", "af2_multimer")
BLOCKED_SCORERS = {
    "gnina": "unavailable_with_reason: network-infeasible download + conda unreachable (D19B evidence)",
    "esmfold": "env_present_weights_pending: HuggingFace unreachable; weights not staged",
    "pyrosetta": "blocked_license: no PyRosetta/Rosetta academic license; not bypassed",
}

# Candidate complex PDBs available for scorer runs (D19 inputs).
CANDIDATE_COMPLEXES = {
    "pepmlm_candidate_1": D19_INPUTS / "pepmlm_candidate_1_complex.pdb",
    "pepmlm_candidate_2": D19_INPUTS / "pepmlm_candidate_2_complex.pdb",
    "pepmlm_candidate_3": D19_INPUTS / "pepmlm_candidate_3_complex.pdb",
    "diffpepbuilder_12aa_sample_0": D19_INPUTS / "p33u_d10_diffpepbuilder_12aa_sample_0_complex.pdb",
    "evobind2_12aa_best": D19_INPUTS / "p33u_d10_evobind2_12aa_best_complex.pdb",
    "pephar_12aa_sample_0": D19_INPUTS / "p33u_d10_pephar_12aa_sample_0_complex.pdb",
    "diffpepbuilder_12aa_sample_1": D19_INPUTS / "p33u_d10_diffpepbuilder_12aa_sample_1_complex.pdb",
    "pephar_12aa_sample_1": D19_INPUTS / "p33u_d10_pephar_12aa_sample_1_complex.pdb",
    "pephar_12aa_sample_2": D19_INPUTS / "p33u_d10_pephar_12aa_sample_2_complex.pdb",
}

# D25: complex-source honesty labels. 8 candidates are D15 structural
# alignment to the EvoBind2 bound pose (PLACEMENT_ARTIFACT, not real docking);
# EvoBind2 keeps its D12 AF2 complex. Never labeled as docking.
COMPLEX_SOURCE_LABELS = {
    "pepmlm_candidate_1": "D15 structural alignment to EvoBind2 peptide (PLACEMENT_ARTIFACT, not real docking)",
    "pepmlm_candidate_2": "D15 structural alignment to EvoBind2 peptide (PLACEMENT_ARTIFACT, not real docking)",
    "pepmlm_candidate_3": "D15 structural alignment to EvoBind2 peptide (PLACEMENT_ARTIFACT, not real docking)",
    "diffpepbuilder_12aa_sample_0": "D15 structural alignment to EvoBind2 peptide (PLACEMENT_ARTIFACT, not real docking)",
    "evobind2_12aa_best": "D12 EvoBind2 AF2 complex (EXISTING_AF2_COMPLEX, not docking)",
    "pephar_12aa_sample_0": "D15 structural alignment to EvoBind2 peptide (PLACEMENT_ARTIFACT, not real docking)",
    "diffpepbuilder_12aa_sample_1": "D15 structural alignment to EvoBind2 peptide (PLACEMENT_ARTIFACT, not real docking)",
    "pephar_12aa_sample_1": "D15 structural alignment to EvoBind2 peptide (PLACEMENT_ARTIFACT, not real docking)",
    "pephar_12aa_sample_2": "D15 structural alignment to EvoBind2 peptide (PLACEMENT_ARTIFACT, not real docking)",
}

# D25: per-scorer input readiness for the console-matrix + Run Console.
# All 5 available scorers have prepared complex PDB inputs (D19_INPUTS) and
# D19 smoke-passed evidence. Complex is placement/AF2 - labeled, not docking.
SCORER_INPUT_READINESS = {
    "prodigy": {"input_ready": True, "missing_complex": False, "blocked_dependency": "",
                "smoke_passed": True, "requires": "complex_pdb",
                "d19_evidence_ref": "d19_scoring_matrix.json (pepmlm_c3 dG=-5.9 kcal/mol, Kd=4.4e-05 M)"},
    "vina": {"input_ready": True, "missing_complex": False, "blocked_dependency": "",
             "smoke_passed": True, "requires": "complex_pdb",
             "d19_evidence_ref": "d19_scoring_matrix.json (pepmlm_c3 pose_score=-1.309 kcal/mol, rigid, NOT docking)"},
    "openmm": {"input_ready": True, "missing_complex": False, "blocked_dependency": "",
               "smoke_passed": True, "requires": "complex_pdb",
               "d19_evidence_ref": "d19_scoring_matrix.json (pepmlm_c3 relax 72386.6->-31067.4 kJ/mol, 50 steps)"},
    "mmgbsa": {"input_ready": True, "missing_complex": False, "blocked_dependency": "",
               "smoke_passed": True, "requires": "openmm_relaxed_complex",
               "d19_evidence_ref": "d19_scoring_matrix.json (pepmlm_c3 dG=52.7 kcal/mol igb=2; positive=unfavorable placement pose)"},
    "af2_multimer": {"input_ready": True, "missing_complex": False, "blocked_dependency": "",
                     "smoke_passed": True, "requires": "fasta_receptor_peptide",
                     "d19_evidence_ref": "d19_scoring_matrix.json (9/9 iptm 0.10-0.24 single_sequence GPU cuda:1)"},
}

# ---------------------------------------------------------------------------
# D20G: five-model console adapter status matrix.
# Each entry carries the precise, auditable per-model status. The UI renders
# these verbatim; blocked models are NOT shown as runnable.
# ---------------------------------------------------------------------------

MODEL_STATUS_MATRIX: dict[str, dict[str, Any]] = {
    "pepmlm": {
        "license_status": "allowed",
        "dependency_status": "ready",
        "runtime_status": "ready",
        "console_status": "real_run_enabled",
        "smoke_status": "smoke_passed_real_run",
        "real_run_enabled": True,
        "blocked_reason": "",
        "expected_artifact": "output/candidate_sequences.json",
        "evidence_ref": "D20A job p33u_model_ae1c8f87e0ae4e21 (PepMLM-650M, cuda:1, exit 0)",
    },
    "pepflow": {
        "license_status": "allowed",
        "dependency_status": "ready",
        "runtime_status": "ready",
        "console_status": "artifact_only_parser_smoke",
        "smoke_status": "smoke_passed_parser_with_vocab",
        "real_run_enabled": False,
        "blocked_reason": (
            "PepFlowAdapter.submit() unconditionally blocked (read-only skeleton); "
            "console exposes parser/artifact smoke on existing D7 real-run output "
            "case0.pt, NOT a new forward pass. D21: raw token indices now decoded "
            "to AA via PepFlow's own restypes_with_x (data/residue_constants.py)."
        ),
        "expected_artifact": "parser_smoke_result.json (with decoded_sequences)",
        "evidence_ref": (
            "D7 run p33u_pepflow_579c0bfffcab41f1 (exit 0, GPU1, model2.pt); "
            "forward_probe SUCCESS (6.88M params, 3.86s); D21 vocab decode added"
        ),
    },
    "diffpepbuilder": {
        "license_status": "allowed",
        "dependency_status": "ready",
        "runtime_status": "runner_present_registry_dispatch_d23",
        "console_status": "real_run_registry_dispatched",
        "smoke_status": "smoke_passed_registry_submit_contract_d23",
        "real_run_enabled": True,
        "blocked_reason": "",
        "expected_artifact": "12aa peptide PDBs (runs/inference/.../target_length_12_sample_*.pdb)",
        "evidence_ref": (
            "D23 registry submit contract: dispatch_dev_smoke -> DiffPepBuilderAdapter."
            "submit_dev_smoke -> SmokeRunnerAdapter (D10-2 path: run_inference.py via "
            "Hydra, cuda:1, 3 samples 12aa, full provenance). Default adapter.submit() "
            "stays BLOCKED (P31B). D21 smoke candidates ingested to P33T dev DB as "
            "dev_smoke_candidate (not Top4, not wetlab shortlist)."
        ),
    },
    "pephar": {
        "license_status": "allowed",
        "dependency_status": "ready",
        "runtime_status": "runner_present_registry_dispatch_d23",
        "console_status": "real_run_registry_dispatched",
        "smoke_status": "smoke_passed_registry_submit_contract_d23",
        "real_run_enabled": True,
        "blocked_reason": "",
        "expected_artifact": "12aa peptide PDBs + test.csv (result/.../gen_*.pdb)",
        "evidence_ref": (
            "D23 registry submit contract: dispatch_dev_smoke -> PepHARAdapter."
            "submit_dev_smoke -> SmokeRunnerAdapter (D10-3 path: AnchorBasedSampler, "
            "CUDA_VISIBLE_DEVICES=1 cuda:0=GPU1, 3 samples 12aa, fixed seed=12345, full "
            "provenance). Default adapter.submit() stays BLOCKED (P31C). D21 + D22 smoke "
            "candidates ingested to P33T dev DB as dev_smoke_candidate (source_round "
            "P33U_D21 / P33U_D22; not Top4, not wetlab shortlist)."
        ),
    },
    "evobind2": {
        "license_status": "allowed_cc_by_nc_4_0_internal_noncommercial_research",
        "dependency_status": "ready",
        "runtime_status": "env_installed_runner_present",
        "console_status": "minimal_smoke_passed_ingested_d29",
        "real_run_maturity": "real_run_enabled_dev_only",
        "smoke_status": "minimal_smoke_passed_d28_ingested_d29",
        "promotion_status": "not_reviewed",
        "real_run_enabled": True,
        "blocked_reason": "",
        "expected_artifact": "designed peptide FASTA + AF2 complex PDB",
        "evidence_ref": "D28 job p33u_d28_evobind2_minimal_smoke_001 (Mhp Eno A0A223MA21, 12aa, 8 MC iterations, cuda:1, exit 0, sequence EYIKAEIERAYE). AF2 params symlinked from existing colabfold cache; model_1 monomer file incomplete so model_1_ptm params used for dev smoke.",
        "risk_hint": "dev only · may use GPU · not experimentally validated · params are ptm fallback"
    },
    "ppflow": {
        "license_status": "blocked_no_upstream_license",
        "dependency_status": "blocked",
        "runtime_status": "blocked",
        "console_status": "disabled_blocked_license",
        "smoke_status": "never_run",
        "real_run_enabled": False,
        "blocked_reason": "blocked_license: no upstream PPFlow LICENSE; never invoked per goal",
        "expected_artifact": "none (never run)",
        "evidence_ref": "PPFLOW_BLOCKED_LICENSE standing",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def _job_dir(job_id: str) -> Path:
    return JOB_STORE_ROOT / job_id


def _write_job(job: dict[str, Any]) -> None:
    jd = _job_dir(job["job_id"])
    jd.mkdir(parents=True, exist_ok=True)
    tmp = jd / "job.json.tmp"
    tmp.write_text(json.dumps(job, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(jd / "job.json")


def _read_job(job_id: str) -> dict[str, Any] | None:
    jp = _job_dir(job_id) / "job.json"
    if not jp.is_file():
        return None
    try:
        return json.loads(jp.read_text(encoding="utf-8"))
    except Exception:
        return None


def _gate_json(job_id: str, kind: str, model_or_scorer: str,
               confirm_flags: dict[str, bool], extra: dict | None = None) -> dict[str, Any]:
    g = {
        "gate_id": f"gate_{job_id}",
        "job_id": job_id,
        "kind": kind,  # model_run | scorer_run
        "model_or_scorer": model_or_scorer,
        "safety_confirmations": confirm_flags,
        "ppflow_blocked": True,
        "prod_untouched": True,
        "validation_status": VALIDATION_STATUS,
        "prediction_tag": PREDICTION_TAG,
        "wetlab_validation_planned": True,
        "opened_at": _now_iso(),
    }
    if extra:
        g.update(extra)
    return g


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ConfirmFlags(BaseModel):
    dev_only_acknowledged: bool = False
    no_experimental_validation_acknowledged: bool = False
    do_not_run_ppflow_acknowledged: bool = False
    gpu_may_be_used_acknowledged: bool = False


class ModelRunRequest(BaseModel):
    model_id: str
    target_sequence: str
    peptide_length: int = 10
    num_candidates: int = 3
    device: str = "auto"
    seed: int | None = None
    top_k: int = 3
    gpu_device: str | None = None  # e.g. "cuda:1"
    confirm: ConfirmFlags


class ScorerRunRequest(BaseModel):
    scorer_id: str
    candidate_id: str = "pepmlm_candidate_3"
    complex_pdb_override: str | None = None
    gpu_device: str | None = None
    confirm: ConfirmFlags


def _validate_confirm(confirm: ConfirmFlags) -> tuple[bool, str]:
    """All four safety confirmations must be true before any run."""
    if not confirm.dev_only_acknowledged:
        return False, "dev_only_acknowledged required"
    if not confirm.no_experimental_validation_acknowledged:
        return False, "no_experimental_validation_acknowledged required"
    if not confirm.do_not_run_ppflow_acknowledged:
        return False, "do_not_run_ppflow_acknowledged required"
    if not confirm.gpu_may_be_used_acknowledged:
        return False, "gpu_may_be_used_acknowledged required"
    return True, "ok"


# ---------------------------------------------------------------------------
# GET /run/console-matrix
# ---------------------------------------------------------------------------

@router.get("/run/console-matrix")
async def console_matrix() -> JSONResponse:
    models = []
    # Available five — Run button enabled for real-run models (PepMLM,
    # DiffPepBuilder, PepHAR) + PepFlow parser smoke. EvoBind2 is NOT runnable
    # (safety_gate_not_enabled_with_evidence — env missing, license allowed).
    for mid in AVAILABLE_MODELS:
        m = MODEL_STATUS_MATRIX[mid]
        if m["real_run_enabled"] or mid == "pepflow":
            run_button = "enabled"
        elif mid == "evobind2":
            run_button = "enabled"  # D28 minimal smoke passed
        else:
            run_button = "disabled_blocked_dependency"
        models.append({
            "model_id": mid,
            "category": "available",
            "run_button": run_button,
            "default": mid == "pepmlm",
            "real_run_maturity": (
                "real_run_wired" if mid == "pepmlm"
                else "real_run_registry_dispatched" if mid in ("diffpepbuilder", "pephar")
                else "artifact_only_parser_smoke" if mid == "pepflow"
                else "safety_gate_not_enabled_with_evidence"
            ),
            "license_status": m["license_status"],
            "dependency_status": m["dependency_status"],
            "runtime_status": m["runtime_status"],
            "console_status": m["console_status"],
            "smoke_status": m["smoke_status"],
            "real_run_enabled": m["real_run_enabled"],
            "blocked_reason": m["blocked_reason"],
            "expected_artifact": m["expected_artifact"],
            "evidence_ref": m["evidence_ref"],
            "risk_hint": "dev only · may use GPU · not experimentally validated",
        })
    # Blocked (PPFlow)
    for mid, reason in BLOCKED_MODELS.items():
        m = MODEL_STATUS_MATRIX[mid]
        models.append({
            "model_id": mid,
            "category": "blocked",
            "run_button": "disabled",
            "reason": reason,
            "license_status": m["license_status"],
            "console_status": m["console_status"],
            "smoke_status": m["smoke_status"],
            "real_run_enabled": False,
            "blocked_reason": m["blocked_reason"],
            "risk_hint": "license blocked · never invoked",
        })
    # Backlog
    for mid, reason in BACKLOG_MODELS.items():
        models.append({
            "model_id": mid,
            "category": "backlog",
            "run_button": "disabled",
            "reason": reason,
            "risk_hint": "backlog · not closed",
        })

    scorers_list = []
    for sid in AVAILABLE_SCORERS:
        rd = SCORER_INPUT_READINESS.get(sid, {})
        scorers_list.append({
            "scorer_id": sid,
            "category": "available",
            "run_button": "enabled",  # D25: all 5 have prepared inputs + D19 smoke-passed
            "input_ready": rd.get("input_ready", False),
            "missing_complex": rd.get("missing_complex", True),
            "blocked_dependency": rd.get("blocked_dependency", ""),
            "smoke_passed": rd.get("smoke_passed", False),
            "requires": rd.get("requires", ""),
            "d19_evidence_ref": rd.get("d19_evidence_ref", ""),
            "complex_source_label": "placement_or_af2 (see manifest); NOT real docking",
            "risk_hint": "dev only · computational rescore · not experimentally validated",
        })
    for sid, reason in BLOCKED_SCORERS.items():
        scorers_list.append({
            "scorer_id": sid,
            "category": "blocked",
            "run_button": "disabled",
            "reason": reason,
            "risk_hint": "unavailable / blocked",
        })

    return JSONResponse(status_code=200, content={
        "code": 200,
        "data": {
            "models": models,
            "scorers": scorers_list,
            "candidates": sorted(CANDIDATE_COMPLEXES.keys()),
            "default_model": "pepmlm",
            "default_scorer": "prodigy",
            "default_candidate": "pepmlm_candidate_3",
            "validation_status": VALIDATION_STATUS,
            "prediction_tag": PREDICTION_TAG,
            "wetlab_validation_planned": True,
            "ppflow_status": "PPFLOW_BLOCKED_LICENSE",
            "round": ROUND_TAG,
        },
    })


# ---------------------------------------------------------------------------
# GET /d26/scoring-matrix  (D26: unified 9x12aa scoring matrix + reranking proposal)
# ---------------------------------------------------------------------------
@router.get("/d26/scoring-matrix")
async def d26_scoring_matrix() -> JSONResponse:
    """D26 unified scoring matrix for the 9 true-12aa candidate set.

    Returns per-candidate PRODIGY/Vina/OpenMM/MMGBSA/AF2 values (column-separated,
    NEVER mixed into one activity score), complex_source labels (PLACEMENT_ARTIFACT
    or EXISTING_AF2_COMPLEX), the D26 reranking PROPOSAL (does NOT overwrite the
    frozen D15/D18 Top4), and honesty disclaimers (NOT docking / NOT Kd).
    """
    if not D26_MATRIX_JSON.is_file():
        raise HTTPException(status_code=404, detail="D26 scoring matrix not built yet")
    try:
        data = json.loads(D26_MATRIX_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"cannot read D26 matrix: {exc}")
    return JSONResponse(status_code=200, content={
        "code": 200, "data": data,
        "validation_status": VALIDATION_STATUS,
        "message": "P33U-D26 unified scoring matrix (9 true 12aa). Proposal only; does not overwrite frozen D15/D18 Top4."})


# ---------------------------------------------------------------------------
# POST /run/model
# ---------------------------------------------------------------------------

def _run_pepflow_parser_smoke(job: dict[str, Any], job_dir: Path) -> None:
    """Artifact-only parser smoke on existing D7 PepFlow case0.pt.

    Read-only: loads case0.pt, decodes tensor structure + raw token indices,
    writes parser_smoke_result.json. Does NOT run a forward pass, does NOT
    generate new candidates, does NOT fake sequences.
    """
    log_path = job_dir / "log.txt"
    out_json = job_dir / "parser_smoke_result.json"
    try:
        if not PEPFLOW_CASE0_PT.is_file():
            job["status"] = "blocked_dependency"
            job["failure_reason"] = f"pepflow case0.pt not found: {PEPFLOW_CASE0_PT}"
            job["end_time"] = _now_iso()
            return
        if not PEPFLOW_PARSER_SCRIPT.is_file():
            job["status"] = "blocked_dependency"
            job["failure_reason"] = f"parser script not found: {PEPFLOW_PARSER_SCRIPT}"
            job["end_time"] = _now_iso()
            return
        cmd = [
            str(PEPFLOW_ENV_PYTHON), str(PEPFLOW_PARSER_SCRIPT),
            "--case0", str(PEPFLOW_CASE0_PT),
            "--provenance", str(PEPFLOW_PROVENANCE),
            "--out", str(out_json),
        ]
        with open(log_path, "w", encoding="utf-8") as lf:
            proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                  timeout=120, check=False)
        job["command"] = cmd
        job["env"] = {"python": str(PEPFLOW_ENV_PYTHON),
                      "case0_pt": str(PEPFLOW_CASE0_PT)}
        job["exit_code"] = proc.returncode
        job["status"] = "succeeded" if proc.returncode == 0 else "failed"
        job["failure_reason"] = "" if proc.returncode == 0 else "pepflow parser smoke non-zero exit; see logs"
        job["checkpoint_loaded"] = "none (artifact parser smoke; no forward pass)"
        job["gpu_used"] = None  # parser smoke is CPU-only
        job["output_path"] = str(out_json)
        if out_json.is_file():
            job["sha256"] = _sha256_file(out_json)
            try:
                parsed = json.loads(out_json.read_text(encoding="utf-8"))
                job["result_summary"] = {
                    "smoke_type": parsed.get("smoke_type"),
                    "case0_sha256": parsed.get("case0_sha256"),
                    "interpretability": parsed.get("interpretability"),
                    "tensor_keys": parsed.get("tensor_keys"),
                    "ran_model_forward": parsed.get("ran_model_forward"),
                    "generated_new_candidates": parsed.get("generated_new_candidates"),
                    "vocab_decoded": parsed.get("vocab_decoded"),
                    "decoded_count": parsed.get("decoded_count"),
                    "decoded_sequences": parsed.get("decoded_sequences"),
                    "vocab_match": (parsed.get("vocab") or {}).get("match"),
                    "label": "pepflow artifact_only_parser_smoke (NOT real run; NOT new candidates; D21 vocab decode added)",
                }
            except (OSError, json.JSONDecodeError):
                pass
        job["end_time"] = _now_iso()
    except subprocess.TimeoutExpired:
        job["status"] = "failed"
        job["failure_reason"] = "pepflow parser smoke timeout (120s)"
        job["end_time"] = _now_iso()
    except Exception as exc:
        job["status"] = "failed"
        job["failure_reason"] = f"exception: {exc!r}"
        job["end_time"] = _now_iso()
        logger.exception("pepflow parser smoke failed")


# ---------------------------------------------------------------------------
# D23: dev-smoke dispatch now goes through the registry adapter contract.
# The D22 _run_diffpepbuilder_smoke / _run_pephar_smoke router helpers are
# removed; _run_model_thread calls dispatch_dev_smoke(...) below, which looks up
# the registry adapter (DiffPepBuilderAdapter / PepHARAdapter) and invokes its
# additive submit_dev_smoke contract method (delegates to SmokeRunnerAdapter
# with full provenance). The default adapter.submit() stays BLOCKED (P31B/P31C).
# ---------------------------------------------------------------------------


def _run_model_thread(job: dict[str, Any], req: ModelRunRequest, confirm_flags: dict[str, bool]) -> None:
    """Background worker: dispatch the model run and update job.json."""
    model_id = req.model_id
    job_dir = _job_dir(job["job_id"])
    log_path = job_dir / "log.txt"
    try:
        if model_id == "pepmlm":
            # Real GPU run via PepMLMAdapter. Open the gate file for this controlled run.
            PEPMLM_GATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            PEPMLM_GATE_FILE.write_text(json.dumps({
                "job_id": job["job_id"], "run_id": job["run_id"],
                "opened_at": _now_iso(), "reason": "D20G dev run console controlled smoke",
            }), encoding="utf-8")
            # Force the free GPU (GPU1) via env so the subprocess inherits it.
            saved_cvd = os.environ.get("CUDA_VISIBLE_DEVICES")
            if req.gpu_device == "cuda:1":
                os.environ["CUDA_VISIBLE_DEVICES"] = "1"
            try:
                from app.services.model_adapters.pepmlm_adapter import PepMLMAdapter
                from app.schemas.model_registry import ModelDryRunPayload
                payload = ModelDryRunPayload(
                    target_sequence=req.target_sequence,
                    peptide_length=req.peptide_length,
                    num_candidates=req.num_candidates,
                    device=req.device,
                    seed=req.seed,
                    top_k=req.top_k,
                )
                adapter = PepMLMAdapter()
                result = adapter.submit(payload, run_id=job["run_id"])
            finally:
                # Always close the gate and restore env.
                try:
                    PEPMLM_GATE_FILE.unlink(missing_ok=True)
                except OSError:
                    pass
                if saved_cvd is None:
                    os.environ.pop("CUDA_VISIBLE_DEVICES", None)
                else:
                    os.environ["CUDA_VISIBLE_DEVICES"] = saved_cvd

            # Capture log from adapter's log file.
            adapter_log = Path(result.artifacts.get("logs/run_stdout_stderr.log", "")) if result.artifacts else None
            if adapter_log and adapter_log.is_file():
                try:
                    log_path.write_text(adapter_log.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
                except OSError:
                    pass

            job["end_time"] = _now_iso()
            job["exit_code"] = 0 if result.status == "SUCCEEDED" else 1
            job["status"] = "succeeded" if result.status == "SUCCEEDED" else "failed"
            job["failure_reason"] = "" if result.status == "SUCCEEDED" else (result.message or "PepMLM real run failed; see logs")
            job["checkpoint_loaded"] = PEPMLM_MODEL_PATH
            job["command"] = result.command_preview or []
            job["env"] = {"python": "/home/xh/kxc/stampup/tools/envs/pepmlm/bin/python",
                          "model_path": PEPMLM_MODEL_PATH,
                          "cuda_visible_devices": "1" if req.gpu_device == "cuda:1" else "default"}
            job["output_path"] = str(Path(result.artifacts.get("output/candidate_sequences.json", ""))) if result.artifacts else ""
            # SHA256 of candidate_sequences.json
            if job["output_path"] and Path(job["output_path"]).is_file():
                job["sha256"] = _sha256_file(Path(job["output_path"]))
            job["result_summary"] = {
                "status": result.status,
                "run_id": result.run_id,
                "artifacts": result.artifacts,
                "safety_flags": result.safety_flags.model_dump() if hasattr(result.safety_flags, "model_dump") else dict(result.safety_flags),
            }
        elif model_id == "pepflow":
            # D20G/D21: artifact-only parser smoke (read-only, CPU). NOT a forward pass.
            # D21: vocab decode added (token indices → AA via restypes_with_x).
            _run_pepflow_parser_smoke(job, job_dir)
        elif model_id == "diffpepbuilder":
            # D23: registry dispatch contract. Router no longer calls a bare
            # helper; dispatch_dev_smoke looks up DiffPepBuilderAdapter and
            # invokes its additive submit_dev_smoke (delegates to
            # SmokeRunnerAdapter; D10-2 path on GPU1, full provenance). Default
            # adapter.submit() stays BLOCKED (P31B).
            from app.services.p33u.dev_smoke_dispatch import dispatch_dev_smoke
            dispatch_dev_smoke("diffpepbuilder", job, job_dir, seed=req.seed)
        elif model_id == "pephar":
            # D23: registry dispatch contract. dispatch_dev_smoke looks up
            # PepHARAdapter and invokes its additive submit_dev_smoke (delegates
            # to SmokeRunnerAdapter; D10-3 path on GPU1, fixed seed default
            # 12345, full provenance). Default adapter.submit() stays BLOCKED (P31C).
            from app.services.p33u.dev_smoke_dispatch import dispatch_dev_smoke
            dispatch_dev_smoke("pephar", job, job_dir, seed=req.seed)
        elif model_id in BLOCKED_MODELS:
            job["status"] = "blocked_license"
            job["failure_reason"] = BLOCKED_MODELS[model_id]
            job["end_time"] = _now_iso()
            job["exit_code"] = None
        elif model_id in BACKLOG_MODELS:
            job["status"] = "blocked_dependency"
            job["failure_reason"] = BACKLOG_MODELS[model_id]
            job["end_time"] = _now_iso()
            job["exit_code"] = None
        elif model_id == "evobind2":
            # D21: license ALLOWED (CC BY-NC 4.0); real-run NOT enabled because the
            # conda env 'evobind' is ABSENT. safety_gate_not_enabled_with_evidence.
            # NOT a license block.
            m = MODEL_STATUS_MATRIX[model_id]
            job["status"] = "safety_gate_not_enabled"
            job["failure_reason"] = m["blocked_reason"]
            job["end_time"] = _now_iso()
            job["exit_code"] = None
        else:
            job["status"] = "failed"
            job["failure_reason"] = f"unknown model_id: {model_id}"
            job["end_time"] = _now_iso()
            job["exit_code"] = 2
    except Exception as exc:
        job["status"] = "failed"
        job["failure_reason"] = f"exception: {exc!r}"
        job["end_time"] = _now_iso()
        job["exit_code"] = 3
        logger.exception("p33u model run thread failed")
    finally:
        _write_job(job)


@router.post("/run/model")
async def run_model(req: ModelRunRequest) -> JSONResponse:
    ok, reason = _validate_confirm(req.confirm)
    if not ok:
        return JSONResponse(status_code=403, content={
            "code": 403, "data": {"status": "BLOCKED", "reason": reason},
            "validation_status": VALIDATION_STATUS,
            "message": "Safety confirmations incomplete."})

    if req.model_id in BLOCKED_MODELS:
        # Never run PPFlow. Record a blocked job and return.
        job_id = f"p33u_model_{uuid.uuid4().hex[:16]}"
        run_id = f"blocked_{job_id}"
        job = _new_job_skeleton(job_id, run_id, "model", req.model_id,
                                req.target_sequence, "", req.confirm.model_dump())
        job["status"] = "blocked_license"
        job["failure_reason"] = BLOCKED_MODELS[req.model_id]
        job["end_time"] = _now_iso()
        _write_job(job)
        return JSONResponse(status_code=200, content={"code": 200, "data": job,
                                                      "validation_status": VALIDATION_STATUS})

    if req.model_id not in AVAILABLE_MODELS and req.model_id not in BACKLOG_MODELS:
        raise HTTPException(status_code=404, detail=f"unknown model_id: {req.model_id}")

    job_id = f"p33u_model_{uuid.uuid4().hex[:16]}"
    run_id = f"pepmlm_{uuid.uuid4().hex[:12]}" if req.model_id == "pepmlm" else f"{req.model_id}_{uuid.uuid4().hex[:12]}"
    job = _new_job_skeleton(job_id, run_id, "model", req.model_id,
                            req.target_sequence, "", req.confirm.model_dump())
    job["gpu_used"] = req.gpu_device or (
        "cuda:1" if req.model_id in ("pepmlm", "diffpepbuilder") else
        "cuda:0 (physical GPU1)" if req.model_id == "pephar" else None
    )
    job["command"] = []  # filled by thread
    _write_job(job)

    # Dispatch: PepMLM / DiffPepBuilder / PepHAR real runs on background threads
    # (slow GPU); PepFlow parser smoke synchronous (fast, CPU-only); blocked /
    # safety-gate models synchronous (instant).
    if req.model_id in ("pepmlm", "diffpepbuilder", "pephar"):
        t = threading.Thread(target=_run_model_thread, args=(job, req, req.confirm.model_dump()), daemon=True)
        t.start()
    else:
        _run_model_thread(job, req, req.confirm.model_dump())

    return JSONResponse(status_code=202, content={"code": 202, "data": job,
                                                  "validation_status": VALIDATION_STATUS,
                                                  "message": "Model run accepted. Poll GET /api/v1/p33u/jobs/{job_id}."})


# ---------------------------------------------------------------------------
# POST /run/scorer
# ---------------------------------------------------------------------------

def _extract_last_json(text: str) -> dict | None:
    """Extract the last top-level {...} JSON object from a multi-line text block.
    Handles indented/pretty-printed JSON (vina/openmm/mmpbsa smoke scripts print
    json.dumps(result, indent=2)). Returns None if no parseable object found."""
    import json as _json
    objs = []
    depth = 0; start = None; in_str = False; esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
            continue
        if ch == '"': in_str = True
        elif ch == "{":
            if depth == 0: start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                objs.append(text[start:i+1]); start = None
    for obj in reversed(objs):
        try: return _json.loads(obj)
        except Exception: continue
    return None


def _run_scorer_thread(job: dict[str, Any], req: ScorerRunRequest) -> None:
    job_dir = _job_dir(job["job_id"])
    log_path = job_dir / "log.txt"
    sid = req.scorer_id
    try:
        complex_pdb = Path(req.complex_pdb_override) if req.complex_pdb_override else CANDIDATE_COMPLEXES.get(req.candidate_id)
        if sid in BLOCKED_SCORERS:
            job["status"] = ("blocked_license" if "license" in BLOCKED_SCORERS[sid]
                             else "unavailable_with_reason")
            job["failure_reason"] = BLOCKED_SCORERS[sid]
            job["end_time"] = _now_iso()
            _write_job(job)
            return

        if sid == "prodigy":
            if not complex_pdb or not complex_pdb.is_file():
                job["status"] = "failed"; job["failure_reason"] = f"complex PDB not found: {complex_pdb}"
                job["end_time"] = _now_iso(); _write_job(job); return
            out = job_dir / "prodigy_out"
            res = scorers.score_kd_prodigy(complex_pdb, out, temperature_k=298.15, timeout_seconds=600)
            job["exit_code"] = 0 if res.status == "ok" else 1
            job["status"] = "succeeded" if res.status == "ok" else "failed"
            job["failure_reason"] = "" if res.status == "ok" else (res.detail.get("reason", "PRODIGY failed") if isinstance(res.detail, dict) else "PRODIGY failed")
            if res.log_path and Path(res.log_path).is_file():
                try:
                    log_path.write_text(Path(res.log_path).read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
                except OSError:
                    pass
            job["output_path"] = str(out)
            job["sha256"] = _sha256_file(complex_pdb)
            job["result_summary"] = {"metric": res.metric, "value": res.value, "unit": res.unit,
                                     "status": res.status, "detail": res.detail,
                                     "label": "predicted_Kd_PRODIGY (NOT experimental Kd)"}

        elif sid == "vina":
            # D25: pass the candidate complex PDB + work_dir to vina_smoke_v4.py
            # (D24 bug: cmd passed no args -> IndexError). Vina scores the BOUND
            # POSE of the placement complex (rigid, no global search): a pose
            # score, NOT a docking search, NOT a Kd. Complex is D15 structural
            # alignment (PLACEMENT_ARTIFACT) for 8 candidates; AF2 for EvoBind2.
            vina_script = VINA_SMOKE_SCRIPT
            if not vina_script.is_file():
                job["status"] = "failed"; job["failure_reason"] = f"vina smoke script not found: {vina_script}"
                job["end_time"] = _now_iso(); _write_job(job); return
            if not complex_pdb or not complex_pdb.is_file():
                job["status"] = "failed"; job["failure_reason"] = f"missing_complex_pdb: candidate {req.candidate_id!r} has no prepared complex PDB at {complex_pdb}"
                job["end_time"] = _now_iso(); _write_job(job); return
            out = job_dir / "vina_out"; out.mkdir(parents=True, exist_ok=True)
            import subprocess
            cmd = [scorers.SCORER_PY, str(vina_script), str(complex_pdb), str(out)]
            with open(log_path, "w", encoding="utf-8") as lf:
                proc = subprocess.run(cmd, cwd=str(out), stdout=lf, stderr=subprocess.STDOUT, timeout=600, check=False)
            job["exit_code"] = proc.returncode
            job["status"] = "succeeded" if proc.returncode == 0 else "failed"
            job["failure_reason"] = "" if proc.returncode == 0 else "vina smoke non-zero exit; see logs"
            job["command"] = cmd
            job["env"] = {"python": scorers.SCORER_PY, "complex_pdb": str(complex_pdb), "cwd": str(out)}
            job["sha256"] = _sha256_file(complex_pdb)
            job["output_path"] = str(out)
            try:
                _j = _extract_last_json(log_path.read_text(encoding="utf-8", errors="ignore")) or {}
                if _j:
                    job["result_summary"] = {"label": "vina_pose_score_kcal_mol (pose score of bound complex; NOT docking search; NOT Kd)",
                                             "vina_pose_score_kcal_mol": _j.get("vina_pose_score_kcal_mol"),
                                             "box_center": _j.get("box_center"), "box_size": _j.get("box_size"),
                                             "elapsed_s": _j.get("elapsed_s"),
                                             "complex_source": COMPLEX_SOURCE_LABELS.get(req.candidate_id, "see manifest")}
                else:
                    job["result_summary"] = {"label": "vina_pose_score (see log)", "note": "no JSON in log"}
            except Exception:
                job["result_summary"] = {"label": "vina_pose_score (see log)"}

        elif sid == "openmm":
            # D25: OpenMM OBC2 implicit 50-step minimization of the candidate
            # complex (PDBFixer + OpenMM). Produces relaxed complex + energy
            # report. Relaxation energy, NOT binding affinity.
            if not complex_pdb or not complex_pdb.is_file():
                job["status"] = "failed"; job["failure_reason"] = f"missing_complex_pdb: candidate {req.candidate_id!r} has no complex PDB at {complex_pdb}"
                job["end_time"] = _now_iso(); _write_job(job); return
            out = job_dir / "openmm_out"; out.mkdir(parents=True, exist_ok=True)
            relaxed = out / f"{req.candidate_id}_relaxed.pdb"
            import subprocess
            cmd = [scorers.SCORER_PY, str(OPENMM_SMOKE_SCRIPT), str(complex_pdb), str(relaxed)]
            with open(log_path, "w", encoding="utf-8") as lf:
                proc = subprocess.run(cmd, cwd=str(out), stdout=lf, stderr=subprocess.STDOUT, timeout=600, check=False)
            job["exit_code"] = proc.returncode
            job["status"] = "succeeded" if proc.returncode == 0 else "failed"
            job["failure_reason"] = "" if proc.returncode == 0 else "openmm smoke non-zero exit; see logs"
            job["command"] = cmd
            job["env"] = {"python": scorers.SCORER_PY, "complex_pdb": str(complex_pdb)}
            job["sha256"] = _sha256_file(complex_pdb)
            job["output_path"] = str(out)
            job["artifacts"] = [str(relaxed)] if relaxed.is_file() else []
            try:
                _j = _extract_last_json(log_path.read_text(encoding="utf-8", errors="ignore")) or {}
                job["result_summary"] = {"label": "openmm relaxation energy (NOT binding affinity)",
                                         "initial_energy_kj_mol": _j.get("initial_energy_kj_mol"),
                                         "final_energy_kj_mol": _j.get("final_energy_kj_mol"),
                                         "missing_report": _j.get("missing_report"),
                                         "minimize_steps": _j.get("minimize_steps"),
                                         "complex_source": COMPLEX_SOURCE_LABELS.get(req.candidate_id, "see manifest")}
            except Exception:
                job["result_summary"] = {"label": "openmm relaxation (see log)"}

        elif sid == "mmgbsa":
            # D25: MM-GBSA (igb=2 OBC) 3-file dG on OpenMM-relaxed complex.
            # 2-step: openmm relax -> mmpbsa_3file.py. Honest dG (positive =
            # unfavorable for the placement pose), NOT Kd, NOT fabricated.
            if not complex_pdb or not complex_pdb.is_file():
                job["status"] = "failed"; job["failure_reason"] = f"missing_complex_pdb: candidate {req.candidate_id!r} has no complex PDB at {complex_pdb}"
                job["end_time"] = _now_iso(); _write_job(job); return
            out = job_dir / "mmgbsa_out"; out.mkdir(parents=True, exist_ok=True)
            relaxed = out / f"{req.candidate_id}_relaxed.pdb"
            import subprocess
            relax_cmd = [scorers.SCORER_PY, str(OPENMM_SMOKE_SCRIPT), str(complex_pdb), str(relaxed)]
            with open(log_path, "w", encoding="utf-8") as lf:
                rc = subprocess.run(relax_cmd, cwd=str(out), stdout=lf, stderr=subprocess.STDOUT, timeout=600, check=False)
            if rc.returncode != 0 or not relaxed.is_file():
                job["exit_code"] = rc.returncode; job["status"] = "failed"
                job["failure_reason"] = "openmm relax step failed; see logs"; job["end_time"] = _now_iso(); _write_job(job); return
            mm_cmd = [scorers.SCORER_PY, str(MMPBSA_SMOKE_SCRIPT), str(relaxed), str(out)]
            mm_log = out / "mmpbsa.log"
            with open(mm_log, "w", encoding="utf-8") as lf:
                proc = subprocess.run(mm_cmd, cwd=str(out), stdout=lf, stderr=subprocess.STDOUT, timeout=900, check=False)
            job["exit_code"] = proc.returncode
            job["status"] = "succeeded" if proc.returncode == 0 else "failed"
            job["failure_reason"] = "" if proc.returncode == 0 else "mmpbsa non-zero exit; see logs"
            job["command"] = mm_cmd
            job["env"] = {"python": scorers.SCORER_PY, "amberhome": AMBERHOME_DIR, "relaxed_complex": str(relaxed)}
            job["sha256"] = _sha256_file(relaxed)
            job["output_path"] = str(out)
            try:
                import re as _re
                _j = _extract_last_json(mm_log.read_text(encoding="utf-8", errors="ignore")) or {}
                _dg = _j.get("mmgbsa_deltaG_kcal_mol")
                if _dg is None:
                    # smoke script leaves deltaG null; parse DELTA TOTAL from results_tail
                    _tail = _j.get("results_tail", "")
                    _m = _re.search(r"DELTA TOTAL\s+(-?\d+\.\d+)", _tail)
                    if _m:
                        _dg = float(_m.group(1))
                job["result_summary"] = {"label": "mmgbsa_deltaG_kcal_mol (rescore of bound complex; NOT Kd; positive=unfavorable)",
                                         "mmgbsa_deltaG_kcal_mol": _dg,
                                         "mmpbsa_exit": _j.get("mmpbsa_exit"),
                                         "complex_source": COMPLEX_SOURCE_LABELS.get(req.candidate_id, "see manifest"),
                                         "disclosure": "positive dG reflects placement pose, not a real binding pose"}
            except Exception:
                job["result_summary"] = {"label": "mmgbsa (see log)"}

        elif sid == "af2_multimer":
            # D25: AF2-Multimer v3 via localcolabfold (single_sequence, GPU
            # cuda:1). Reuses D19 per-candidate FASTA (receptor:peptide).
            # Returns pLDDT/pTM/ipTM confidence (NOT affinity; pLDDT NOT Kd).
            # D26: D19 scoring_runs dirs use full p33u_d10_* names for non-pepmlm
            # candidates but short names for pepmlm. Try short, then p33u_d10_ prefix.
            fasta = D19_SCORING_RUNS / req.candidate_id / "colabfold" / f"{req.candidate_id}.fasta"
            if not fasta.is_file():
                _full = "p33u_d10_" + req.candidate_id
                _alt = D19_SCORING_RUNS / _full / "colabfold" / f"{_full}.fasta"
                if _alt.is_file():
                    fasta = _alt
            if not fasta.is_file():
                job["status"] = "failed"; job["failure_reason"] = f"missing_af2_fasta: {fasta}"
                job["end_time"] = _now_iso(); _write_job(job); return
            if not COLABFOLD_BIN.is_file():
                job["status"] = "blocked_dependency"; job["failure_reason"] = "colabfold_batch not installed"
                job["end_time"] = _now_iso(); _write_job(job); return
            out = job_dir / "af2_out"; out.mkdir(parents=True, exist_ok=True)
            import subprocess, os as _os
            env = dict(_os.environ)
            _gpu = req.gpu_device or "1"
            if _gpu.startswith("cuda:"):
                _gpu = _gpu.split(":", 1)[1]
            env["CUDA_VISIBLE_DEVICES"] = _gpu
            env["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
            cmd = [str(COLABFOLD_BIN), "--msa-mode", "single_sequence", "--model-type",
                   "alphafold2_multimer_v3", "--num-models", "1", "--rank", "iptm",
                   str(fasta), str(out)]
            with open(log_path, "w", encoding="utf-8") as lf:
                proc = subprocess.run(cmd, cwd=str(out), env=env, stdout=lf, stderr=subprocess.STDOUT, timeout=1200, check=False)
            job["exit_code"] = proc.returncode
            job["status"] = "succeeded" if proc.returncode == 0 else "failed"
            job["failure_reason"] = "" if proc.returncode == 0 else "af2 colabfold non-zero exit; see logs"
            job["command"] = cmd
            job["gpu_used"] = req.gpu_device or "cuda:1"
            job["env"] = {"colabfold": str(COLABFOLD_BIN), "cuda_visible_devices": env["CUDA_VISIBLE_DEVICES"]}
            job["output_path"] = str(out)
            # Parse pLDDT/pTM/ipTM from colabfold scores JSON
            try:
                import json as _json, glob as _glob
                _sf = _glob.glob(str(out / "*_scores_rank_001_*.json"))
                if _sf:
                    _j = _json.loads(Path(_sf[0]).read_text(encoding="utf-8"))
                    _plddt = _j.get("plddt", [])
                    _mean = round(sum(_plddt) / len(_plddt), 2) if _plddt else None
                    job["sha256"] = _sha256_file(Path(_sf[0]))
                    job["result_summary"] = {"label": "af2_multimer confidence (pLDDT/pTM/ipTM; NOT affinity; pLDDT NOT Kd)",
                                             "af2_plddt": _mean, "af2_ptm": _j.get("ptm"),
                                             "af2_iptm": _j.get("iptm"), "max_pae": _j.get("max_pae"),
                                             "msa_mode": "single_sequence", "model_type": "alphafold2_multimer_v3",
                                             "complex_source": COMPLEX_SOURCE_LABELS.get(req.candidate_id, "see manifest")}
                else:
                    job["result_summary"] = {"label": "af2_multimer (see log)", "note": "no scores JSON found"}
            except Exception:
                job["result_summary"] = {"label": "af2_multimer (see log)"}
        else:
            job["status"] = "failed"; job["failure_reason"] = f"unknown scorer_id: {sid}"
            job["end_time"] = _now_iso()
    except Exception as exc:
        job["status"] = "failed"
        job["failure_reason"] = f"exception: {exc!r}"
        job["end_time"] = _now_iso()
        logger.exception("p33u scorer run thread failed")
    finally:
        _write_job(job)


@router.post("/run/scorer")
async def run_scorer(req: ScorerRunRequest) -> JSONResponse:
    ok, reason = _validate_confirm(req.confirm)
    if not ok:
        return JSONResponse(status_code=403, content={
            "code": 403, "data": {"status": "BLOCKED", "reason": reason},
            "validation_status": VALIDATION_STATUS,
            "message": "Safety confirmations incomplete."})

    if req.scorer_id not in AVAILABLE_SCORERS and req.scorer_id not in BLOCKED_SCORERS:
        raise HTTPException(status_code=404, detail=f"unknown scorer_id: {req.scorer_id}")

    job_id = f"p33u_scorer_{uuid.uuid4().hex[:16]}"
    run_id = f"scorer_{req.scorer_id}_{uuid.uuid4().hex[:12]}"
    cand = req.candidate_id
    job = _new_job_skeleton(job_id, run_id, "scorer", req.scorer_id, "", cand, req.confirm.model_dump())
    job["gpu_used"] = None
    _write_job(job)

    # D25: thread all scorers (af2 ~100s GPU; openmm/mmgbsa a few s).
    t = threading.Thread(target=_run_scorer_thread, args=(job, req), daemon=True)
    t.start()

    return JSONResponse(status_code=202, content={"code": 202, "data": job,
                                                  "validation_status": VALIDATION_STATUS,
                                                  "message": "Scorer run accepted. Poll GET /api/v1/p33u/jobs/{job_id}."})


# ---------------------------------------------------------------------------
# Job status / logs / artifacts
# ---------------------------------------------------------------------------

def _new_job_skeleton(job_id: str, run_id: str, kind: str, model_or_scorer: str,
                      input_target: str, input_candidate: str,
                      confirm_flags: dict[str, bool]) -> dict[str, Any]:
    gate = _gate_json(job_id, "model_run" if kind == "model" else "scorer_run",
                      model_or_scorer, confirm_flags)
    return {
        "job_id": job_id,
        "run_id": run_id,
        "kind": kind,
        "model_or_scorer": model_or_scorer,
        "input_target": input_target,
        "input_candidate": input_candidate,
        "start_time": _now_iso(),
        "end_time": "",
        "command": [],
        "env": {},
        "gpu_used": None,
        "checkpoint_loaded": "",
        "exit_code": None,
        "status": "running" if model_or_scorer not in BLOCKED_MODELS else "blocked_license",
        "failure_reason": "",
        "output_path": "",
        "sha256": "",
        "gate": gate,
        "validation_status": VALIDATION_STATUS,
        "prediction_tag": PREDICTION_TAG,
        "wetlab_validation_planned": True,
        "round": ROUND_TAG,
    }


@router.get("/jobs")
async def list_jobs(limit: int = 20) -> JSONResponse:
    jobs = []
    if JOB_STORE_ROOT.is_dir():
        for jd in sorted(JOB_STORE_ROOT.iterdir(), reverse=True)[:limit]:
            jp = jd / "job.json"
            if jp.is_file():
                try:
                    jobs.append(json.loads(jp.read_text(encoding="utf-8")))
                except Exception:
                    pass
    return JSONResponse(status_code=200, content={"code": 200, "data": {"jobs": jobs, "count": len(jobs)},
                                                  "validation_status": VALIDATION_STATUS})


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> JSONResponse:
    job = _read_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JSONResponse(status_code=200, content={"code": 200, "data": job,
                                                  "validation_status": VALIDATION_STATUS})


@router.get("/jobs/{job_id}/logs")
async def get_job_logs(job_id: str) -> JSONResponse:
    lp = _job_dir(job_id) / "log.txt"
    if not lp.is_file():
        # fall back to adapter log if referenced in job
        job = _read_job(job_id) or {}
        op = job.get("output_path", "")
        return JSONResponse(status_code=200, content={"code": 200, "data": {
            "job_id": job_id, "log": "", "note": "no log.txt yet; job may still be running"},
            "validation_status": VALIDATION_STATUS})
    try:
        text = lp.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"cannot read log: {exc}")
    return JSONResponse(status_code=200, content={"code": 200, "data": {
        "job_id": job_id, "log": text, "sha256": _sha256_file(lp)},
        "validation_status": VALIDATION_STATUS})


@router.get("/jobs/{job_id}/artifacts")
async def get_job_artifacts(job_id: str) -> JSONResponse:
    jd = _job_dir(job_id)
    job = _read_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    artifacts = []
    # 1. files in job dir
    if jd.is_dir():
        for f in sorted(jd.rglob("*")):
            if f.is_file() and f.name not in ("job.json", "log.txt"):
                artifacts.append({"name": str(f.relative_to(jd)), "path": str(f),
                                  "sha256": _sha256_file(f), "size": f.stat().st_size})
    # 2. referenced output (model adapter artifacts live under data_dev/artifacts/pepmlm/<run_id>)
    result_summary = job.get("result_summary") or {}
    arts = result_summary.get("artifacts") if isinstance(result_summary, dict) else None
    if isinstance(arts, dict):
        for rel, full in arts.items():
            p = Path(full)
            if p.is_file():
                artifacts.append({"name": rel, "path": str(p), "sha256": _sha256_file(p),
                                  "size": p.stat().st_size})
    # 3. D22: cross-reference P33T dev DB for smoke candidates ingested from this job.
    ingested = _smoke_candidates_for_job(job_id)
    # 4. D23: surface full provenance + dispatch contract metadata so the Run
    #    Console job detail can show adapter_id / adapter_formal_path / dispatch
    #    contract / source_round / seed / script+config+checkpoint SHA / gate JSON.
    provenance = job.get("provenance") or {}
    dispatch_meta = {
        "dispatch_contract": job.get("dispatch_contract"),
        "dispatch_module": job.get("dispatch_module"),
        "dispatch_entrypoint": job.get("dispatch_entrypoint"),
        "adapter_registry_id": job.get("adapter_registry_id"),
    }
    # source_round: infer from ingested smoke candidates if present, else None.
    source_round = None
    if ingested:
        rounds = sorted({r.get("source_round") for r in ingested if r.get("source_round")})
        source_round = rounds[0] if rounds else None
    return JSONResponse(status_code=200, content={"code": 200, "data": {
        "job_id": job_id, "artifacts": artifacts, "count": len(artifacts),
        "ingested_smoke_candidates": ingested,
        "ingested_smoke_candidate_count": len(ingested),
        "source_round": source_round,
        "provenance": provenance,
        "dispatch": dispatch_meta,
        "gate_json_path": str(jd / "job.json") if jd.is_dir() else None,
        "smoke_candidate_note": (
            "dev_smoke_candidate: NOT Top4, NOT wetlab shortlist, NOT experimentally validated. "
            "Computational prediction only."
        )},
        "validation_status": VALIDATION_STATUS})


# ---------------------------------------------------------------------------
# GET /smoke-candidates  (D22: dev smoke candidates ingested to P33T dev DB)
# ---------------------------------------------------------------------------

P33T_DEV_DB = Path(
    "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/db/p33t_results.db"
)


def _smoke_candidates_for_job(job_id: str) -> list[dict[str, Any]]:
    """Return dev_smoke_candidate rows in P33T dev DB whose source_job_id matches."""
    if not P33T_DEV_DB.is_file():
        return []
    try:
        import sqlite3
        conn = sqlite3.connect(str(P33T_DEV_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT candidate_id, sequence, length, source_model_id, source_run_id, "
            "input_target, candidate_class, source_round, not_for_primary_ranking, "
            "not_for_wetlab_shortlist, source_job_id, gate_json_path, promotion_status "
            "FROM p33t_candidate_peptide "
            "WHERE candidate_class='dev_smoke_candidate' AND source_job_id=?",
            (job_id,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


def _build_d30_scoring(cur: Any, candidate_id: str) -> dict[str, Any]:
    """D30: build a unified-scoring summary for a smoke candidate from its
    p33t_candidate_metric rows whose metric_id starts with 'p33u_d30_'.

    Returns an honest, D26-standard 5-scorer summary (PRODIGY, Vina, OpenMM,
    MMGBSA, AF2-Multimer). Values are computational predictions, NOT Kd / NOT
    affinity. If no D30 metrics exist yet, returns status='not_scored'.
    Mirrors the D26 unified scoring matrix columns so the UI can render a
    challenger comparison without mixing into the primary ranking.
    """
    D30_METRIC_TO_SCORER = {
        "prodigy_delta_g_kcal_mol": "prodigy",
        "prodigy_predicted_kd_molar": "prodigy",
        "vina_pose_score_kcal_mol": "vina",
        "openmm_initial_energy_kj_mol": "openmm",
        "openmm_final_energy_kj_mol": "openmm",
        "mmgbsa_delta_g_kcal_mol": "mmgbsa",
        "af2_plddt": "af2_multimer",
        "af2_ptm": "af2_multimer",
        "af2_iptm": "af2_multimer",
        "af2_max_pae": "af2_multimer",
    }
    summary: dict[str, Any] = {
        "d30_round": "P33U_D30",
        "status": "not_scored",
        "scorers_succeeded": 0,
        "scorers_expected": 5,
        "complex_source": None,
        "values": {},
        "provenance": {},
        "disclosure": "All values are computational predictions. Docking pose NOT Kd. "
                      "pLDDT/ipTM are confidence metrics NOT affinity. MMGBSA positive "
                      "= unfavorable. NOT_EXPERIMENTALLY_VALIDATED.",
    }
    try:
        cur.execute(
            "SELECT metric_id, metric_name, metric_value, unit, scorer_name, "
            "scorer_version, scorer_license, metric_provenance, artifact_sha256 "
            "FROM p33t_candidate_metric WHERE candidate_id=? AND metric_id LIKE 'p33u_d30_%'",
            (candidate_id,))
        rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        return summary
    if not rows:
        return summary
    scorer_seen: set[str] = set()
    for r in rows:
        mname = r["metric_name"]
        sname = D30_METRIC_TO_SCORER.get(mname)
        if sname:
            scorer_seen.add(sname)
        summary["values"][mname] = {
            "value": r["metric_value"], "unit": r["unit"],
            "scorer_name": r["scorer_name"],
        }
        summary["provenance"][mname] = {
            "metric_id": r["metric_id"],
            "scorer_version": r["scorer_version"],
            "scorer_license": r["scorer_license"],
            "metric_provenance": r["metric_provenance"],
            "artifact_sha256": r["artifact_sha256"],
        }
    summary["scorers_succeeded"] = len(scorer_seen)
    summary["status"] = "scored" if len(scorer_seen) == 5 else f"partial_{len(scorer_seen)}_of_5"
    # Complex source for D28 challenger: EXISTING_AF2_COMPLEX_D28_AF2 (D26 mirrors D10 evobind2)
    if candidate_id == "p33u_d28_evobind2_smoke_12aa_best":
        summary["complex_source"] = "EXISTING_AF2_COMPLEX_D28_AF2"
        summary["complex_source_label"] = ("D28 EvoBind2 AF2 (model_1_ptm) receptor+peptide "
                                           "complex, OpenMM-relaxed per scorer; NOT real docking; "
                                           "mirrors D10 evobind2 EXISTING_AF2_COMPLEX handling in D26")
    return summary



# ---- P33U-D31: Wet-lab ordering decision freeze ----
# Static authority: Top4 (D15/D18/D19D/D27) = APPROVE_FOR_QUOTE;
# D28 EvoBind2 challenger = HOLD_AS_REVIEWED_CHALLENGER;
# other 12aa primary = HOLD_NOT_FIRST_ROUND;
# 22aa deviation / dev_smoke / PPFlow / 9-10aa = NOT_FOR_FIRST_ROUND.
# This is a decision FREEZE: order_status is always 'not_ordered',
# experimental_validation is always False. Nothing here implies an order
# has been placed. PPFlow never run (blocked_license). No models/scorers run.
D31_SYNTHESIS_SPEC = {
    "purity_hplc_min": ">=95%",
    "amount_mg": 10,
    "salt_form": "TFA default; acetate exchange before cell-based safety assays",
    "n_terminus": "free (H-)",
    "c_terminus": "free (-OH)",
    "cyclization": "none (linear)",
    "label": "none (no fluorescent/biotin)",
    "storage": "lyophilized, -20C, protect from light; resuspended aliquots -80C; max 3 freeze-thaw",
    "delivery_docs": "HPLC chromatogram + MS spectrum",
}
D31_VALIDATION_PLAN = (
    "1. solubility/DLS aggregation (light-protected for Trp); "
    "2. target binding SPR/BLI/ELISA/pull-down vs Mhp Enolase (qualified personnel); "
    "3. activity/MIC screen by qualified personnel per institutional SOP; "
    "4. hemolysis/cytotoxicity basic safety window; "
    "5. enolase inhibition mechanism. No pathogen culture params; does not replace institutional SOP."
)
D31_TOP4_RISKS = {
    "pepmlm_candidate_3": "high_hydrophobic; aggregation_risk; Trp_oxidation(1W); placement_artifact_NOT_docking; low_AF2_ipTM(0.15); not_experimentally_validated",
    "pepmlm_candidate_1": "high_hydrophobic; aromatic_stack; Trp_oxidation(2W); placement_artifact_NOT_docking; low_AF2_ipTM(0.18); not_experimentally_validated",
    "pepmlm_candidate_2": "high_hydrophobic; aromatic_stack; Trp_oxidation(2W); placement_artifact_NOT_docking; lowest_AF2_ipTM(0.12); not_experimentally_validated",
    "p33u_d10_pephar_12aa_sample_2": "proline_rich(6P/12aa); poor_aqueous_solubility; placement_artifact_NOT_docking; low_AF2_ipTM(0.10); not_experimentally_validated",
}
# candidate_id -> (order_decision, reason)
D31_ORDER_DECISIONS: dict[str, tuple[str, str]] = {
    "pepmlm_candidate_3": ("APPROVE_FOR_QUOTE", "Frozen Top4 #1 (D15/D18/D19D/D27); PRODIGY dG=-5.9; D26 proposal rank 2 does not overwrite frozen Top4"),
    "pepmlm_candidate_1": ("APPROVE_FOR_QUOTE", "Frozen Top4 #2; PRODIGY dG=-5.9; D26 proposal rank 1; best Vina pose -4.303"),
    "pepmlm_candidate_2": ("APPROVE_FOR_QUOTE", "Frozen Top4 #3; PRODIGY dG=-5.0; D26 proposal rank 3"),
    "p33u_d10_pephar_12aa_sample_2": ("APPROVE_FOR_QUOTE", "Frozen Top4 #4; PRODIGY dG=-5.0; D26 proposal rank 4; model diversity (PepHAR)"),
    "p33u_d28_evobind2_smoke_12aa_best": ("HOLD_AS_REVIEWED_CHALLENGER", "D30 5/5 scored (PRODIGY -4.4, weaker than all Top4); promotion_status=reviewed_challenger; round-2 candidate; requires human approval to promote"),
    "p33u_d10_diffpepbuilder_12aa_sample_0": ("HOLD_NOT_FIRST_ROUND", "D26 proposal rank 5; PRODIGY -4.8; below Top4 threshold"),
    "p33u_d10_pephar_12aa_sample_1": ("HOLD_NOT_FIRST_ROUND", "D26 proposal rank 6; PRODIGY -4.8; proline-rich solubility concern"),
    "p33u_d10_evobind2_12aa_best": ("HOLD_NOT_FIRST_ROUND", "D26 proposal rank 7; PRODIGY -4.8; EXISTING_AF2_COMPLEX (D12)"),
    "p33u_d10_diffpepbuilder_12aa_sample_1": ("HOLD_NOT_FIRST_ROUND", "D26 proposal rank 8; PRODIGY -4.7"),
    "p33u_d10_pephar_12aa_sample_0": ("HOLD_NOT_FIRST_ROUND", "D26 proposal rank 9; PRODIGY -4.3; extreme proline content"),
}


def _build_d31_order_decision(candidate_id: str) -> dict[str, Any]:
    """D31: return the wet-lab ordering decision for a candidate.

    Static freeze: order_status is always 'not_ordered', experimental_validation
    always False. Top4 -> APPROVE_FOR_QUOTE (pending_order=True); D28 challenger
    -> HOLD_AS_REVIEWED_CHALLENGER; other 12aa primary -> HOLD_NOT_FIRST_ROUND;
    22aa deviation / dev_smoke / PPFlow / 9-10aa -> NOT_FOR_FIRST_ROUND (derived).
    NEVER returns 'ordered' or 'completed'. Does not run models/scorers, does
    not modify Top4, does not place orders.
    """
    entry = D31_ORDER_DECISIONS.get(candidate_id)
    if entry is None:
        decision = "NOT_FOR_FIRST_ROUND"
        reason = ("Not in round-1 scope (dev_smoke / 22aa or 9-10aa length deviation / "
                  "PPFlow blocked_license / not in D26 9x12aa primary matrix)")
    else:
        decision, reason = entry
    is_top4 = decision == "APPROVE_FOR_QUOTE"
    return {
        "d31_round": "P33U_D31",
        "candidate_id": candidate_id,
        "order_decision": decision,
        "order_status": "not_ordered",
        "experimental_validation": False,
        "pending_order": is_top4,
        "reason": reason,
        "risk_flags": D31_TOP4_RISKS.get(candidate_id, ""),
        "synthesis_spec": D31_SYNTHESIS_SPEC if is_top4 else None,
        "validation_plan": D31_VALIDATION_PLAN if is_top4 else None,
        "disclosure": ("COMPUTATIONAL_PREDICTION_ONLY / NOT_EXPERIMENTALLY_VALIDATED. "
                       "order_status='not_ordered' = no order placed. PPFlow blocked_license "
                       "(never run). Placement artifact NOT docking. pLDDT/ipTM are confidence "
                       "NOT affinity. Top4 authority frozen by D15/D18/D19D/D27; D26 proposal "
                       "does NOT overwrite frozen Top4."),
    }


@router.get("/d31/order-decisions")
async def d31_order_decisions() -> JSONResponse:
    """D31: wet-lab ordering decision freeze.

    Returns the order_decision for the frozen Top4 (APPROVE_FOR_QUOTE), the D28
    EvoBind2 challenger (HOLD_AS_REVIEWED_CHALLENGER), and the other 12aa primary
    (HOLD_NOT_FIRST_ROUND). 22aa/dev_smoke/PPFlow/9-10aa are NOT_FOR_FIRST_ROUND
    (derived). order_status is always 'not_ordered'; experimental_validation
    always False. NEVER 'ordered'/'completed'. Does NOT run models/scorers, does
    NOT modify Top4, does NOT place orders.
    """
    top4_ids = ["pepmlm_candidate_3", "pepmlm_candidate_1",
                "pepmlm_candidate_2", "p33u_d10_pephar_12aa_sample_2"]
    challenger_id = "p33u_d28_evobind2_smoke_12aa_best"
    hold_ids = ["p33u_d10_diffpepbuilder_12aa_sample_0", "p33u_d10_pephar_12aa_sample_1",
                "p33u_d10_evobind2_12aa_best", "p33u_d10_diffpepbuilder_12aa_sample_1",
                "p33u_d10_pephar_12aa_sample_0"]
    top4 = [_build_d31_order_decision(c) for c in top4_ids]
    challenger = _build_d31_order_decision(challenger_id)
    held = [_build_d31_order_decision(c) for c in hold_ids]
    return JSONResponse(status_code=200, content={"code": 200, "data": {
        "round": ROUND_TAG,
        "d31_round": "P33U_D31",
        "gate": "P33U_D31_WETLAB_ORDERING_APPROVAL_READY",
        "top4": top4,
        "challenger": challenger,
        "hold_not_first_round": held,
        "synthesis_spec_top4": D31_SYNTHESIS_SPEC,
        "validation_plan_top4": D31_VALIDATION_PLAN,
        "order_status_all": "not_ordered",
        "experimental_validation_all": False,
        "pending_order_top4": True,
        "ppflow_status": "PPFLOW_BLOCKED_LICENSE (never run, no checkpoint loaded, no GPU)",
        "decision_counts": {
            "APPROVE_FOR_QUOTE": len(top4),
            "HOLD_AS_REVIEWED_CHALLENGER": 1,
            "HOLD_NOT_FIRST_ROUND": len(held),
            "NOT_FOR_FIRST_ROUND": 22,
        },
        "disclosure": ("All candidates COMPUTATIONAL_PREDICTION_ONLY / NOT_EXPERIMENTALLY_VALIDATED. "
                       "No order placed. Top4 authority frozen by D15/D18/D19D/D27; D26 proposal "
                       "does NOT overwrite frozen Top4. PPFlow blocked_license."),
        "warning": "Decision freeze only; not an order; not experimental validation",
    }, "validation_status": VALIDATION_STATUS})


@router.get("/smoke-candidates")
async def list_smoke_candidates(source_round: str | None = None, model: str | None = None) -> JSONResponse:
    """D22/D23: list dev_smoke_candidate rows ingested to P33T dev DB.

    These are dev-only smoke results (D21 DiffPepBuilder / PepHAR minimal real-run
    smokes; D22 PepHAR verification rerun). They are NOT Top4, NOT wetlab
    shortlist, NOT experimentally validated. Returned separately from /results
    (primary candidates) so the UI never mixes dev smoke with primary ranking
    candidates.

    D23: optional ``source_round`` query param filters by the ingestion round
    (e.g. ``P33U_D21`` or ``P33U_D22``) so the UI can render D21 / D22 smoke in
    separate layers. Omit to list all dev-smoke rows.
    """
    if not P33T_DEV_DB.is_file():
        return JSONResponse(status_code=200, content={"code": 200, "data": {
            "smoke_candidates": [], "count": 0,
            "note": "P33T dev DB not found"},
            "validation_status": VALIDATION_STATUS})
    try:
        import sqlite3
        conn = sqlite3.connect(str(P33T_DEV_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if source_round:
            cur.execute(
                "SELECT candidate_id, sequence, length, source_model_id, source_run_id, "
                "input_target, candidate_class, source_round, not_for_primary_ranking, "
                "not_for_wetlab_shortlist, source_job_id, gate_json_path, created_at, promotion_status "
                "FROM p33t_candidate_peptide "
                "WHERE candidate_class='dev_smoke_candidate' AND source_round=? "
                "ORDER BY candidate_id",
                (source_round,))
        else:
            cur.execute(
                "SELECT candidate_id, sequence, length, source_model_id, source_run_id, "
                "input_target, candidate_class, source_round, not_for_primary_ranking, "
                "not_for_wetlab_shortlist, source_job_id, gate_json_path, created_at, promotion_status "
                "FROM p33t_candidate_peptide "
                "WHERE candidate_class='dev_smoke_candidate' ORDER BY candidate_id")
        rows = [dict(r) for r in cur.fetchall()]
        # D29: optional model filter (source_model_id)
        if model:
            rows = [r for r in rows if r.get("source_model_id") == model]
        # attach structure + metrics per candidate
        for r in rows:
            cur.execute(
                "SELECT structure_id, structure_model, pdb_path, artifact_sha256 "
                "FROM p33t_candidate_structure WHERE candidate_id=?", (r["candidate_id"],))
            r["structures"] = [dict(s) for s in cur.fetchall()]
            cur.execute(
                "SELECT metric_name, metric_value, unit, scorer_name, artifact_sha256 "
                "FROM p33t_candidate_metric WHERE candidate_id=?", (r["candidate_id"],))
            r["metrics"] = [dict(m) for m in cur.fetchall()]
            r["d30_scoring"] = _build_d30_scoring(cur, r["candidate_id"])
            r["d31_order_decision"] = _build_d31_order_decision(r["candidate_id"])
        conn.close()
    except Exception as exc:
        return JSONResponse(status_code=500, content={"code": 500, "data": {
            "error": str(exc)}, "validation_status": VALIDATION_STATUS})
    # D23: group counts by source_round so the UI can render D21 / D22 layers.
    round_counts: dict[str, int] = {}
    for r in rows:
        rk = r.get("source_round") or "unknown"
        round_counts[rk] = round_counts.get(rk, 0) + 1
    return JSONResponse(status_code=200, content={"code": 200, "data": {
        "smoke_candidates": rows, "count": len(rows),
        "candidate_class": "dev_smoke_candidate",
        "source_round_filter": source_round,
        "round_counts": round_counts,
        "not_for_primary_ranking": True,
        "not_for_wetlab_shortlist": True,
        "computational_prediction_only": True,
        "experimental_validation": False,
        "promotion_status_field": "not_reviewed (default); reviewed_challenger after D30 scoring; promoted_candidate requires human approval",
        "promotion_gate": {
            "states": ["smoke_candidate", "reviewed_challenger", "promoted_candidate", "rejected"],
            "current_default": "not_reviewed",
            "requires": "D30 unified scoring + human approval",
        },
        "d30_round_available": True,
        "d30_scorers": ["prodigy", "vina", "openmm", "mmgbsa", "af2_multimer"],
        "d30_standard": "D26 unified scoring matrix standard (5 scorers); challenger is NOT inserted into D26 primary ranking",
        "d31_round_available": True,
        "d31_order_decision_field": "d31_order_decision per candidate; APPROVE_FOR_QUOTE (Top4), HOLD_AS_REVIEWED_CHALLENGER (D28 challenger)",
        "d31_order_status_all": "not_ordered",
        "d31_experimental_validation_all": False,
        "d31_gate": "P33U_D31_WETLAB_ORDERING_APPROVAL_READY",

        "model_filter": model,
        "warning": "Dev smoke only / not Top4 / not experimentally validated",
        "round": ROUND_TAG,
    }, "validation_status": VALIDATION_STATUS})

