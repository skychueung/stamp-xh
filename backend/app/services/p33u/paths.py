"""P33U path / run-id / gate / artifact contracts.

Independent of P33L. All P33U gates live under run_gates/p33u_lane_d/.
No gate.json is created here — this module only computes paths. Gate files
are created at real-run time (Lane D), which this round does NOT enter.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from .config import (
    ARTIFACT_ROOT,
    GATE_ROOT,
    LINEAGE,
    RUN_ID_PREFIX,
    STATE_PATH,
)


def new_run_id(model_id: str) -> str:
    """Return a P33U run id, e.g. p33u_pephar_<8hex16>.

    Deliberately distinct from P33L's p33l_<model>_<uuid> scheme so that
    P33U jobs can never be confused with frozen P33L history.
    """
    return f"{RUN_ID_PREFIX}_{model_id}_{uuid.uuid4().hex[:16]}"


def gate_dir(model_id: str) -> str:
    """Directory holding gate.json files for one model."""
    return os.path.join(GATE_ROOT, model_id)


def gate_path(model_id: str, run_id: str) -> str:
    """Path to a single per-run gate.json (created at Lane D time)."""
    return os.path.join(gate_dir(model_id), f"{run_id}.gate.json")


def artifact_dir(model_id: str, run_id: str) -> str:
    """Per-run artifact root under the P33U artifact tree."""
    return os.path.join(ARTIFACT_ROOT, model_id, run_id)


def run_input_dir(model_id: str, run_id: str) -> str:
    return os.path.join(artifact_dir(model_id, run_id), "input")


def run_output_dir(model_id: str, run_id: str) -> str:
    return os.path.join(artifact_dir(model_id, run_id), "output")


def state_path() -> str:
    return STATE_PATH


def lineage() -> str:
    return LINEAGE


def contract_summary(model_id: str, run_id: str) -> dict[str, Any]:
    """Return the full path contract for one (model, run_id) — for manifests."""
    return {
        "lineage": LINEAGE,
        "model_id": model_id,
        "run_id": run_id,
        "state_path": STATE_PATH,
        "gate_path": gate_path(model_id, run_id),
        "artifact_dir": artifact_dir(model_id, run_id),
        "input_dir": run_input_dir(model_id, run_id),
        "output_dir": run_output_dir(model_id, run_id),
    }
