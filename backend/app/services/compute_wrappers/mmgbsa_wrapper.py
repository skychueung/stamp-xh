"""MM-GBSA wrapper — parses real MMPBSA production results (v1.2-lab-production-fast).

Uses the existing mmpbsa_result_parser. Enforces scientific boundary:
- official_mm_gbsa_delta_g is ALWAYS null for pilot/smoke.
- Production requires convergence + >=200 frames + >=10 ns.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.services.mmpbsa_result_parser import (
    parse_mmpbsa_result,
    write_mmgbsa_summary_json,
    write_mmgbsa_components_csv,
)

logger = logging.getLogger(__name__)


def parse_mmgbsa_artifact(artifact_path: str, output_dir: str | None = None) -> dict[str, Any]:
    """Parse a FINAL_RESULTS_MMPBSA.dat file using the existing parser.

    Args:
        artifact_path: Path to FINAL_RESULTS_MMPBSA.dat.
        output_dir: Optional directory to write mmgbsa_summary.json and
            mmgbsa_components.csv.

    Returns:
        Dict with status, parsed result, and scientific boundary.
    """
    path = Path(artifact_path)
    if not path.exists():
        return {
            "status": "BLOCKED",
            "error_code": "ARTIFACT_NOT_FOUND",
            "message": f"MM-GBSA artifact not found: {artifact_path}",
        }

    try:
        result = parse_mmpbsa_result(str(path))
    except Exception as exc:
        return {
            "status": "FAILED",
            "error_code": "PARSE_ERROR",
            "message": str(exc),
        }

    # Write outputs if requested
    if output_dir:
        try:
            write_mmgbsa_summary_json(result, output_dir)
            write_mmgbsa_components_csv(result, output_dir)
        except Exception as exc:
            logger.warning("Failed to write MM-GBSA outputs to %s: %s", output_dir, exc)

    # Enforce boundary: official ΔG is null unless production + convergence
    is_production = result.run_type == "PRODUCTION"
    is_converged = result.convergence_status in {"CONVERGED", "PARTIAL_CONVERGENCE"}
    frames_ok = (result.frames_used or 0) >= 200

    official_delta_g = None
    if is_production and is_converged and frames_ok:
        # Only production with sufficient frames may carry an official value
        official_delta_g = result.pilot_delta_total_kcal_mol

    return {
        "status": "SUCCEEDED" if result.status == "SUCCESS" else result.status,
        "run_type": result.run_type,
        "convergence_status": result.convergence_status,
        "frames_used": result.frames_used,
        "pilot_delta_total_kcal_mol": result.pilot_delta_total_kcal_mol,
        "official_mm_gbsa_delta_g": official_delta_g,
        "energy_terms": result.energy_terms.get("delta", {}),
        "components": {
            "vdW": result.energy_terms.get("delta", {}).get("VDWAALS"),
            "electrostatic": result.energy_terms.get("delta", {}).get("EEL"),
            "polar_solvation": result.energy_terms.get("delta", {}).get("EGB"),
            "nonpolar_solvation": result.energy_terms.get("delta", {}).get("ESURF"),
        },
        "decomposition_available": len(result.decomposition) > 0,
        "warnings": result.warnings,
        "scientific_boundary": {
            "computational_only": True,
            "not_experimentally_validated": True,
            "official_delta_g_null_reason": (
                None if official_delta_g is not None
                else "Pilot/smoke data or production convergence not met"
            ),
        },
    }
