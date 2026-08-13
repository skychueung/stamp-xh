"""P33U-D23: formal registry dispatch for dev-only minimal real-run smoke.

Replaces the D22 router-helper dispatch (``_run_diffpepbuilder_smoke`` /
``_run_pephar_smoke``) with a registry-level dispatch contract. The Run Console
router now calls ``dispatch_dev_smoke(model_id, job, job_dir, seed)`` instead of
bare helpers, so the dev-smoke path is reached through the formal adapter
contract (``adapter.submit_dev_smoke``) rather than a router-side bypass.

Contract bridge (additive — nothing existing is weakened):
  - The default registry ``adapter.submit()`` stays BLOCKED (read-only P31B /
    P31C / P30D). P33U-D23 does NOT open it.
  - A NEW additive method ``submit_dev_smoke(job, job_dir, seed)`` is defined on
    ``BaseModelAdapter`` (default: not supported) and overridden on
    ``DiffPepBuilderAdapter`` + ``PepHARAdapter`` to delegate to
    ``SmokeRunnerAdapter`` with full provenance.
  - This module is the single entry point the router calls; it looks up the
    registry adapter by ``model_id`` and invokes ``submit_dev_smoke``. The
    PepMLM real-run path (``PepMLMAdapter.submit`` with the gate file) is
    untouched and stays on its own branch.

The SmokeRunnerAdapter still invokes the D21 smoke wrapper scripts via
subprocess (they wrap the real model runners — DiffPepBuilder run_inference.py /
PepHAR AnchorBasedSampler — on GPU1), but now records full provenance
(script_sha256 / config_sha256 / checkpoint_sha256 / env / seed) and is reached
via the adapter contract. GPU0 prod untouched. PPFlow never invoked. EvoBind2
env never created.

Forbidden by the D23 goal: this dispatch never writes dev-smoke as Top4 /
primary candidates, never claims experimental validation, never invokes PPFlow,
never creates the evobind conda env, never uses P33U_FINAL_GOAL_COMPLETE.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

DISPATCH_CONTRACT = "p33u_d23_registry_dev_smoke_dispatch"
DISPATCH_MODULE = "app.services.p33u.dev_smoke_dispatch"
DISPATCH_ENTRYPOINT = "adapter.submit_dev_smoke"

# Models allowed for dev-smoke dispatch (D21/D22-proven minimal real-run smoke
# on GPU1). PepMLM is NOT here — it has its own real-run submit() path. PepFlow
# is NOT here — it is artifact-only parser smoke handled on its own router
# branch. EvoBind2 is NOT here — env missing (license allowed). PPFlow is NEVER
# here — blocked_license.
DEV_SMOKE_ALLOWED: tuple[str, ...] = ("diffpepbuilder", "pephar")


def dispatch_dev_smoke(
    model_id: str,
    job: dict[str, Any],
    job_dir: Path,
    seed: int | None = None,
) -> None:
    """Formal registry dispatch for dev-only minimal real-run smoke.

    Looks up the registry adapter for ``model_id`` and invokes its additive
    ``submit_dev_smoke`` contract method, which delegates to SmokeRunnerAdapter.
    Records dispatch metadata on the job dict before the adapter runs, so the
    resulting job.json / gate JSON is self-describing: dispatch_contract,
    dispatch_module, dispatch_entrypoint, adapter_registry_id.

    If the model is not in ``DEV_SMOKE_ALLOWED`` the job is marked blocked with
    a precise reason (no exception raised — the job dict records the block so
    the Run Console surfaces it like any other blocked run).
    """
    # Record dispatch metadata on the job up front (always, even on block).
    job["dispatch_contract"] = DISPATCH_CONTRACT
    job["dispatch_module"] = DISPATCH_MODULE
    job["dispatch_entrypoint"] = DISPATCH_ENTRYPOINT

    if model_id not in DEV_SMOKE_ALLOWED:
        job["status"] = "blocked"
        job["failure_reason"] = (
            f"dev_smoke_dispatch: model_id '{model_id}' not in DEV_SMOKE_ALLOWED "
            f"(={list(DEV_SMOKE_ALLOWED)}); submit_dev_smoke not supported. "
            f"PepMLM uses its own real-run submit() path; PepFlow is parser smoke; "
            f"EvoBind2 env missing; PPFlow blocked_license."
        )
        return

    # Lazy import to avoid circulars at module load time.
    from app.services.model_adapters import DiffPepBuilderAdapter, PepHARAdapter

    _ADAPTERS = {
        "diffpepbuilder": DiffPepBuilderAdapter,
        "pephar": PepHARAdapter,
    }
    adapter_cls = _ADAPTERS[model_id]
    adapter = adapter_cls(model_id)
    job["adapter_registry_id"] = adapter.adapter_id

    # Invoke the formal additive adapter contract method. The adapter delegates
    # to SmokeRunnerAdapter, which runs the smoke script on GPU1 and records
    # full provenance (script / config / checkpoint / env / seed) on the job.
    adapter.submit_dev_smoke(job, job_dir, seed=seed)
