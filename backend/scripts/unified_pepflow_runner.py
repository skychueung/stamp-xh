#!/usr/bin/env python3
"""Execute PepFlow GPU inference on the proven structural fixture and decode candidates."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

SOURCE = Path("/mnt/sdb/kxc/stamp_models/source/pepflow/extracted_p25_install_probe/PepFlowww-main")
PYTHON = "/mnt/sdb/kxc/stamp_models/envs/pepflow_py310_pypi_candidate/bin/python"
CHECKPOINT = "/mnt/sdb/kxc/stamp_models/checkpoints/pepflow/p25_install_probe/PepFlow2024_share/model2.pt"
FIXTURE = Path("/mnt/sdb/kxc/stamp_models/artifacts/p33u_lane_d/p33u_d7_20260703_2100/pepflow/input")
RESTYPES = list("ARNDCEQGHILKMFPSTWYV")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-json", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--result-json", required=True)
    args = ap.parse_args()
    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    output = Path(args.output_dir).resolve()
    (output / "outputs").mkdir(parents=True, exist_ok=True)
    input_copy = output / "input"
    shutil.copytree(FIXTURE, input_copy, dirs_exist_ok=True)
    config = (input_copy / "full_config.yaml").read_text(encoding="utf-8")
    config = config.replace(str(FIXTURE / "structure_dir"), str(input_copy / "structure_dir"))
    config = config.replace(str(FIXTURE), str(input_copy))
    config_path = input_copy / "runtime_config.yaml"
    config_path.write_text(config, encoding="utf-8")
    inference_source = SOURCE / "models_con" / "inference.py"
    runtime_inference = input_copy / "inference_seeded.py"
    inference_text = inference_source.read_text(encoding="utf-8")
    fixed_seed = "seed_all(114514)"
    if fixed_seed not in inference_text:
        raise RuntimeError("PEPFLOW_SEED_HOOK_NOT_FOUND")
    inference_text = inference_text.replace(fixed_seed, f"seed_all({int(payload.get('seed', 42))})", 1)
    runtime_inference.write_text(inference_text, encoding="utf-8")
    command = [
        os.environ.get("STAMP_PEPFLOW_PYTHON", PYTHON),
        str(runtime_inference),
        "--config", str(config_path), "--device", "cuda:0",
        "--ckpt", os.environ.get("STAMP_PEPFLOW_CHECKPOINT", CHECKPOINT),
        "--output", str(output), "--num_steps", str(payload.get("num_steps", 3)),
        "--num_samples", str(payload.get("num_candidates", 1)),
    ]
    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = str(payload.get("gpu_index", 1))
    env["PYTHONPATH"] = str(SOURCE) + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.run(command, check=True, cwd=str(SOURCE), env=env)
    decoder = (
        "import json,torch,sys; p=torch.load(sys.argv[1],map_location='cpu',weights_only=False);"
        "s=p['seqs'].cpu();m=p['batch']['generate_mask'].cpu().bool();aa='ARNDCEQGHILKMFPSTWYV';"
        "print(json.dumps([''.join(aa[int(x)] for x in s[i][m[i]].tolist()) for i in range(s.shape[0])]))"
    )
    decoded = subprocess.run(
        [command[0], "-c", decoder, str(output / "outputs" / "case0.pt")],
        check=True, capture_output=True, text=True,
    )
    candidates = [{"sequence": sequence, "rank": rank}
                  for rank, sequence in enumerate(json.loads(decoded.stdout), 1)]
    Path(args.result_json).write_text(json.dumps({
        "candidates": candidates,
        "metrics": {"num_steps": int(payload.get("num_steps", 3)), "job_seed": payload.get("seed")},
        "runner_command": command, "checkpoint_load": "PepFlow model2.pt",
        "warnings": ["Uses the server's proven case0 receptor/pocket fixture for structural input."],
    }, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
