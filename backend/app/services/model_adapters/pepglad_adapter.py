"""PepGLAD adapter for the unified Model Registry (P9C).

PepGLAD is a geometric latent diffusion model for peptide sequence-structure
co-design. This adapter performs read-only probes and dry-run planning in P9B/P9C;
real execution is gated and requires the source repository, checkpoint weights,
and an isolated conda environment to be present and validated.

All outputs are computational predictions only and marked
NOT_EXPERIMENTALLY_VALIDATED.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from app.schemas.model_registry import (
    ModelArtifactsResponse,
    ModelArtifactItem,
    ModelDryRunPayload,
    ModelDryRunResult,
    ModelProbeResult,
    ModelSafetyFlags,
)
from app.services.model_adapters.base import BaseModelAdapter
from app.services.target_peptide_model_registry import (
    MODEL_STATUS_NOT_CONNECTED,
    SCIENTIFIC_BOUNDARY_NOTE,
    build_default_safety_flags,
)

# ---------------------------------------------------------------------------
# Paths and gates (all isolated under /home/xh/kxc/stampup)
# ---------------------------------------------------------------------------

PEPGLAD_ROOT = Path("/home/xh/kxc/stampup/models_dev/pepglad")
PEPGLAD_SOURCE = PEPGLAD_ROOT / "source" / "PepGLAD"
PEPGLAD_ENV_PYTHON = Path("/mnt/sdb/kxc/stamp_models/envs/pepglad_p31b_py39_torch113") / "bin" / "python"
PEPGLAD_ENV_PLAN = PEPGLAD_ROOT / "envs" / "pepglad-env-plan.md"
PEPGLAD_WEIGHTS_DIR = PEPGLAD_ROOT / "weights"
PEPGLAD_CODESIGN_CKPT = PEPGLAD_WEIGHTS_DIR / "codesign.ckpt"
PEPGLAD_FIXSEQ_CKPT = PEPGLAD_WEIGHTS_DIR / "fixseq.ckpt"
PEPGLAD_ARTIFACT_ROOT = Path(
    "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/artifacts/pepglad"
)
PEPGLAD_LOG_ROOT = PEPGLAD_ROOT / "logs"
PEPGLAD_GATE_FILE = PEPGLAD_ROOT / ".real_run_enabled"

# Probe status vocabulary used by P9B/P9C
PEPGLAD_STATUS_READY_FOR_DRY_RUN = "READY_FOR_DRY_RUN"
PEPGLAD_STATUS_DEGRADED = "DEGRADED"
PEPGLAD_STATUS_BLOCKED_MISSING_SOURCE = "BLOCKED_MISSING_SOURCE"
PEPGLAD_STATUS_BLOCKED_MISSING_WEIGHTS = "BLOCKED_MISSING_WEIGHTS"
PEPGLAD_STATUS_BLOCKED_ENV_INCOMPLETE = "BLOCKED_ENV_INCOMPLETE"
PEPGLAD_STATUS_BLOCKED_PYROSETTA_REQUIRED = "BLOCKED_PYROSETTA_REQUIRED"
PEPGLAD_STATUS_BLOCKED_MANUAL_UPLOAD_REQUIRED = "BLOCKED_MANUAL_UPLOAD_REQUIRED"
PEPGLAD_STATUS_READY_FOR_REAL_RUN_GATE = "READY_FOR_REAL_RUN_GATE"
PEPGLAD_STATUS_BLOCKED_DEPENDENCY_MISSING = "BLOCKED_DEPENDENCY_MISSING"
PEPGLAD_STATUS_BLOCKED_CHECKPOINT_LOAD_FAILED = "BLOCKED_CHECKPOINT_LOAD_FAILED"


# ---------------------------------------------------------------------------
# Gate helpers
# ---------------------------------------------------------------------------


def _real_run_allowed() -> bool:
    """Return True only when an explicit real-run gate is open."""
    enabled = os.environ.get("PEPGLAD_REAL_RUN_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    token = os.environ.get("PEPGLAD_REAL_RUN_TOKEN", "")
    return enabled or PEPGLAD_GATE_FILE.exists() or bool(token)


def _close_real_run_gate() -> None:
    """Close the real-run gate by removing the gate file and clearing the token."""
    try:
        PEPGLAD_GATE_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    os.environ.pop("PEPGLAD_REAL_RUN_TOKEN", None)


# ---------------------------------------------------------------------------
# Safety / utility helpers
# ---------------------------------------------------------------------------


def _base_safety_flags() -> ModelSafetyFlags:
    flags = build_default_safety_flags()
    flags["executed_model"] = False
    flags["generated_candidates"] = False
    flags["generated_structure"] = False
    flags["generated_msa"] = False
    flags["is_scientific_result"] = False
    flags["computational_prediction_only"] = True
    return ModelSafetyFlags(**flags)


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    PEPGLAD_ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    PEPGLAD_LOG_ROOT.mkdir(parents=True, exist_ok=True)


def _build_run_artifact_paths(run_id: str) -> dict[str, Path]:
    run_dir = PEPGLAD_ARTIFACT_ROOT / run_id
    return {
        "run_dir": run_dir,
        "input_dir": run_dir / "input",
        "output_dir": run_dir / "output",
        "logs_dir": run_dir / "logs",
        "manifest_dir": run_dir / "manifest",
    }


def _artifact_name_to_path(paths: dict[str, Path], artifact_name: str) -> Path | None:
    """Map a well-known artifact name to an absolute path."""
    mapping = {
        "input/target.pdb": paths["input_dir"] / "target.pdb",
        "input/pocket.json": paths["input_dir"] / "pocket.json",
        "output/generated_peptides.csv": paths["output_dir"] / "generated_peptides.csv",
        "output/generated_structures": paths["output_dir"] / "generated_structures",
        "output/pepglad_summary.json": paths["output_dir"] / "pepglad_summary.json",
        "logs/run_stdout_stderr.log": paths["logs_dir"] / "run_stdout_stderr.log",
        "manifest/manifest_pre.json": paths["manifest_dir"] / "manifest_pre.json",
        "manifest/manifest_post.json": paths["manifest_dir"] / "manifest_post.json",
    }
    return mapping.get(artifact_name)


def _path_within_root(path: Path, root: Path) -> bool:
    """Return True if *path* resolves to a location under *root*."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _python_version(python: Path | None = None) -> str:
    """Return the Python version reported by the given interpreter, or 'unknown'."""
    exe = python if python else Path(sys.executable)
    if not exe.exists():
        return "unknown"
    try:
        result = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        text = (result.stdout + result.stderr).strip()
        return text or "unknown"
    except Exception:
        return "unknown"


def _env_has_pip(python: Path | None = None) -> bool:
    """Return True if the given interpreter can run pip --version."""
    exe = python if python else Path(sys.executable)
    if not exe.exists():
        return False
    try:
        result = subprocess.run(
            [str(exe), "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return result.returncode == 0 and "pip" in result.stdout
    except Exception:
        return False


def _module_importable(module: str, python: Path | None = None) -> bool:
    """Return True if *module* can be imported by the given interpreter."""
    exe = python if python else Path(sys.executable)
    if not exe.exists():
        return False
    try:
        result = subprocess.run(
            [str(exe), "-c", f"import {module}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def _cuda_available() -> bool:
    """Return True if torch CUDA is available in the PepGLAD env or system python."""
    # Prefer the PepGLAD isolated environment, fall back to the system interpreter.
    for exe in (PEPGLAD_ENV_PYTHON, Path("/usr/bin/python3"), Path(sys.executable)):
        if not exe.exists():
            continue
        try:
            result = subprocess.run(
                [str(exe), "-c", "import torch; print(torch.cuda.is_available())"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode == 0 and "true" in result.stdout.lower():
                return True
        except Exception:
            continue
    return False


def _license_present() -> bool:
    """Return True if the PepGLAD source contains an MIT LICENSE file."""
    license_path = PEPGLAD_SOURCE / "LICENSE"
    if not license_path.exists():
        return False
    try:
        text = license_path.read_text(encoding="utf-8", errors="ignore")
        return "MIT License" in text or "Permission is hereby granted" in text
    except OSError:
        return False


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file, or empty string on error."""
    if not path.exists():
        return ""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def _weights_files() -> list[str]:
    """List materialised checkpoint filenames under the PepGLAD weights directory."""
    if not PEPGLAD_WEIGHTS_DIR.exists():
        return []
    return sorted(
        p.name
        for p in PEPGLAD_WEIGHTS_DIR.iterdir()
        if p.is_file() and p.suffix == ".ckpt"
    )


def _weights_sha256() -> dict[str, str]:
    """Return SHA-256 checksums for materialised checkpoint files."""
    result: dict[str, str] = {}
    for name in _weights_files():
        digest = _sha256_file(PEPGLAD_WEIGHTS_DIR / name)
        if digest:
            result[name] = digest
    return result


def _env_toolchain() -> str:
    """Detect which environment toolchain is available on stamp218."""
    if PEPGLAD_ENV_PYTHON.exists():
        return "conda-pack-p9c4"
    if Path("/home/xh/miniconda3/bin/conda").exists():
        return "conda"
    if shutil.which("micromamba"):
        return "micromamba"
    if shutil.which("mamba"):
        return "mamba"
    if shutil.which("uv"):
        return "uv"
    if shutil.which("virtualenv"):
        return "virtualenv"
    return "none"

def _manual_upload_required() -> bool:
    """Return True if dependency installation is blocked and manual upload is needed.

    This is triggered when:
      - the venv exists but cannot run pip (ensurepip missing), or
      - conda is available but offline package cache is insufficient to create
        a new environment (recorded by P9C2 bootstrap script).
    """
    marker = PEPGLAD_ROOT / "reports" / "p9c2_conda_create_status.txt"
    if PEPGLAD_ENV_PYTHON.exists() and _env_has_pip(PEPGLAD_ENV_PYTHON):
        return False
    if marker.exists():
        try:
            text = marker.read_text(encoding="utf-8", errors="ignore")
            if "CONDA_CREATE_FAILED" in text:
                return True
        except OSError:
            pass
    if PEPGLAD_ENV_PYTHON.exists() and not _env_has_pip(PEPGLAD_ENV_PYTHON):
        return True
    return False



def _dependency_summary() -> dict[str, dict[str, Any]]:
    """Return import availability for the packed PepGLAD environment."""
    modules = ["torch", "torch_scatter", "numpy", "Bio", "rdkit", "scipy", "ray", "yaml", "tqdm", "openmm", "pdbfixer", "freesasa", "pyrosetta"]
    summary: dict[str, dict[str, Any]] = {}
    if not PEPGLAD_ENV_PYTHON.exists():
        return {m: {"ok": False, "error": "env python missing"} for m in modules}
    for module in modules:
        code = (
            "import importlib\n"
            f"m = importlib.import_module('{module}')\n"
            "print(getattr(m, '__version__', 'unknown'))\n"
        )
        try:
            result = subprocess.run(
                [str(PEPGLAD_ENV_PYTHON), "-c", code],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            summary[module] = {
                "ok": result.returncode == 0,
                "version": result.stdout.strip() if result.returncode == 0 else "",
                "error": result.stderr.strip()[-500:] if result.returncode != 0 else "",
            }
        except Exception as exc:
            summary[module] = {"ok": False, "version": "", "error": repr(exc)}
    return summary


def _checkpoint_load_probe() -> dict[str, Any]:
    """Probe whether PepGLAD checkpoints can be loaded on CPU without running generation."""
    if not PEPGLAD_ENV_PYTHON.exists():
        return {"ok": False, "error": "env python missing", "files": []}
    code = """
from pathlib import Path
import torch
files = []
ok = True
for p in sorted(Path('/home/xh/kxc/stampup/models_dev/pepglad/weights').glob('*.ckpt')):
    files.append(p.name)
    try:
        obj = torch.load(str(p), map_location='cpu')
        print('load_ok', p.name, type(obj))
        del obj
    except Exception as exc:
        ok = False
        print('load_fail', p.name, repr(exc))
if not files:
    ok = False
    print('no_ckpt_found')
raise SystemExit(0 if ok else 1)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PEPGLAD_SOURCE)
    try:
        result = subprocess.run(
            [str(PEPGLAD_ENV_PYTHON), "-c", code],
            cwd=str(PEPGLAD_SOURCE),
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        return {
            "ok": result.returncode == 0,
            "files": _weights_files(),
            "stdout": result.stdout.strip()[-2000:],
            "stderr": result.stderr.strip()[-2000:],
        }
    except Exception as exc:
        return {"ok": False, "files": _weights_files(), "error": repr(exc)}


def _entrypoint_help_probe() -> dict[str, Any]:
    """Probe api.run --help without running PepGLAD generation."""
    if not PEPGLAD_ENV_PYTHON.exists():
        return {"ok": False, "error": "env python missing"}
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PEPGLAD_SOURCE)
    try:
        result = subprocess.run(
            [str(PEPGLAD_ENV_PYTHON), "-m", "api.run", "--help"],
            cwd=str(PEPGLAD_SOURCE),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip()[-1000:],
            "stderr": result.stderr.strip()[-2000:],
        }
    except Exception as exc:
        return {"ok": False, "error": repr(exc)}

# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class PepGLADAdapter(BaseModelAdapter):
    """PepGLAD peptide sequence-structure co-design adapter."""

    def __init__(self, model_id: str = "pepglad") -> None:
        super().__init__(model_id)

    def probe(self) -> ModelProbeResult:
        """Read-only probe of PepGLAD source, license, entrypoint, env and weights."""
        checks: list[dict[str, str]] = []

        def check(
            name: str,
            condition: bool,
            message: str,
            detail: str = "",
            severity: str = "ERROR",
        ) -> None:
            checks.append(
                {
                    "name": name,
                    "status": "PASS" if condition else "FAIL",
                    "message": message,
                    "detail": detail,
                    "severity": "INFO" if condition else severity,
                }
            )

        # Source-level checks
        root_exists = PEPGLAD_ROOT.exists()
        source_present = PEPGLAD_SOURCE.exists()
        license_present = _license_present()
        entrypoint_present = (PEPGLAD_SOURCE / "api" / "run.py").exists()
        requirements_present = (PEPGLAD_SOURCE / "env.yaml").exists()

        check("pepglad_root", root_exists, "PepGLAD root directory exists", str(PEPGLAD_ROOT))
        check(
            "pepglad_source",
            source_present,
            "PepGLAD source repository exists",
            str(PEPGLAD_SOURCE),
        )
        check(
            "pepglad_license",
            license_present,
            "PepGLAD LICENSE (MIT) is present",
            str(PEPGLAD_SOURCE / "LICENSE"),
        )
        check(
            "pepglad_entrypoint",
            entrypoint_present,
            "PepGLAD entrypoint api.run exists",
            str(PEPGLAD_SOURCE / "api" / "run.py"),
        )
        check(
            "pepglad_requirements",
            requirements_present,
            "PepGLAD environment file (env.yaml) is present",
            str(PEPGLAD_SOURCE / "env.yaml"),
        )

        # Environment / dependency checks
        env_present = PEPGLAD_ENV_PYTHON.exists()
        check(
            "pepglad_env_python",
            env_present,
            "PepGLAD venv python exists",
            str(PEPGLAD_ENV_PYTHON),
        )

        env_has_pip = _env_has_pip(PEPGLAD_ENV_PYTHON)
        check(
            "pepglad_env_pip",
            env_has_pip,
            "PepGLAD venv has pip" if env_has_pip else "PepGLAD venv pip is not available",
            "pip --version in venv",
            severity="WARNING" if not env_has_pip else "INFO",
        )

        dependency_summary = _dependency_summary()
        required_dependency_modules = ["torch", "torch_scatter", "numpy", "Bio", "rdkit", "scipy", "ray", "yaml", "tqdm", "openmm", "pdbfixer", "freesasa"]
        project_wide_optional_modules = ["pytorch_lightning", "dgl", "torch_geometric"]
        missing_dependencies = [m for m in required_dependency_modules if not dependency_summary.get(m, {}).get("ok")]
        optional_missing_dependencies = [m for m in ("pyrosetta",) if not dependency_summary.get(m, {}).get("ok")]
        dependency_ok = not missing_dependencies
        entrypoint_help_probe = _entrypoint_help_probe()
        checkpoint_load_probe = _checkpoint_load_probe()

        # Weight checks
        codesign_exists = PEPGLAD_CODESIGN_CKPT.exists()
        fixseq_exists = PEPGLAD_FIXSEQ_CKPT.exists()
        weights_present = codesign_exists or fixseq_exists
        check(
            "pepglad_codesign_ckpt",
            codesign_exists,
            "PepGLAD codesign checkpoint is present",
            str(PEPGLAD_CODESIGN_CKPT),
        )
        check(
            "pepglad_fixseq_ckpt",
            fixseq_exists,
            "PepGLAD fixseq checkpoint is present",
            str(PEPGLAD_FIXSEQ_CKPT),
        )

        # Optional / runtime checks
        pyrosetta_available = _module_importable("pyrosetta", PEPGLAD_ENV_PYTHON)
        pyrosetta_required = False  # README marks PyRosetta as optional
        check(
            "pepglad_pyrosetta",
            not pyrosetta_required or pyrosetta_available,
            "PyRosetta interface energy (optional) is available" if pyrosetta_available else "PyRosetta is optional and not installed",
            "optional",
            severity="WARNING" if pyrosetta_required and not pyrosetta_available else "INFO",
        )

        cuda_available = _cuda_available()
        check(
            "pepglad_cuda",
            cuda_available,
            "CUDA/torch GPU runtime is available in PepGLAD environment",
            "torch.cuda.is_available()",
            severity="WARNING",
        )

        env_toolchain = _env_toolchain()
        manual_upload_required = _manual_upload_required()

        errors: list[str] = []
        if not source_present:
            errors.append("PepGLAD source is not present.")
        if not license_present:
            errors.append("PepGLAD LICENSE is missing or not MIT.")
        if not entrypoint_present:
            errors.append("PepGLAD entrypoint (api/run.py) is missing.")
        if not requirements_present:
            errors.append("PepGLAD requirements (env.yaml) are missing.")
        if not env_present:
            errors.append(
                "PepGLAD isolated venv is not installed at the expected path. "
                "See /home/xh/kxc/stampup/models_dev/pepglad/envs/pepglad-env-plan.md."
            )
        if env_present and not env_has_pip:
            errors.append(
                "PepGLAD venv exists but pip is not available; dependency installation is blocked. "
                "Network/bootstrap.pypa.io is unreachable from stamp218. "
                "Manual upload of an offline environment or package cache is required."
            )
        if manual_upload_required:
            errors.append(
                "PepGLAD environment cannot be bootstrapped automatically on stamp218 "
                "(no outbound HTTPS, ensurepip missing, offline conda cache insufficient). "
                "See /home/xh/kxc/stampup/models_dev/pepglad/reports/PEPGLAD_P9C2_MANUAL_UPLOAD_REQUIREMENTS.md."
            )
        if not weights_present:
            errors.append(
                "PepGLAD checkpoints are not present. "
                "Weights are hosted on GitHub Releases (THUNLP-MT/PepGLAD releases/tag/v1.0)."
            )
        if pyrosetta_required and not pyrosetta_available:
            errors.append("PyRosetta is required but not available in the PepGLAD environment.")
        if weights_present and not env_present:
            errors.append(
                "Checkpoints are materialised but the PepGLAD isolated environment is incomplete; "
                "real execution remains blocked until conda env and CUDA runtime are ready."
            )

        check("pepglad_required_dependencies", dependency_ok, "PepGLAD required dependencies are importable", ", ".join(missing_dependencies) or "all required imports ok", severity="ERROR")
        check("pepglad_checkpoint_cpu_load", bool(checkpoint_load_probe.get("ok")), "PepGLAD checkpoints load on CPU", str(checkpoint_load_probe.get("files", [])), severity="ERROR")
        check("pepglad_entrypoint_help", bool(entrypoint_help_probe.get("ok")), "PepGLAD entrypoint help probe passes", str(entrypoint_help_probe.get("returncode", "")), severity="ERROR")

        # Status decision tree
        if not source_present or not entrypoint_present or not requirements_present:
            overall_status = PEPGLAD_STATUS_BLOCKED_MISSING_SOURCE
        elif pyrosetta_required and not pyrosetta_available:
            overall_status = PEPGLAD_STATUS_BLOCKED_PYROSETTA_REQUIRED
        elif not weights_present:
            overall_status = PEPGLAD_STATUS_BLOCKED_MISSING_WEIGHTS
        elif manual_upload_required:
            overall_status = PEPGLAD_STATUS_BLOCKED_MANUAL_UPLOAD_REQUIRED
        elif not env_present or not env_has_pip:
            overall_status = PEPGLAD_STATUS_BLOCKED_ENV_INCOMPLETE
        elif not dependency_ok or not entrypoint_help_probe.get("ok"):
            overall_status = PEPGLAD_STATUS_BLOCKED_DEPENDENCY_MISSING
        elif not checkpoint_load_probe.get("ok"):
            overall_status = PEPGLAD_STATUS_BLOCKED_CHECKPOINT_LOAD_FAILED
        else:
            overall_status = PEPGLAD_STATUS_READY_FOR_REAL_RUN_GATE

        message_parts = [
            "PepGLAD probe completed.",
        ]
        if overall_status == PEPGLAD_STATUS_READY_FOR_REAL_RUN_GATE:
            message_parts.append("Source, license, packed environment, CUDA, checkpoints and CPU checkpoint load probe are ready; real run remains gated.")
        elif overall_status == PEPGLAD_STATUS_READY_FOR_DRY_RUN:
            message_parts.append("Source, license, entrypoint, environment and checkpoints are ready for dry-run planning.")
        elif overall_status == PEPGLAD_STATUS_DEGRADED:
            message_parts.append("Source and checkpoints are present but the environment or CUDA runtime is degraded.")
        elif overall_status == PEPGLAD_STATUS_BLOCKED_MISSING_SOURCE:
            message_parts.append("Source, license, entrypoint or requirements are missing.")
        elif overall_status == PEPGLAD_STATUS_BLOCKED_MISSING_WEIGHTS:
            message_parts.append("Checkpoints are missing; dry-run can still build a command preview but real execution is blocked.")
        elif overall_status == PEPGLAD_STATUS_BLOCKED_ENV_INCOMPLETE:
            message_parts.append("Checkpoints are materialised but the isolated environment or CUDA runtime is incomplete; real execution is blocked.")
        elif overall_status == PEPGLAD_STATUS_BLOCKED_MANUAL_UPLOAD_REQUIRED:
            message_parts.append("Checkpoints are materialised but the environment cannot be bootstrapped automatically; manual upload of an offline environment or package cache is required.")
        elif overall_status == PEPGLAD_STATUS_BLOCKED_PYROSETTA_REQUIRED:
            message_parts.append("PyRosetta is required but not available.")
        elif overall_status == PEPGLAD_STATUS_BLOCKED_DEPENDENCY_MISSING:
            message_parts.append("Packed environment is present but one or more dependencies or entrypoint imports are missing.")
        elif overall_status == PEPGLAD_STATUS_BLOCKED_CHECKPOINT_LOAD_FAILED:
            message_parts.append("Packed environment is present but checkpoint CPU load probe failed.")
        message_parts.append("Real execution remains gated until all blockers are cleared.")

        safety = _base_safety_flags()
        return ModelProbeResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status=overall_status,
            message=" ".join(message_parts),
            probe_time=_now(),
            adapter_id=self.adapter_id,
            safety_flags=safety,
            detail={
                "source_present": source_present,
                "license_present": license_present,
                "entrypoint_present": entrypoint_present,
                "requirements_present": requirements_present,
                "env_present": env_present,
                "env_python_path": str(PEPGLAD_ENV_PYTHON),
                "env_has_pip": env_has_pip,
                "env_plan_path": str(PEPGLAD_ENV_PLAN),
                "weights_present": weights_present,
                "weights_files": _weights_files(),
                "weights_sha256": _weights_sha256(),
                "codesign_ckpt_present": codesign_exists,
                "fixseq_ckpt_present": fixseq_exists,
                "pyrosetta_available": pyrosetta_available,
                "pyrosetta_required": pyrosetta_required,
                "cuda_available": cuda_available,
                "dependency_summary": dependency_summary,
                "missing_dependencies": missing_dependencies,
                "optional_missing_dependencies": optional_missing_dependencies,
                "checkpoint_load_probe": checkpoint_load_probe,
                "entrypoint_help_probe": entrypoint_help_probe,
                "python_version": _python_version(PEPGLAD_ENV_PYTHON),
                "env_toolchain": env_toolchain,
                "manual_upload_required": manual_upload_required,
                "checks": checks,
                "errors": errors,
                "real_run_enabled": _real_run_allowed(),
            },
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def dry_run(self, payload: ModelDryRunPayload) -> ModelDryRunResult:
        """Plan a PepGLAD run without executing it."""
        _ensure_dirs()
        run_id = str(uuid.uuid4())
        paths = _build_run_artifact_paths(run_id)
        for p in paths.values():
            p.mkdir(parents=True, exist_ok=True)

        # Input resolution: prefer explicit PDB/pocket, otherwise plan with placeholder paths
        target_pdb_path = payload.target_pdb_path or str(paths["input_dir"] / "target.pdb")
        pocket_json_path = str(paths["input_dir"] / "pocket.json")
        pocket_residues = payload.pocket_residues or ["A:45", "A:46"]

        peptide_length = max(1, min(payload.peptide_length, 100))
        length_min = max(1, peptide_length - 2)
        length_max = max(length_min + 1, peptide_length + 2)
        n_samples = max(1, getattr(payload, "num_candidates", 5))

        out_dir = paths["output_dir"]

        command_preview = [
            "CUDA_VISIBLE_DEVICES=0",
            str(PEPGLAD_ENV_PYTHON) if PEPGLAD_ENV_PYTHON.exists() else "python3",
            "-m",
            "api.run",
            "--mode",
            "codesign",
            "--pdb",
            str(target_pdb_path),
            "--pocket",
            str(pocket_json_path),
            "--out_dir",
            str(out_dir),
            "--length_min",
            str(length_min),
            "--length_max",
            str(length_max),
            "--n_samples",
            str(n_samples),
            "--gpu",
            "0",
        ]

        env_preview = {
            "PYTHONPATH": str(PEPGLAD_SOURCE),
            "CUDA_VISIBLE_DEVICES": "0",
            "PEPGLAD_ROOT": str(PEPGLAD_ROOT),
            "PEPGLAD_MODE": "codesign",
        }

        expected_artifacts = {
            "input/target.pdb": str(paths["input_dir"] / "target.pdb"),
            "input/pocket.json": str(paths["input_dir"] / "pocket.json"),
            "output/generated_peptides.csv": str(paths["output_dir"] / "generated_peptides.csv"),
            "output/generated_structures": str(paths["output_dir"] / "generated_structures"),
            "output/pepglad_summary.json": str(paths["output_dir"] / "pepglad_summary.json"),
            "logs/run_stdout_stderr.log": str(paths["logs_dir"] / "run_stdout_stderr.log"),
            "manifest/manifest_pre.json": str(paths["manifest_dir"] / "manifest_pre.json"),
            "manifest/manifest_post.json": str(paths["manifest_dir"] / "manifest_post.json"),
        }

        environment_summary = {
            "source_present": PEPGLAD_SOURCE.exists(),
            "license_present": _license_present(),
            "entrypoint_present": (PEPGLAD_SOURCE / "api" / "run.py").exists(),
            "requirements_present": (PEPGLAD_SOURCE / "env.yaml").exists(),
            "env_present": PEPGLAD_ENV_PYTHON.exists(),
            "env_python_path": str(PEPGLAD_ENV_PYTHON),
            "env_has_pip": _env_has_pip(PEPGLAD_ENV_PYTHON),
            "env_toolchain": _env_toolchain(),
            "manual_upload_required": _manual_upload_required(),
            "weights_present": PEPGLAD_CODESIGN_CKPT.exists() or PEPGLAD_FIXSEQ_CKPT.exists(),
            "weights_files": _weights_files(),
            "codesign_ckpt_present": PEPGLAD_CODESIGN_CKPT.exists(),
            "fixseq_ckpt_present": PEPGLAD_FIXSEQ_CKPT.exists(),
            "pyrosetta_available": _module_importable("pyrosetta", PEPGLAD_ENV_PYTHON),
            "pyrosetta_required": False,
            "cuda_available": _cuda_available(),
            "dependency_summary": _dependency_summary(),
            "checkpoint_load_probe": _checkpoint_load_probe(),
            "entrypoint_help_probe": _entrypoint_help_probe(),
        }

        env_present = PEPGLAD_ENV_PYTHON.exists()
        env_has_pip = _env_has_pip(PEPGLAD_ENV_PYTHON)
        manual_upload_required = _manual_upload_required()

        blocked_reasons: list[str] = []
        if not PEPGLAD_SOURCE.exists():
            blocked_reasons.append("PepGLAD source is not present.")
        if not _license_present():
            blocked_reasons.append("PepGLAD LICENSE is missing or not MIT.")
        if not (PEPGLAD_SOURCE / "api" / "run.py").exists():
            blocked_reasons.append("PepGLAD entrypoint (api/run.py) is missing.")
        if not (PEPGLAD_SOURCE / "env.yaml").exists():
            blocked_reasons.append("PepGLAD requirements (env.yaml) are missing.")
        if not PEPGLAD_ENV_PYTHON.exists():
            blocked_reasons.append(
                "PepGLAD isolated venv is not installed at the expected path. "
                "See /home/xh/kxc/stampup/models_dev/pepglad/envs/pepglad-env-plan.md."
            )
        if env_present and not env_has_pip:
            blocked_reasons.append(
                "PepGLAD venv exists but pip is not available; dependency installation is blocked. "
                "Network/bootstrap.pypa.io is unreachable from stamp218."
            )
        if manual_upload_required:
            blocked_reasons.append(
                "PepGLAD environment cannot be bootstrapped automatically on stamp218 "
                "(no outbound HTTPS, ensurepip missing, offline conda cache insufficient). "
                "See /home/xh/kxc/stampup/models_dev/pepglad/reports/PEPGLAD_P9C2_MANUAL_UPLOAD_REQUIREMENTS.md."
            )
        if not (PEPGLAD_CODESIGN_CKPT.exists() or PEPGLAD_FIXSEQ_CKPT.exists()):
            blocked_reasons.append(
                "PepGLAD checkpoints (codesign.ckpt / fixseq.ckpt) are not present; "
                "weights are hosted on GitHub Releases (THUNLP-MT/PepGLAD releases/tag/v1.0)."
            )
        if not _cuda_available():
            blocked_reasons.append("CUDA/torch GPU runtime is not available in the PepGLAD environment.")
        missing_dependencies = [
            module
            for module in ("torch", "torch_scatter", "numpy", "Bio", "rdkit", "scipy", "ray", "yaml", "tqdm", "openmm", "pdbfixer", "freesasa")
            if not environment_summary["dependency_summary"].get(module, {}).get("ok")
        ]
        project_wide_optional_missing = [
            module
            for module in ("pytorch_lightning", "dgl", "torch_geometric")
            if not environment_summary["dependency_summary"].get(module, {}).get("ok")
        ]
        if missing_dependencies:
            blocked_reasons.append("PepGLAD required dependencies are missing: " + ", ".join(missing_dependencies))

        if not PEPGLAD_SOURCE.exists():
            status = PEPGLAD_STATUS_BLOCKED_MISSING_SOURCE
        elif not (PEPGLAD_CODESIGN_CKPT.exists() or PEPGLAD_FIXSEQ_CKPT.exists()):
            status = PEPGLAD_STATUS_BLOCKED_MISSING_WEIGHTS
        elif manual_upload_required:
            status = PEPGLAD_STATUS_BLOCKED_MANUAL_UPLOAD_REQUIRED
        elif missing_dependencies:
            status = PEPGLAD_STATUS_BLOCKED_DEPENDENCY_MISSING
        elif not environment_summary["checkpoint_load_probe"].get("ok"):
            status = PEPGLAD_STATUS_BLOCKED_CHECKPOINT_LOAD_FAILED
        elif not environment_summary["entrypoint_help_probe"].get("ok"):
            status = PEPGLAD_STATUS_BLOCKED_DEPENDENCY_MISSING
        elif blocked_reasons:
            status = PEPGLAD_STATUS_BLOCKED_ENV_INCOMPLETE
        else:
            status = PEPGLAD_STATUS_READY_FOR_REAL_RUN_GATE

        if status == PEPGLAD_STATUS_READY_FOR_REAL_RUN_GATE:
            message = (
                "PepGLAD dry-run command preview generated. No model was executed. "
                "Packed P9C4 environment, pdbfixer, entrypoint help, and checkpoints are ready; "
                "real execution remains gated."
            )
        elif status == PEPGLAD_STATUS_BLOCKED_MANUAL_UPLOAD_REQUIRED:
            message = (
                "PepGLAD dry-run command preview generated. No model was executed. "
                "Checkpoints are materialised but the environment cannot be bootstrapped automatically; "
                "manual upload of an offline environment or package cache is required."
            )
        elif status == PEPGLAD_STATUS_BLOCKED_ENV_INCOMPLETE:
            message = (
                "PepGLAD dry-run command preview generated. No model was executed. "
                "Weights are materialised but the isolated environment is incomplete; real run remains blocked."
            )
        else:
            message = "PepGLAD dry-run is blocked: " + " ".join(blocked_reasons)

        safety = _base_safety_flags()
        return ModelDryRunResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status=status,
            message=message,
            run_id=run_id,
            artifacts=expected_artifacts,
            expected_artifacts=expected_artifacts,
            command_preview=command_preview,
            env_preview=env_preview,
            environment_summary=environment_summary,
            blocked_reasons=blocked_reasons,
            safety_flags=safety,
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def submit(self, payload: ModelDryRunPayload) -> ModelDryRunResult:
        """Block real submission for the skeleton adapter."""
        _close_real_run_gate()
        return ModelDryRunResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status="BLOCKED",
            message=(
                "PepGLAD real execution is disabled in this phase. "
                "Provide an offline environment or package cache "
                "before enabling real runs."
            ),
            run_id=None,
            artifacts={},
            expected_artifacts={},
            command_preview=None,
            env_preview={},
            environment_summary={},
            blocked_reasons=["Real execution is gated."],
            safety_flags=_base_safety_flags(),
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def list_artifacts(self, job_id: str) -> ModelArtifactsResponse:
        """List artifact slots for a job; files are empty because nothing ran."""
        _ensure_dirs()
        paths = _build_run_artifact_paths(job_id)
        artifacts: list[ModelArtifactItem] = []
        for name in (
            "input/target.pdb",
            "input/pocket.json",
            "output/generated_peptides.csv",
            "output/generated_structures",
            "output/pepglad_summary.json",
            "logs/run_stdout_stderr.log",
            "manifest/manifest_pre.json",
            "manifest/manifest_post.json",
        ):
            artifact_path = _artifact_name_to_path(paths, name)
            if artifact_path is None:
                continue
            exists = artifact_path.exists()
            artifact_type = "pdb" if name.endswith(".pdb") else "json" if name.endswith(".json") else "csv" if name.endswith(".csv") else "directory" if name.endswith("generated_structures") else "other"
            artifacts.append(
                ModelArtifactItem(
                    name=name,
                    path=str(artifact_path.relative_to(PEPGLAD_ARTIFACT_ROOT)),
                    artifact_type=artifact_type,
                    exists=exists,
                    size_bytes=artifact_path.stat().st_size if exists else 0,
                )
            )
        return ModelArtifactsResponse(
            model_id=self.model_id,
            job_id=job_id,
            status=MODEL_STATUS_NOT_CONNECTED,
            artifacts=artifacts,
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )
