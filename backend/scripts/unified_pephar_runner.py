#!/usr/bin/env python3
"""Bridge the proven PepHAR forward-pass script to the unified result schema."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from pathlib import Path

THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def peptide_from_pdb(path: Path) -> str:
    residues: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.startswith("ATOM") or line[21:22] != "Z":
            continue
        key = (line[21:22], line[22:26].strip(), line[26:27])
        if key in seen:
            continue
        seen.add(key)
        residues.append(THREE_TO_ONE.get(line[17:20].strip(), "X"))
    return "".join(residues)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-json", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--result-json", required=True)
    ap.add_argument("--runner", default=str(Path(__file__).with_name("p33u_d21_pephar_smoke.py")))
    args = ap.parse_args()
    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    output = Path(args.output_dir).resolve()
    job_dir = output / "pephar_run"
    command = [
        os.environ.get("STAMP_PEPHAR_PYTHON", "/mnt/sdb/kxc/stamp_models/envs/pephar_py310/bin/python"),
        args.runner, "--job-dir", str(job_dir),
        "--n-samples", str(payload.get("num_candidates", 1)),
        "--gpu", "0", "--seed", str(payload.get("seed", 42)),
    ]
    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = str(payload.get("gpu_index", 1))
    subprocess.run(command, check=True, env=env)
    metrics_path = next(job_dir.rglob("test.csv"))
    metrics_rows = list(csv.DictReader(metrics_path.open(encoding="utf-8")))
    candidates = []
    for rank, pdb in enumerate(sorted(job_dir.rglob("gen_*.pdb")), 1):
        sequence = peptide_from_pdb(pdb)
        if "X" in sequence or not sequence:
            raise RuntimeError(f"PEPHAR_PDB_SEQUENCE_INVALID: {pdb}")
        row = metrics_rows[rank - 1] if rank <= len(metrics_rows) else {}
        candidates.append({
            "sequence": sequence, "rank": rank,
            "score": float(row["recovery"]) if row.get("recovery") else None,
            "structure_path": str(pdb.relative_to(output)),
        })
    result = {"candidates": candidates, "metrics": {"rows": metrics_rows},
              "runner_command": command, "checkpoint_load": "density+prediction"}
    Path(args.result_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
