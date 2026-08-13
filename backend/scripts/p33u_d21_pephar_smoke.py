"""P33U-D21 PepHAR dev-only minimal real-run smoke.

Faithful re-run of the D10-3 proven path (gate P33U_D10_PEPHAR_12AA_CLOSED):
use the D7-proven ``sample_remapped`` approach with the 12aa-truncated input
pkl (``test_data_12aa.pkl``) and ``AnchorBasedSampler``, 3 samples, on GPU1.

This is a REAL PepHAR forward pass producing real 12aa peptide PDBs + rmsd /
recovery / valid metrics. NOT a dry-run. NOT truncated from D8 22aa output.
Outputs tagged NOT_EXPERIMENTALLY_VALIDATED / COMPUTATIONAL_PREDICTION_ONLY.

D10 bugs bypassed: the p33l wrapper (``stamp_pephar_p33l_real_runner.py``) had
``NameError: name 'device' is not defined`` + TruncateProteinV3 import scope
bugs; D10 bypassed it with ``sample_remapped_d10.py``. This D21 script is that
script, refactored to take ``--job-dir`` so output lands in the D21 job dir
(additive; D10 original untouched).

Usage:
  CUDA_VISIBLE_DEVICES=1 python p33u_d21_pephar_smoke.py --job-dir <dir> [--n-samples 3]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# PepHAR source root (must be on sys.path before the model imports below).
PEPHAR_SRC = "/mnt/sdb/kxc/stamp_models/source/pephar/extracted_p25_install_probe/PepHAR-main"
sys.path.insert(0, PEPHAR_SRC)

# D10 input pkl (12aa-truncated peptide init). Reused read-only; copied into the
# job dir so the D10 artifact dir is never mutated.
D10_INPUT_PKL = Path(
    "/mnt/sdb/kxc/stamp_models/artifacts/p33u_lane_d/p33u_d10_20260704/"
    "pephar/p33u_d10_pephar_12aa/test_data_12aa.pkl"
)
# Checkpoint dirs (contain both the .yml config and checkpoints/*.pt). The D10
# script symlinked these into <project_root>/logs/; this script reproduces that.
DENSITY_CKPT_DIR = Path(
    "/mnt/sdb/kxc/stamp_models/checkpoints/pephar/p25_install_probe/"
    "PepHAR_ICLR2025_SHARE/ckpts/density_v4_x5o2_2024_09_08__11_25_36"
)
PREDICTION_CKPT_DIR = Path(
    "/mnt/sdb/kxc/stamp_models/checkpoints/pephar/p25_install_probe/"
    "PepHAR_ICLR2025_SHARE/ckpts/prediction_d2_x2o1_2024_09_08__11_21_33"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--n-samples", type=int, default=3)
    parser.add_argument("--gpu", type=int, default=0)  # cuda:{gpu}; under CUDA_VISIBLE_DEVICES=1, 0 == physical GPU1
    parser.add_argument("--anchor-steps", type=int, default=10)
    parser.add_argument("--finetune-steps", type=int, default=0)
    parser.add_argument("--dist-strategy", type=str, default="single")
    parser.add_argument("--anchor-strategy", type=str, default="gt")
    parser.add_argument("--extend-strategy", type=str, default="sto")
    parser.add_argument("--anchor-nums", type=int, default=1)
    # D22: fixed seed for reproducible smoke (extend_strategy=sto is stochastic).
    # D21 ran with no seed; D22 defaults to seed=12345 via the SmokeRunnerAdapter.
    # When None, behavior matches D21 (stochastic).
    parser.add_argument("--seed", type=int, default=None)
    # AnchorBasedSampler reads these four attrs off the namespace (see
    # evaluate/sample.py). Defaults are set AFTER parse_args (once job_dir is
    # known) — same layout as D10 sample_remapped_d10.py: logs/<ckpt_name>
    # symlinks recreated in the job dir.
    parser.add_argument("--density-config-path", type=str, default="")
    parser.add_argument("--density-param-path", type=str, default="")
    parser.add_argument("--prediction-config-path", type=str, default="")
    parser.add_argument("--prediction-param-path", type=str, default="")
    args = parser.parse_args()

    job_dir = Path(args.job_dir).resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    project_root = str(job_dir)

    # Copy the 12aa input pkl into the job dir (D10 artifact untouched).
    if not D10_INPUT_PKL.is_file():
        print(f"[D21-PEPHAR] FATAL: D10 input pkl not found: {D10_INPUT_PKL}", flush=True)
        return 2
    local_pkl = job_dir / "test_data_12aa.pkl"
    if not local_pkl.is_file():
        shutil.copy2(D10_INPUT_PKL, local_pkl)

    # Recreate the logs/<ckpt_name> symlinks the D10 script expected (config +
    # checkpoint resolution).
    logs_dir = job_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    for ckpt_dir in (DENSITY_CKPT_DIR, PREDICTION_CKPT_DIR):
        link = logs_dir / ckpt_dir.name
        if not link.exists():
            link.symlink_to(ckpt_dir, target_is_directory=True)

    # Now populate the four density/prediction path attrs (defaults point at
    # the logs/ symlinks recreated above).
    if not args.density_config_path:
        args.density_config_path = f"{project_root}/logs/{DENSITY_CKPT_DIR.name}/density_v4_x5o2.yml"
    if not args.density_param_path:
        args.density_param_path = f"{project_root}/logs/{DENSITY_CKPT_DIR.name}/checkpoints/1400.pt"
    if not args.prediction_config_path:
        args.prediction_config_path = f"{project_root}/logs/{PREDICTION_CKPT_DIR.name}/prediction_d2_x2o1.yml"
    if not args.prediction_param_path:
        args.prediction_param_path = f"{project_root}/logs/{PREDICTION_CKPT_DIR.name}/checkpoints/2400.pt"

    # Now replicate sample_remapped_d10.py with project_root = job_dir.
    # (Imports happen here so --help / arg errors don't trigger the heavy import.)
    sys.path.append(project_root)
    from evaluate.sample import AnchorBasedSampler  # noqa: E402
    import warnings  # noqa: E402
    warnings.filterwarnings("ignore")
    from torchvision import transforms  # noqa: E402
    from tqdm.autonotebook import tqdm  # noqa: E402
    import torch  # noqa: E402
    from datasets.protein_peptide_dataset import ProteinPeptideDataset  # noqa: E402
    from datasets.transforms.truncate_protein_transform import TruncateProteinV3  # noqa: E402
    import pandas as pd  # noqa: E402

    args.device = f"cuda:{args.gpu}" if torch.cuda.is_available() else "cpu"
    args.max_pep_length_density = 32

    # D22: seed RNGs for reproducible smoke (extend_strategy=sto is stochastic).
    # Seeding happens after torch import, before any sampling. When --seed is
    # None, behavior matches D21 (stochastic).
    if args.seed is not None:
        import random as _random  # noqa: E402
        import numpy as _np  # noqa: E402
        _random.seed(args.seed)
        _np.random.seed(args.seed)
        torch.manual_seed(args.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(args.seed)
        print(f"[D22-PEPHAR] seed={args.seed} (fixed; reproducible smoke)", flush=True)
    else:
        print(f"[D22-PEPHAR] seed=None (stochastic; D21 parity)", flush=True)

    data_root = str(local_pkl)
    transform = transforms.Compose([TruncateProteinV3()])
    dataset = ProteinPeptideDataset(data_root, train=False, transform=transform, return_name=True)
    dataset_no = ProteinPeptideDataset(data_root, train=False, transform=None, return_name=True)

    pdb_path = (
        f"result/new_{args.anchor_steps}_{args.finetune_steps}_{args.dist_strategy}_"
        f"{args.anchor_strategy}_{args.extend_strategy}_{args.anchor_nums}"
    )
    csv_name = f"{project_root}/{pdb_path}/test.csv"
    Path(f"{project_root}/{pdb_path}").mkdir(parents=True, exist_ok=True)

    table = {"name": [], "rmsd": [], "recovery": [], "rec_length": [], "pep_length": [], "num": [], "valid": []}
    print(f"[D21-PEPHAR] start device={args.device} n_samples={args.n_samples}", flush=True)
    for i in tqdm(range(len(dataset))):
        for j in range(args.n_samples):
            name, data = dataset[i]
            name, data_full = dataset_no[i]
            if j == 0:
                from evaluate.writer import save_pdb_rec_pep
                save_pdb_rec_pep(data_full, data_full, f"{project_root}/{pdb_path}/{name}/gt.pdb")
            sampler = AnchorBasedSampler(args)
            peptide, metrics = sampler.sample(
                data, anchor_steps=args.anchor_steps, finetune_steps=args.finetune_steps,
                dist_strategy=args.dist_strategy, anchor_strategy=args.anchor_strategy,
                extend_strategy=args.extend_strategy, verbose=False, anchor_nums=args.anchor_nums,
            )
            table["name"].append(name)
            table["num"].append(j)
            table["rmsd"].append(metrics["rmsd"])
            table["recovery"].append(metrics["recovery"])
            table["rec_length"].append((data["rec_aa"] != 20).sum().item())
            table["pep_length"].append((data["pep_aa"] != 20).sum().item())
            table["valid"].append(metrics["valid"])
            pd.DataFrame(table).to_csv(csv_name, index=None)
            from evaluate.writer import save_pdb_rec_pep
            save_pdb_rec_pep(data_full, peptide, f"{project_root}/{pdb_path}/{name}/gen_{j}.pdb")
            print(
                f"sample {j}: pep_length={table['pep_length'][-1]} "
                f"rmsd={metrics['rmsd']:.3f} recovery={metrics['recovery']:.3f} valid={metrics['valid']}",
                flush=True,
            )
    print("PEPHAR_D21_DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
