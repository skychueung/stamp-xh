#!/bin/bash
# P6l: Batch ColabFold Complex Prediction Runner
#
# Iterates over input/*.fasta and runs colabfold_batch for each candidate
# into its own output/<candidate_id>/ directory.
#
# Usage:
#   bash P6L_RUN_BATCH_COLABFOLD.sh [INPUT_DIR] [OUTPUT_DIR] [LOG_DIR]
#
# Defaults:
#   INPUT_DIR=~/kxc/p6l_batch_complex_prediction/input
#   OUTPUT_DIR=~/kxc/p6l_batch_complex_prediction/output
#   LOG_DIR=~/kxc/p6l_batch_complex_prediction/logs

set -euo pipefail

INPUT_DIR="${1:-$HOME/kxc/p6l_batch_complex_prediction/input}"
OUTPUT_DIR="${2:-$HOME/kxc/p6l_batch_complex_prediction/output}"
LOG_DIR="${3:-$HOME/kxc/p6l_batch_complex_prediction/logs}"

mkdir -p "$OUTPUT_DIR" "$LOG_DIR"

# Activate localcolabfold environment
export PATH="$HOME/.local/bin:$PATH"
export MAMBA_ROOT_PREFIX="$HOME/micromamba"
eval "$(micromamba shell hook --shell bash)"
micromamba activate localcolabfold

TOTAL=0
SUCCESS=0
FAILED=0

SUMMARY_FILE="$OUTPUT_DIR/batch_run_summary.json"
SUMMARY_ENTRIES=()

for fasta in "$INPUT_DIR"/*.fasta; do
    [ -f "$fasta" ] || continue

    # Extract candidate_id from filename: candidate_<id>_complex.fasta
    basename_fasta=$(basename "$fasta")
    candidate_id="${basename_fasta#candidate_}"
    candidate_id="${candidate_id%_complex.fasta}"

    outdir="$OUTPUT_DIR/candidate_$candidate_id"
    logfile="$LOG_DIR/${candidate_id}.log"

    mkdir -p "$outdir"

    TOTAL=$((TOTAL + 1))
    echo "[P6L-BATCH] [$TOTAL] Running candidate $candidate_id → $outdir"

    set +e
    colabfold_batch \
        --num-models 1 \
        --num-recycle 3 \
        --msa-mode single_sequence \
        --pair-mode unpaired_paired \
        --model-type alphafold2_multimer_v3 \
        --rank multimer \
        --save-all \
        "$fasta" \
        "$outdir" \
        > "$logfile" 2>&1
    exit_code=$?
    set -e

    if [ $exit_code -eq 0 ]; then
        echo "[P6L-BATCH]   ✓ Success"
        SUCCESS=$((SUCCESS + 1))
        status="SUCCESS"
    else
        echo "[P6L-BATCH]   ✗ Failed (exit $exit_code)"
        FAILED=$((FAILED + 1))
        status="FAILED"
    fi

    # Build JSON summary entry
    entry=$(printf '{"candidate_id":"%s","status":"%s","exit_code":%d,"log":"%s","output_dir":"%s"}' \
        "$candidate_id" "$status" "$exit_code" "$logfile" "$outdir")
    SUMMARY_ENTRIES+=("$entry")
done

# Write summary JSON
printf '[%s]' "$(IFS=,; echo "${SUMMARY_ENTRIES[*]}")" > "$SUMMARY_FILE"

echo ""
echo "[P6L-BATCH] ===================================="
echo "[P6L-BATCH] Batch complete"
echo "[P6L-BATCH] Total:   $TOTAL"
echo "[P6L-BATCH] Success: $SUCCESS"
echo "[P6L-BATCH] Failed:  $FAILED"
echo "[P6L-BATCH] Summary: $SUMMARY_FILE"
echo "[P6L-BATCH] ===================================="
