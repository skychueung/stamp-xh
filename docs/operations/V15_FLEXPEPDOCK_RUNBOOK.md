# STAMP v1.5 P1 — FlexPepDock Runbook

## Overview

This runbook documents the FlexPepDock peptide-protein docking integration added in STAMP v1.5 P1.

FlexPepDock is a Rosetta-based protocol for docking flexible peptides onto rigid protein receptors. It is the fastest computational win identified in the v1.5 environment audit because Rosetta is already installed on the server.

## Activation

### 1. Source Rosetta Environment

```bash
source /home/xh/kxc/tools/rosetta/rosetta_env.sh
```

This sets:
- `ROSETTA_ROOT=/home/xh/kxc/tools/rosetta`
- `PATH` includes the Rosetta binary directory

### 2. Verify Binary

```bash
which FlexPepDocking.default.linuxgccrelease
```

Expected output:
```
/home/xh/kxc/tools/rosetta/rosetta.binary.ubuntu.release-408/main/source/build/src/release/linux/5.4/64/x86/gcc/7/static/FlexPepDocking.default.linuxgccrelease
```

### 3. Verify Database

```bash
ls $ROSETTA_ROOT/database/
```

Should contain subdirectories like `chemical/`, `scoring/`, `sampling/`.

## API Endpoints

### Probe Environment

```
GET /api/v1/flexpepdock-pilot/probe
```

Returns `AVAILABLE` or `BLOCKED` with specific reasons.

### Validate Input

```
POST /api/v1/flexpepdock-pilot/validate-input
Body: {"input_json": {"receptor_pdb": "...", "peptide_pdb": "...", "receptor_chain": "A", "peptide_chain": "B"}}
```

### Create Workdir

```
POST /api/v1/flexpepdock-pilot/create-workdir
Body: {"batch_id": "...", "item_id": "..."}
```

### Dry Run

```
POST /api/v1/flexpepdock-pilot/dry-run
Body: {"batch_id": "...", "item_id": "...", "input_json": {...}}
```

### Smoke Test

```
POST /api/v1/flexpepdock-pilot/smoke
```

Runs `FlexPepDocking.default.linuxgccrelease -help`.

## Input Requirements

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `receptor_pdb` | string | Yes | Path to receptor PDB file |
| `peptide_pdb` | string | No* | Path to peptide PDB file |
| `peptide_fasta` | string | No* | Path to peptide FASTA file |
| `receptor_chain` | string | Yes | Chain ID for receptor interface (default: "A") |
| `peptide_chain` | string | Yes | Chain ID for peptide (default: "B") |

*Either `peptide_pdb` or `peptide_fasta` must be provided.

## Artifact Directory Structure

```
data/batch_jobs/{batch_id}/flexpepdock/{item_id}/
  inputs/       # Input PDB/FASTA files
  prepared/     # Pre-processed structures
  runs/         # Silent files from docking runs
  scores/       # Score files (.sc)
  logs/         # stdout/stderr logs
  artifacts/    # Final curated outputs
```

## Status Rules

| Status | Trigger |
|--------|---------|
| PENDING | Initial state |
| RUNNING | Input valid, env available, workdir created |
| BLOCKED | Rosetta env missing or binary not found |
| FAILED | Input files missing, or empty artifact dir on finalize |
| SUCCEEDED | Only when real silent files exist in artifact dir |
| CANCELLED | User-initiated cancellation |

## Scientific Boundaries

1. **No fabricated scores**: The runner never writes hardcoded docking scores.
2. **Empty artifact guard**: `finalize_batch_item()` downgrades `success=True` to `FAILED` if the artifact directory is empty.
3. **Dry run only in P1**: Actual docking execution is deferred to v1.5 P2.
4. **Smoke test only**: The `-help` smoke test verifies binary responsiveness but does not produce docking results.

## Troubleshooting

### "Rosetta env script not found"
- Verify `/home/xh/kxc/tools/rosetta/rosetta_env.sh` exists.
- If Rosetta is installed elsewhere, set `ROSETTA_ENV_SCRIPT` environment variable.

### "FlexPepDock binary not found after sourcing env"
- Verify the binary name matches `FlexPepDocking.default.linuxgccrelease`.
- Check that the Rosetta build includes FlexPepDock (it is included in the standard release).

### "ROSETTA database not found"
- Verify `$ROSETTA_ROOT/database/` exists.
- The database may need to be downloaded separately if using a minimal installation.

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.5 P1 | 2026-05-12 | Initial probe, runner skeleton, batch integration, tests |
