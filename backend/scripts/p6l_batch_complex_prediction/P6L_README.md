# P6l Batch Complex Prediction — Server Scripts

These scripts automate the Top-N candidate → ColabFold complex → interface_quality pipeline on the Ubuntu server.

## Prerequisites

- ColabFold 1.6.1 installed in `localcolabfold` micromamba env
- AlphaFold-Multimer v3 weights in `~/.cache/colabfold/params/`
- STAMP backend Python environment accessible (for DB access)
- Database contains stamp candidates with composite_score

## Directory Layout

```
~/kxc/p6l_batch_complex_prediction/
├── input/          # Generated FASTA files
├── output/         # ColabFold per-candidate outputs
├── logs/           # Per-candidate ColabFold logs
├── manifests/      # batch_manifest.json + target_sequence.txt
└── batch_parse_report.json
└── batch_import_report.json
```

## Step 1: Prepare Batch Inputs

Generate FASTA files and manifest from DB candidates:

```bash
cd ~/kxc/p6l_batch_complex_prediction
python3 /path/to/P6L_PREPARE_BATCH_COMPLEX_INPUTS.py <project_id> --top-n 3
```

This creates:
- `input/candidate_<id>_complex.fasta` for each Top-3 candidate
- `manifests/batch_manifest_<project_id>_top3.json`
- `manifests/target_sequence_<project_id>.txt`

## Step 2: Run ColabFold Batch

```bash
cd ~/kxc/p6l_batch_complex_prediction
bash /path/to/P6L_RUN_BATCH_COLABFOLD.sh input/ output/ logs/
```

Features:
- Runs each FASTA independently into `output/candidate_<id>/`
- Continues on single failure (does not abort entire batch)
- Writes `output/batch_run_summary.json`
- Logs to `logs/<candidate_id>.log`

## Step 3: Parse Batch Outputs

```bash
python3 /path/to/P6L_PARSE_BATCH_OUTPUTS.py --output-dir output/
```

Validates each candidate output has:
- Complex PDB with chain A and chain B
- PAE JSON
- Ranking JSON

## Step 4: Import interface_quality

```bash
python3 /path/to/P6L_IMPORT_INTERFACE_QUALITY.py --output-dir output/
```

For each successful candidate:
1. Runs `complex_interface_parser` (P6i)
2. Runs `pdockq_calculator` (P6j)
3. Persists to `stamp_candidate.metrics["interface_quality"]`

Options:
- `--overwrite` to re-import existing interface_quality entries

## Scientific Boundaries

- **pDockQ**: Computed from ColabFold interface contacts + pLDDT (Bryant 2022). Computational estimate only.
- **delta_G**: NOT computed. Requires FoldX/Rosetta/MM-GBSA. Kept as `null`.
- **docking_score**: NOT computed. Requires FlexPepDock/RosettaDock. Kept as `null`.
- All metrics marked `NOT_EXPERIMENTALLY_VALIDATED`.

## Troubleshooting

**No candidates found**: Ensure the project has stamp_candidates with composite_score in the DB.

**ColabFold fails for one candidate**: Check `logs/<candidate_id>.log`. Other candidates continue.

**Missing chain B in PDB**: Usually means FASTA format was wrong (two records instead of one with `:`). Verify `input/*.fasta` has single-record format.
