# P6h Complex ColabFold Smoke Test — Server Execution Package

## Overview

This package contains everything needed to run a target + peptide complex
structure prediction smoke test using ColabFold (AlphaFold-Multimer v3).

**Status:** INPUT_PREPARATION_ONLY — real prediction requires multimer model weights.

## Prerequisites

- Ubuntu 24.04 with NVIDIA GPU (tested on RTX 4090)
- ColabFold 1.6.1 installed in `localcolabfold` conda/micromamba env
- ~4GB free disk space for multimer model weights
- ~10GB free RAM

## Known Blocker

**AlphaFold-Multimer v3 weights are NOT currently installed.**

The server has monomer weights (`alphafold_params_2021-07-14.tar`, ~3.5GB)
but lacks multimer weights (`alphafold_params_2022-12-06.tar`, ~3.8GB).

Downloading from Google Storage is throttled at ~300-400 KB/s,
estimated 2.5–3 hours for the full download.

### Workaround

Option A: Let ColabFold auto-download on first run (slow but automatic).
Option B: Manually download and extract:

```bash
wget https://storage.googleapis.com/alphafold/alphafold_params_2022-12-06.tar
# or use axel for faster parallel download:
# axel -n 16 https://storage.googleapis.com/alphafold/alphafold_params_2022-12-06.tar

tar -xf alphafold_params_2022-12-06.tar -C ~/.cache/colabfold/params/
```

## Files

| File | Description |
|------|-------------|
| `P6H_RUN_COMPLEX_COLABFOLD_SMOKE.sh` | Main execution script |
| `P6H_PARSE_COMPLEX_OUTPUT.py` | Output parser (run after prediction) |
| `input/p6h_complex_smoke.fasta` | Target + peptide two-chain FASTA |

## Usage

```bash
cd ~/kxc/p6h_complex_smoke
bash P6H_RUN_COMPLEX_COLABFOLD_SMOKE.sh
```

After completion:

```bash
python3 P6H_PARSE_COMPLEX_OUTPUT.py ~/kxc/p6h_complex_smoke/output
```

## Input Design

The FASTA contains two records:
- `target_chain_A`: 100 aa target protein
- `candidate_peptide_chain_B`: 15 aa candidate peptide

Both are separate chains — NOT concatenated.

## Command Flags

| Flag | Value | Reason |
|------|-------|--------|
| `--model-type` | `alphafold2_multimer_v3` | Multimer model for complex prediction |
| `--num-models` | `1` | Smoke test: only one model |
| `--num-recycle` | `1` | Smoke test: minimal recycling |
| `--msa-mode` | `single_sequence` | Skip MSA server for speed |
| `--pair-mode` | `unpaired_paired` | Standard multimer MSA pairing |
| `--rank` | `multimer` | Use multimer ranking metric |

## Expected Outputs

```
output/
  p6h_complex_smoke_unrelaxed_rank_001_alphafold2_multimer_v3_model_1_seed_000.pdb
  p6h_complex_smoke_scores_rank_001_alphafold2_multimer_v3_model_1_seed_000.json
  p6h_complex_smoke_pae.png
  p6h_complex_smoke_coverage.png
  ranking_debug.json
```

## Scientific Boundaries

- **NOT_EXPERIMENTALLY_VALIDATED**
- **COMPUTATIONAL_COMPLEX_STRUCTURE_PREDICTION_ONLY**
- No pDockQ / delta_G / docking_score is computed
- This is a smoke test, not a production prediction
