# Production stabilization acceptance report — 2026-08-13

## Build identity

- Branch: `goal/production-stabilization-20260813`
- Base: `c4f461f180e481d252240739b312a2351691b8d6`
- Validated runtime: Python 3.12.3, Node 18.19.1, npm 9.2.0, SQLite WAL
- Deployment paths and credentials are intentionally represented by configuration variables.

## Verified commands

| Gate | Result |
|---|---|
| `npm run lint -- --max-warnings=0` | PASS, 0 warnings |
| `npm test` | PASS, 21 tests |
| `npm run build` | PASS |
| Focused backend stabilization suite | PASS, 55 tests |
| Alembic empty DB upgrade → downgrade → upgrade | PASS (`9b2e4f7a1c30`) |
| Golden benchmark, two targets × five repetitions | PASS, 10/10, failure rate 0 |
| PepMLM CUDA E2E, one generated candidate | PASS |
| Git remote branch verification | PASS |

## Benchmark

- Runs: 10
- Successful: 10
- Failure rate: 0.0
- Mean runtime: 0.6263 seconds
- Candidates/run: 5
- Duplicate rate: 0.0
- Diversity: 1.0
- Every run wrote structured logs and an independent run directory.

## PepMLM evidence

A CUDA inference run returned `SUCCEEDED` and wrote FASTA, CSV, JSON, combined
stdout/stderr, and pre/post manifests. The post-manifest records model id,
model version, checkpoint SHA-256, normalized input SHA-256, seed, parameters,
and validation boundary. The checkpoint digest observed was
`e80587d2ac4a3fb84f2be2cd4f4d02d5f2127cafc75144108ba349d4796c3668`.

## Security and recovery coverage

Authentication, cross-user hiding, project ownership, CSRF on writes, rate
limits, cancellation, retry idempotency, stale worker lease recovery, durable
queue claim, path traversal, stable SHA-256, and ten repeated runs are covered
by automated tests. Production startup validates secret strength and explicit
credentialed CORS origins.

## Known repository-wide legacy gates

The historical full backend collection has pre-existing collection debt outside
this stabilization scope: a stale FlexPepDock batch test contract, an optional
NumPy dependency absent from the server web environment, and a test file stored
inside a legacy `.tmp` source directory that collides with a normal test module.
The focused production pipeline suite is green; CI makes the repository-wide
items visible for subsequent cleanup.

Ruff over the full historical backend currently reports legacy lint debt; all
files added or changed by this stabilization pass Ruff. The frontend lint,
tests, and build are green.

## Rollback

1. Stop API and worker processes.
2. Back up the database and run `alembic downgrade 1e3bcd1d779f`.
3. Redeploy base commit `c4f461f180e481d252240739b312a2351691b8d6`.
4. Restart API and worker, then run health and ownership checks.

## Final repository state

The publishing worktree is clean and the independent branch is pushed. Model
weights, databases, logs, runtime artifacts, credentials, and bytecode are not
part of the commit.
