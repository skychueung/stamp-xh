# Production stabilization acceptance report — 2026-08-13

## Build identity

- Branch: `goal/production-stabilization-20260813`
- Repository: `https://github.com/skychueung/stamp-xh.git`
- Server worktree: `/home/xh/kxc/stamp-v3/.goal-worktrees/production-stabilization`
- Base commit: `c4f461f180e481d252240739b312a2351691b8d6`
- Runtime: Python 3.13.9, Node 18.19.1, npm 9.2.0, SQLite WAL
- The published Git commit is recorded in the delivery summary after push.

## Final automated gates

| Gate | Result |
|---|---|
| Full backend Ruff (`ruff check app tests`) | PASS, zero findings |
| Full backend pytest (`pytest -q`) | PASS, 1670 passed, 3 skipped |
| Frontend ESLint (`npm run lint -- --max-warnings=0`) | PASS, zero warnings |
| Frontend Vitest (`npm test`) | PASS, 21 passed |
| Frontend production build (`npm run build`) | PASS |
| Empty DB Alembic upgrade → downgrade → upgrade | PASS, head `9b2e4f7a1c30` |
| Golden benchmark, two targets × five repetitions | PASS, 10/10 |
| PepMLM CUDA E2E | PASS, one generated candidate with provenance |

The complete test collection originally exposed 12 collection errors and 99
failures. The final collection runs without errors and has no failed tests.
Skipped tests are the repository's explicit optional integration cases.

## Repeatability and observability benchmark

- Runs: 10
- Successful terminal runs: 10
- Unique run IDs/directories: 10
- Failure rate: 0.0
- Mean runtime: 0.6161 seconds
- Minimum structured log records per run: 18
- Candidates per run: 5
- Duplicate rate: 0.0
- Diversity: 1.0
- Machine-readable outputs: `pipeline_benchmark.json` and
  `pipeline_benchmark.csv`

Each run writes `request.json`, `manifest.json`, `logs.jsonl`, `steps/`, and
`artifacts/`. Input identity uses SHA-256. Tests cover ten consecutive runs,
retry idempotency, unique run roots, persisted step states, non-empty logs, and
artifact enumeration.

## Durable worker and recovery

The API persists and enqueues work; the independent database-backed worker
claims jobs with a lease, renews heartbeat state, applies bounded retry/backoff,
recovers expired leases, respects cancellation at step boundaries, and skips
verified completed steps. Automated tests cover duplicate delivery, one-time
claiming, stale lease recovery, retry, cancellation, and task recovery.

## Five-model registry and model truthfulness

`GET /api/v1/models/production/status` returns exactly:

1. PepMLM
2. PepPrCLIP
3. EvoBind2
4. PepHAR
5. PepFlow

Every adapter implements probe, input validation, resource estimation, run
dispatch and normalized result methods. The probe reports filesystem-derived
states and missing components. A selected pipeline model is probed before
dispatch; unknown or non-ready selections end in a truthful blocked state.
PepMLM has a verified CUDA E2E path. Its post-manifest records model ID/version,
checkpoint SHA-256, input SHA-256, seed, parameters and environment. The
observed checkpoint digest was
`e80587d2ac4a3fb84f2be2cd4f4d02d5f2127cafc75144108ba349d4796c3668`.

## Security evidence

Automated coverage includes login requirements, cross-user object hiding,
project ownership, CSRF on writes, rate limiting, cancellation and retry
authorization, malicious filenames, and artifact path traversal. Production
startup validates secret strength and explicit credentialed CORS origins.
SQLite enables foreign keys, WAL and a 30-second busy timeout. Runtime weights,
credentials, databases, logs, PIDs and generated artifacts remain outside Git.

## Repository governance

- CI runs frontend lint/test/build, backend Ruff/full pytest, Alembic round-trip,
  and gitleaks.
- Historical `.orig`, `.tmp`, snapshot and backup source noise was removed.
- Static data required by application startup is versioned under
  `backend/app/data/` and its default path is repository-relative.
- FlexPepDock environment configuration resolves at call time.
- Runner commands use the active Python interpreter portably.
- Deployment, architecture, recovery and operations guidance is in
  `docs/PRODUCTION_STABILIZATION.md` and `.env.example`.

## Runtime notes

The server build succeeds with Node 18.19.1 and emits Vite's recommendation for
Node 20.19+ or 22.12+. CI uses Node 20. The main frontend bundle remains large;
route-level chunk splitting is a future performance enhancement and does not
affect the acceptance result.

## Rollback

1. Stop the API and worker processes.
2. Back up the database and run `alembic downgrade 1e3bcd1d779f`.
3. Deploy base commit `c4f461f180e481d252240739b312a2351691b8d6`.
4. Restart API and worker, then run health, ownership and queue checks.

## Final repository condition

The independent branch is committed and pushed only after all gates above pass.
The publishing worktree is verified clean after push, and the remote branch SHA
is compared with local HEAD.
