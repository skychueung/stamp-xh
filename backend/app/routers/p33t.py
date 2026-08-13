"""P33T result delivery center API router.

Serves candidate peptides, metrics, manifests, and delivery bundles produced by
P33S-C real model runs. All responses are tagged NOT_EXPERIMENTALLY_VALIDATED.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from app.core.security import require_active
from pydantic import BaseModel

DB_PATH = Path("/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/db/p33t_results.db")
BUNDLE_DIR = Path("/home/xh/kxc/stampup/reports_p33t/p33t_candidate_delivery_center_20260702/delivery_bundle")
P33S_C_ROOT = Path("/mnt/sdb/kxc/stamp_models/artifacts/p33s/p33s_c_20260702")
# D8: D5/D7 (P33U Lane D) candidate delivery. Additive resolution paths; the
# 9 endpoints stay identical. Manifest + artifact resolution falls back to these
# dirs when P33S_C_ROOT has no match for a D5/D7 source_run_id.
D8_BUNDLE_DIR = Path("/home/xh/kxc/stampup/reports_p33t/p33u_d8_delivery_20260703/phase5_bundle")
# D12: per-run manifests extracted from D10 bundle run_manifest.json list (fixes D11 manifest 404).
D12_MANIFESTS_DIR = Path("/home/xh/kxc/stampup/reports_p33t/p33u_d12_scoring_and_shortlist/manifests")
P33U_LANE_D_ROOT = Path("/mnt/sdb/kxc/stamp_models/artifacts/p33u_lane_d")
D5_RUN_ID = "p33u_d_min_20260703_155248"
D7_RUN_ID = "p33u_d7_20260703_2100"

VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"

# P33U-D16: D15 frozen Top4 wet-lab shortlist (replaces D12-era Top4 set).
# Source: p33u_d15_wetlab_validation_package/top4_shortlist. Frozen, do not edit.
D15_TOP4 = (
    "pepmlm_candidate_3",
    "pepmlm_candidate_1",
    "pepmlm_candidate_2",
    "p33u_d10_pephar_12aa_sample_2",
)

# P33U-D16: D15 PRODIGY predicted binding free energy (kcal/mol) for the 9 true
# 12-mer candidates. COMPUTATIONAL prediction on D15 alignment-based complexes,
# NOT wet-lab Kd. Source: p33u_d15_scoring_matrix.csv.
D15_PRODIGY = {
    "pepmlm_candidate_3": -5.935,
    "pepmlm_candidate_1": -5.877,
    "pepmlm_candidate_2": -5.044,
    "p33u_d10_pephar_12aa_sample_2": -4.994,
    "p33u_d10_evobind2_12aa_best": -4.787,
    "p33u_d10_pephar_12aa_sample_1": -4.838,
    "p33u_d10_pephar_12aa_sample_0": -4.258,
    "p33u_d10_diffpepbuilder_12aa_sample_0": -4.821,
    "p33u_d10_diffpepbuilder_12aa_sample_1": -4.682,
}

router = APIRouter(prefix="/api/v1/target-design", tags=["p33t"])


class FilterRequest(BaseModel):
    sequence_contains: str | None = None
    source_model_id: str | None = None
    min_length: int | None = None
    max_length: int | None = None
    scope: str | None = None  # D12: "all" | "P33U" | "legacy"
    length: int | None = None  # D12: exact length match
    deviation: bool | None = None  # D12: true=length!=12, false=length==12
    top4: bool | None = None  # D12: filter to Top4 wet-lab shortlist 


def _db() -> sqlite3.Connection:
    if not DB_PATH.is_file():
        raise HTTPException(status_code=503, detail="P33T database not initialized")
    return sqlite3.connect(str(DB_PATH))


def _row_to_candidate(row: sqlite3.Row) -> dict[str, Any]:
    cid = row["candidate_id"]
    in_top4 = cid in D15_TOP4
    # D22: candidate_class / source_round columns are nullable (added in D22;
    # pre-existing primary candidates have NULL = primary_candidate).
    candidate_class = row["candidate_class"] if "candidate_class" in row.keys() else None
    source_round = row["source_round"] if "source_round" in row.keys() else None
    is_smoke = candidate_class == "dev_smoke_candidate"
    return {
        "candidate_id": cid,
        "sequence": row["sequence"],
        "length": row["length"],
        "source_model_id": row["source_model_id"],
        "source_run_id": row["source_run_id"],
        "generation_rank": row["generation_rank"],
        "generation_score": row["generation_score"],
        "input_target": row["input_target"],
        "created_at": row["created_at"],
        "validation_status": VALIDATION_STATUS,
        "computational_prediction_only": True,
        "experimental_validation": False,
        # P33U-D16: wet-lab plan summary for list display.
        "top4_wetlab_shortlist": in_top4,
        "wetlab_planned_status": "PLANNED_WETLAB" if in_top4 else "not_in_top4",
        "order_status": "not_ordered" if in_top4 else "not_applicable",
        "pending_experiment": in_top4,
        "d16_wetlab_plan": _d16_wetlab_plan(cid),
        "d19_scoring": _d19_scoring(cid),
        # D22: dev_smoke_candidate disambiguation. Smoke candidates are never
        # Top4, never wetlab shortlist, never experimentally validated.
        "candidate_class": candidate_class or "primary_candidate",
        "source_round": source_round,
        "is_dev_smoke": is_smoke,
        "not_for_primary_ranking": bool(is_smoke),
        "not_for_wetlab_shortlist": bool(is_smoke),
    }


def _d12_scoring_summary(candidate_id: str) -> dict[str, Any]:
    """P33U-D16: per-candidate scoring summary.

    D15 ran PRODIGY on all 9 true 12-mer candidates (alignment-based complexes),
    so prodigy_binding_kcal_mol is now real for all 9. Vina/GNINA, MM-GBSA,
    Rosetta ddG, AF2-Multimer, and all experimental metrics remain
    unavailable_with_reason (not deleted). PRODIGY dG is a COMPUTATIONAL
    prediction, NOT a wet-lab Kd.
    """
    prodigy = D15_PRODIGY.get(candidate_id)
    return {
        "prodigy_binding_kcal_mol": prodigy,
        "prodigy_prediction_note": (
            "computational predicted binding free energy (PRODIGY on D15 "
            "alignment-based complex); NOT a wet-lab Kd"
            if prodigy is not None else None
        ),
        "prodigy_unavailable_with_reason": (
            None if prodigy is not None
            else "no PRODIGY score available for this candidate"
        ),
        "vina_unavailable_with_reason": "vina_peptide_docking_cpu_prohibitive_in_dev_receptor_truncation_attempted_and_alignment_used",
        "mmgbsa_unavailable_with_reason": "single-point MM/GBSA on AF2 unrelaxed structure non-physical (+2472 kcal/mol clashes); needs MD relaxation",
        "rosetta_ddg_unavailable_with_reason": "PyRosetta/Rosetta not installed; license-blocked",
        "af2_multimer_unavailable_with_reason": "ColabFold AF2-Multimer CPU-only (no CUDA jaxlib)",
        "experimental_all_unavailable_with_reason": "no wet-lab MIC/hemolysis/cytotoxicity/binding/efficacy performed",
        "scoring_status": "real_binding_score" if prodigy is not None else "binding_unavailable_with_reason",
    }


def _plddt_normalization(conn: sqlite3.Connection, candidate_id: str) -> dict[str, Any] | None:
    """P33U-D12: return pLDDT with normalized 0-100 scale.

    PepMLM ESMFold pLDDT is 0-1 fractional; EvoBind2 AF2 pLDDT is 0-100.
    Other models have no pLDDT. Raw value is preserved; normalized is additive.
    """
    s = conn.execute(
        "SELECT structure_model, plddt FROM p33t_candidate_structure WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    if not s or s["plddt"] is None:
        return None
    raw = s["plddt"]
    structure_model = s["structure_model"] or ""
    sm_lower = structure_model.lower()
    if "esmfold" in sm_lower:
        scale = "0-1 fractional"
        source = "ESMFold (peptide-only)"
        normalized = float(raw) * 100.0
        interpretation = (
            f"ESMFold per-residue confidence on peptide-only structure; raw {raw:.4f} on 0-1 scale "
            f"-> normalized {normalized:.2f}/100. Not directly comparable to AF2 complex pLDDT; "
            f"reflects peptide fold confidence, not binding affinity."
        )
    elif "evobind2" in sm_lower or "af2" in sm_lower:
        scale = "0-100"
        source = "AF2 (EvoBind2 receptor-peptide complex)"
        normalized = float(raw)
        interpretation = (
            f"AF2 per-residue confidence on receptor-peptide complex; raw {raw:.2f} on 0-100 scale. "
            f"Not directly comparable to ESMFold peptide-only pLDDT; reflects complex confidence, "
            f"not binding affinity."
        )
    else:
        scale = "0-100 (assumed)"
        source = structure_model
        normalized = float(raw)
        interpretation = f"pLDDT from {structure_model}; scale assumed 0-100. Not a binding affinity metric."
    return {
        "plddt_raw": raw,
        "plddt_raw_scale": scale,
        "plddt_normalized_0_100": round(normalized, 4),
        "plddt_source": source,
        "plddt_interpretation": interpretation,
        "structure_model": structure_model,
    }


def _d16_wetlab_plan(candidate_id: str) -> dict[str, Any]:
    """P33U-D16: wet-lab validation plan status for a candidate.

    Top4 candidates return PLANNED_WETLAB with not_ordered / not_started statuses.
    Non-Top4 candidates return not_in_top4. No field is ever marked completed or
    validated — all experimental fields remain not_started / pending.
    """
    if candidate_id in D15_TOP4:
        return {
            "wetlab_planned_status": "PLANNED_WETLAB",
            "top4_wetlab_shortlist": True,
            "tracking_status": "PLANNED",
            "order_status": "not_ordered",
            "sample_status": "not_synthesized",
            "assay_status": {
                "binding_assay_status": "not_started",
                "activity_assay_status": "not_started",
                "safety_assay_status": "not_started",
                "mechanism_assay_status": "not_started",
            },
            "experimental_validation": False,
            "pending_experiment": True,
            "planned_assays": [
                "solubility_stability",
                "binding_SPR_BLI_or_ELISA_or_pull_down",
                "MIC_broth_microdilution_by_qualified_personnel_per_institutional_SOP",
                "hemolysis",
                "cytotoxicity",
            ],
        }
    return {
        "wetlab_planned_status": "not_in_top4",
        "top4_wetlab_shortlist": False,
        "tracking_status": "not_planned",
        "order_status": "not_applicable",
        "sample_status": "not_applicable",
        "assay_status": {
            "binding_assay_status": "not_started",
            "activity_assay_status": "not_started",
            "safety_assay_status": "not_started",
            "mechanism_assay_status": "not_started",
        },
        "experimental_validation": False,
        "pending_experiment": False,
        "planned_assays": [],
    }


_D19_MATRIX_CACHE = {"mtime": 0.0, "data": {}}


def _load_d19_matrix() -> dict[str, Any]:
    """Load D19 scoring matrix JSON with mtime cache. Returns {} if missing."""
    path = "/mnt/sdb/kxc/p33u_d19_work/d19_scoring_matrix.json"
    try:
        m = os.path.getmtime(path)
    except OSError:
        return {}
    if m != _D19_MATRIX_CACHE["mtime"]:
        try:
            with open(path) as f:
                _D19_MATRIX_CACHE["data"] = json.load(f)
            _D19_MATRIX_CACHE["mtime"] = m
        except Exception:
            return {}
    return _D19_MATRIX_CACHE["data"]


def _d19_scoring(candidate_id: str) -> dict[str, Any]:
    """P33U-D19: per-candidate computational scoring from D19 matrix.

    Returns scores from the D19 orchestrator (PRODIGY/Vina/OpenMM/MM-GBSA/AF2-Multimer).
    Unavailable scorers recorded with reason. ALL values are computational predictions,
    NOT experimental. Docking score != Kd; pLDDT != affinity; PRODIGY/MM-GBSA are predicted not measured.
    """
    matrix = _load_d19_matrix()
    if not matrix:
        return {}
    for c in matrix.get("candidates", []):
        if c.get("cid") == candidate_id:
            scores: dict[str, Any] = {}
            for key in ("prodigy", "vina", "openmm", "mmpbsa", "af2_multimer"):
                s = c.get(key, {})
                for k in ("prodigy_deltaG_kcal_mol", "vina_pose_score_kcal_mol",
                          "openmm_final_energy_kj_mol", "mmgbsa_deltaG_kcal_mol",
                          "af2_plddt", "af2_ptm", "af2_iptm"):
                    if isinstance(s, dict) and k in s:
                        scores[k] = s[k]
            unavailable = {
                "gnina": c.get("gnina", {}).get("unavailable_with_reason", "unavailable_with_reason") if isinstance(c.get("gnina"), dict) else "unavailable_with_reason",
                "pyrosetta": c.get("pyrosetta", {}).get("unavailable_with_reason", "blocked_license") if isinstance(c.get("pyrosetta"), dict) else "blocked_license",
                "haddock": "unavailable_with_reason",
                "mic": "unavailable_with_reason",
            }
            return {
                "round": "P33U_D19B",
                "scores": scores,
                "unavailable": unavailable,
                "provenance": "PRODIGY 2.4.0; Vina 1.2.7; OpenMM 8.5.2; AmberTools MMPBSA.py 14.0; ColabFold AF2-Multimer v3 (jax 0.5.3 GPU). See /api/v1/p33s/scorer-availability.",
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                "prediction_tag": "COMPUTATIONAL_PREDICTION_ONLY",
            }
    return {}


def _resolve_candidate_id(conn: sqlite3.Connection, candidate_id: str) -> str | None:
    """Resolve a candidate_id, following the D9 alias table if direct lookup misses.

    D8 bundle referenced PepMLM candidates as p33u_d8_pepmlm_pepmlm_candidate_N
    while the D5 DB rows are pepmlm_candidate_N. The alias table bridges the two
    without rewriting original D5 evidence. Returns the canonical candidate_id
    or None if neither direct nor alias lookup succeeds.
    """
    row = conn.execute(
        "SELECT candidate_id FROM p33t_candidate_peptide WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    if row:
        return row[0]
    alias = conn.execute(
        "SELECT canonical_id FROM p33t_candidate_alias WHERE alias_id = ?",
        (candidate_id,),
    ).fetchone()
    if alias:
        return alias[0]
    return None


@router.get("/results", dependencies=[Depends(require_active)])
async def list_candidates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source_model_id: str | None = None,
    scope: str = Query("P33U", pattern="^(all|P33U|legacy)$"),
    length: int | None = None,
    deviation: bool | None = None,
    top4: bool | None = None,
    include_smoke: bool = Query(False, description="D22: include dev_smoke_candidate rows (default excluded so primary ranking is never polluted)"),
) -> JSONResponse:
    conn = _db()
    conn.row_factory = sqlite3.Row
    where = []
    params: list[Any] = []
    if source_model_id:
        where.append("source_model_id = ?")
        params.append(source_model_id)
    # D12: scope filter disambiguates P33U vs legacy p33t_ P33S-C demo candidates.
    if scope == "P33U":
        where.append("candidate_id NOT LIKE ?")
        params.append("p33t_%")
    elif scope == "legacy":
        where.append("candidate_id LIKE ?")
        params.append("p33t_%")
    if length is not None:
        where.append("length = ?")
        params.append(length)
    if deviation is True:
        where.append("length != 12")
    elif deviation is False:
        where.append("length = 12")
    if top4:
        # P33U-D16: D15 frozen Top4 (3 PepMLM + 1 PepHAR; replaces D12 set).
        where.append("candidate_id IN (?, ?, ?, ?)")
        params.extend(list(D15_TOP4))
    # D22: dev_smoke_candidate rows (D21 DiffPepBuilder/PepHAR smoke) are EXCLUDED
    # by default so primary ranking / Top4 / wetlab shortlist never mix with dev
    # smoke. Opt in via include_smoke=true. Smoke candidates are also reachable
    # via the p33u /api/v1/p33u/smoke-candidates endpoint.
    if not include_smoke:
        where.append("(candidate_class IS NULL OR candidate_class != 'dev_smoke_candidate')")
    sql = "SELECT * FROM p33t_candidate_peptide"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY generation_score ASC LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    rows = conn.execute(sql, params).fetchall()
    # total respects scope + model filter (D12 fix: previously unscoped)
    count_sql = "SELECT COUNT(*) FROM p33t_candidate_peptide"
    if where:
        count_sql += " WHERE " + " AND ".join(where)
    total = conn.execute(count_sql, params[:-2]).fetchone()[0]
    conn.close()
    return JSONResponse(status_code=200, content={
        "code": 200,
        "data": {
            "items": [_row_to_candidate(r) for r in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
        "validation_status": VALIDATION_STATUS,
        "computational_prediction_only": True,
        "experimental_validation": False,
    })


@router.get("/results/{candidate_id}", dependencies=[Depends(require_active)])
async def get_candidate(candidate_id: str) -> JSONResponse:
    conn = _db()
    conn.row_factory = sqlite3.Row
    resolved_id = _resolve_candidate_id(conn, candidate_id)
    if resolved_id is None:
        conn.close()
        raise HTTPException(status_code=404, detail="candidate not found")
    row = conn.execute("SELECT * FROM p33t_candidate_peptide WHERE candidate_id = ?", (resolved_id,)).fetchone()
    plddt_norm = _plddt_normalization(conn, resolved_id) if row else None
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="candidate not found")
    data = _row_to_candidate(row)
    if plddt_norm:
        data["plddt_normalization"] = plddt_norm
    # P33U-D12: scoring summary
    data["d12_scoring"] = _d12_scoring_summary(resolved_id)
    # P33U-D16: D15 frozen Top4 + wet-lab plan (PLANNED, not validated).
    data["top4_wetlab_shortlist"] = resolved_id in D15_TOP4
    data["d16_wetlab_plan"] = _d16_wetlab_plan(resolved_id)
    data["d19_scoring"] = _d19_scoring(resolved_id)
    if resolved_id != candidate_id:
        data["queried_alias_id"] = candidate_id
    return JSONResponse(status_code=200, content={
        "code": 200,
        "data": data,
        "validation_status": VALIDATION_STATUS,
        "computational_prediction_only": True,
        "experimental_validation": False,
    })


@router.get("/results/{candidate_id}/metrics", dependencies=[Depends(require_active)])
async def get_candidate_metrics(candidate_id: str) -> JSONResponse:
    conn = _db()
    conn.row_factory = sqlite3.Row
    resolved_id = _resolve_candidate_id(conn, candidate_id)
    if resolved_id is None:
        conn.close()
        raise HTTPException(status_code=404, detail="candidate not found")
    rows = conn.execute(
        "SELECT * FROM p33t_candidate_metric WHERE candidate_id = ? ORDER BY metric_name", (resolved_id,)
    ).fetchall()
    conn.close()
    metrics = []
    for r in rows:
        metrics.append({
            "metric_id": r["metric_id"],
            "metric_name": r["metric_name"],
            "metric_value": r["metric_value"],
            "unit": r["unit"],
            "scorer_name": r["scorer_name"],
            "scorer_version": r["scorer_version"],
            "scorer_license": r["scorer_license"],
            "metric_provenance": json.loads(r["metric_provenance"]),
            "unavailable_with_reason": r["unavailable_with_reason"],
            "artifact_sha256": r["artifact_sha256"],
        })
    return JSONResponse(status_code=200, content={
        "code": 200,
        "data": {"candidate_id": resolved_id, "metrics": metrics},
        "validation_status": VALIDATION_STATUS,
        "computational_prediction_only": True,
        "experimental_validation": False,
    })


@router.get("/results/{candidate_id}/manifest", dependencies=[Depends(require_active)])
async def get_candidate_manifest(candidate_id: str) -> JSONResponse:
    conn = _db()
    conn.row_factory = sqlite3.Row
    resolved_id = _resolve_candidate_id(conn, candidate_id)
    if resolved_id is None:
        conn.close()
        raise HTTPException(status_code=404, detail="candidate not found")
    row = conn.execute(
        "SELECT source_run_id FROM p33t_candidate_peptide WHERE candidate_id = ?", (resolved_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="candidate not found")
    run_id = row["source_run_id"]
    # Find manifest file by run_id
    manifest_path = None
    for model_dir in P33S_C_ROOT.iterdir():
        if not model_dir.is_dir():
            continue
        for run_dir in model_dir.iterdir():
            if run_dir.name == run_id:
                candidate = run_dir / "manifest" / "run_manifest.json"
                if candidate.is_file():
                    manifest_path = candidate
                    break
        if manifest_path:
            break
    if not manifest_path:
        # D8 fallback: D5/D7 run_manifest_{run_id}.json in D8 bundle dir
        d8_candidate = D8_BUNDLE_DIR / f"run_manifest_{run_id}.json"
        if d8_candidate.is_file() and _is_allowed_file(d8_candidate):
            manifest_path = d8_candidate
    if not manifest_path:
        # D12 fallback: D10 per-run manifests extracted from D10 bundle list.
        d12_candidate = D12_MANIFESTS_DIR / f"run_manifest_{run_id}.json"
        if d12_candidate.is_file() and _is_allowed_file(d12_candidate):
            manifest_path = d12_candidate
    if not manifest_path:
        raise HTTPException(status_code=404, detail="manifest not found")
    return JSONResponse(status_code=200, content={
        "code": 200,
        "data": json.loads(manifest_path.read_text(encoding="utf-8")),
        "validation_status": VALIDATION_STATUS,
    })


_DOWNLOAD_ALLOWED_EXTS = {".json", ".tsv", ".csv", ".txt", ".md", ".log", ".pdb"}
_DOWNLOAD_FORBIDDEN_PARTS = ["checkpoints", "envs", "source", ".git", ".."]


def _is_allowed_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if any(part in str(path) for part in _DOWNLOAD_FORBIDDEN_PARTS):
        return False
    if path.suffix not in _DOWNLOAD_ALLOWED_EXTS:
        return False
    return True


def _resolve_artifact_for_run(artifact_id: str, run_id: str) -> Path | None:
    # First: candidate's own P33S-C run directory.
    for model_dir in P33S_C_ROOT.iterdir():
        if not model_dir.is_dir():
            continue
        run_dir = model_dir / run_id
        if run_dir.is_dir():
            for f in run_dir.rglob(artifact_id):
                if _is_allowed_file(f):
                    try:
                        f.relative_to(P33S_C_ROOT)
                        return f
                    except ValueError:
                        continue
    # Second: delivery bundle files.
    bundle_file = BUNDLE_DIR / artifact_id
    if _is_allowed_file(bundle_file):
        try:
            bundle_file.relative_to(BUNDLE_DIR)
            return bundle_file
        except ValueError:
            pass
    # Third: D8 bundle dir (D5/D7 artifacts copied with descriptive names).
    d8_file = D8_BUNDLE_DIR / artifact_id
    if _is_allowed_file(d8_file):
        try:
            d8_file.relative_to(D8_BUNDLE_DIR)
            return d8_file
        except ValueError:
            pass
    return None


@router.get("/results/{candidate_id}/downloads/{artifact_id}", dependencies=[Depends(require_active)])
async def download_artifact(candidate_id: str, artifact_id: str) -> FileResponse:
    conn = _db()
    conn.row_factory = sqlite3.Row
    resolved_id = _resolve_candidate_id(conn, candidate_id)
    if resolved_id is None:
        conn.close()
        raise HTTPException(status_code=404, detail="candidate not found")
    row = conn.execute(
        "SELECT source_run_id FROM p33t_candidate_peptide WHERE candidate_id = ?", (resolved_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="candidate not found")
    run_id = row["source_run_id"]
    # Resolve artifact within the candidate's run directory or delivery bundle.
    path = _resolve_artifact_for_run(artifact_id, run_id)
    if not path:
        raise HTTPException(status_code=403, detail="artifact not in download whitelist for this candidate")
    return FileResponse(path, filename=artifact_id)


@router.post("/results/filter", dependencies=[Depends(require_active)])
async def filter_candidates(req: FilterRequest) -> JSONResponse:
    conn = _db()
    conn.row_factory = sqlite3.Row
    where = []
    params: list[Any] = []
    if req.sequence_contains:
        where.append("sequence LIKE ?")
        params.append(f"%{req.sequence_contains}%")
    if req.source_model_id:
        where.append("source_model_id = ?")
        params.append(req.source_model_id)
    # D12: scope filter
    if req.scope == "P33U":
        where.append("candidate_id NOT LIKE ?")
        params.append("p33t_%")
    elif req.scope == "legacy":
        where.append("candidate_id LIKE ?")
        params.append("p33t_%")
    if req.length is not None:
        where.append("length = ?")
        params.append(req.length)
    if req.deviation is True:
        where.append("length != 12")
    elif req.deviation is False:
        where.append("length = 12")
    if req.top4:
        # P33U-D16: D15 frozen Top4.
        where.append("candidate_id IN (?, ?, ?, ?)")
        params.extend(list(D15_TOP4))
    if req.min_length is not None:
        where.append("length >= ?")
        params.append(req.min_length)
    if req.max_length is not None:
        where.append("length <= ?")
        params.append(req.max_length)
    sql = "SELECT * FROM p33t_candidate_peptide"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY generation_score ASC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return JSONResponse(status_code=200, content={
        "code": 200,
        "data": {"items": [_row_to_candidate(r) for r in rows], "total": len(rows)},
        "validation_status": VALIDATION_STATUS,
        "computational_prediction_only": True,
        "experimental_validation": False,
    })


@router.post("/delivery-bundles", dependencies=[Depends(require_active)])
async def create_bundle() -> JSONResponse:
    # Return the latest pre-built bundle metadata.
    conn = _db()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM p33t_candidate_delivery_bundle ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="no delivery bundle available")
    return JSONResponse(status_code=200, content={
        "code": 200,
        "data": {
            "bundle_id": row["bundle_id"],
            "selected_candidate_ids": json.loads(row["selected_candidate_ids"]),
            "ranking_policy": row["ranking_policy"],
            "export_files": json.loads(row["export_files"]),
            "sha256_manifest": row["sha256_manifest"],
            "created_at": row["created_at"],
        },
        "validation_status": VALIDATION_STATUS,
        "computational_prediction_only": True,
        "experimental_validation": False,
    })


@router.get("/delivery-bundles/{bundle_id}", dependencies=[Depends(require_active)])
async def get_bundle(bundle_id: str) -> JSONResponse:
    conn = _db()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM p33t_candidate_delivery_bundle WHERE bundle_id = ?", (bundle_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="bundle not found")
    return JSONResponse(status_code=200, content={
        "code": 200,
        "data": {
            "bundle_id": row["bundle_id"],
            "selected_candidate_ids": json.loads(row["selected_candidate_ids"]),
            "ranking_policy": row["ranking_policy"],
            "export_files": json.loads(row["export_files"]),
            "sha256_manifest": row["sha256_manifest"],
            "created_at": row["created_at"],
        },
        "validation_status": VALIDATION_STATUS,
        "computational_prediction_only": True,
        "experimental_validation": False,
    })


@router.get("/delivery-bundles/{bundle_id}/download", dependencies=[Depends(require_active)])
async def download_bundle(bundle_id: str) -> StreamingResponse:
    conn = _db()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT export_files FROM p33t_candidate_delivery_bundle WHERE bundle_id = ?", (bundle_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="bundle not found")
    files = json.loads(row["export_files"])

    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in files:
            path = BUNDLE_DIR / name
            if not path.is_file():
                # D8 fallback: D8 delivery bundle dir
                d8_path = D8_BUNDLE_DIR / name
                if d8_path.is_file() and _is_allowed_file(d8_path):
                    path = d8_path
            if path.is_file() and _is_allowed_file(path):
                zf.write(path, arcname=name)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={bundle_id}.zip"},
    )
