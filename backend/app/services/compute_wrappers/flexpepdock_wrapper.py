"""FlexPepDock wrapper — parses real Rosetta FlexPepDock output (v1.2-lab-production-fast).

Reads JSON result files or scorefiles. Returns interface metrics.
No fabricated docking_score. All outputs marked COMPUTATIONAL_DOCKING_ESTIMATE_ONLY.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def parse_flexpepdock_artifact(artifact_path: str) -> dict[str, Any]:
    """Parse a FlexPepDock result JSON or scorefile.

    Args:
        artifact_path: Path to result JSON or .sc file.

    Returns:
        Dict with status, interface metrics, and scientific boundary.
    """
    path = Path(artifact_path)
    if not path.exists():
        return {
            "status": "BLOCKED",
            "error_code": "ARTIFACT_NOT_FOUND",
            "message": f"FlexPepDock artifact not found: {artifact_path}",
        }

    # Try JSON first
    if path.suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return {
                "status": "FAILED",
                "error_code": "PARSE_ERROR",
                "message": str(exc),
            }

        flex = data.get("flexpepdock", {})
        return {
            "status": "SUCCEEDED",
            "run_type": "PILOT",
            "prediction_status": "COMPUTATIONAL_DOCKING_ESTIMATE_ONLY",
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
            "metrics": {
                "total_score": flex.get("total_score"),
                "interface_score_isc": flex.get("interface_score_isc"),
                "interface_bsa": flex.get("interface_bsa"),
                "interface_hbonds": flex.get("interface_hbonds"),
                "interface_packstat": flex.get("interface_packstat"),
                "interface_unsat": flex.get("interface_unsat"),
                "pep_sc": flex.get("pep_sc"),
                "nstruct": flex.get("nstruct"),
            },
            "scientific_boundary": {
                "computational_only": True,
                "not_docking_score": True,
                "not_experimentally_validated": True,
            },
        }

    # Fallback for .sc scorefile (simple tabular parsing)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) < 2:
            return {"status": "FAILED", "error_code": "EMPTY_FILE", "message": "Scorefile is empty."}
        # Header + first data row
        header = lines[0].split()
        row = lines[1].split()
        score_map = dict(zip(header, row))
        return {
            "status": "SUCCEEDED",
            "run_type": "PILOT",
            "prediction_status": "COMPUTATIONAL_DOCKING_ESTIMATE_ONLY",
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
            "metrics": {
                "total_score": float(score_map.get("total_score", 0)),
                "I_sc": float(score_map.get("I_sc", 0)),
            },
            "scientific_boundary": {
                "computational_only": True,
                "not_docking_score": True,
                "not_experimentally_validated": True,
            },
        }
    except Exception as exc:
        return {
            "status": "FAILED",
            "error_code": "PARSE_ERROR",
            "message": str(exc),
        }
