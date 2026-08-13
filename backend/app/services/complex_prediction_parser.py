"""STAMP Platform — Complex Prediction Output Parser (v0.10-P6h).

Parses the output directory of a complex structure prediction run
and reports whether the outputs are sufficient for downstream
interface parsing and pDockQ computation.

Does NOT compute pDockQ, delta_G, or docking_score.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def parse_complex_output(output_dir: str | Path) -> dict[str, Any]:
    """Parse complex prediction output directory.

    Returns a structured report dict describing what files are present
    and whether the outputs are ready for interface parsing.

    Args:
        output_dir: Path to the ColabFold/AlphaFold output directory.

    Returns:
        Audit report dict.
    """
    output_dir = Path(output_dir)
    report: dict[str, Any] = {
        "complex_prediction_ran": False,
        "has_complex_structure_file": False,
        "has_chain_A": False,
        "has_chain_B": False,
        "has_pae": False,
        "has_ranking_json": False,
        "has_plddt_json": False,
        "structure_file_path": None,
        "pae_file_path": None,
        "ranking_json_path": None,
        "plddt_json_path": None,
        "ready_for_interface_parser": False,
        "ready_for_pdockq": False,
        "reason_pdockq_not_computed": (
            "P6h only validates complex output availability; "
            "pDockQ calculation deferred to P6j."
        ),
        "forbidden_metrics": {
            "pDockQ": None,
            "delta_G": None,
            "docking_score": None,
        },
        "prediction_status": "COMPUTATIONAL_COMPLEX_STRUCTURE_PREDICTION_ONLY",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "metrics_are_real": False,
        "files_found": [],
    }

    if not output_dir.exists():
        report["reason"] = "Output directory does not exist"
        return report

    files = list(output_dir.iterdir())
    report["files_found"] = [f.name for f in files]

    # Check for structure files (PDB or CIF)
    pdb_files = [f for f in files if f.suffix == ".pdb"]
    cif_files = [f for f in files if f.suffix == ".cif"]
    struct_files = pdb_files + cif_files

    if struct_files:
        report["has_complex_structure_file"] = True
        report["structure_file_path"] = str(struct_files[0])

    # Check for PAE files (json or npy)
    pae_files = [f for f in files if "pae" in f.name.lower()]
    if pae_files:
        report["has_pae"] = True
        report["pae_file_path"] = str(pae_files[0])

    # Check for ranking JSON
    ranking_files = [f for f in files if "ranking" in f.name.lower() and f.suffix == ".json"]
    if ranking_files:
        report["has_ranking_json"] = True
        report["ranking_json_path"] = str(ranking_files[0])

    # Check for pLDDT JSON
    plddt_files = [f for f in files if "plddt" in f.name.lower() and f.suffix == ".json"]
    if plddt_files:
        report["has_plddt_json"] = True
        report["plddt_json_path"] = str(plddt_files[0])

    # Check if prediction actually ran (by presence of key output files)
    if report["has_complex_structure_file"] or report["has_ranking_json"]:
        report["complex_prediction_ran"] = True

    # Inspect PDB for chain IDs if available
    if pdb_files:
        try:
            pdb_text = pdb_files[0].read_text(encoding="utf-8", errors="ignore")
            report["has_chain_A"] = any(
                line.startswith("ATOM") and line[21:22].strip() == "A"
                for line in pdb_text.splitlines()
            )
            report["has_chain_B"] = any(
                line.startswith("ATOM") and line[21:22].strip() == "B"
                for line in pdb_text.splitlines()
            )
        except Exception:
            logger.warning("Failed to read PDB file %s for chain inspection", pdb_files[0])

    # Determine readiness for interface parser
    report["ready_for_interface_parser"] = (
        report["has_complex_structure_file"]
        and report["has_chain_A"]
        and report["has_chain_B"]
    )

    # pDockQ readiness: needs interface parser first
    report["ready_for_pdockq"] = False
    if not report["ready_for_interface_parser"]:
        report["reason_pdockq_not_computed"] += (
            " Additionally, interface parser prerequisites are not met: "
            f"structure={report['has_complex_structure_file']}, "
            f"chain_A={report['has_chain_A']}, chain_B={report['has_chain_B']}."
        )

    return report
