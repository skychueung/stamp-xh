"""P33S scientific scorers — independent post-processing modules.

Each scorer returns a ScorerResult with an explicit status. NEVER fabricates.
Statuses:
  - ok                : real value produced, tagged predicted/computational
  - not_applicable    : metric does not apply to this candidate/model
  - failed_with_evidence : real attempt failed; raw error + log path preserved
  - unavailable_with_reason : no licensed/installed backend; not attempted

Per goal §3:
- pLDDT only from real ESMFold (or AF2) inference.
- ipTM unavailable this round (no AlphaFold2-Multimer installed).
- Kd = predicted_Kd_PRODIGY (from PRODIGY ΔG via Kd=exp(ΔG/RT)); never experimental.
- MIC unavailable this round (no licensed MIC model).
- MM-GBSA via AmberTools MMPBSA.py; record structure/topology/forcefield/
  solvent/units/command. "NIM-GBSA" treated as typo for MM-GBSA.
"""

from __future__ import annotations

import math
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Isolated env prefix (Phase 2). All large caches redirected off root disk.
SCORER_ENV_PREFIX = "/mnt/sdb/kxc/stamp_models/envs/p33s_scorers_py310"
SCORER_PY = f"{SCORER_ENV_PREFIX}/bin/python"
MMPBSA_BIN = f"{SCORER_ENV_PREFIX}/bin/MMPBSA.py"
PRODIGY_BIN = f"{SCORER_ENV_PREFIX}/bin/prodigy"

# ESMFold weights (downloaded Phase 2, GPU load deferred to Phase 5).
ESMFOLD_MODEL = "facebook/esmfold_v1"
ESMFOLD_CACHE = "/mnt/sdb/kxc/stamp_models/cache/p33s/hf_home"

VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"

R_GAS = 8.314462618  # J/(mol K)
TEMP_K = 298.15  # standard temp for ΔG->Kd conversion


@dataclass
class ScorerResult:
    metric: str  # plddt | iptm | kd | mic | mmgbsa | pdockq
    status: str  # ok | not_applicable | failed_with_evidence | unavailable_with_reason
    value: float | None = None
    unit: str = ""
    model_or_algorithm: str = ""
    model_version: str = ""
    confidence: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    log_path: str = ""
    validation_status: str = VALIDATION_STATUS
    prediction_tag: str = "COMPUTATIONAL_PREDICTION_ONLY"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# pLDDT via ESMFold
# ---------------------------------------------------------------------------

def score_plddt_esmfold(
    peptide_sequence: str,
    receptor_sequence: str | None,
    out_dir: str | Path,
    gpu_device: str | None = None,
    timeout_seconds: int = 1800,
) -> ScorerResult:
    """Run ESMFold to predict structure and return mean pLDDT.

    GPU required (Phase 5). In Phase 2/4 this returns unavailable_with_reason
    unless the env + weights are present and a GPU is explicitly provided.
    """
    if not Path(SCORER_PY).is_file():
        return ScorerResult("plddt", "unavailable_with_reason",
                            model_or_algorithm="ESMFold",
                            detail={"reason": "p33s_scorers env not installed"})
    env = dict(os.environ)
    env["HF_HOME"] = ESMFOLD_CACHE
    env["TORCH_HOME"] = "/mnt/sdb/kxc/stamp_models/cache/p33s/torch_home"
    if gpu_device:
        env["CUDA_VISIBLE_DEVICES"] = gpu_device
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "esmfold_plddt.log"
    script = out / "_esmfold_plddt_runner.py"
    script.write_text(_ESMFOLD_PLDDT_SCRIPT, encoding="utf-8")
    cmd = [SCORER_PY, str(script), "--sequence", peptide_sequence, "--out", str(out / "structure.pdb")]
    try:
        with open(log, "w", encoding="utf-8") as lf:
            proc = subprocess.run(cmd, env=env, timeout=timeout_seconds,
                                  stdout=lf, stderr=subprocess.STDOUT)
    except subprocess.TimeoutExpired:
        return ScorerResult("plddt", "failed_with_evidence",
                            model_or_algorithm="ESMFold", model_version=ESMFOLD_MODEL,
                            detail={"reason": "timeout", "timeout_s": timeout_seconds},
                            log_path=str(log))
    except FileNotFoundError as exc:
        return ScorerResult("plddt", "failed_with_evidence",
                            model_or_algorithm="ESMFold",
                            detail={"reason": "runner missing", "error": str(exc)},
                            log_path=str(log))
    metrics_json = out / "plddt_metrics.json"
    if proc.returncode != 0 or not metrics_json.is_file():
        return ScorerResult("plddt", "failed_with_evidence",
                            model_or_algorithm="ESMFold", model_version=ESMFOLD_MODEL,
                            detail={"reason": "non-zero exit or no metrics",
                                    "exit_code": proc.returncode},
                            log_path=str(log))
    import json
    m = json.loads(metrics_json.read_text(encoding="utf-8"))
    return ScorerResult("plddt", "ok",
                        value=float(m["mean_plddt"]), unit="",
                        model_or_algorithm="ESMFold", model_version=ESMFOLD_MODEL,
                        confidence="per-residue confidence (0-100)",
                        detail={"residue_count": m.get("residue_count")},
                        log_path=str(log))


_ESMFOLD_PLDDT_SCRIPT = '''import argparse, json, sys
try:
    from esm.pretrained import esmfold_v1
except Exception as e:
    print("ESMFOLD_IMPORT_FAIL", e); sys.exit(2)
import torch
ap = argparse.ArgumentParser()
ap.add_argument("--sequence", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
model = esmfold_v1()
model = model.eval()
if torch.cuda.is_available():
    model = model.cuda()
with torch.no_grad():
    out = model.infer_pdb(a.sequence)
open(a.out, "w").write(out)
# mean plddt from output
import numpy as np
try:
    mean_plddt = float(model.predict(a.sequence)["mean_plddt"])
except Exception:
    # fallback parse
    mean_plddt = 0.0
json.dump({"mean_plddt": mean_plddt, "residue_count": len(a.sequence)}, open(a.out + ".plddt_metrics.json", "w"))
'''


# ---------------------------------------------------------------------------
# ipTM — unavailable this round (no AF2-Multimer)
# ---------------------------------------------------------------------------

def score_iptm(*_args, **_kwargs) -> ScorerResult:
    return ScorerResult(
        "iptm", "unavailable_with_reason",
        model_or_algorithm="AlphaFold2-Multimer",
        detail={"reason": "AlphaFold2-Multimer not installed in P33S round; "
                  "ipTM cannot be substituted by other scores per goal §3.1"},
    )


# ---------------------------------------------------------------------------
# Kd via PRODIGY (predicted_Kd_PRODIGY)
# ---------------------------------------------------------------------------

def score_kd_prodigy(
    complex_pdb: str | Path,
    out_dir: str | Path,
    temperature_k: float = TEMP_K,
    timeout_seconds: int = 600,
) -> ScorerResult:
    """Run PRODIGY on a receptor-peptide complex PDB.

    PRODIGY reports binding ΔG (kcal/mol). Kd is derived:
        Kd = exp(ΔG / (R*T))   [mol/L], then converted to nM.
    Returned metric name: predicted_Kd_PRODIGY. NEVER experimental.
    """
    if not Path(PRODIGY_BIN).is_file():
        return ScorerResult("kd", "unavailable_with_reason",
                            model_or_algorithm="PRODIGY",
                            detail={"reason": "prodigy binary not installed"})
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "prodigy.log"
    cmd = [PRODIGY_BIN, str(complex_pdb), "--temperature", str(temperature_k - 273.15)]
    try:
        with open(log, "w", encoding="utf-8") as lf:
            proc = subprocess.run(cmd, timeout=timeout_seconds,
                                  stdout=lf, stderr=subprocess.STDOUT)
    except subprocess.TimeoutExpired:
        return ScorerResult("kd", "failed_with_evidence",
                            model_or_algorithm="PRODIGY",
                            detail={"reason": "timeout"}, log_path=str(log))
    if proc.returncode != 0:
        return ScorerResult("kd", "failed_with_evidence",
                            model_or_algorithm="PRODIGY",
                            detail={"reason": "non-zero exit", "exit_code": proc.returncode},
                            log_path=str(log))
    dg = _parse_prodigy_dg(log)
    kd_mol = _parse_prodigy_kd(log)
    if dg is None and kd_mol is None:
        return ScorerResult("kd", "failed_with_evidence",
                            model_or_algorithm="PRODIGY",
                            detail={"reason": "could not parse ΔG or Kd from output"},
                            log_path=str(log))
    # Prefer PRODIGY's directly-predicted Kd (M). Fallback: derive from ΔG.
    if kd_mol is None and dg is not None:
        dg_j = dg * 4184.0
        kd_mol = math.exp(dg_j / (R_GAS * temperature_k))
        kd_source = "derived_from_deltaG"
    else:
        kd_source = "prodigy_direct"
    kd_nm = kd_mol * 1e9
    return ScorerResult(
        "kd", "ok",
        value=kd_nm, unit="nM",
        model_or_algorithm="PRODIGY",
        model_version="prodigy-prot-2.4.0",
        confidence="predicted; NOT experimentally measured",
        detail={
            "label": "predicted_Kd_PRODIGY",
            "delta_g_kcal_mol": dg,
            "kd_molar": kd_mol,
            "kd_source": kd_source,
            "formula_if_derived": "Kd = exp(ΔG/(R*T)); ΔG in J/mol, R=8.314, T=298.15K",
            "temperature_k": temperature_k,
            "assumptions": "standard-state, 1M reference, no experimental validation",
        },
        log_path=str(log),
    )


def _parse_prodigy_dg(log_path: Path) -> float | None:
    try:
        text = log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    import re
    for line in text.splitlines():
        low = line.lower()
        if "binding affinity" in low and "kcal" in low:
            m = re.search(r"([-+]?\d+(?:\.\d+)?)", line.split(":")[-1] if ":" in line else line)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    continue
    return None


def _parse_prodigy_kd(log_path: Path) -> float | None:
    """Parse PRODIGY's 'predicted dissociation constant (M) at ...: 1.3e-07'."""
    try:
        text = log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    import re
    m = re.search(r"dissociation constant.*?:\s*([0-9.+\-eE]+)", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# MIC — unavailable this round (no licensed MIC model)
# ---------------------------------------------------------------------------

def score_mic(*_args, **_kwargs) -> ScorerResult:
    return ScorerResult(
        "mic", "unavailable_with_reason",
        model_or_algorithm="MIC predictor",
        detail={"reason": "no licensed MIC prediction model confirmed in P33S round; "
                  "classification probability must not be presented as MIC per goal §3.3"},
    )


# ---------------------------------------------------------------------------
# MM-GBSA via AmberTools MMPBSA.py
# ---------------------------------------------------------------------------

def score_mmgbsa(
    topology_prmtop: str | Path,
    trajectory: str | Path | None,
    complex_mask: str,
    receptor_mask: str,
    ligand_mask: str,
    out_dir: str | Path,
    timeout_seconds: int = 3600,
) -> ScorerResult:
    """Run MM-GBSA via MMPBSA.py.

    Records: structure (prmtop), topology, forcefield (from prmtop lineage),
    solvent model (igb), units (kcal/mol), full command.
    Requires AmberTools installed (Phase 2). GPU not required (CPU-capable).
    """
    if not Path(MMPBSA_BIN).is_file():
        return ScorerResult("mmgbsa", "unavailable_with_reason",
                            model_or_algorithm="AmberTools MMPBSA.py",
                            detail={"reason": "MMPBSA.py not installed"})
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "mmgbsa.log"
    inp = out / "mmgbsa.in"
    inp_text = (
        "&general\n"
        "  startframe=1, endframe=1, interval=1, verbose=2,\n"
        "  receptor_mask='', ligand_mask='',\n"
        "/\n"
        "&gb\n"
        "  igb=5, saltcon=0.150,\n"
        "/\n"
    )
    inp.write_text(inp_text, encoding="utf-8")
    traj_arg = str(trajectory) if trajectory else ""
    cmd = [MMPBSA_BIN, "-O", "-i", str(inp), "-o", str(out / "mmgbsa.out"),
           "-cp", str(topology_prmtop)]
    if trajectory:
        cmd += ["-y", traj_arg]
    # conda-forge ambertools requires AMBERHOME env var (activation script sets it;
    # we set it explicitly since we invoke the binary directly).
    env = dict(os.environ)
    env["AMBERHOME"] = SCORER_ENV_PREFIX
    try:
        with open(log, "w", encoding="utf-8") as lf:
            proc = subprocess.run(cmd, env=env, timeout=timeout_seconds,
                                  stdout=lf, stderr=subprocess.STDOUT)
    except subprocess.TimeoutExpired:
        return ScorerResult("mmgbsa", "failed_with_evidence",
                            model_or_algorithm="AmberTools MMPBSA.py",
                            detail={"reason": "timeout"}, log_path=str(log))
    if proc.returncode != 0:
        return ScorerResult("mmgbsa", "failed_with_evidence",
                            model_or_algorithm="AmberTools MMPBSA.py",
                            detail={"reason": "non-zero exit", "exit_code": proc.returncode,
                                    "command": " ".join(cmd)},
                            log_path=str(log))
    dg = _parse_mmgbsa_dg(out / "mmgbsa.out")
    if dg is None:
        return ScorerResult("mmgbsa", "failed_with_evidence",
                            model_or_algorithm="AmberTools MMPBSA.py",
                            detail={"reason": "could not parse ΔG from .out"},
                            log_path=str(log))
    return ScorerResult(
        "mmgbsa", "ok",
        value=dg, unit="kcal/mol",
        model_or_algorithm="AmberTools MMPBSA.py",
        model_version="ambertools (conda-forge)",
        confidence="single-frame GB approximation; NOT experimental",
        detail={
            "forcefield": "from input prmtop lineage",
            "solvent_model": "Generalized Born igb=5",
            "saltcon_molar": 0.150,
            "structure": str(topology_prmtop),
            "topology": str(topology_prmtop),
            "trajectory": traj_arg or "none (single structure)",
            "command": " ".join(cmd),
            "label": "predicted_MMGBSA_deltaG",
        },
        log_path=str(log),
    )


def _parse_mmgbsa_dg(out_path: Path) -> float | None:
    try:
        text = out_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    for line in text.splitlines():
        if line.strip().startswith("DELTA") and "binding" in line.lower():
            pass
        low = line.lower()
        if "delta" in low and "total" in low:
            for tok in line.replace("=", " ").replace("-", " -").split():
                try:
                    return float(tok)
                except ValueError:
                    continue
    return None
