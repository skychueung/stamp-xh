"""P33U-D22: formal SmokeRunnerAdapter for DiffPepBuilder / PepHAR dev smoke.

Replaces the D21 bare router helpers with a provenance-recorded adapter call.
The adapter still invokes the D21 smoke scripts via subprocess (the scripts wrap
the real model runners — DiffPepBuilder ``run_inference.py`` / PepHAR
``AnchorBasedSampler`` — on GPU1), but now records full provenance in the job /
gate JSON so each smoke run is self-describing and traceable:

  - adapter_id            (this adapter)
  - adapter_formal_path   (True — hardened D22 path, not a D21 bare bypass)
  - script_sha256         (smoke wrapper script)
  - config_sha256         (smoke config = wrapper script for these runs)
  - checkpoint_sha256     (model weights, per checkpoint file)
  - env_python            (interpreter path)
  - seed                  (PepHAR fixed seed for reproducibility; None for DiffPepBuilder)

D8-D21 artifacts untouched. The registry adapters in ``app/services/model_adapters/``
(``DiffPepBuilderAdapter`` / ``PepHARAdapter``) stay read-only with ``submit()``
blocked by design (P31B / P31C); this SmokeRunnerAdapter is the Run Console's
formal dev-smoke path, separate from the registry adapter contract.

Forbidden by the D22 goal: this adapter never writes dev-smoke results as Top4 /
primary candidates, never claims experimental validation, and never invokes PPFlow.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any

# --- script / env / checkpoint paths (D21-proven, additive) -----------------
DIFFPEPBUILDER_SMOKE_SCRIPT = Path(
    "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/"
    "backend/scripts/p33u_d21_diffpepbuilder_smoke.sh"
)
DIFFPEPBUILDER_ENV_PYTHON = Path(
    "/mnt/sdb/kxc/stamp_models/envs/diffpepbuilder_py39/bin/python"
)
DIFFPEPBUILDER_CHECKPOINT = Path(
    "/mnt/sdb/kxc/stamp_models/weights/diffpepbuilder/diffpepbuilder_v1.pth"
)

PEPHAR_SMOKE_SCRIPT = Path(
    "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/"
    "backend/scripts/p33u_d21_pephar_smoke.py"
)
PEPHAR_ENV_PYTHON = Path(
    "/mnt/sdb/kxc/stamp_models/envs/pephar_py310/bin/python"
)
PEPHAR_PREDICTION_CKPT = Path(
    "/mnt/sdb/kxc/stamp_models/checkpoints/pephar/p25_install_probe/"
    "PepHAR_ICLR2025_SHARE/ckpts/prediction_d2_x2o1_2024_09_08__11_21_33/checkpoints/2400.pt"
)
PEPHAR_DENSITY_CKPT = Path(
    "/mnt/sdb/kxc/stamp_models/checkpoints/pephar/p25_install_probe/"
    "PepHAR_ICLR2025_SHARE/ckpts/density_v4_x5o2_2024_09_08__11_25_36/checkpoints/1400.pt"
)

# D22 default fixed seed for PepHAR smoke reproducibility. The D21 smoke used
# extend_strategy=sto with no seed (stochastic); D22 fixes seed=12345 so reruns
# are reproducible. The D21 already-ingested candidates keep source_round=P33U_D21
# (stochastic); new D22 runs use this seed and are tagged source_round=P33U_D22.
PEPHAR_DEFAULT_SEED = 12345

VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
PREDICTION_TAG = "COMPUTATIONAL_PREDICTION_ONLY"

# Module-level checkpoint SHA cache (avoids re-hashing 1.2GB on every smoke run).
_CKPT_SHA_CACHE: dict[str, str] = {}


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ckpt_sha(p: Path) -> str:
    key = str(p)
    if key not in _CKPT_SHA_CACHE:
        _CKPT_SHA_CACHE[key] = _sha256_file(p) if p.is_file() else ""
    return _CKPT_SHA_CACHE[key]


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SmokeRunnerAdapter:
    """Formal adapter path for dev-only minimal real-run smoke.

    Called by the p33u router's ``_run_model_thread`` dispatch (replaces the D21
    bare ``_run_diffpepbuilder_smoke`` / ``_run_pephar_smoke`` helpers). Each
    method runs the smoke script via subprocess on GPU1 (GPU0 prod untouched),
    parses the produced PDBs / metrics, and records full provenance on the job
    dict so the resulting job.json / gate JSON is self-describing.
    """

    adapter_id = "p33u_d22_smoke_runner"
    adapter_formal_path = True

    # ------------------------------------------------------------------ provenance
    def _record_provenance(
        self,
        job: dict[str, Any],
        *,
        script: Path,
        checkpoint_paths: list[Path],
        env_python: Path,
        seed: int | None,
        smoke_type: str,
    ) -> None:
        job["provenance"] = {
            "adapter_id": self.adapter_id,
            "adapter_formal_path": True,
            "smoke_type": smoke_type,
            "script_path": str(script),
            "script_sha256": _sha256_file(script) if script.is_file() else "",
            "config_sha256": _sha256_file(script) if script.is_file() else "",
            "checkpoint_sha256": {str(p): _ckpt_sha(p) for p in checkpoint_paths},
            "env_python": str(env_python),
            "env_python_exists": env_python.is_file(),
            "seed": seed,
            "seed_note": (
                "fixed (D22 reproducibility)" if seed is not None else "none (model has no seed hook)"
            ),
        }

    # ---------------------------------------------------------- diffpepbuilder
    def run_diffpepbuilder_smoke(
        self, job: dict[str, Any], job_dir: Path, seed: int | None = None
    ) -> None:
        """D10-2 path: run_inference.py via Hydra, 3x12aa, cuda:1 (no CV_D mask)."""
        log_path = job_dir / "log.txt"
        try:
            if not DIFFPEPBUILDER_SMOKE_SCRIPT.is_file():
                job["status"] = "blocked_dependency"
                job["failure_reason"] = f"smoke script not found: {DIFFPEPBUILDER_SMOKE_SCRIPT}"
                job["end_time"] = _now_iso()
                return
            cmd = ["bash", str(DIFFPEPBUILDER_SMOKE_SCRIPT), str(job_dir)]
            with open(log_path, "w", encoding="utf-8") as lf:
                proc = subprocess.run(
                    cmd, stdout=lf, stderr=subprocess.STDOUT, timeout=600, check=False
                )
            job["command"] = cmd
            job["env"] = {
                "python": str(DIFFPEPBUILDER_ENV_PYTHON),
                "script": str(DIFFPEPBUILDER_SMOKE_SCRIPT),
                "cuda_visible_devices": "unset (D10-proven; GPUtil picks GPU1)",
            }
            job["exit_code"] = proc.returncode
            job["status"] = "succeeded" if proc.returncode == 0 else "failed"
            job["failure_reason"] = (
                "" if proc.returncode == 0 else "diffpepbuilder smoke non-zero exit; see logs"
            )
            job["checkpoint_loaded"] = str(DIFFPEPBUILDER_CHECKPOINT)
            job["gpu_used"] = "cuda:1 (GPU1; GPU0 prod untouched)"
            produced = sorted(job_dir.glob("**/target_length_12_sample_*.pdb"))
            job["output_path"] = str(produced[0]) if produced else ""
            if produced:
                job["sha256"] = _sha256_file(produced[0])
            job["result_summary"] = {
                "smoke_type": "diffpepbuilder_real_run_minimal_smoke",
                "label": "diffpepbuilder dev-only minimal REAL run (D10-2 path; 3 samples 12aa; NOT dry-run)",
                "produced_pdb_count": len(produced),
                "produced_pdbs": [str(p.relative_to(job_dir)) for p in produced],
                "ran_model_forward": proc.returncode == 0,
                "generated_new_candidates": proc.returncode == 0,
                "validation_status": VALIDATION_STATUS,
                "prediction_tag": PREDICTION_TAG,
            }
            self._record_provenance(
                job,
                script=DIFFPEPBUILDER_SMOKE_SCRIPT,
                checkpoint_paths=[DIFFPEPBUILDER_CHECKPOINT],
                env_python=DIFFPEPBUILDER_ENV_PYTHON,
                seed=None,  # diffusion runner exposes no seed hook in D21 wrapper
                smoke_type="diffpepbuilder_real_run_minimal_smoke",
            )
            job["end_time"] = _now_iso()
        except subprocess.TimeoutExpired:
            job["status"] = "failed"
            job["failure_reason"] = "diffpepbuilder smoke timeout (600s)"
            job["end_time"] = _now_iso()
        except Exception as exc:
            job["status"] = "failed"
            job["failure_reason"] = f"exception: {exc!r}"
            job["end_time"] = _now_iso()

    # ------------------------------------------------------------------ pephar
    def run_pephar_smoke(
        self, job: dict[str, Any], job_dir: Path, seed: int | None = None
    ) -> None:
        """D10-3 path: AnchorBasedSampler, 3x12aa, CUDA_VISIBLE_DEVICES=1 (GPU1)."""
        if seed is None:
            seed = PEPHAR_DEFAULT_SEED
        log_path = job_dir / "log.txt"
        try:
            if not PEPHAR_SMOKE_SCRIPT.is_file():
                job["status"] = "blocked_dependency"
                job["failure_reason"] = f"smoke script not found: {PEPHAR_SMOKE_SCRIPT}"
                job["end_time"] = _now_iso()
                return
            cmd = [
                str(PEPHAR_ENV_PYTHON),
                str(PEPHAR_SMOKE_SCRIPT),
                "--job-dir", str(job_dir),
                "--n-samples", "3",
                "--gpu", "0",
                "--seed", str(seed),
            ]
            env = os.environ.copy()
            env["CUDA_VISIBLE_DEVICES"] = "1"
            with open(log_path, "w", encoding="utf-8") as lf:
                proc = subprocess.run(
                    cmd, stdout=lf, stderr=subprocess.STDOUT, env=env, timeout=300, check=False
                )
            job["command"] = cmd
            job["env"] = {
                "python": str(PEPHAR_ENV_PYTHON),
                "script": str(PEPHAR_SMOKE_SCRIPT),
                "cuda_visible_devices": "1 (cuda:0 == physical GPU1)",
                "seed": seed,
            }
            job["exit_code"] = proc.returncode
            job["status"] = "succeeded" if proc.returncode == 0 else "failed"
            job["failure_reason"] = (
                "" if proc.returncode == 0 else "pephar smoke non-zero exit; see logs"
            )
            job["checkpoint_loaded"] = (
                f"{PEPHAR_PREDICTION_CKPT} + {PEPHAR_DENSITY_CKPT}"
            )
            job["gpu_used"] = "cuda:0 (physical GPU1 via CUDA_VISIBLE_DEVICES=1; GPU0 prod untouched)"
            produced = sorted(job_dir.glob("result/**/gen_*.pdb"))
            csv_files = sorted(job_dir.glob("result/**/test.csv"))
            job["output_path"] = (
                str(csv_files[0]) if csv_files else (str(produced[0]) if produced else "")
            )
            if csv_files:
                job["sha256"] = _sha256_file(csv_files[0])
            elif produced:
                job["sha256"] = _sha256_file(produced[0])
            metrics_rows: list[dict[str, Any]] = []
            if csv_files:
                try:
                    import csv as _csv
                    with open(csv_files[0], "r", encoding="utf-8") as fh:
                        metrics_rows = list(_csv.DictReader(fh))
                except Exception:
                    pass
            job["result_summary"] = {
                "smoke_type": "pephar_real_run_minimal_smoke",
                "label": "pephar dev-only minimal REAL run (D10-3 path; 3 samples 12aa; NOT dry-run)",
                "produced_pdb_count": len(produced),
                "produced_pdbs": [str(p.relative_to(job_dir)) for p in produced],
                "metrics_rows": metrics_rows,
                "ran_model_forward": proc.returncode == 0,
                "generated_new_candidates": proc.returncode == 0,
                "validation_status": VALIDATION_STATUS,
                "prediction_tag": PREDICTION_TAG,
                "seed": seed,
            }
            self._record_provenance(
                job,
                script=PEPHAR_SMOKE_SCRIPT,
                checkpoint_paths=[PEPHAR_PREDICTION_CKPT, PEPHAR_DENSITY_CKPT],
                env_python=PEPHAR_ENV_PYTHON,
                seed=seed,
                smoke_type="pephar_real_run_minimal_smoke",
            )
            job["end_time"] = _now_iso()
        except subprocess.TimeoutExpired:
            job["status"] = "failed"
            job["failure_reason"] = "pephar smoke timeout (300s)"
            job["end_time"] = _now_iso()
        except Exception as exc:
            job["status"] = "failed"
            job["failure_reason"] = f"exception: {exc!r}"
            job["end_time"] = _now_iso()
