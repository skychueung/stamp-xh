"""STAMP Platform — Structure Prediction Result Import (v0.10-P6c).

Loads real LocalColabFold (or compatible) prediction metrics from disk,
normalizes them into a standard job.output_json, and enforces the
scientific-integrity boundary: no fabricated wet-lab metrics.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
REQUIRED_PREDICTION_STATUS = "COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY"
FORBIDDEN_METRIC_KEYS = ("pDockQ", "delta_G", "docking_score")

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def load_localcolabfold_metrics(result_dir: str | Path) -> dict[str, Any]:
    """Read parsed_metrics.json from a LocalColabFold result directory.

    Validates integrity constraints before returning raw data.

    Raises:
        FileNotFoundError: if parsed_metrics.json does not exist.
        ValueError: if integrity checks fail.
    """
    result_dir = Path(result_dir)
    metrics_path = result_dir / "parsed_metrics.json"

    if not metrics_path.is_file():
        raise FileNotFoundError(f"parsed_metrics.json not found in {result_dir}")

    with open(metrics_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    # --- integrity checks ---
    if raw.get("metrics_are_real") is not True:
        raise ValueError("metrics_are_real must be true")

    if raw.get("validation_status") != REQUIRED_VALIDATION_STATUS:
        raise ValueError(
            f"validation_status must be {REQUIRED_VALIDATION_STATUS!r}, "
            f"got {raw.get('validation_status')!r}"
        )

    if raw.get("prediction_status") != REQUIRED_PREDICTION_STATUS:
        raise ValueError(
            f"prediction_status must be {REQUIRED_PREDICTION_STATUS!r}, "
            f"got {raw.get('prediction_status')!r}"
        )

    mean_plddt = raw.get("mean_plddt")
    if mean_plddt is None or not isinstance(mean_plddt, (int, float)):
        raise ValueError(f"mean_plddt must be a real numeric value, got {mean_plddt!r}")

    return raw


# ---------------------------------------------------------------------------
# Normalize
# ---------------------------------------------------------------------------


def normalize_localcolabfold_metrics(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert raw LocalColabFold parsed_metrics into standard job.output_json.

    Preserves real metrics, explicitly nulls forbidden metrics, and stamps
    the scientific-integrity boundary.
    """
    output: dict[str, Any] = {
        "job_type": "structure_prediction",
        "mode": "LOCALCOLABFOLD_IMPORTED_RESULT",
        "model_source": raw.get("model_source", "LocalColabFold"),
        "validation_status": REQUIRED_VALIDATION_STATUS,
        "prediction_status": REQUIRED_PREDICTION_STATUS,
        "metrics_are_real": True,
        "mean_plddt": raw.get("mean_plddt"),
        "ptm": raw.get("ptm"),
        "iptm": raw.get("iptm"),
        "structure_file": raw.get("best_model_pdb") or raw.get("structure_file"),
        "pae_file": raw.get("pae_file"),
        "raw_score_json": raw.get("raw_score_json"),
        "plddt_per_residue": raw.get("plddt_per_residue"),
        "coverage_plot": raw.get("coverage_plot"),
        "source_result_dir": raw.get("output_directory"),
        "forbidden_metrics": {
            "pDockQ": None,
            "delta_G": None,
            "docking_score": None,
        },
    }

    return output


# ---------------------------------------------------------------------------
# Validate no fabrication
# ---------------------------------------------------------------------------


def validate_no_fabricated_structure_metrics(output_json: dict[str, Any]) -> None:
    """Enforce the scientific-integrity boundary on structure metrics.

    Rules:
      - pLDDT / pTM may be real numbers (computed by ColabFold).
      - ipTM must be null for monomer runs (absent is also acceptable).
      - pDockQ / delta_G / docking_score must be null or absent.
      - No experimentally_validated or wet_lab_confirmed flags.

    Raises:
        ValueError: if any forbidden metric is present and non-null,
                    or if wet-lab validation is claimed.
    """
    # 1. Forbidden metrics must be null or absent
    for key in FORBIDDEN_METRIC_KEYS:
        value = output_json.get(key)
        if value is not None:
            raise ValueError(
                f"Forbidden metric '{key}' must be null or absent, got {value!r}"
            )

    # Check inside nested forbidden_metrics as well
    nested = output_json.get("forbidden_metrics", {})
    for key in FORBIDDEN_METRIC_KEYS:
        value = nested.get(key)
        if value is not None:
            raise ValueError(
                f"Forbidden metric '{key}' in forbidden_metrics must be null, got {value!r}"
            )

    # 2. No wet-lab validation claims
    vs = output_json.get("validation_status", "")
    if vs != REQUIRED_VALIDATION_STATUS and "experimentally_validated" in str(vs).lower():
        raise ValueError(
            f"validation_status claims experimental validation: {vs!r}"
        )

    ps = output_json.get("prediction_status", "")
    if "wet_lab" in str(ps).lower() or "experimentally_confirmed" in str(ps).lower():
        raise ValueError(
            f"prediction_status claims wet-lab confirmation: {ps!r}"
        )

    logger.info("Structure metrics validation passed: no fabricated wet-lab metrics detected.")
