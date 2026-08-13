#!/usr/bin/env bash
# P33U-D21 DiffPepBuilder dev-only minimal real-run smoke.
#
# Reuses the D10-proven path (D10-2, gate P33U_D10_DIFFPEPBUILDER_12AA_CLOSED):
# invoke experiments/run_inference.py directly via Hydra with
# inference.sampling.min_length=12 max_length=12 samples_per_length=3, using the
# D10 processed receptor (metadata_test.csv with `processed_path` column) and the
# diffpepbuilder_v1.pth checkpoint. NO CUDA_VISIBLE_DEVICES mask (D10-proven:
# GPUtil picks cuda:1 = GPU1, which has more free memory than GPU0 prod).
#
# This is a REAL model forward pass on GPU1 producing real 12aa peptide PDBs.
# NOT a dry-run. NOT truncated from D8 22aa. Outputs tagged
# NOT_EXPERIMENTALLY_VALIDATED / COMPUTATIONAL_PREDICTION_ONLY.
#
# Usage: bash p33u_d21_diffpepbuilder_smoke.sh <job_dir>
# Writes: <job_dir>/log.txt (stdout+stderr), PDBs under <job_dir>/runs/inference/...

set -uo pipefail

JOB_DIR="${1:?job_dir required}"
mkdir -p "$JOB_DIR"

DPB_ROOT="/mnt/sdb/kxc/stamp_models/source/diffpepbuilder/extracted_p24_install_probe/DiffPepBuilder-main"
PY="/mnt/sdb/kxc/stamp_models/envs/diffpepbuilder_py39/bin/python"
CKPT="/mnt/sdb/kxc/stamp_models/weights/diffpepbuilder/diffpepbuilder_v1.pth"
# D10 processed receptor CSV (has the correct `processed_path` column that
# run_inference.py reads at line 135; the wrapper's receptors.csv used the
# buggy `processed_file_path` column and was bypassed in D10).
VAL_CSV="/mnt/sdb/kxc/stamp_models/artifacts/p33u_lane_d/p33u_d10_20260704/diffpepbuilder/p33u_d10_diffpepbuilder_12aa/processed/metadata_test.csv"

LOG="$JOB_DIR/log.txt"

# BASE_PATH must point to DiffPepBuilder-main so ${oc.env:BASE_PATH}/runs/.cache/
# resolves to the cached IGSO3 (D10 reused this cache).
export BASE_PATH="$DPB_ROOT"

# NOTE: deliberately NOT setting CUDA_VISIBLE_DEVICES — D10-proven: GPUtil picks
# cuda:1 (GPU1, ~free) over cuda:0 (GPU0 prod, ~9GB used). GPU0 prod untouched.
cd "$DPB_ROOT"

echo "[D21-DPB] start $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
echo "[D21-DPB] job_dir=$JOB_DIR" | tee -a "$LOG"
echo "[D21-DPB] ckpt=$CKPT" | tee -a "$LOG"
echo "[D21-DPB] val_csv=$VAL_CSV" | tee -a "$LOG"
echo "[D21-DPB] python=$PY" | tee -a "$LOG"

"$PY" experiments/run_inference.py \
  --config-name inference \
  inference.sampling.min_length=12 \
  inference.sampling.max_length=12 \
  inference.sampling.samples_per_length=3 \
  experiment.use_gpu=true \
  experiment.num_gpus=1 \
  experiment.use_ddp=false \
  experiment.eval_ckpt_path="$CKPT" \
  experiment.eval_dir="$JOB_DIR" \
  data.val_csv_path="$VAL_CSV" \
  >> "$LOG" 2>&1

EXIT=$?
echo "[D21-DPB] exit=$EXIT $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"

# Collect produced PDBs into a flat list for easy SHA / artifact enumeration.
# Path is <eval_dir>/inference/<ts>/target/length_12/target_length_12_sample_*.pdb
# (broad glob so it matches whether or not a runs/ prefix is inserted).
find "$JOB_DIR" -name "target_length_12_sample_*.pdb" -type f 2>/dev/null | sort > "$JOB_DIR/produced_pdbs.txt"
echo "[D21-DPB] produced $(wc -l < "$JOB_DIR/produced_pdbs.txt" 2>/dev/null || echo 0) PDB sample(s)" | tee -a "$LOG"

exit $EXIT
