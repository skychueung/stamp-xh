# STAMP v1.2 Lab Production Runbook

## Daily Operations

### Morning Check

```bash
bash scripts/healthcheck.sh
```

Expected: All 4 checks return `[OK]`.

### Job Queue Monitoring

```bash
curl http://localhost:8000/api/health/queue
```

Watch for:
- `blocked` > 0 → check server `192.168.31.218` SSH connectivity
- `failed` > 0 → review retry policy; auto-retry kicks in if `retry_count < max_retries`

### LIMS/ELN Sync

1. Navigate to **LIMS / ELN** page
2. Verify integration status:
   - `CONFIG_REQUIRED` → fill base_url and token_secret_ref
   - `REAL_API_READY` → ready to test
   - `TEST_FAILED` → check error message, fix credentials, click **Test** again
   - `SYNC_SUCCEEDED` → last sync succeeded (real HTTP 2xx)
3. Never mark `SYNC_SUCCEEDED` manually unless you have verified real API success.

### Production MD Launch

1. Navigate to **Production MD** page
2. Fill Project ID, Candidate ID, Topology Path, Coordinates Path
3. Select duration (1/5/10/50 ns)
4. Click **Submit MD Job**
5. If server unreachable, job is `BLOCKED` — retry when server recovers
6. After run completes, results (RMSD, RMSF, etc.) are parsed from real artifacts only

## Troubleshooting

| Symptom | Cause | Action |
|---------|-------|--------|
| Jobs stuck in `BLOCKED` | Server unreachable | `ssh xh@192.168.31.218 echo ok` |
| `TEST_FAILED` on LIMS | Bad URL or token | Verify base_url and env var/token |
| 422 on MD submit | Invalid duration | Use only 1, 5, 10, 50 ns |
| pytest failures | Schema drift | Re-init DB or run Alembic migration |

## Safety Rules

- **No fabricated metrics** — MIC, MBC, ΔG, RMSD only from real data
- **No fake LIMS sync** — `SYNC_SUCCEEDED` requires real HTTP success
- **Backup before deploy** — `deploy_server.sh` auto-backs up DB
