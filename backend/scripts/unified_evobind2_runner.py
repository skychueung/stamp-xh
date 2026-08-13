#!/usr/bin/env python3
"""Run EvoBind2's real AlphaFold-backed design entrypoint and normalize output."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from pathlib import Path

SOURCE = Path("/home/xh/kxc/stampup/models_dev/evobind2/source/EvoBind")
PYTHON = "/home/xh/kxc/stampup/stamp-small-change-model/models/evobind2/envs/evobind/bin/python"
DATA_DIR = "/home/xh/kxc/stampup/stamp-small-change-model/models/evobind2/cache/af2_params"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-json", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--result-json", required=True)
    args = ap.parse_args()
    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    sequence = str(payload["target_sequence"]).strip().upper()
    output = Path(args.output_dir).resolve()
    data = output / "input"
    design = output / "design"
    data.mkdir(parents=True, exist_ok=True)
    design.mkdir(parents=True, exist_ok=True)
    fasta = data / "receptor.fasta"
    a3m = data / "receptor.a3m"
    fasta.write_text(f">target\n{sequence}\n", encoding="utf-8")
    a3m.write_text(f">target\n{sequence}\n", encoding="utf-8")
    command = [
        os.environ.get("STAMP_EVOBIND2_PYTHON", PYTHON),
        str(SOURCE / "src" / "mc_design.py"),
        f"--receptor_fasta_path={fasta}",
        f"--peptide_length={int(payload.get('peptide_length', 12))}",
        f"--output_dir={design}", "--model_names=model_1",
        f"--data_dir={os.environ.get('STAMP_EVOBIND2_DATA_DIR', DATA_DIR)}",
        "--max_recycles=1", f"--num_iterations={int(payload.get('num_iterations', 1))}",
        f"--random_seed={int(payload.get('seed', 42))}", f"--msas={a3m}",
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SOURCE / "src" / "AF2") + os.pathsep + env.get("PYTHONPATH", "")
    env["CUDA_VISIBLE_DEVICES"] = str(payload.get("gpu_index", 1))
    subprocess.run(command, check=True, cwd=str(SOURCE), env=env)
    metrics_file = design / "metrics.csv"
    rows = list(csv.DictReader(metrics_file.open(encoding="utf-8")))
    candidates = []
    for rank, row in enumerate(rows, 1):
        if row.get("iteration") == "init":
            continue
        iteration = row.get("iteration", str(rank))
        pdb = design / f"unrelaxed_{iteration}.pdb"
        candidates.append({
            "sequence": row["sequence"], "rank": len(candidates) + 1,
            "score": -float(row["loss"]),
            "structure_path": str(pdb.relative_to(output)) if pdb.is_file() else None,
        })
    if not candidates and rows:
        candidates = [{"sequence": rows[-1]["sequence"], "rank": 1,
                       "score": -float(rows[-1]["loss"])}]
    Path(args.result_json).write_text(json.dumps({
        "candidates": candidates, "metrics": {"iterations": rows},
        "runner_command": command, "checkpoint_load": "AlphaFold model_1",
    }, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
