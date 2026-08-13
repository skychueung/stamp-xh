# STAMP v1.2 Architecture — LIMS/ELN & Production MD

## Overview

v1.2 introduces two production-grade subsystems:
1. **LIMS/ELN Integration** — external lab system connectors
2. **Production MD** — GROMACS molecular dynamics task queue

Both integrate with the v1.2 Job Queue (P1) and Server Scheduler (P2).

---

## LIMS/ELN Integration

### Data Model

```
IntegrationConfig
├── id (UUID)
├── integration_type: "LIMS" | "ELN"
├── base_url: string | null
├── auth_mode: "token" | "oauth2" | "basic"
├── token_secret_ref: string | null   (env var name, never stored raw)
├── field_mapping_json: dict
├── status: CONFIG_REQUIRED | REAL_API_READY | TEST_FAILED | SYNC_SUCCEEDED | SYNC_FAILED
├── last_sync_at: datetime | null
├── last_error: string | null
├── enabled: bool
└── test_mode: bool
```

### State Machine

```
CONFIG_REQUIRED ──[base_url + token set]──> REAL_API_READY
     │                                        │
     │                                [test-sync success]
     │                                        ↓
     │                                   SYNC_SUCCEEDED
     │                                        │
     └────────────────────────────────────────┘
              [test-sync failure]
                   TEST_FAILED
```

### Security

- Tokens are never stored in the database.
- `token_secret_ref` points to an environment variable or vault path.
- `test_mode` isolates integration from production data.

---

## Production MD

### Task Flow

```
User submits MD job
        │
        ▼
ProductionMDCreateRequest validated (duration_ns ∈ {1,5,10,50})
        │
        ▼
Job record created (status = PENDING)
        │
        ▼
User or auto-trigger submit
        │
        ▼
ServerComputeRunner.dispatch()
        │
        ├── Server reachable ──> SSH command queued (status = RUNNING)
        └── Server unreachable ──> status = BLOCKED, retryable error logged
```

### GROMACS MDP Parameters

| Duration | nsteps | dt |
|----------|--------|-----|
| 1 ns | 500,000 | 0.002 ps |
| 5 ns | 2,500,000 | 0.002 ps |
| 10 ns | 5,000,000 | 0.002 ps |
| 50 ns | 25,000,000 | 0.002 ps |

Standard settings: NVT → NPT, V-rescale thermostat, Parrinello-Rahman barostat, PME, LINCS constraints.

### Result Parsing (Future)

After job finishes:
- `md.xtc` → RMSD, RMSF via `gmx rms`, `gmx rmsf`
- `md.edr` → energy terms via `gmx energy`
- No synthetic values; all metrics derived from real trajectory files.

---

## Integration with Job Queue

Both LIMS sync and Production MD jobs use the unified `Job` model:

- `candidate_id` links job to a specific peptide candidate
- `batch_id` groups jobs into multi-candidate pipelines
- `retry_count` / `max_retries` handles transient failures
- `server_host` routes heavy compute to `192.168.31.218`
- `priority` controls queue ordering
- `AuditLogEntry` records all status transitions immutably
