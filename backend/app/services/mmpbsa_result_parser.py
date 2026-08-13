"""
mmpbsa_result_parser.py
-----------------------
Parse MMPBSA.py FINAL_RESULTS_MMPBSA*.dat output into structured JSON.

Scientific boundaries:
- Pilot / smoke results are NEVER promoted to official mm_gbsa_delta_g.
- Missing values are reported as None, not invented.
- If source file is missing, parser returns BLOCKED status.
- All output is based ONLY on real files; no hard-coded example values.
"""

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

PARSER_VERSION = "0.2.0"


@dataclass
class MMPBSAParsedResult:
    source_file: Optional[str] = None
    parser_version: str = PARSER_VERSION
    run_type: str = "UNKNOWN"  # PILOT, SMOKE, PRODUCTION, UNKNOWN
    convergence_status: str = "UNKNOWN"  # CONVERGED, PARTIAL_CONVERGENCE, PILOT_ONLY, SMOKE_ONLY, NOT_CONVERGED, UNKNOWN
    frames_used: Optional[int] = None
    frames_available: Optional[int] = None
    pilot_delta_total_kcal_mol: Optional[float] = None
    pilot_delta_gb_kcal_mol: Optional[float] = None
    pilot_delta_gsolv_kcal_mol: Optional[float] = None
    energy_terms: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    official_mm_gbsa_delta_g: Optional[float] = None  # Always null for pilot/smoke
    raw_header: Dict[str, str] = field(default_factory=dict)
    status: str = "PENDING"  # SUCCESS, BLOCKED, PARSE_ERROR
    decomposition: List[Dict[str, Any]] = field(default_factory=list)


def _extract_float(text: str, pattern: str) -> Optional[float]:
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _extract_int(text: str, pattern: str) -> Optional[int]:
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def _extract_section(text: str, section_name: str) -> str:
    """Extract the text block for a named section (Complex, Receptor, Ligand, Differences)."""
    # Match section header (allow optional suffix like " (Complex - Receptor - Ligand)")
    # up to the next section header or end of file
    pattern = rf"{re.escape(section_name)}(?:\s*\([^)]*\))?\s*:(.*?)(?=\n[A-Z][a-z]+:\s|\nDifferences(?:\s*\([^)]*\))?\s*:|\Z)"
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)
    return ""


def _extract_values_from_section(section_text: str) -> Dict[str, Optional[float]]:
    """Extract energy component values from a section text block."""
    values: Dict[str, Optional[float]] = {}
    # Extract known components
    for key in ["EGB", "ESURF", "VDWAALS", "EEL"]:
        val = _extract_float(section_text, rf"{key}\s+([-\d.Ee]+)")
        if val is not None:
            values[key] = val
    for key in ["G gas", "G solv", "TOTAL"]:
        val = _extract_float(section_text, rf"{re.escape(key)}\s+([-\d.Ee]+)")
        if val is not None:
            values[key.replace(" ", "_")] = val
    return values


def _extract_decomposition(text: str) -> List[Dict[str, Any]]:
    """Extract per-residue decomposition results if present."""
    decomp: List[Dict[str, Any]] = []
    # Look for DECOMP MM-GBSA or DECOMP MMPBSA section
    decomp_match = re.search(
        r"DECOMP\s+(?:MM-GBSA|MMPBSA)\s*:(.*?)(?=\n[A-Z][a-z]+:\s|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not decomp_match:
        return decomp

    decomp_text = decomp_match.group(1)
    # Find each residue block
    residue_blocks = re.findall(
        r"Residue\s+(\S+)\s*\n.*?(?:Energy Component.*?\n-+\n)(.*?)(?=\nResidue\s+\S+|\n\s*\n\s*[A-Z]|\Z)",
        decomp_text,
        re.DOTALL | re.IGNORECASE,
    )
    for residue_id, block in residue_blocks:
        row: Dict[str, Any] = {"residue": residue_id.strip().rstrip(":")}
        for key in ["Internal", "VDWAALS", "EEL", "EGB", "ESURF", "G gas", "G solv", "TOTAL"]:
            val = _extract_float(block, rf"{re.escape(key)}\s+([-\d.Ee]+)")
            if val is not None:
                row[key.replace(" ", "_")] = val
        if len(row) > 1:
            decomp.append(row)
    return decomp


def parse_mmpbsa_result(
    file_path: Union[str, Path],
    run_type_hint: Optional[str] = None,
) -> MMPBSAParsedResult:
    """
    Parse a MMPBSA.py FINAL_RESULTS file.

    Args:
        file_path: Path to FINAL_RESULTS_MMPBSA*.dat
        run_type_hint: Optional hint (PILOT, SMOKE, PRODUCTION) to override auto-detection

    Returns:
        MMPBSAParsedResult with all extracted fields and scientific boundaries enforced.
    """
    path = Path(file_path)
    result = MMPBSAParsedResult(source_file=str(path))

    if not path.exists():
        result.status = "BLOCKED"
        result.warnings.append(f"Source file not found: {path}")
        return result

    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        result.status = "PARSE_ERROR"
        result.warnings.append(f"Failed to read file: {e}")
        return result

    # --- Header extraction ---
    run_date_match = re.search(r"\|\s*Run on\s+(.+?)(?:\r?\n|\r)", text)
    if run_date_match:
        result.raw_header["run_date"] = run_date_match.group(1).strip()

    version_match = re.search(r"MMPBSA\.py Version=(.+?)(?:\r?\n|\r)", text)
    if version_match:
        result.raw_header["mmpbsa_version"] = version_match.group(1).strip()

    frames_match = re.search(r"Calculations performed using\s+([0-9.]+)\s+complex frames", text, re.IGNORECASE)
    if frames_match:
        try:
            result.frames_used = int(float(frames_match.group(1)))
        except ValueError:
            pass

    # --- Section-based energy extraction ---
    complex_section = _extract_section(text, "Complex")
    receptor_section = _extract_section(text, "Receptor")
    ligand_section = _extract_section(text, "Ligand")
    differences_section = _extract_section(text, "Differences")

    complex_vals = _extract_values_from_section(complex_section)
    receptor_vals = _extract_values_from_section(receptor_section)
    ligand_vals = _extract_values_from_section(ligand_section)
    delta_vals = _extract_values_from_section(differences_section)

    if complex_vals.get("TOTAL") is not None:
        result.energy_terms["complex"] = {
            "TOTAL": complex_vals.get("TOTAL"),
            "EGB": complex_vals.get("EGB"),
            "ESURF": complex_vals.get("ESURF"),
            "G_gas": complex_vals.get("G_gas"),
            "G_solv": complex_vals.get("G_solv"),
        }
    if receptor_vals.get("TOTAL") is not None:
        result.energy_terms["receptor"] = {
            "TOTAL": receptor_vals.get("TOTAL"),
            "EGB": receptor_vals.get("EGB"),
            "ESURF": receptor_vals.get("ESURF"),
            "G_gas": receptor_vals.get("G_gas"),
            "G_solv": receptor_vals.get("G_solv"),
        }
    if ligand_vals.get("TOTAL") is not None:
        result.energy_terms["ligand"] = {
            "TOTAL": ligand_vals.get("TOTAL"),
            "EGB": ligand_vals.get("EGB"),
            "ESURF": ligand_vals.get("ESURF"),
            "G_gas": ligand_vals.get("G_gas"),
            "G_solv": ligand_vals.get("G_solv"),
        }

    # --- Delta extraction ---
    delta_total = _extract_float(differences_section, r"DELTA TOTAL\s+([-\d.Ee]+)")
    if delta_total is not None:
        result.pilot_delta_total_kcal_mol = delta_total
        result.energy_terms["delta"] = {
            "DELTA_TOTAL": delta_total,
            "DELTA_G_gas": delta_vals.get("G_gas"),
            "DELTA_G_solv": delta_vals.get("G_solv"),
            "VDWAALS": delta_vals.get("VDWAALS"),
            "EEL": delta_vals.get("EEL"),
            "EGB": delta_vals.get("EGB"),
            "ESURF": delta_vals.get("ESURF"),
        }

    # --- Decomposition ---
    result.decomposition = _extract_decomposition(text)

    # --- Run type & convergence status ---
    if run_type_hint:
        result.run_type = run_type_hint.upper()
    else:
        path_str = str(path).lower()
        if "pilot" in path_str or "pilot" in text.lower():
            result.run_type = "PILOT"
        elif "smoke" in path_str or "smoke" in text.lower():
            result.run_type = "SMOKE"
        elif "production" in path_str or "production" in text.lower():
            result.run_type = "PRODUCTION"
        else:
            result.run_type = "UNKNOWN"

    if result.run_type in ("PILOT", "SMOKE"):
        result.convergence_status = f"{result.run_type}_ONLY"
        result.official_mm_gbsa_delta_g = None
        result.warnings.append(
            f"Result is {result.run_type}-only ({result.frames_used or 'unknown'} frames). "
            "official_mm_gbsa_delta_g remains null. Not suitable for candidate ranking."
        )
    elif result.run_type == "PRODUCTION":
        if result.frames_used and result.frames_used >= 200:
            result.convergence_status = "CONVERGED"
        elif result.frames_used and result.frames_used >= 50:
            result.convergence_status = "PARTIAL_CONVERGENCE"
        else:
            result.convergence_status = "NOT_CONVERGED"
            result.warnings.append(
                "Production run has insufficient frames for convergence assessment."
            )
    else:
        result.convergence_status = "UNKNOWN"
        result.warnings.append("Could not determine run type or convergence status.")

    # --- Warnings for zero gas phase ---
    cg = complex_vals.get("G_gas")
    rg = receptor_vals.get("G_gas")
    lg = ligand_vals.get("G_gas")
    if cg == 0.0 and rg == 0.0 and lg == 0.0:
        result.warnings.append(
            "G gas = 0 for all components. This may indicate mmpbsa_py_energy was used "
            "instead of sander for gas-phase term calculation. Result is non-physical."
        )

    # --- Warning for low frame count ---
    if result.frames_used and result.frames_used < 10:
        result.warnings.append(
            f"Only {result.frames_used} frames used. Statistics are unreliable."
        )

    result.status = "SUCCESS"
    return result


# Alias used by compute wrappers
parse_mmpbsa_dat = parse_mmpbsa_result


def to_dict(result: MMPBSAParsedResult) -> Dict[str, Any]:
    """Serialize parsed result to plain dict for JSON output."""
    return {
        "source_file": result.source_file,
        "parser_version": result.parser_version,
        "status": result.status,
        "run_type": result.run_type,
        "convergence_status": result.convergence_status,
        "frames_used": result.frames_used,
        "frames_available": result.frames_available,
        "pilot_delta_total_kcal_mol": result.pilot_delta_total_kcal_mol,
        "pilot_delta_gb_kcal_mol": result.pilot_delta_gb_kcal_mol,
        "pilot_delta_gsolv_kcal_mol": result.pilot_delta_gsolv_kcal_mol,
        "energy_terms": result.energy_terms,
        "warnings": result.warnings,
        "official_mm_gbsa_delta_g": result.official_mm_gbsa_delta_g,
        "raw_header": result.raw_header,
        "decomposition": result.decomposition,
    }


def get_mmgbsa_components(result: MMPBSAParsedResult) -> Dict[str, Optional[float]]:
    """Return user-friendly MM-GBSA energy components from parsed result.

    Maps raw terms to:
    - delta_g_total: DELTA TOTAL
    - vdw: VDWAALS
    - electrostatic: EEL
    - polar_solvation: EGB
    - nonpolar_solvation: ESURF
    """
    delta = result.energy_terms.get("delta", {})
    return {
        "delta_g_total": delta.get("DELTA_TOTAL"),
        "vdw": delta.get("VDWAALS"),
        "electrostatic": delta.get("EEL"),
        "polar_solvation": delta.get("EGB"),
        "nonpolar_solvation": delta.get("ESURF"),
    }


def write_mmgbsa_summary_json(
    result: MMPBSAParsedResult,
    output_dir: Union[str, Path],
) -> Path:
    """Write mmgbsa_summary.json to output_dir.

    Contains high-level summary, user-friendly components, and scientific boundaries.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "mmgbsa_summary.json"

    components = get_mmgbsa_components(result)
    summary = {
        "source_file": result.source_file,
        "parser_version": result.parser_version,
        "status": result.status,
        "run_type": result.run_type,
        "convergence_status": result.convergence_status,
        "frames_used": result.frames_used,
        "frames_available": result.frames_available,
        "delta_g_total": components["delta_g_total"],
        "components": {
            "vdW": components["vdw"],
            "electrostatic": components["electrostatic"],
            "polar_solvation": components["polar_solvation"],
            "nonpolar_solvation": components["nonpolar_solvation"],
        },
        "official_mm_gbsa_delta_g": result.official_mm_gbsa_delta_g,
        "warnings": result.warnings,
        "decomposition_available": len(result.decomposition) > 0,
        "decomposition_count": len(result.decomposition),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary_path


def write_mmgbsa_components_csv(
    result: MMPBSAParsedResult,
    output_dir: Union[str, Path],
) -> Path:
    """Write mmgbsa_components.csv to output_dir.

    Contains one row per energy component (delta, complex, receptor, ligand)
    plus decomposition rows if available.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "mmgbsa_components.csv"

    rows: List[Dict[str, Any]] = []
    # Delta components
    delta = result.energy_terms.get("delta", {})
    rows.append({
        "section": "delta",
        "term": "DELTA_TOTAL",
        "value_kcal_mol": delta.get("DELTA_TOTAL"),
    })
    rows.append({
        "section": "delta",
        "term": "VDWAALS",
        "value_kcal_mol": delta.get("VDWAALS"),
    })
    rows.append({
        "section": "delta",
        "term": "EEL",
        "value_kcal_mol": delta.get("EEL"),
    })
    rows.append({
        "section": "delta",
        "term": "EGB",
        "value_kcal_mol": delta.get("EGB"),
    })
    rows.append({
        "section": "delta",
        "term": "ESURF",
        "value_kcal_mol": delta.get("ESURF"),
    })

    # Complex / Receptor / Ligand totals
    for section in ("complex", "receptor", "ligand"):
        terms = result.energy_terms.get(section, {})
        for term, value in terms.items():
            rows.append({
                "section": section,
                "term": term,
                "value_kcal_mol": value,
            })

    # Decomposition rows
    for row in result.decomposition:
        residue = row.get("residue", "")
        for term, value in row.items():
            if term == "residue":
                continue
            rows.append({
                "section": f"decomp_{residue}",
                "term": term,
                "value_kcal_mol": value,
            })

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["section", "term", "value_kcal_mol"])
        writer.writeheader()
        writer.writerows(rows)

    return csv_path
