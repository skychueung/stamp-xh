# STAMP P33L — Input, Output and Delivery Contract

**Task ID:** P33L  
**Phase:** Phase 2  
**Date:** 2026-06-29  

---

## 1. Purpose

Define the exact input, output, manifest, and download contract for the six-model one-click real run. This contract governs Phase 4 execution and Phase 5 delivery verification.

---

## 2. Input Contract

### 2.1 Authorized Input Sources

1. **User-provided scientific input** submitted through the `/target-design` form.
2. **Acceptance fixture** — a model-specific minimal fixture used only when no scientific input is provided. It must be explicitly tagged `acceptance_fixture` in the manifest and must not be presented as a user scientific result.

### 2.2 Per-Model Input Schema

| Model | Required Input | Optional Input | Schema Validation |
|---|---|---|---|
| PepMLM | `target_sequence` (FASTA or raw), `peptide_length`, `num_candidates` | `seed`, `top_k`, `device` | Regex: valid amino-acid sequence; length positive integer; candidates 1–100 |
| EvoBind2 | `receptor_fasta_path` or `receptor_sequence`, `peptide_length` | `receptor_msa_path`, `peptide_sequence`, `max_recycles`, `num_iterations`, `device` | FASTA valid; length positive integer; paths under allow-list |
| DiffPepBuilder | `target_pdb_path`, `num_candidates` | `seed`, `device` | PDB file exists and is under allow-list; candidates 1–100 |
| PepFlow | `receptor_pdb_path`, `num_samples`, `num_steps` | `seed`, `device`, `checkpoint` | PDB allow-list; samples/steps positive integers |
| PepHAR | `input_pdb_path`, `model_variant` (`density` or `prediction`) | `device`, `seed` | PDB allow-list; variant enum |
| PPFlow | `target_pdb_path`, `batch_size`, `tag` | `seed`, `device`, `checkpoint`, `config` | PDB allow-list; batch_size positive integer |

### 2.3 Input Provenance

Every run must record:

- SHA256 of the input file(s).
- Source (`user_upload` or `acceptance_fixture`).
- Schema validation result.
- User ID / session ID (for audit only).
- Timestamp.

### 2.4 Input Restrictions

- No path traversal (`..`, symlinks, absolute paths outside allow-list).
- No executable uploads.
- Input files must be copied into `<run_dir>/input/` before execution; the runner must not read from arbitrary user paths.
- Scientific parameters may not be altered to mask runner/env/source errors.

---

## 3. Output Contract

### 3.1 Run Directory Layout

```
/mnt/sdb/kxc/stamp_models/artifacts/p33l/<job_id>/
├── input/
│   └── <input files with SHA>
├── output/
│   └── <model-specific output files>
├── logs/
│   ├── run_stdout_stderr.log
│   └── resource_summary.log
├── manifest/
│   ├── run_manifest.json
│   └── sha256_manifest.txt
└── gate.json
```

### 3.2 Required Output Files

| File | Content | Success | Failure |
|---|---|---|---|
| `run_manifest.json` | Job metadata, input provenance, command, exit code, timestamps, resource summary, disclaimer | Required | Required |
| `sha256_manifest.txt` | SHA256 of every file in run directory | Required | Required (of files that exist) |
| `logs/run_stdout_stderr.log` | Sanitized stdout/stderr | Required | Required |
| `output/` | Model-specific results | Required | May be empty or contain partial output |

### 3.3 `run_manifest.json` Schema

```json
{
  "task_id": "P33L",
  "job_id": "<uuid>",
  "model_id": "<model>",
  "model_display_name": "...",
  "attempt_number": 1,
  "manifest_sha": "<sha>",
  "input": {
    "source": "user_upload|acceptance_fixture",
    "files": [{"path": "input/...", "sha256": "..."}],
    "schema_valid": true
  },
  "command": "<full command>",
  "environment": {
    "python": "<path>",
    "conda_env": "<name>",
    "cuda_visible_devices": "<device>"
  },
  "provenance": {
    "source_commit": "<git hash>",
    "checkpoint_sha256": "...",
    "adapter_sha256": "...",
    "runner_sha256": "..."
  },
  "execution": {
    "started_at": "ISO8601",
    "finished_at": "ISO8601",
    "exit_code": 0,
    "status": "SUCCEEDED|FAILED|TIMEOUT|CANCELLED",
    "timeout_seconds": 3600,
    "disk_quota_bytes": 1073741824
  },
  "resources": {
    "gpu": "NVIDIA GeForce RTX 4090",
    "peak_memory_mib": 0,
    "device_id": 0
  },
  "disclaimer": "NOT_EXPERIMENTALLY_VALIDATED",
  "artifact_download_base": "/api/v1/p33l/jobs/<job_id>/download/"
}
```

### 3.4 Model-Specific Output

| Model | Expected Output Files |
|---|---|
| PepMLM | `candidate_sequences.csv`, `candidate_sequences.json` |
| EvoBind2 | `unrelaxed_true.pdb`, `metrics.csv` |
| DiffPepBuilder | `generated_sequences.csv`, `generated_structures/` (if available) |
| PepFlow | `generated_samples.csv`, `samples.pdb` (if supported) |
| PepHAR | `affinity_scores.csv`, `predicted_structures.pdb` |
| PPFlow | `generated_sequences.csv`, `metrics.json` |

---

## 4. Delivery Contract

### 4.1 Download API

- `GET /api/v1/p33l/jobs/{job_id}/download/{relative_path}`
- `relative_path` must resolve inside `<run_dir>` and not contain `..` or symlinks.
- Response includes `Content-SHA256` header matching `sha256_manifest.txt`.
- Failed jobs allow download of `logs/` and `run_manifest.json` only.

### 4.2 Download Package

- Success jobs may offer a zip bundle containing `manifest/`, `input/`, `output/`, and `logs/`.
- Zip SHA256 must match the server-side manifest.
- Package must include the `NOT_EXPERIMENTALLY_VALIDATED` disclaimer.

### 4.3 UI Display

- Success: show summary, disclaimer, and download links.
- Failure: show error, logs download, and evidence reference.
- No fake candidates, fake metrics, or empty-shell success packages.

---

## 5. Acceptance Fixture Policy

- Acceptance fixtures are used only for engineering verification.
- They must be minimal, legal, and already present in the project.
- Manifest must tag them as `acceptance_fixture`.
- They may not be presented to the user as scientific results.

---

## 6. Compliance Statements

- All outputs are `NOT_EXPERIMENTALLY_VALIDATED`.
- No claim of clinical validity, production validation, or experimental reproducibility.
- Real-run artifacts are engineering evidence only.
