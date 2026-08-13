# STAMP five-model runtime baseline — 2026-08-14

## Scope and evidence boundary

This baseline was collected before deployment of the unified runtime patch. It
distinguishes source availability, environment availability, checkpoint
availability, historical execution artifacts and the live production path.
Historical artifacts are not counted as executions for the new acceptance run.

## Repository baseline

- Local worktree: `D:/ai/_temp/stamp-xh-push`
- Local branch before work: `goal/production-stabilization-20260813`
- Task branch: `fix/five-model-unified-runtime`
- Baseline HEAD: `91aef5c6dbac902043e8331b365dad01f83e98f6`
- Target remote: `git@github.com:skychueung/stamp-xh.git`
- Server worktree: `/home/xh/kxc/stamp-v3/.goal-worktrees/production-stabilization`
- Server baseline: clean, same HEAD, branch ahead of `stamp-xh/main` by five commits
- Server primary `/home/xh/kxc/stamp-v3` contains extensive unrelated changes
  and is excluded from direct edits.

## Connectivity and service baseline

- Tailscale node: `stamp218`, `100.75.69.36`
- LAN address `192.168.31.218` was not routed from the client during audit.
- Requested port `12973`: no listener on the server.
- Development backend: port `12824`, PID `3243818`, cwd
  `/home/xh/kxc/stamp-v3/backend`, health HTTP 200.
- Formal backend: port `8001`, PID `3922673`, health HTTP 200.
- Frontend: Docker nginx on port `8080`, HTTP 200.
- No dedicated five-model worker process was running.
- GPU inventory: two NVIDIA GeForce RTX 4090 devices, 24564 MiB each.

## Model asset matrix

| Model | Source/environment | Checkpoint | Historical evidence | Baseline live unified execution |
|---|---|---|---|---|
| PepMLM | inference script and Python environment present | `model.safetensors`, 2,609,667,120 bytes, SHA256 `e80587d2ac4a3fb84f2be2cd4f4d02d5f2127cafc75144108ba349d4796c3668` | generated candidate artifacts exist | only model wired by the previous pipeline orchestrator |
| PepPrCLIP | source/notebooks and ranking script present | expected MiniCLIP checkpoint absent; uploaded 4.83 GB ZIP contains experimental raw data and no checkpoint-like entry | no real generation artifact found | registered only |
| EvoBind2 | source, environment, AF2 parameters and UniRef30 present | AF2 `params_model_1_ptm.npz` present | 12-aa real-design PDB artifacts exist | independent worker exists; previous unified pipeline excluded it |
| PepHAR | source and Python 3.10 environment present | density SHA256 `06b9a270...32d15`; prediction SHA256 `94eb9933...23f6` | checkpoint-load/forward and generation artifacts exist | previous unified pipeline excluded it |
| PepFlow | source and Python 3.10 environment present | `model2.pt`, SHA256 `80ef4d7a07eddd877067859b5df95c50833cb72c40ef10d6ff5aa1263f0dba21` | real-design output artifacts exist | previous unified pipeline excluded it |

## Confirmed root causes

1. `production_model_registry.py` exposed five names but its generic `run()`
   returned a static acceptance object rather than creating an executable job.
2. `pipeline_orchestrator.py` explicitly classified every selected model except
   PepMLM as an unsupported runtime.
3. Model-specific code used different queues, gates, artifact roots, log formats
   and process lifecycles.
4. No persistent common job-log endpoint existed for all five models.
5. The legacy P33U executor intentionally rejected a second attempt, which is
   incompatible with the required repeatable production job semantics.
6. PepPrCLIP currently lacks the official gated MiniCLIP checkpoint. The
   uploaded `PepPrCLIP.zip` is an experimental-data bundle, not model weights.
7. The requested port 12973 has no server listener, so final browser acceptance
   requires a deployment binding or reverse proxy for that port.

## Patch status after baseline

The task branch now contains the first implementation slice:

- a durable five-model job service;
- common CREATED/QUEUED/PREFLIGHT/RUNNING/POSTPROCESSING/terminal states;
- isolated artifacts, temporary files and JSONL logs;
- common submit/status/cancel/log/artifact/run endpoints;
- subprocess execution through JSON argv arrays with `shell=False`;
- credential redaction;
- restart recovery;
- lock and busy-marker cleanup in `finally`;
- production adapters with submit/status/cancel/artifact methods;
- removal of the PepMLM-only branch in the pipeline orchestrator.

Initial focused verification: `26 passed`; the dedicated runtime suite performs
15 isolated executions (five model IDs × seeds 41/42/43) through fixture runner
processes. These fixture executions validate orchestration mechanics only and
are not counted as real-model acceptance evidence.

## Current verdict

`PARTIAL` — runtime infrastructure implementation is in progress. Real-model
acceptance remains pending deployment, runner-command binding, PepPrCLIP
checkpoint acquisition, 15 real executions, combination/concurrency/restart
tests, frontend browser validation and GitHub delivery.
