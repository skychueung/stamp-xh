"""ColabFold wrapper — parses real LocalColabFold artifacts (v1.2-lab-production-fast).

Reads parsed_metrics.json or scores.json and returns structured metrics.
No fabricated values. All outputs marked COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def parse_colabfold_artifact(artifact_path: str) -> dict[str, Any]:
    """Parse a LocalColabFold artifact (parsed_metrics.json or scores.json).

    Args:
        artifact_path: Path to parsed_metrics.json or scores.json.

    Returns:
        Dict with status, metrics, and scientific boundary.
    """
    path = Path(artifact_path)
    if not path.exists():
        return {
            "status": "BLOCKED",
            "error_code": "ARTIFACT_NOT_FOUND",
            "message": f"ColabFold artifact not found: {artifact_path}",
        }

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "FAILED",
            "error_code": "PARSE_ERROR",
            "message": str(exc),
        }

    return {
        "status": "SUCCEEDED",
        "run_type": "PILOT",
        "prediction_status": "COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "metrics": {
            "mean_plddt": data.get("mean_plddt"),
            "ptm": data.get("ptm"),
            "iptm": data.get("iptm"),
            "ranking_confidence": data.get("ranking_confidence"),
            "plddt_per_residue": data.get("plddt_per_residue") or data.get("plddt"),
        },
        "files": {
            "best_model_pdb": data.get("best_model_pdb"),
            "pae_file": data.get("pae_file"),
            "raw_score_json": data.get("raw_score_json"),
        },
        "scientific_boundary": {
            "computational_only": True,
            "not_experimentally_validated": True,
        },
    }
