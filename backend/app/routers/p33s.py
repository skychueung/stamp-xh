"""P33S API router — real-model GPU inference & scientific scoring pipeline.

Endpoints (all responses tagged NOT_EXPERIMENTALLY_VALIDATED):
  GET  /api/v1/p33s/scorer-availability
  POST /api/v1/p33s/{model_id}/probe
  POST /api/v1/p33s/{model_id}/dry-run
  POST /api/v1/p33s/{model_id}/real-run
  GET  /api/v1/p33s/{model_id}/jobs/{job_id}/status
  POST /api/v1/p33s/{model_id}/jobs/{job_id}/cancel
  GET  /api/v1/p33s/{model_id}/jobs/{job_id}/manifest

Real-run is gated by ALL of:
  - registry supports_real_run == true
  - registry real_run_enabled == true
  - registry execution_locked == false
  - model not in P33S UNAVAILABLE_MODELS (license/asset blockers)
Per goal: never batch-set real_run_enabled=true; only individually verified models unlock.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.p33s.orchestrator import (
    MODEL_ORDER,
    UNAVAILABLE_MODELS,
    PipelineConfig,
    cancel_job,
    run_pipeline,
)
from app.services.p33s import scorers
from app.services.target_peptide_model_registry import get_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/p33s", tags=["p33s"])

VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"


class PipelineRequest(BaseModel):
    target_sequence: str
    peptide_length: int = 10
    seed: int = 2024
    gpu_device: str | None = None
    max_wall_seconds: int = 1800
    output_quota_bytes: int = 52428800


def _can_real_run(model_id: str) -> tuple[bool, str]:
    """Check the three registry flags + P33S availability. Returns (ok, reason)."""
    if model_id in UNAVAILABLE_MODELS:
        return False, f"unavailable_with_reason: {UNAVAILABLE_MODELS[model_id]}"
    m = get_model(model_id)
    if m is None:
        return False, "model not in registry"
    if not m.get("supports_real_run", False):
        return False, "supports_real_run=false"
    if not m.get("real_run_enabled", False):
        return False, "real_run_enabled=false (locked per P33Q/P33R; individual unlock only)"
    if m.get("execution_locked", True):
        return False, "execution_locked=true"
    return True, "ok"


@router.get("/scorer-availability")
async def scorer_availability() -> JSONResponse:
    """D19 read-only scorer backend status. No model run. Reflects P33U-D19 install+smoke."""
    p33s_py = Path(scorers.SCORER_PY)
    env_prefix = scorers.SCORER_ENV_PREFIX
    vina_py = Path(env_prefix + "/lib/python3.10/site-packages/vina/__init__.py")
    openmm_py = Path(env_prefix + "/lib/python3.10/site-packages/openmm/__init__.py")
    pdbfixer_py = Path(env_prefix + "/lib/python3.10/site-packages/pdbfixer/__init__.py")
    colabfold_bin = Path("/home/xh/micromamba/envs/localcolabfold/bin/colabfold_batch")
    colabfold_params = Path("/home/xh/.cache/colabfold/params/params_model_1_multimer_v3.npz")
    mmpbsa_bin = Path(scorers.MMPBSA_BIN)
    prodigy_bin = Path(scorers.PRODIGY_BIN)
    esmfold_weights = Path("/mnt/sdb/kxc/stamp_models/artifacts/p33s/esmfold_weights_manifest.json")
    return JSONResponse(status_code=200, content={
        "code": 200,
        "data": {
            "scorers": {
                "prodigy": {
                    "backend": "PRODIGY (prodigy-prot 2.4.0, Apache-2.0)",
                    "bin_present": prodigy_bin.is_file(),
                    "smoke_test": "passed (pepmlm_candidate_3: predicted binding affinity -5.9 kcal/mol, matches D15 -5.935)",
                    "label": "prodigy_deltaG_kcal_mol / prodigy_predicted_Kd_M",
                    "status": "ok" if prodigy_bin.is_file() else "unavailable_with_reason",
                },
                "vina": {
                    "backend": "AutoDock Vina 1.2.7 (Apache-2.0)",
                    "bin_present": vina_py.is_file(),
                    "smoke_test": "passed (pepmlm_candidate_3: vina_pose_score -1.309 kcal/mol)",
                    "label": "vina_pose_score_kcal_mol",
                    "status": "installed_smoke_passed" if vina_py.is_file() else "unavailable_with_reason",
                    "note": "vina-sf pose score of bound pose (rigid receptor+ligand, no global search); docking score NOT Kd",
                },
                "openmm": {
                    "backend": "OpenMM 8.5.2 (LGPL-2.1/MIT) + PDBFixer 1.12.0",
                    "bin_present": openmm_py.is_file() and pdbfixer_py.is_file(),
                    "smoke_test": "passed (pepmlm_candidate_3: 50-step OBC2 minimization, energy drop, 0 missing atoms)",
                    "label": "openmm_final_energy_kj_mol",
                    "status": "installed_smoke_passed" if openmm_py.is_file() else "unavailable_with_reason",
                    "note": "implicit-solvent (OBC2) minimization for clash removal before MM-GBSA; relaxation energy NOT affinity",
                },
                "mmgbsa": {
                    "backend": "AmberTools MMPBSA.py 14.0 (GPL-3.0); sander 24.0; tleap; ff14SB",
                    "bin_present": mmpbsa_bin.is_file(),
                    "requires_env": "AMBERHOME=" + env_prefix,
                    "smoke_test": "passed (pepmlm_candidate_3 OpenMM-relaxed: 3-file MM-GBSA DELTA TOTAL produced)",
                    "label": "mmgbsa_deltaG_kcal_mol",
                    "status": "installed_smoke_passed" if mmpbsa_bin.is_file() else "unavailable_with_reason",
                    "note": "3-file MM-GBSA (igb=2 OBC) on OpenMM-relaxed complex; computational rescoring NOT Kd",
                },
                "af2_multimer": {
                    "backend": "ColabFold localcolabfold + AlphaFold2-Multimer v3 (jax 0.5.3 + CUDA jaxlib)",
                    "bin_present": colabfold_bin.is_file(),
                    "weights_present": colabfold_params.is_file(),
                    "gpu_inference": "passed (2x RTX 4090, CUDA jaxlib 0.5.3)",
                    "smoke_test": "passed (test complex: pLDDT=39 ipTM=0.023; pepmlm_candidate_3 462aa: pLDDT=39.7 ipTM=0.152)",
                    "label": "af2_plddt / af2_ptm / af2_iptm",
                    "status": "installed_smoke_passed" if (colabfold_bin.is_file() and colabfold_params.is_file()) else "unavailable_with_reason",
                    "note": "single_sequence mode (no MSA server: LAN cannot reach hosted MMseqs2); confidence NOT affinity; pLDDT NOT Kd",
                },
                "esmfold_plddt": {
                    "backend": "ESMFold (facebook/esmfold_v1)",
                    "env_present": p33s_py.is_file(),
                    "weights_present": esmfold_weights.is_file(),
                    "gpu_inference": "deferred",
                    "status": "env_present_weights_pending" if p33s_py.is_file() else "unavailable_with_reason",
                    "note": "monomer pLDDT deferred; complex-level confidence via AF2-Multimer ipTM this round",
                },
                "gnina": {
                    "backend": "GNINA (Apache-2.0)",
                    "bin_present": False,
                    "smoke_test": "not run",
                    "status": "unavailable_with_reason",
                    "reason": "GNINA binary not installed; D19B attempted download of prebuilt v1.3.3 gnina.cuda12.8.static (1.96GB) from github.com/gnina/gnina/releases but host network ~5KB/s makes download infeasible (~4.5d est); conda-forge/bioconda channel indexes unreachable within 40-60s; libmolgrid/caffe absent (source compile infeasible); system CUDA not modified per goal",
                },
                "haddock_hdock": {
                    "backend": "HADDOCK / HDOCK",
                    "bin_present": False,
                    "status": "unavailable_with_reason",
                    "reason": "HADDOCK requires CNS + academic registration not completed; HDOCK primarily web-server (no local binary)",
                },
                "pyrosetta": {
                    "backend": "PyRosetta / Rosetta",
                    "bin_present": False,
                    "status": "blocked_license",
                    "reason": "no PyRosetta/Rosetta academic license confirmed on this host; not bypassed per goal",
                },
                "mic": {
                    "backend": "MIC predictor",
                    "status": "unavailable_with_reason",
                    "reason": "no licensed MIC model confirmed; classification probability != MIC; no fabrication",
                },
            },
            "models": {
                mid: {"order": i + 1, "unavailable": mid in UNAVAILABLE_MODELS,
                      "unavailable_reason": UNAVAILABLE_MODELS.get(mid, "")}
                for i, mid in enumerate(MODEL_ORDER)
            },
            "validation_status": VALIDATION_STATUS,
            "prediction_tag": "COMPUTATIONAL_PREDICTION_ONLY",
            "ppflow_status": "PPFLOW_BLOCKED_LICENSE",
            "d19b_reverification": {"date": "2026-07-05", "verify_cid": "pepmlm_candidate_3", "prodigy_deltaG_kcal_mol": -5.9, "vina_pose_score_kcal_mol": -1.309, "openmm_final_energy_kj_mol": -33716.7, "mmgbsa_deltaG_kcal_mol": 48.3538, "af2_plddt": 37.4, "af2_ptm": 0.255, "af2_iptm": 0.135, "af2_runtime_s": 94.3, "af2_gpu": "GPU1 RTX4090", "d19b_new_installs": 0, "d19b_new_installs_attempted": ["gnina", "esmfold"], "d19b_new_installs_blocked": {"gnina": "network-infeasible download + conda unreachable", "esmfold": "weights pending + HF unreachable"}, "gate": "P33U_D19B_COMPUTATIONAL_SCORERS_READY"},
            "round": "P33U_D19B",
        },
    })


@router.post("/{model_id}/probe")
async def p33s_probe(model_id: str) -> JSONResponse:
    if model_id not in MODEL_ORDER:
        raise HTTPException(status_code=404, detail="unknown model_id")
    cfg = PipelineConfig(model_id=model_id, job_id=f"p33s_probe_{model_id}",
                         mode="probe", target_sequence="PROBE_ONLY")
    summary = run_pipeline(cfg)
    return JSONResponse(status_code=200, content={"code": 200, "data": summary,
                                                  "validation_status": VALIDATION_STATUS})


@router.post("/{model_id}/dry-run")
async def p33s_dry_run(model_id: str, req: PipelineRequest) -> JSONResponse:
    if model_id not in MODEL_ORDER:
        raise HTTPException(status_code=404, detail="unknown model_id")
    cfg = PipelineConfig(model_id=model_id, job_id=f"p33s_dryrun_{model_id}_{os.getpid()}",
                         mode="dry_run", target_sequence=req.target_sequence,
                         peptide_length=req.peptide_length, seed=req.seed,
                         gpu_device=req.gpu_device, max_wall_seconds=req.max_wall_seconds,
                         output_quota_bytes=req.output_quota_bytes)
    summary = run_pipeline(cfg)
    return JSONResponse(status_code=200, content={"code": 200, "data": summary,
                                                  "validation_status": VALIDATION_STATUS})


@router.post("/{model_id}/real-run")
async def p33s_real_run(model_id: str, req: PipelineRequest) -> JSONResponse:
    ok, reason = _can_real_run(model_id)
    if not ok:
        return JSONResponse(status_code=403, content={
            "code": 403, "data": {"status": "BLOCKED", "reason": reason,
                                  "model_id": model_id},
            "validation_status": VALIDATION_STATUS,
            "message": "Real run is gated; per-goal individual unlock only."})
    cfg = PipelineConfig(model_id=model_id, job_id=f"p33s_real_{model_id}_{os.getpid()}",
                         mode="real_run", target_sequence=req.target_sequence,
                         peptide_length=req.peptide_length, seed=req.seed,
                         gpu_device=req.gpu_device, max_wall_seconds=req.max_wall_seconds,
                         output_quota_bytes=req.output_quota_bytes)
    summary = run_pipeline(cfg)
    return JSONResponse(status_code=200, content={"code": 200, "data": summary,
                                                  "validation_status": VALIDATION_STATUS})


@router.get("/{model_id}/jobs/{job_id}/status")
async def p33s_status(model_id: str, job_id: str) -> JSONResponse:
    job_dir = Path("/mnt/sdb/kxc/stamp_models/artifacts/p33s") / model_id / job_id
    dm = job_dir / "delivery.manifest.json"
    if not dm.is_file():
        raise HTTPException(status_code=404, detail="job not found")
    return JSONResponse(status_code=200, content={"code": 200,
                                                  "data": json.loads(dm.read_text(encoding="utf-8")),
                                                  "validation_status": VALIDATION_STATUS})


@router.post("/{model_id}/jobs/{job_id}/cancel")
async def p33s_cancel(model_id: str, job_id: str) -> JSONResponse:
    result = cancel_job(model_id, job_id)
    return JSONResponse(status_code=200, content={"code": 200, "data": result,
                                                  "validation_status": VALIDATION_STATUS})


@router.get("/{model_id}/jobs/{job_id}/manifest")
async def p33s_manifest(model_id: str, job_id: str) -> JSONResponse:
    job_dir = Path("/mnt/sdb/kxc/stamp_models/artifacts/p33s") / model_id / job_id
    manifests = sorted(job_dir.glob("*.manifest.json"))
    if not manifests:
        raise HTTPException(status_code=404, detail="no manifests for job")
    out = {m.name: json.loads(m.read_text(encoding="utf-8")) for m in manifests}
    return JSONResponse(status_code=200, content={"code": 200, "data": out,
                                                  "validation_status": VALIDATION_STATUS})
