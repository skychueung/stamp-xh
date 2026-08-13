"""P33U non-dummy runner contracts for Lane D-min.

Each contract exposes:
    - validate_input(input_dir)         : check Lane-D input files exist + are
                                          well-formed. NO model execution.
    - command_preview(run_id, ...)      : the exact command token list(s) that
                                          Lane D WOULD run. Also used by
                                          execute() (no separate string concat).
    - runner_cwd(step_idx)              : cwd for each command step.
    - expected_artifacts(output_dir)    : paths Lane D SHOULD produce.
    - verify_assets()                   : check registered source/checkpoint
                                          paths exist and SHA matches.
    - parse_output(output_dir)          : delegate to output_parsers; returns a
                                          dict with `empty` flag.
    - execute(...)                      : REAL implementation via runner.execute_run.
                                          Refuses on SHA mismatch / retry /
                                          block env. Spawns via ProcessTransport
                                          (mock in tests, real at Lane D).

CRITICAL: this module imports no subprocess and performs no shell-out.
execute() delegates to runner.execute_run, which uses a ProcessTransport
abstraction. RealSubprocessTransport refuses to spawn when
P33U_BLOCK_ALL_EXECUTION is set. Tests inject MockProcessRunner — no real
process, no GPU, no 8189, no checkpoint load.

Commands are list[str] (never shell=True, never string-concatenated).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any

from .config import (
    BLOCK_ALL_EXECUTION_ENV,
    LANE_D_MIN_MODELS,
    MODEL_BY_ID,
    PREDICTION_TAG,
    VALIDATION_STATUS,
)
from . import output_parsers


# ---------------------------------------------------------------------------
# Guard helper (kept for back-compat with the C2 test; secondary defense)
# ---------------------------------------------------------------------------
def _assert_not_executing() -> None:
    """Secondary env-guard. The primary block is inside
    RealSubprocessTransport.run (runner.py). This helper remains so any future
    direct-execution helper can gate on it."""
    if os.environ.get(BLOCK_ALL_EXECUTION_ENV):
        raise RuntimeError(
            "P33U execution blocked: %s is set. Runner contracts must not "
            "execute models." % BLOCK_ALL_EXECUTION_ENV
        )


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass
class ValidationResult:
    valid: bool
    model_id: str
    errors: list[str] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)
    validation_status: str = VALIDATION_STATUS
    prediction_tag: str = PREDICTION_TAG


@dataclass
class AssetReport:
    model_id: str
    source_ok: bool
    checkpoint_ok: bool
    source_sha_match: bool
    checkpoint_sha_match: bool
    details: dict[str, Any] = field(default_factory=dict)
    validation_status: str = VALIDATION_STATUS


# ---------------------------------------------------------------------------
# Base contract
# ---------------------------------------------------------------------------
class RunnerContract:
    """Base class. Subclasses implement model-specific methods."""

    model_id: str = ""

    @property
    def meta(self) -> dict[str, Any]:
        return MODEL_BY_ID[self.model_id]

    def validate_input(self, input_dir: str) -> ValidationResult:  # pragma: no cover - abstract
        raise NotImplementedError

    def command_preview(
        self, run_id: str, input_dir: str, output_dir: str, **opts: Any
    ) -> list[list[str]]:  # pragma: no cover - abstract
        raise NotImplementedError

    def runner_cwd(self, step_idx: int) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def expected_artifacts(self, output_dir: str) -> list[str]:  # pragma: no cover - abstract
        raise NotImplementedError

    def verify_assets(self) -> AssetReport:  # pragma: no cover - abstract
        raise NotImplementedError

    def parse_output(self, output_dir: str) -> dict[str, Any]:
        return output_parsers.parse_output(self.model_id, output_dir)

    def execute(self, *, run_id: str, input_dir: str, output_dir: str,
                manifest_sha: str, authorized_manifest_sha: str,
                state: Any, process_transport: Any = None,
                gpu_device: str | None = None,
                timeout_seconds: int | None = None,
                extra_env: dict[str, str] | None = None,
                mock_artifacts: dict[str, bytes] | None = None) -> Any:
        """REAL execution entry (P33U-D0). Delegates to runner.execute_run.

        Refuses (ExecutionRefused) on: empty/mismatched authorized_manifest_sha,
        model already attempted (retry_count=0), failed input precheck.
        Refuses (ExecutionBlocked) when real transport + P33U_BLOCK_ALL_EXECUTION.
        On timeout / non-zero exit / empty artifacts: closes gate FAILED/TIMEOUT,
        records failed attempt, preserves scene, returns FAILED outcome.
        """
        from .runner import execute_run  # local import to avoid cycles
        return execute_run(
            contract=self,
            run_id=run_id,
            input_dir=input_dir,
            output_dir=output_dir,
            manifest_sha=manifest_sha,
            authorized_manifest_sha=authorized_manifest_sha,
            state=state,
            process_transport=process_transport,
            gpu_device=gpu_device,
            timeout_seconds=timeout_seconds,
            extra_env=extra_env,
            mock_artifacts=mock_artifacts,
        )

    # --- shared input file checks ---
    @staticmethod
    def _require_file(input_dir: str, name: str, errors: list[str], checked: list[str],
                      min_bytes: int = 1) -> bool:
        p = os.path.join(input_dir, name)
        checked.append(p)
        if not os.path.isfile(p):
            errors.append(f"missing input file: {p}")
            return False
        if os.path.getsize(p) < min_bytes:
            errors.append(f"empty input file: {p}")
            return False
        return True


# ---------------------------------------------------------------------------
# PepMLM
# ---------------------------------------------------------------------------
class PepMLMContract(RunnerContract):
    model_id = "pepmlm"

    def validate_input(self, input_dir: str) -> ValidationResult:
        errors: list[str] = []
        checked: list[str] = []
        self._require_file(input_dir, "target.fasta", errors, checked, min_bytes=1)
        fasta = os.path.join(input_dir, "target.fasta")
        if os.path.isfile(fasta):
            checked.append(fasta + ":content")
            with open(fasta, "r", encoding="utf-8", errors="replace") as fh:
                head = fh.read(4096)
            if ">" not in head:
                errors.append("target.fasta has no '>' fasta header")
        return ValidationResult(valid=not errors, model_id=self.model_id,
                                errors=errors, checked=checked)

    def command_preview(self, run_id: str, input_dir: str, output_dir: str,
                        peptide_length: int = 9, num_candidates: int = 3,
                        device: str = "cuda", **opts: Any) -> list[list[str]]:
        m = self.meta
        ckpt_dir = os.path.dirname(m["checkpoint"])
        return [[
            m["env_python"], m["source"],
            "--model_path", ckpt_dir,
            "--target_sequence", "<from target.fasta>",
            "--peptide_length", str(peptide_length),
            "--num_candidates", str(num_candidates),
            "--device", device,
            "--output_dir", output_dir,
        ]]

    def runner_cwd(self, step_idx: int) -> str:
        return os.path.dirname(self.meta["source"])

    def expected_artifacts(self, output_dir: str) -> list[str]:
        return [
            os.path.join(output_dir, "candidate_sequences.csv"),
            os.path.join(output_dir, "run_manifest.json"),
        ]

    def verify_assets(self) -> AssetReport:
        m = self.meta
        src_ok = os.path.isfile(m["source"])
        ckpt_ok = os.path.isfile(m["checkpoint"])
        src_match = src_ok and sha256_file(m["source"]) == m["source_sha256"]
        ckpt_match = ckpt_ok and sha256_file(m["checkpoint"]) == m["checkpoint_sha256"]
        return AssetReport(self.model_id, src_ok, ckpt_ok, src_match, ckpt_match,
                           details={"source": m["source"], "checkpoint": m["checkpoint"]})


# ---------------------------------------------------------------------------
# DiffPepBuilder — real receptor PDB + hotspots JSON, 3-step official chain
# ---------------------------------------------------------------------------
class DiffPepBuilderContract(RunnerContract):
    """Non-dummy: real receptor PDB (filename MUST NOT contain '_') + real
    hotspots JSON. Three official steps: preprocess, torchrun inference,
    postprocess. No synthetic dummy_batch tensors."""

    model_id = "diffpepbuilder"

    def validate_input(self, input_dir: str) -> ValidationResult:
        errors: list[str] = []
        checked: list[str] = []
        self._require_file(input_dir, "target.pdb", errors, checked, min_bytes=1)
        self._require_file(input_dir, "de_novo_cases.json", errors, checked, min_bytes=2)
        pdb = os.path.join(input_dir, "target.pdb")
        if os.path.isfile(pdb):
            checked.append(pdb + ":name")
            if "_" in os.path.basename(pdb):
                errors.append(
                    "receptor PDB filename contains '_' which breaks "
                    "process_receptor.py name splitting; rename to e.g. target.pdb"
                )
        # SSBLIB / PyRosetta status precheck (existence only; no install/run)
        m = self.meta
        ssbuilder = os.path.join(m["source"], "SSbuilder")
        checked.append(ssbuilder)
        if os.path.isdir(ssbuilder):
            ssblib_tar = os.path.join(ssbuilder, "SSBLIB.tar.gz")
            ssblib_dir = os.path.join(ssbuilder, "SSBLIB")
            if not os.path.isdir(ssblib_dir) and not os.path.isfile(ssblib_tar):
                errors.append("SSbuilder has neither SSBLIB/ nor SSBLIB.tar.gz")
        # PyRosetta availability is a Lane D runtime prereq; we only note it.
        return ValidationResult(valid=not errors, model_id=self.model_id,
                                errors=errors, checked=checked)

    def command_preview(self, run_id: str, input_dir: str, output_dir: str,
                        nproc: int = 1, **opts: Any) -> list[list[str]]:
        m = self.meta
        py = m["env_python"]
        src = m["source"]
        data_dir = os.path.join(output_dir, "data")
        step1 = [
            py, os.path.join(src, "experiments", "process_receptor.py"),
            "--pdb_dir", input_dir,
            "--write_dir", data_dir,
            "--receptor_info_path", os.path.join(input_dir, "de_novo_cases.json"),
        ]
        step2 = [
            "torchrun", f"--nproc-per-node={nproc}",
            os.path.join(src, "experiments", "run_inference.py"),
            f"data.val_csv_path={data_dir}/metadata_test.csv",
        ]
        step3 = [
            py, os.path.join(src, "experiments", "run_postprocess.py"),
            "--in_pdbs", os.path.join(src, "runs", "inference"),
            "--ori_pdbs", input_dir,
            "--amber_relax", "--rosetta_relax",
        ]
        return [step1, step2, step3]

    def runner_cwd(self, step_idx: int) -> str:
        return self.meta["source"]

    def expected_artifacts(self, output_dir: str) -> list[str]:
        return [
            "runs/inference/postprocess_results.csv",
            "runs/inference/<case>/<sample>.pdb",
            os.path.join(output_dir, "run_manifest.json"),
        ]

    def verify_assets(self) -> AssetReport:
        m = self.meta
        entry = os.path.join(m["source"], "experiments", "process_receptor.py")
        src_ok = os.path.isfile(entry)
        ckpt_ok = os.path.isfile(m["checkpoint"])
        src_match = src_ok and sha256_file(entry) == m["source_entry_sha256"]
        ckpt_match = ckpt_ok and sha256_file(m["checkpoint"]) == m["checkpoint_sha256"]
        return AssetReport(self.model_id, src_ok, ckpt_ok, src_match, ckpt_match,
                           details={"source_entry": entry, "checkpoint": m["checkpoint"],
                                    "note": m.get("source_entry_note", "")})


# ---------------------------------------------------------------------------
# PepFlow — real PepMerge LMDB + model2.pt + full steps
# ---------------------------------------------------------------------------
class PepFlowContract(RunnerContract):
    """Non-dummy: real PepMerge LMDB data point + model2.pt + full 200 steps."""

    model_id = "pepflow"

    def validate_input(self, input_dir: str) -> ValidationResult:
        errors: list[str] = []
        checked: list[str] = []
        self._require_file(input_dir, "dataset_config.yaml", errors, checked, min_bytes=1)
        lmdb_dir = os.path.join(input_dir, "lmdb_data")
        checked.append(lmdb_dir)
        if not os.path.isdir(lmdb_dir):
            errors.append(f"missing real PepMerge LMDB data dir: {lmdb_dir}")
        else:
            if not (os.path.exists(os.path.join(lmdb_dir, "data.mdb"))):
                errors.append(f"LMDB dir has no data.mdb: {lmdb_dir}")
        return ValidationResult(valid=not errors, model_id=self.model_id,
                                errors=errors, checked=checked)

    def command_preview(self, run_id: str, input_dir: str, output_dir: str,
                        num_samples: int = 3, num_steps: int = 200,
                        device: str = "cuda", **opts: Any) -> list[list[str]]:
        m = self.meta
        return [[
            m["env_python"], m["source"],
            "--config", os.path.join(input_dir, "dataset_config.yaml"),
            "--ckpt", m["checkpoint"],
            "--device", device,
            "--output", output_dir,
            "--num_samples", str(num_samples),
            "--num_steps", str(num_steps),
            "--sample_bb", "--sample_ang", "--sample_seq",
        ]]

    def runner_cwd(self, step_idx: int) -> str:
        return os.path.dirname(self.meta["source"])

    def expected_artifacts(self, output_dir: str) -> list[str]:
        return [
            os.path.join(output_dir, "outputs", "<id>.pt"),
            os.path.join(output_dir, "outputs.csv"),
            os.path.join(output_dir, "run_manifest.json"),
        ]

    def verify_assets(self) -> AssetReport:
        m = self.meta
        src_ok = os.path.isfile(m["source"])
        ckpt_ok = os.path.isfile(m["checkpoint"])
        src_match = src_ok and sha256_file(m["source"]) == m["source_sha256"]
        ckpt_match = ckpt_ok and sha256_file(m["checkpoint"]) == m["checkpoint_sha256"]
        return AssetReport(self.model_id, src_ok, ckpt_ok, src_match, ckpt_match,
                           details={"source": m["source"], "checkpoint": m["checkpoint"],
                                    "checkpoint_note": "model2.pt = real-design ckpt (README §57)"})


# ---------------------------------------------------------------------------
# PepHAR — real .pkl + dual checkpoint + project/data root remap
# ---------------------------------------------------------------------------
class PepHARContract(RunnerContract):
    """Non-dummy: real .pkl + dual checkpoint at corrected paths + project/data
    root remap. Invalid --rec-length/--pep-length/--qry-length removed."""

    model_id = "pephar"

    def validate_input(self, input_dir: str) -> ValidationResult:
        errors: list[str] = []
        checked: list[str] = []
        self._require_file(input_dir, "test_data.pkl", errors, checked, min_bytes=1)
        self._require_file(input_dir, "remap_plan.json", errors, checked, min_bytes=2)
        return ValidationResult(valid=not errors, model_id=self.model_id,
                                errors=errors, checked=checked)

    def command_preview(self, run_id: str, input_dir: str, output_dir: str,
                        gpu: int = 0, n_samples: int = 3, **opts: Any) -> list[list[str]]:
        m = self.meta
        return [[
            m["env_python"], os.path.join(m["source"], "sample.py"),
            "--n_samples", str(n_samples),
            "--gpu", str(gpu),
            "--density_config_path", m["density_config"],
            "--density_param_path", m["density_checkpoint"],
            "--prediction_config_path", m["prediction_config"],
            "--prediction_param_path", m["prediction_checkpoint"],
            "--anchor_strategy", "gt",
            "--extend_strategy", "sto",
            "--anchor_nums", "1",
            "--anchor_steps", "10",
            "--finetune_steps", "0",
            "--dist_strategy", "single",
        ]]

    def runner_cwd(self, step_idx: int) -> str:
        return self.meta["source"]

    def expected_artifacts(self, output_dir: str) -> list[str]:
        return [
            os.path.join(output_dir, "<name>", "gt.pdb"),
            os.path.join(output_dir, "<name>", "gen_0.pdb"),
            os.path.join(output_dir, "test.csv"),
            os.path.join(output_dir, "run_manifest.json"),
        ]

    def verify_assets(self) -> AssetReport:
        m = self.meta
        entry = os.path.join(m["source"], "sample.py")
        src_ok = os.path.isfile(entry)
        dens_ok = os.path.isfile(m["density_checkpoint"])
        pred_ok = os.path.isfile(m["prediction_checkpoint"])
        src_match = src_ok and sha256_file(entry) == m["source_entry_sha256"]
        dens_match = dens_ok and sha256_file(m["density_checkpoint"]) == m["density_checkpoint_sha256"]
        pred_match = pred_ok and sha256_file(m["prediction_checkpoint"]) == m["prediction_checkpoint_sha256"]
        ckpt_ok = dens_ok and pred_ok
        ckpt_match = dens_match and pred_match
        return AssetReport(
            self.model_id, src_ok, ckpt_ok, src_match, ckpt_match,
            details={
                "source_entry": entry,
                "density_checkpoint": m["density_checkpoint"],
                "density_sha": m["density_checkpoint_sha256"],
                "prediction_checkpoint": m["prediction_checkpoint"],
                "prediction_sha": m["prediction_checkpoint_sha256"],
                "note": "paths corrected from P33L <source>/logs/... (nonexistent)",
            },
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_CONTRACTS: dict[str, type[RunnerContract]] = {
    "pepmlm": PepMLMContract,
    "diffpepbuilder": DiffPepBuilderContract,
    "pepflow": PepFlowContract,
    "pephar": PepHARContract,
}


def get_contract(model_id: str) -> RunnerContract:
    if model_id not in _CONTRACTS:
        raise KeyError(
            f"P33U has no contract for {model_id!r}. Lane D-min scope: "
            f"{[m['model_id'] for m in LANE_D_MIN_MODELS]}"
        )
    return _CONTRACTS[model_id]()


def all_contracts() -> dict[str, RunnerContract]:
    return {mid: cls() for mid, cls in _CONTRACTS.items()}
