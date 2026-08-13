#!/bin/bash
# P6h Complex ColabFold Smoke Test
# Target + Peptide multimer prediction

set -euo pipefail

WORK_DIR="$HOME/kxc/p6h_complex_smoke"
INPUT_DIR="$WORK_DIR/input"
OUTPUT_DIR="$WORK_DIR/output"
LOG_DIR="$WORK_DIR/logs"
FASTA="$INPUT_DIR/p6h_complex_smoke.fasta"

mkdir -p "$OUTPUT_DIR" "$LOG_DIR"

# Activate localcolabfold environment
export PATH="$HOME/.local/bin:$PATH"
export MAMBA_ROOT_PREFIX="$HOME/micromamba"
eval "$(micromamba shell hook --shell bash)"
micromamba activate localcolabfold

echo "[P6H] Starting complex structure prediction smoke test"
echo "[P6H] Input FASTA: $FASTA"
echo "[P6H] Output dir: $OUTPUT_DIR"
echo "[P6H] Model type: alphafold2_multimer_v3"
echo "[P6H] GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
echo "[P6H] Start time: $(date -Iseconds)"

# Run ColabFold in multimer mode with minimal settings for smoke test
colabfold_batch \
    --num-models 1 \
    --num-recycle 1 \
    --msa-mode single_sequence \
    --pair-mode unpaired_paired \
    --model-type alphafold2_multimer_v3 \
    --rank multimer \
    --save-all \
    "$FASTA" \
    "$OUTPUT_DIR" \
    2>&1 | tee "$LOG_DIR/p6h_complex_smoke_$(date +%Y%m%d_%H%M%S).log"

echo "[P6H] Finished at: $(date -Iseconds)"
