"""STAMP Platform — Candidate Report Export (v0.10-P7).

Generates structured candidate reports in JSON, Markdown, CSV, XLSX, and PDF formats.
All outputs enforce the scientific-integrity boundary: no fabricated wet-lab
metrics, no docking_score, no MM-GBSA ΔG.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.crud.experimental_validation import summarize_candidate_experimental_validation
from app.crud.project_results import list_project_stamp_results
from app.crud.projects import get_project

logger = logging.getLogger(__name__)

REQUIRED_VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"

FORBIDDEN_TOP_LEVEL_KEYS = (
    "MIC",
    "MBC",
    "hemolysis",
    "toxicity",
    "docking_score",
    "mmgbsa_delta_G",
    "experimental_delta_G",
    "wet_lab_confirmed",
    "experimentally_validated",
)


def build_candidate_report_data(
    db: Session,
    project_id: str,
    top_k: int = 10,
) -> dict[str, Any]:
    """Build a structured candidate report dict from project stamp results.

    Args:
        db: Database session.
        project_id: Project ID.
        top_k: Number of top candidates to include.

    Returns:
        Report data dict.

    Raises:
        ValueError: If project not found.
    """
    project = get_project(db, project_id)
    if project is None:
        raise ValueError(f"Project '{project_id}' not found")

    results = list_project_stamp_results(db, project_id, top_k=top_k, include_metrics=True)
    if results is None:
        raise ValueError(f"Project '{project_id}' not found")

    candidates = results.get("candidates", [])

    has_epitope = False
    has_pepmlm = False
    has_structure = False
    has_interface = False
    has_energy = False

    report_candidates = []
    for rank, cand in enumerate(candidates, start=1):
        metrics = cand.metrics or {}
        sp = metrics.get("structure_prediction") or {}
        iq = metrics.get("interface_quality") or {}
        eq = metrics.get("energy_quality") or {}

        if metrics.get("epitope") or metrics.get("epitope_scan"):
            has_epitope = True
        if "pepmlm" in str(metrics.get("source", "")).lower():
            has_pepmlm = True
        if sp:
            has_structure = True
        if iq:
            has_interface = True
        if eq:
            has_energy = True

        report_candidates.append({
            "rank": rank,
            "candidate_id": cand.id,
            "targeting_peptide_seq": cand.targeting_peptide_seq,
            "linker_seq": cand.linker_seq,
            "full_sequence": cand.full_sequence,
            "composite_score": cand.composite_score,
            "validation_status": cand.validation_status or REQUIRED_VALIDATION_STATUS,
            "source": metrics.get("source", "unknown"),
            "generation": {
                "model": metrics.get("model", "PepMLM-650M"),
                "generation_status": "COMPUTATIONAL_GENERATION_ONLY",
                "ppl": metrics.get("ppl"),
                "charge": metrics.get("charge") or metrics.get("net_charge"),
                "pi": metrics.get("pI") or metrics.get("pi"),
            },
            "structure_prediction": {
                "mean_plddt": sp.get("mean_plddt") if sp else None,
                "ptm": sp.get("ptm") if sp else None,
                "iptm": sp.get("iptm") if sp else None,
                "prediction_status": sp.get("prediction_status") if sp else "COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY",
            },
            "interface_quality": {
                "pdockq": iq.get("pdockq") if iq else None,
                "interface_contacts": (
                    iq.get("input_features", {}).get("interface_contact_count")
                    if iq else None
                ),
                "prediction_status": iq.get("prediction_status") if iq else "COMPUTATIONAL_INTERFACE_QUALITY_PREDICTION_ONLY",
            },
            "energy_quality": {
                "interaction_energy_kcal_mol": eq.get("interaction_energy_kcal_mol") if eq else None,
                "vdw_clashes": (
                    eq.get("energy_terms", {}).get("vdw_clashes")
                    if eq else None
                ),
                "prediction_status": eq.get("prediction_status") if eq else "COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY",
                "not_docking_score": True,
                "not_mmgbsa_delta_g": True,
            },
        })

    # Append experimental validation section per candidate
    for rc in report_candidates:
        cand_id = rc["candidate_id"]
        exp_summary = summarize_candidate_experimental_validation(db, cand_id)
        if exp_summary["measurement_count"] == 0:
            rc["experimental_validation"] = {
                "status": "NOT_EXPERIMENTALLY_VALIDATED",
                "note": "No wet-lab measurements have been recorded.",
                "measurements": [],
            }
        else:
            rc["experimental_validation"] = {
                "status": exp_summary["overall_validation_status"],
                "note": "Experimental measurements are available. See details below.",
                "measurements": [
                    {
                        "metric_name": m.metric_name,
                        "value": m.value,
                        "unit": m.unit,
                        "quality_flag": m.quality_flag,
                        "experiment_type": next(
                            (r.experiment_type for r in exp_summary["runs"] if r.id == m.validation_run_id),
                            "UNKNOWN",
                        ),
                        "experiment_date": next(
                            (r.experiment_date.isoformat() if r.experiment_date else None
                             for r in exp_summary["runs"] if r.id == m.validation_run_id),
                            None,
                        ),
                        "protocol_name": next(
                            (r.protocol_name for r in exp_summary["runs"] if r.id == m.validation_run_id),
                            None,
                        ),
                    }
                    for m in exp_summary["measurements"]
                ],
            }

    return {
        "project_id": project_id,
        "report_type": "STAMP_CANDIDATE_REPORT",
        "validation_status": REQUIRED_VALIDATION_STATUS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "candidate_count": len(report_candidates),
            "has_epitope_prediction": has_epitope,
            "has_pepmlm_generation": has_pepmlm,
            "has_structure_prediction": has_structure,
            "has_interface_quality": has_interface,
            "has_energy_quality": has_energy,
        },
        "scientific_boundary": {
            "computational_only": True,
            "not_wet_lab_validated": True,
            "not_mic": True,
            "not_docking_score": True,
            "not_mmgbsa_delta_g": True,
        },
        "candidates": report_candidates,
    }


def render_candidate_report_markdown(report_data: dict[str, Any]) -> str:
    """Render a candidate report as Markdown.

    Args:
        report_data: Output from build_candidate_report_data().

    Returns:
        Markdown string.
    """
    lines = [
        "# STAMP Candidate Report",
        "",
        f"**Project ID:** {report_data['project_id']}",
        f"**Report Type:** {report_data['report_type']}",
        f"**Generated At:** {report_data['generated_at']}",
        f"**Validation Status:** {report_data['validation_status']}",
        "",
        "---",
        "",
        "## 1. Project Summary",
        "",
        f"- Total candidates in report: {report_data['summary']['candidate_count']}",
        f"- Has epitope prediction: {'Yes' if report_data['summary']['has_epitope_prediction'] else 'No'}",
        f"- Has PepMLM generation: {'Yes' if report_data['summary']['has_pepmlm_generation'] else 'No'}",
        f"- Has structure prediction: {'Yes' if report_data['summary']['has_structure_prediction'] else 'No'}",
        f"- Has interface quality (pDockQ): {'Yes' if report_data['summary']['has_interface_quality'] else 'No'}",
        f"- Has energy quality (FoldX): {'Yes' if report_data['summary']['has_energy_quality'] else 'No'}",
        "",
        "## 2. Top Candidate Peptides",
        "",
    ]

    for c in report_data["candidates"]:
        lines.extend([
            f"### Rank {c['rank']} — {c['candidate_id']}",
            "",
            f"- **Targeting peptide:** `{c['targeting_peptide_seq']}`",
            f"- **Linker:** `{c['linker_seq']}`",
            f"- **Full sequence:** `{c['full_sequence']}`",
            f"- **Composite score:** {c['composite_score']}",
            f"- **Validation status:** {c['validation_status']}",
            f"- **Source:** {c['source']}",
            "",
            "#### Generation",
            f"- Model: {c['generation']['model']}",
            f"- Status: {c['generation']['generation_status']}",
            f"- PPL: {c['generation']['ppl'] if c['generation']['ppl'] is not None else 'N/A'}",
            f"- Charge: {c['generation']['charge'] if c['generation']['charge'] is not None else 'N/A'}",
            f"- pI: {c['generation']['pi'] if c['generation']['pi'] is not None else 'N/A'}",
            "",
            "#### Structure Prediction",
            f"- mean pLDDT: {c['structure_prediction']['mean_plddt'] if c['structure_prediction']['mean_plddt'] is not None else 'N/A'}",
            f"- pTM: {c['structure_prediction']['ptm'] if c['structure_prediction']['ptm'] is not None else 'N/A'}",
            f"- ipTM: {c['structure_prediction']['iptm'] if c['structure_prediction']['iptm'] is not None else 'N/A'}",
            f"- Status: {c['structure_prediction']['prediction_status']}",
            "",
            "#### Interface Quality",
            f"- pDockQ: {c['interface_quality']['pdockq'] if c['interface_quality']['pdockq'] is not None else 'N/A'}",
            f"- Interface contacts: {c['interface_quality']['interface_contacts'] if c['interface_quality']['interface_contacts'] is not None else 'N/A'}",
            f"- Status: {c['interface_quality']['prediction_status']}",
            "",
            "#### FoldX Energy Quality",
            f"- Interaction energy: {c['energy_quality']['interaction_energy_kcal_mol'] if c['energy_quality']['interaction_energy_kcal_mol'] is not None else 'N/A'} kcal/mol",
            f"- VdW clashes: {c['energy_quality']['vdw_clashes'] if c['energy_quality']['vdw_clashes'] is not None else 'N/A'}",
            f"- Status: {c['energy_quality']['prediction_status']}",
            "",
            "> **Note:** FoldX AnalyseComplex provides interaction energy and energy decomposition terms. It does **not** provide a docking_score or MM-GBSA ΔG.",
            "",
            "---",
            "",
        ])

        # Experimental Validation section
        ev = c.get("experimental_validation", {})
        lines.extend([
            "#### Experimental Validation",
            f"- **Status:** {ev.get('status', 'NOT_EXPERIMENTALLY_VALIDATED')}",
            f"- **Note:** {ev.get('note', 'No wet-lab measurements recorded.')}",
            "",
        ])
        if ev.get("measurements"):
            lines.append("| Metric | Value | Unit | Quality Flag | Experiment Type |")
            lines.append("|--------|-------|------|--------------|-----------------|")
            for m in ev["measurements"]:
                lines.append(
                    f"| {m['metric_name']} | {m['value'] if m['value'] is not None else 'N/A'} | "
                    f"{m['unit'] if m['unit'] else 'N/A'} | {m['quality_flag']} | {m['experiment_type']} |"
                )
            lines.append("")
        lines.extend([
            "> **Note:** Experimental measurements are distinct from computational predictions. "
            "These values come from wet-lab assays, not from BepiPred3, PepMLM, ColabFold, pDockQ, or FoldX.",
            "",
            "---",
            "",
        ])

    lines.extend([
        "## 3. Epitope Prediction Source",
        "",
        "Epitope predictions were generated using BepiPred-3.0 (or equivalent computational epitope scanning tools). These are computational surface-exposure and antigenicity predictions, not experimental epitope mapping results.",
        "",
        "## 4. Peptide Generation Source",
        "",
        "Targeting peptides were generated using PepMLM-650M (a 650M-parameter protein language model fine-tuned for antimicrobial peptide generation). Generation is purely computational; no wet-lab screening or selection was performed.",
        "",
        "## 5. Computational Structure Validation",
        "",
        "### 5.1 Structure Prediction",
        "Complex structures were predicted using LocalColabFold (AlphaFold2 multimer). mean pLDDT, pTM, and ipTM are model confidence scores, not experimental validation.",
        "",
        "### 5.2 Interface Quality",
        "pDockQ was computed from interface contact counts and interface residue pLDDT using the Bryant et al. 2022 sigmoid formula. It is a computational interface-confidence estimate.",
        "",
        "### 5.3 FoldX Energy Quality",
        "Interaction energy and energy decomposition terms were computed using FoldX 5.1 AnalyseComplex. These are computational energy estimates derived from the predicted structure, not experimentally measured binding affinities.",
        "",
        "---",
        "",
        "## 6. Scientific Boundary",
        "",
        "> **All results in this report are computational predictions or model-generated candidates. They are NOT experimentally validated.**",
        ">",
        "> This report does not provide:",
        "> - MIC (minimum inhibitory concentration)",
        "> - MBC (minimum bactericidal concentration)",
        "> - Hemolysis assays",
        "> - Toxicity assays",
        "> - docking_score (FlexPepDock not integrated)",
        "> - MM-GBSA ΔG (not computed)",
        "> - Experimentally validated binding affinity",
        "> - Wet-lab confirmed activity",
        "",
        "For experimental validation, additional in-vitro and in-vivo assays are required.",
        "",
    ])

    return "\n".join(lines)


def render_candidate_report_csv(report_data: dict[str, Any]) -> str:
    """Render a candidate report as CSV.

    Args:
        report_data: Output from build_candidate_report_data().

    Returns:
        CSV string.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "rank",
        "candidate_id",
        "targeting_peptide_seq",
        "linker_seq",
        "full_sequence",
        "composite_score",
        "validation_status",
        "source",
        "ppl",
        "charge",
        "pi",
        "mean_plddt",
        "ptm",
        "iptm",
        "pdockq",
        "interface_contacts",
        "interaction_energy_kcal_mol",
        "vdw_clashes",
        "energy_interpretation",
    ])

    for c in report_data["candidates"]:
        eq = c.get("energy_quality", {})
        interpretation = ""
        if eq.get("interaction_energy_kcal_mol") is not None and eq.get("interaction_energy_kcal_mol", 0) > 0:
            interpretation = "Unfavorable interaction energy (positive value suggests poorly relaxed model)"
        elif eq.get("interaction_energy_kcal_mol") is not None:
            interpretation = "Favorable interaction energy"

        writer.writerow([
            c["rank"],
            c["candidate_id"],
            c["targeting_peptide_seq"],
            c["linker_seq"],
            c["full_sequence"],
            c["composite_score"],
            c["validation_status"],
            c["source"],
            c["generation"]["ppl"] if c["generation"]["ppl"] is not None else "N/A",
            c["generation"]["charge"] if c["generation"]["charge"] is not None else "N/A",
            c["generation"]["pi"] if c["generation"]["pi"] is not None else "N/A",
            c["structure_prediction"]["mean_plddt"] if c["structure_prediction"]["mean_plddt"] is not None else "N/A",
            c["structure_prediction"]["ptm"] if c["structure_prediction"]["ptm"] is not None else "N/A",
            c["structure_prediction"]["iptm"] if c["structure_prediction"]["iptm"] is not None else "N/A",
            c["interface_quality"]["pdockq"] if c["interface_quality"]["pdockq"] is not None else "N/A",
            c["interface_quality"]["interface_contacts"] if c["interface_quality"]["interface_contacts"] is not None else "N/A",
            eq.get("interaction_energy_kcal_mol") if eq.get("interaction_energy_kcal_mol") is not None else "N/A",
            eq.get("vdw_clashes") if eq.get("vdw_clashes") is not None else "N/A",
            interpretation,
        ])

    return output.getvalue()


def validate_report_no_fabricated_metrics(report_data: dict[str, Any]) -> None:
    """Validate that the report contains no fabricated wet-lab metrics.

    Args:
        report_data: Report data dict.

    Raises:
        ValueError: If forbidden metrics are found.
    """
    issues = []

    # Check top-level keys
    for key in FORBIDDEN_TOP_LEVEL_KEYS:
        if key in report_data:
            issues.append(f"Forbidden top-level key '{key}' found in report")

    # Check candidates
    for c in report_data.get("candidates", []):
        for key in FORBIDDEN_TOP_LEVEL_KEYS:
            if key in c:
                issues.append(f"Forbidden key '{key}' found in candidate {c.get('candidate_id', '?')}")

        # Check energy_quality does not claim to be docking_score or MM-GBSA
        eq = c.get("energy_quality", {})
        if eq.get("docking_score") is not None:
            issues.append(f"Candidate {c.get('candidate_id', '?')} has non-null docking_score")
        if eq.get("mmgbsa_delta_G") is not None:
            issues.append(f"Candidate {c.get('candidate_id', '?')} has non-null mmgbsa_delta_G")

    if issues:
        raise ValueError("Report validation failed: " + "; ".join(issues))


# ---------------------------------------------------------------------------
# XLSX renderer
# ---------------------------------------------------------------------------

def render_candidate_report_xlsx(report_data: dict[str, Any]) -> bytes:
    """Render a candidate report as XLSX bytes.

    Args:
        report_data: Output from build_candidate_report_data().

    Returns:
        XLSX file as bytes.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    wb = Workbook()

    # ---- Summary sheet ----
    ws_summary = wb.active
    ws_summary.title = "Summary"
    ws_summary.append(["STAMP Candidate Report"])
    ws_summary.append([])
    ws_summary.append(["Project ID", report_data["project_id"]])
    ws_summary.append(["Report Type", report_data["report_type"]])
    ws_summary.append(["Generated At", report_data["generated_at"]])
    ws_summary.append(["Validation Status", report_data["validation_status"]])
    ws_summary.append([])
    summary = report_data["summary"]
    ws_summary.append(["Candidate Count", summary["candidate_count"]])
    ws_summary.append(["Has Epitope Prediction", "Yes" if summary["has_epitope_prediction"] else "No"])
    ws_summary.append(["Has PepMLM Generation", "Yes" if summary["has_pepmlm_generation"] else "No"])
    ws_summary.append(["Has Structure Prediction", "Yes" if summary["has_structure_prediction"] else "No"])
    ws_summary.append(["Has Interface Quality", "Yes" if summary["has_interface_quality"] else "No"])
    ws_summary.append(["Has Energy Quality", "Yes" if summary["has_energy_quality"] else "No"])

    header_font = Font(bold=True)
    for cell in ws_summary[1]:
        cell.font = Font(bold=True, size=14)
    for row in ws_summary.iter_rows(min_row=3, max_row=ws_summary.max_row):
        row[0].font = header_font

    # ---- Candidates sheet ----
    ws_cand = wb.create_sheet(title="Candidates")
    headers = [
        "Rank", "Candidate ID", "Targeting Peptide", "Linker", "Full Sequence",
        "Composite Score", "Validation Status", "Source", "Model", "Generation Status",
        "PPL", "Charge", "pI", "mean pLDDT", "pTM", "ipTM",
        "pDockQ", "Interface Contacts", "Interaction Energy (kcal/mol)", "VdW Clashes",
        "Energy Status", "Exp Validation Status", "Exp Note",
    ]
    ws_cand.append(headers)
    for cell in ws_cand[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")

    for c in report_data["candidates"]:
        gen = c.get("generation", {})
        sp = c.get("structure_prediction", {})
        iq = c.get("interface_quality", {})
        eq = c.get("energy_quality", {})
        ev = c.get("experimental_validation", {})
        ws_cand.append([
            c["rank"],
            c["candidate_id"],
            c["targeting_peptide_seq"],
            c["linker_seq"],
            c["full_sequence"],
            c["composite_score"],
            c["validation_status"],
            c["source"],
            gen.get("model", ""),
            gen.get("generation_status", ""),
            gen.get("ppl") if gen.get("ppl") is not None else "N/A",
            gen.get("charge") if gen.get("charge") is not None else "N/A",
            gen.get("pi") if gen.get("pi") is not None else "N/A",
            sp.get("mean_plddt") if sp.get("mean_plddt") is not None else "N/A",
            sp.get("ptm") if sp.get("ptm") is not None else "N/A",
            sp.get("iptm") if sp.get("iptm") is not None else "N/A",
            iq.get("pdockq") if iq.get("pdockq") is not None else "N/A",
            iq.get("interface_contacts") if iq.get("interface_contacts") is not None else "N/A",
            eq.get("interaction_energy_kcal_mol") if eq.get("interaction_energy_kcal_mol") is not None else "N/A",
            eq.get("vdw_clashes") if eq.get("vdw_clashes") is not None else "N/A",
            eq.get("prediction_status", ""),
            ev.get("status", ""),
            ev.get("note", ""),
        ])

    # ---- Scientific Boundary sheet ----
    ws_boundary = wb.create_sheet(title="Scientific Boundary")
    ws_boundary.append(["Scientific Boundary Declaration"])
    ws_boundary.append([])
    boundary = report_data.get("scientific_boundary", {})
    ws_boundary.append(["Computational Only", "Yes" if boundary.get("computational_only") else "No"])
    ws_boundary.append(["Not Wet-lab Validated", "Yes" if boundary.get("not_wet_lab_validated") else "No"])
    ws_boundary.append(["Not MIC", "Yes" if boundary.get("not_mic") else "No"])
    ws_boundary.append(["Not Docking Score", "Yes" if boundary.get("not_docking_score") else "No"])
    ws_boundary.append(["Not MM-GBSA ΔG", "Yes" if boundary.get("not_mmgbsa_delta_g") else "No"])
    ws_boundary.append([])
    ws_boundary.append(["All results in this report are computational predictions or model-generated candidates."])
    ws_boundary.append(["They are NOT experimentally validated."])
    ws_boundary.append(["This report does not provide MIC, MBC, hemolysis, toxicity, docking_score, MM-GBSA ΔG, or experimentally validated binding affinity."])
    for cell in ws_boundary[1]:
        cell.font = Font(bold=True, size=14)
    for row in ws_boundary.iter_rows(min_row=9, max_row=11):
        for cell in row:
            cell.font = Font(bold=True, color="FF0000")

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


# ---------------------------------------------------------------------------
# PDF renderer
# ---------------------------------------------------------------------------

def render_candidate_report_pdf(report_data: dict[str, Any]) -> bytes:
    """Render a candidate report as PDF bytes.

    Args:
        report_data: Output from build_candidate_report_data().

    Returns:
        PDF file as bytes.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=50, leftMargin=50,
                            topMargin=50, bottomMargin=30)
    styles = getSampleStyleSheet()
    story: list[Any] = []

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=12,
    )
    story.append(Paragraph("STAMP Candidate Report", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Project ID:</b> {report_data['project_id']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Report Type:</b> {report_data['report_type']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Generated:</b> {report_data['generated_at']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Validation Status:</b> {report_data['validation_status']}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Summary table
    summary = report_data["summary"]
    summary_data = [
        ["Metric", "Value"],
        ["Candidate Count", str(summary["candidate_count"])],
        ["Has Epitope Prediction", "Yes" if summary["has_epitope_prediction"] else "No"],
        ["Has PepMLM Generation", "Yes" if summary["has_pepmlm_generation"] else "No"],
        ["Has Structure Prediction", "Yes" if summary["has_structure_prediction"] else "No"],
        ["Has Interface Quality", "Yes" if summary["has_interface_quality"] else "No"],
        ["Has Energy Quality", "Yes" if summary["has_energy_quality"] else "No"],
    ]
    summary_table = Table(summary_data, colWidths=[3 * inch, 2 * inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDDDDD")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(Paragraph("<b>Project Summary</b>", styles["Heading2"]))
    story.append(summary_table)
    story.append(Spacer(1, 12))

    # Candidates table
    story.append(Paragraph("<b>Top Candidate Peptides</b>", styles["Heading2"]))
    cand_headers = ["Rank", "Candidate ID", "Sequence", "Score", "Status"]
    cand_data = [cand_headers]
    for c in report_data["candidates"]:
        seq = c["full_sequence"]
        if len(seq) > 35:
            seq = seq[:32] + "..."
        cand_data.append([
            str(c["rank"]),
            c["candidate_id"][:8] + "...",
            seq,
            f"{c['composite_score']:.2f}",
            c["validation_status"],
        ])
    cand_table = Table(cand_data, colWidths=[0.5 * inch, 1.2 * inch, 2.5 * inch, 0.7 * inch, 1.1 * inch])
    cand_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDDDDD")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(cand_table)
    story.append(Spacer(1, 12))

    # Scientific Boundary box
    boundary = report_data.get("scientific_boundary", {})
    story.append(Paragraph("<b>Scientific Boundary</b>", styles["Heading2"]))
    boundary_text = (
        "All results in this report are computational predictions or model-generated candidates. "
        "They are <b>NOT experimentally validated</b>.<br/><br/>"
        "This report does not provide:<br/>"
        "- MIC (minimum inhibitory concentration)<br/>"
        "- MBC (minimum bactericidal concentration)<br/>"
        "- Hemolysis assays<br/>"
        "- Toxicity assays<br/>"
        "- docking_score (FlexPepDock not integrated)<br/>"
        "- MM-GBSA ΔG (not computed)<br/>"
        "- Experimentally validated binding affinity<br/>"
        "- Wet-lab confirmed activity<br/><br/>"
        "For experimental validation, additional in-vitro and in-vivo assays are required."
    )
    boundary_para = Paragraph(boundary_text, ParagraphStyle(
        "BoundaryBox",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#8B0000"),
        backColor=colors.HexColor("#FFF8F8"),
        borderWidth=1,
        borderColor=colors.HexColor("#CC0000"),
        borderPadding=8,
        leading=14,
    ))
    story.append(boundary_para)
    story.append(Spacer(1, 12))

    # Footer
    story.append(Paragraph(
        "<i>Report generated by STAMP Platform. "
        "Computational metrics: in-silico predictions only.</i>",
        styles["Italic"]
    ))

    doc.build(story)
    return buffer.getvalue()
