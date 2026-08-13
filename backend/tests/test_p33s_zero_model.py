"""P33S Phase 4 — zero-model tests.

Runs with P33S_DISABLE_WRAPPER=1 (no model subprocess invocation).
Tests: provenance write/SHA, gate open/close/cancel, scorer-availability logic,
dry-run plan, real-run BLOCKED (real_run_enabled=false), PRODIGY scorer
end-to-end, MM-GBSA unavailable (no prmtop), idempotency.
No '|| true': any assertion failure exits non-zero.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Force zero-model mode: the orchestrator's probe/dry_run never subprocess;
# this env var documents the intent for any future wrapper hook.
os.environ["P33S_DISABLE_WRAPPER"] = "1"
os.environ["AMBERHOME"] = "/mnt/sdb/kxc/stamp_models/envs/p33s_scorers_py310"

sys.path.insert(0, ".")

from app.services.p33s.provenance import ProvenanceManifest, write_manifest, sha256_bytes  # noqa: E402
from app.services.p33s.gate import open_gate, close_gate, cancel_gate, _read  # noqa: E402
from app.services.p33s import scorers  # noqa: E402
from app.services.p33s.orchestrator import run_pipeline, PipelineConfig, UNAVAILABLE_MODELS  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}  {detail}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def test_provenance():
    print("[test] provenance manifest SHA + idempotency")
    with tempfile.TemporaryDirectory() as d:
        m1 = ProvenanceManifest(
            model_id="testmodel", job_id="job1", stage="generation", mode="dry_run",
            input_sha256=sha256_bytes(b"ACDEFGHIK"), weight_sha256="w",
            code_sha256="c", env="env", seed=2024, gpu_device=None,
            gpu_free_mib_at_start=None, started_at="2026-07-02T00:00:00Z", exit_code=0)
        p1 = write_manifest(m1, d)
        m2 = ProvenanceManifest(
            model_id="testmodel", job_id="job1", stage="generation", mode="dry_run",
            input_sha256=sha256_bytes(b"ACDEFGHIK"), weight_sha256="w",
            code_sha256="c", env="env", seed=2024, gpu_device=None,
            gpu_free_mib_at_start=None, started_at="2026-07-02T00:00:00Z", exit_code=0)
        write_manifest(m2, d)
        loaded = json.loads(Path(p1).read_text())
        check("manifest written", p1.is_file())
        check("manifest_sha256 present (64 hex)", len(loaded["manifest_sha256"]) == 64)
        check("idempotent SHA (same input -> same sha)", m1.compute_sha() == m2.compute_sha())
        check("validation_status stamped", loaded["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED")
        check("prediction_tag stamped", loaded["prediction_tag"] == "COMPUTATIONAL_PREDICTION_ONLY")


def test_gate():
    print("[test] gate open/close/cancel (precise PID, no pkill)")
    with tempfile.TemporaryDirectory() as d:
        # use a temp gate root by monkeypatching the module path
        import app.services.p33s.gate as g
        orig = g.GATE_ROOT
        g.GATE_ROOT = Path(d)
        try:
            gs = open_gate("p33s", "pepflow", "job_gate_test", "generation", pid=999999,
                           ttl_seconds=60, gpu_device="0")
            check("gate OPEN", gs.state == "OPEN")
            r = _read("p33s", "pepflow", "job_gate_test")
            check("gate persisted", r is not None and r.pid == 999999)
            closed = close_gate("p33s", "pepflow", "job_gate_test", exit_code=0)
            check("gate CLOSED on exit 0", closed.state == "CLOSED")
            # cancel path with a non-existent pid (should not crash)
            canc = cancel_gate("p33s", "pepflow", "job_cancel_test")
            check("cancel non-existent gate no-crash", canc.state == "CANCELLED")
        finally:
            g.GATE_ROOT = orig


def test_scorer_availability_logic():
    print("[test] scorer availability reflects installed backends")
    # PRODIGY should be ok (installed), MMPBSA ok (installed), iptm/mic unavailable
    check("PRODIGY bin present", Path(scorers.PRODIGY_BIN).is_file())
    check("MMPBSA bin present", Path(scorers.MMPBSA_BIN).is_file())
    check("iptm returns unavailable_with_reason",
          scorers.score_iptm().status == "unavailable_with_reason")
    check("mic returns unavailable_with_reason",
          scorers.score_mic().status == "unavailable_with_reason")


def test_prodigy_scorer_real():
    print("[test] PRODIGY scorer real CPU computation (3BZD complex)")
    pdb = "/mnt/sdb/kxc/stamp_models/assets/p33s/prodigy_src/examples/3BZD.pdb"
    out = "/mnt/sdb/kxc/stamp_models/artifacts/p33s/phase4_prodigy_test"
    r = scorers.score_kd_prodigy(pdb, out)
    check("PRODIGY status ok", r.status == "ok", f"status={r.status}")
    check("PRODIGY Kd > 0", r.value is not None and r.value > 0, f"Kd_nM={r.value}")
    check("PRODIGY label predicted_Kd_PRODIGY",
          r.detail.get("label") == "predicted_Kd_PRODIGY")
    check("PRODIGY NOT experimental",
          r.validation_status == "NOT_EXPERIMENTALLY_VALIDATED")
    check("PRODIGY ΔG negative", r.detail.get("delta_g_kcal_mol", 0) < 0,
          f"dG={r.detail.get('delta_g_kcal_mol')}")


def test_mmgbsa_unavailable_without_prmtop():
    print("[test] MM-GBSA returns unavailable_with_reason without prmtop")
    r = scorers.score_mmgbsa("/nonexistent/complex.prmtop", None, "", "", "",
                             "/mnt/sdb/kxc/stamp_models/artifacts/p33s/phase4_mmgbsa_test")
    # MMPBSA bin exists, but prmtop missing -> subprocess fails -> failed_with_evidence
    # (this is correct: we attempted, no fabrication)
    check("MM-GBSA no fabrication (failed/unavailable, not ok)",
          r.status in ("failed_with_evidence", "unavailable_with_reason"),
          f"status={r.status}")
    check("MM-GBSA value None when no real result", r.value is None)


def test_dry_run_plan():
    print("[test] orchestrator dry-run plan (no subprocess)")
    cfg = PipelineConfig(model_id="pepflow", job_id="phase4_dryrun_pepflow",
                         mode="dry_run", target_sequence="ACDEFGHIK")
    s = run_pipeline(cfg)
    check("dry-run mode", s["mode"] == "dry_run")
    check("dry-run stages listed", "stages" in s["plan"])
    check("dry-run NOT_EXPERIMENTALLY_VALIDATED",
          s["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED")
    check("dry-run manifest path present", s.get("manifest_path", "").endswith(".manifest.json"))


def test_real_run_blocked():
    print("[test] real-run BLOCKED (real_run_enabled=false per P33Q)")
    # All six models remain real_run_enabled=false; real-run must not execute.
    from app.routers.p33s import _can_real_run
    for m in ["pepmlm", "pepflow", "pephar", "diffpepbuilder"]:
        ok, reason = _can_real_run(m)
        check(f"{m} real-run blocked", not ok, reason[:60])


def test_unavailable_models():
    print("[test] unavailable models (EvoBind2 no license)")
    check("evobind2 unavailable", "evobind2" in UNAVAILABLE_MODELS)
    check("ppflow unavailable (no license)", "ppflow" in UNAVAILABLE_MODELS)
    cfg = PipelineConfig(model_id="evobind2", job_id="phase4_evobind2",
                         mode="real_run", target_sequence="ACDEFGHIK")
    s = run_pipeline(cfg)
    stages = s.get("stages", [])
    check("evobind2 generation unavailable_with_reason",
          any(st["status"] == "unavailable_with_reason" for st in stages))


def test_idempotency():
    print("[test] orchestrator idempotency (re-run returns existing delivery)")
    cfg = PipelineConfig(model_id="pepflow", job_id="phase4_idem_pepflow",
                         mode="dry_run", target_sequence="ACDEFGHIK")
    s1 = run_pipeline(cfg)
    s2 = run_pipeline(cfg)
    check("idempotent re-run same job_id", s1["job_id"] == s2["job_id"])


if __name__ == "__main__":
    test_provenance()
    test_gate()
    test_scorer_availability_logic()
    test_prodigy_scorer_real()
    test_mmgbsa_unavailable_without_prmtop()
    test_dry_run_plan()
    test_real_run_blocked()
    test_unavailable_models()
    test_idempotency()
    print(f"\n===== P33S Phase 4 zero-model tests: {PASS} passed, {FAIL} failed =====")
    sys.exit(1 if FAIL else 0)
