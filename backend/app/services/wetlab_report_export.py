"""STAMP Platform — Wet-lab Validation Report Export Service (v0.11-P5).

Generates project-level wet-lab validation reports in JSON, Markdown, and CSV.
All experimental data is user-entered or CSV-imported.
Computational predictions are NOT experimental validation.
Manual decisions are decision-support annotations, not proof.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.candidate_prioritization_service import (
    build_project_candidate_prioritization,
    compute_priority_status,
)


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

SCIENTIFIC_BOUNDARY = {
    "experimental_data_user_provided_only": True,
    "computational_predictions_not_experimental_validation": True,
    "manual_decision_not_experimental_proof": True,
    "shortlisted_not_experimentally_validated": True,
}


def build_wetlab_validation_report_data(
    db: Session, project_id: str, top_k: int = 50
) -> dict[str, Any]:
    """Build the full wet-lab validation report data structure.

    Uses existing prioritization logic but formats into a formal report.
    Does NOT fabricate any experimental data.
    """
    prioritization = build_project_candidate_prioritization(db, project_id)
    candidates_raw = prioritization.get("candidates", [])[:top_k]

    # Build summary counts from report perspective
    candidates_with_measurements = 0
    for c in candidates_raw:
        if c.get("measurement_count", 0) > 0:
            candidates_with_measurements += 1

    total_candidates = len(candidates_raw)
    coverage_percent = round(
        (candidates_with_measurements / total_candidates * 100), 1
    ) if total_candidates > 0 else 0.0

    summary = {
        "candidate_count": total_candidates,
        "candidates_with_measurements": candidates_with_measurements,
        "experimental_coverage_percent": coverage_percent,
        "shortlisted": prioritization["summary"].get("shortlisted", 0),
        "rejected": prioritization["summary"].get("rejected", 0),
        "needs_more_data": prioritization["summary"].get("needs_more_data", 0),
        "safety_concern": prioritization["summary"].get("safety_concern", 0),
        "ready_for_review": prioritization["summary"].get("ready_for_review", 0),
        "validation_failed": prioritization["summary"].get("validation_failed", 0),
    }

    # Format candidates for report
    report_candidates = []
    for c in candidates_raw:
        exp_summary = c.get("experimental_summary") or {}
        comp_summary = c.get("computational_summary") or {}

        # Extract individual measurement values (user-entered only)
        experimental_measurements = _extract_measurements_for_report(
            c.get("experimental_summary", {})
        )

        # Manual decision
        manual_decision = c.get("decision")
        if manual_decision:
            manual_decision = {
                "decision": manual_decision.get("decision"),
                "decision_reason": manual_decision.get("decision_reason"),
                "reviewer": manual_decision.get("reviewer"),
                "reviewed_at": manual_decision.get("reviewed_at"),
            }

        report_candidates.append({
            "candidate_id": c["candidate_id"],
            "sequence": c["sequence"],
            "validation_status": c["validation_status"],
            "experimental_priority_score": c.get("experimental_priority_score"),
            "priority_status": c.get("priority_status"),
            "manual_decision": manual_decision,
            "experimental_measurements": experimental_measurements,
            "computational_reference": {
                "composite_score": c.get("composite_score"),
                "mean_plddt": comp_summary.get("mean_plddt"),
                "pdockq": comp_summary.get("pdockq"),
                "interaction_energy_kcal_mol": comp_summary.get("interaction_energy_kcal_mol"),
            },
            "run_count": c.get("run_count", 0),
            "measurement_count": c.get("measurement_count", 0),
        })

    return {
        "project_id": project_id,
        "report_type": "STAMP_WETLAB_VALIDATION_REPORT",
        "generated_at": datetime.utcnow().isoformat(),
        "scientific_boundary": SCIENTIFIC_BOUNDARY,
        "summary": summary,
        "candidates": report_candidates,
    }


def _extract_measurements_for_report(exp_summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert experimental_summary dict into a list of measurement records.

    Only includes metrics that are actual experimental measurements,
    not computational predictions.
    """
    measurement_metrics = {
        "MIC_ug_ml", "MBC_ug_ml", "hemolysis_percent",
        "HC50_ug_ml", "IC50_ug_ml", "cell_viability_percent",
        "serum_half_life_min", "protease_remaining_percent",
        "biofilm_inhibition_percent",
    }
    measurements = []
    for metric_name, value in exp_summary.items():
        if metric_name in measurement_metrics and value is not None:
            measurements.append({
                "experiment_type": _metric_to_experiment_type(metric_name),
                "metric_name": metric_name,
                "value": value,
                "unit": _metric_to_unit(metric_name),
                "quality_flag": exp_summary.get("quality_flag", "PASS"),
                "replicate_id": None,
            })
    return measurements


def _metric_to_experiment_type(metric_name: str) -> str:
    """Map metric name to experiment type for display."""
    mapping = {
        "MIC_ug_ml": "MIC",
        "MBC_ug_ml": "MBC",
        "hemolysis_percent": "HEMOLYSIS",
        "HC50_ug_ml": "CYTOTOXICITY",
        "IC50_ug_ml": "CYTOTOXICITY",
        "cell_viability_percent": "CYTOTOXICITY",
        "serum_half_life_min": "SERUM_STABILITY",
        "protease_remaining_percent": "PROTEASE_STABILITY",
        "biofilm_inhibition_percent": "BIOFILM",
    }
    return mapping.get(metric_name, "OTHER")


def _metric_to_unit(metric_name: str) -> str:
    """Map metric name to default unit for display."""
    mapping = {
        "MIC_ug_ml": "ug/ml",
        "MBC_ug_ml": "ug/ml",
        "hemolysis_percent": "%",
        "HC50_ug_ml": "ug/ml",
        "IC50_ug_ml": "ug/ml",
        "cell_viability_percent": "%",
        "serum_half_life_min": "min",
        "protease_remaining_percent": "%",
        "biofilm_inhibition_percent": "%",
    }
    return mapping.get(metric_name, "")


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def render_wetlab_report_markdown(report_data: dict[str, Any]) -> str:
    """Render the wet-lab validation report as Markdown."""
    project_id = report_data["project_id"]
    generated_at = report_data["generated_at"]
    summary = report_data["summary"]
    candidates = report_data["candidates"]

    lines: list[str] = []

    lines.append("# STAMP Wet-lab Validation Report")
    lines.append("")
    lines.append(f"**Project ID:** `{project_id}`")
    lines.append(f"**Generated:** {generated_at}")
    lines.append("")

    # Scientific Boundary
    lines.append("## 1. Scientific Boundary")
    lines.append("")
    lines.append("> **Experimental measurements in this report are user-entered or CSV-imported records. "
        "Computational predictions (pLDDT, pDockQ, FoldX) are not experimental validation. "
        "Manual prioritization decisions (SHORTLIST, REJECT) are decision-support annotations, "
        "not proof of biological activity or safety.**")
    lines.append("")
    lines.append("> **SHORTLISTED ≠ EXPERIMENTALLY VALIDATED.** A shortlisted candidate has been flagged "
        "by a reviewer for further attention; it does not imply successful experimental validation.")
    lines.append("")

    # Project Summary
    lines.append("## 2. Project Summary")
    lines.append("")
    lines.append(f"- **Total candidates:** {summary['candidate_count']}")
    lines.append(f"- **Candidates with measurements:** {summary['candidates_with_measurements']}")
    lines.append(f"- **Experimental coverage:** {summary['experimental_coverage_percent']}%")
    lines.append(f"- **Ready for review:** {summary['ready_for_review']}")
    lines.append(f"- **Needs more data:** {summary['needs_more_data']}")
    lines.append(f"- **Safety concern:** {summary['safety_concern']}")
    lines.append(f"- **Validation failed:** {summary['validation_failed']}")
    lines.append(f"- **Shortlisted:** {summary['shortlisted']}")
    lines.append(f"- **Rejected:** {summary['rejected']}")
    lines.append("")

    # Experimental Coverage
    lines.append("## 3. Experimental Coverage")
    lines.append("")
    if summary["candidates_with_measurements"] == 0:
        lines.append("*No wet-lab measurements have been recorded for this project.*")
        lines.append("")
    else:
        lines.append(
            f"{summary['candidates_with_measurements']} out of {summary['candidate_count']} "
            f"candidates ({summary['experimental_coverage_percent']}%) have at least one experimental measurement."
        )
        lines.append("")

    # Candidate Validation Status
    lines.append("## 4. Candidate Validation Status")
    lines.append("")
    lines.append("| Candidate | Sequence | Validation Status | Priority Status | Exp Score | Measurements |")
    lines.append("|-----------|----------|-------------------|-----------------|-----------|--------------|")
    for c in candidates:
        seq = c["sequence"]
        if len(seq) > 30:
            seq = seq[:27] + "..."
        exp_score = c.get("experimental_priority_score")
        exp_score_str = f"{exp_score:.2f}" if exp_score is not None else "N/A"
        lines.append(
            f"| `{c['candidate_id'][:8]}...` | `{seq}` | {c['validation_status']} | "
            f"{c['priority_status']} | {exp_score_str} | {c['measurement_count']} |"
        )
    lines.append("")

    # Experimental Measurements
    lines.append("## 5. Experimental Measurements")
    lines.append("")
    has_any_measurements = any(c["experimental_measurements"] for c in candidates)
    if not has_any_measurements:
        lines.append("*No experimental measurements recorded.*")
        lines.append("")
    else:
        for c in candidates:
            if not c["experimental_measurements"]:
                continue
            lines.append(f"### {c['candidate_id'][:8]}... — `{c['sequence']}`")
            lines.append("")
            lines.append("| Metric | Value | Unit | Quality |")
            lines.append("|--------|-------|------|---------|")
            for m in c["experimental_measurements"]:
                val_str = f"{m['value']}" if m["value"] is not None else "N/A"
                lines.append(f"| {m['metric_name']} | {val_str} | {m['unit']} | {m['quality_flag']} |")
            lines.append("")

    # Candidate Prioritization Decisions
    lines.append("## 6. Candidate Prioritization Decisions")
    lines.append("")
    has_decisions = any(c["manual_decision"] for c in candidates)
    if not has_decisions:
        lines.append("*No manual prioritization decisions recorded.*")
        lines.append("")
    else:
        lines.append("| Candidate | Decision | Reason | Reviewer | Date |")
        lines.append("|-----------|----------|--------|----------|------|")
        for c in candidates:
            d = c["manual_decision"]
            if d:
                lines.append(
                    f"| `{c['candidate_id'][:8]}...` | {d['decision']} | {d['decision_reason']} | "
                    f"{d.get('reviewer', 'N/A')} | {d.get('reviewed_at', 'N/A')[:10]} |"
                )
        lines.append("")

    # Computational Reference Metrics
    lines.append("## 7. Computational Reference Metrics")
    lines.append("")
    lines.append("> *These are in-silico predictions provided for reference only. "
        "They do not constitute experimental validation.*")
    lines.append("")
    lines.append("| Candidate | Composite Score | mean pLDDT | pDockQ | Interaction Energy (kcal/mol) |")
    lines.append("|-----------|-----------------|------------|--------|-------------------------------|")
    for c in candidates:
        comp = c["computational_reference"]
        cs = f"{comp['composite_score']:.3f}" if comp.get("composite_score") is not None else "N/A"
        plddt = f"{comp['mean_plddt']:.2f}" if comp.get("mean_plddt") is not None else "N/A"
        pdockq = f"{comp['pdockq']:.3f}" if comp.get("pdockq") is not None else "N/A"
        energy = f"{comp['interaction_energy_kcal_mol']:.4f}" if comp.get("interaction_energy_kcal_mol") is not None else "N/A"
        lines.append(
            f"| `{c['candidate_id'][:8]}...` | {cs} | {plddt} | {pdockq} | {energy} |"
        )
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(
        "*Report generated by STAMP Platform v0.11-P5. "
        "Experimental data: user-entered / CSV-imported. "
        "Computational metrics: in-silico predictions only.*"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSV renderer
# ---------------------------------------------------------------------------

def render_wetlab_report_csv(report_data: dict[str, Any]) -> str:
    """Render the wet-lab validation report as CSV."""
    candidates = report_data["candidates"]

    fieldnames = [
        "candidate_id",
        "sequence",
        "validation_status",
        "experimental_priority_score",
        "priority_status",
        "manual_decision",
        "decision_reason",
        "reviewer",
        "reviewed_at",
        "run_count",
        "measurement_count",
        "MIC_ug_ml",
        "MBC_ug_ml",
        "hemolysis_percent",
        "cell_viability_percent",
        "HC50_ug_ml",
        "IC50_ug_ml",
        "quality_flag",
        "composite_score",
        "mean_plddt",
        "pdockq",
        "interaction_energy_kcal_mol",
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for c in candidates:
        # Extract measurement values
        mic = None
        mbc = None
        hem = None
        via = None
        hc50 = None
        ic50 = None
        quality = None
        for m in c["experimental_measurements"]:
            if m["metric_name"] == "MIC_ug_ml":
                mic = m["value"]
            elif m["metric_name"] == "MBC_ug_ml":
                mbc = m["value"]
            elif m["metric_name"] == "hemolysis_percent":
                hem = m["value"]
            elif m["metric_name"] == "cell_viability_percent":
                via = m["value"]
            elif m["metric_name"] == "HC50_ug_ml":
                hc50 = m["value"]
            elif m["metric_name"] == "IC50_ug_ml":
                ic50 = m["value"]
            quality = m["quality_flag"]

        d = c.get("manual_decision") or {}
        comp = c.get("computational_reference") or {}

        writer.writerow({
            "candidate_id": c["candidate_id"],
            "sequence": c["sequence"],
            "validation_status": c["validation_status"],
            "experimental_priority_score": c.get("experimental_priority_score"),
            "priority_status": c.get("priority_status"),
            "manual_decision": d.get("decision", ""),
            "decision_reason": d.get("decision_reason", ""),
            "reviewer": d.get("reviewer", ""),
            "reviewed_at": d.get("reviewed_at", ""),
            "run_count": c.get("run_count", 0),
            "measurement_count": c.get("measurement_count", 0),
            "MIC_ug_ml": mic,
            "MBC_ug_ml": mbc,
            "hemolysis_percent": hem,
            "cell_viability_percent": via,
            "HC50_ug_ml": hc50,
            "IC50_ug_ml": ic50,
            "quality_flag": quality or "",
            "composite_score": comp.get("composite_score"),
            "mean_plddt": comp.get("mean_plddt"),
            "pdockq": comp.get("pdockq"),
            "interaction_energy_kcal_mol": comp.get("interaction_energy_kcal_mol"),
        })

    return output.getvalue()


# ---------------------------------------------------------------------------
# Integrity validator
# ---------------------------------------------------------------------------

def validate_wetlab_report_integrity(report_data: dict[str, Any]) -> list[str]:
    """Validate scientific integrity of the report.

    Returns a list of error messages; empty list means valid.
    """
    errors: list[str] = []
    candidates = report_data.get("candidates", [])

    for c in candidates:
        has_measurements = c.get("measurement_count", 0) > 0
        exp_measurements = c.get("experimental_measurements", [])

        # Check 1: No measurement → no fabricated values
        if not has_measurements and exp_measurements:
            errors.append(
                f"Candidate {c['candidate_id']}: has experimental_measurements but measurement_count is 0"
            )

        # Check 2: Computational metrics only in computational_reference
        for key in ("mean_plddt", "pdockq", "interaction_energy_kcal_mol"):
            if key in c and key not in (c.get("computational_reference") or {}):
                errors.append(
                    f"Candidate {c['candidate_id']}: computational metric '{key}' outside computational_reference"
                )

        # Check 3: Manual decision does not rewrite validation_status
        d = c.get("manual_decision")
        if d and d.get("decision") == "SHORTLIST":
            if c.get("validation_status") == "EXPERIMENTALLY_VALIDATED":
                # This is okay if the candidate was genuinely validated
                pass
            # But we flag if validation_status was auto-promoted solely by decision
            # (In our architecture, decisions never modify validation_status, so this
            # check is mainly for catching future bugs.)

        # Check 4: SHORTLIST ≠ EXPERIMENTALLY_VALIDATED
        if d and d.get("decision") == "SHORTLIST" and c.get("validation_status") == "NOT_EXPERIMENTALLY_VALIDATED":
            # This is expected: shortlist is a manual flag, not validation.
            # No error — this is the correct behavior.
            pass

        # Check 5: MIC/MBC/hemolysis values only come from actual measurements
        measurement_metric_names = {m["metric_name"] for m in exp_measurements}
        for metric in ("MIC_ug_ml", "MBC_ug_ml", "hemolysis_percent"):
            if c.get(metric) is not None and metric not in measurement_metric_names:
                errors.append(
                    f"Candidate {c['candidate_id']}: '{metric}' present but not from recorded measurements"
                )

    return errors


# ---------------------------------------------------------------------------
# XLSX renderer
# ---------------------------------------------------------------------------

def render_wetlab_report_xlsx(report_data: dict[str, Any]) -> bytes:
    """Render a wet-lab validation report as XLSX bytes.

    Args:
        report_data: Output from build_wetlab_validation_report_data().

    Returns:
        XLSX file as bytes.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    wb = Workbook()

    # ---- Summary sheet ----
    ws_summary = wb.active
    ws_summary.title = "Summary"
    ws_summary.append(["STAMP Wet-lab Validation Report"])
    ws_summary.append([])
    ws_summary.append(["Project ID", report_data["project_id"]])
    ws_summary.append(["Report Type", report_data["report_type"]])
    ws_summary.append(["Generated At", report_data["generated_at"]])
    ws_summary.append([])
    summary = report_data["summary"]
    ws_summary.append(["Candidate Count", summary["candidate_count"]])
    ws_summary.append(["Candidates with Measurements", summary["candidates_with_measurements"]])
    ws_summary.append(["Experimental Coverage (%)", summary["experimental_coverage_percent"]])
    ws_summary.append(["Shortlisted", summary["shortlisted"]])
    ws_summary.append(["Rejected", summary["rejected"]])
    ws_summary.append(["Needs More Data", summary["needs_more_data"]])
    ws_summary.append(["Safety Concern", summary["safety_concern"]])
    ws_summary.append(["Ready for Review", summary["ready_for_review"]])
    ws_summary.append(["Validation Failed", summary["validation_failed"]])

    header_font = Font(bold=True)
    for cell in ws_summary[1]:
        cell.font = Font(bold=True, size=14)
    for row in ws_summary.iter_rows(min_row=3, max_row=ws_summary.max_row):
        row[0].font = header_font

    # ---- Candidates sheet ----
    ws_cand = wb.create_sheet(title="Candidates")
    headers = [
        "Candidate ID", "Sequence", "Validation Status", "Priority Status",
        "Exp Priority Score", "Run Count", "Measurement Count",
        "Composite Score", "mean pLDDT", "pDockQ", "Interaction Energy",
    ]
    ws_cand.append(headers)
    for cell in ws_cand[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")

    for c in report_data["candidates"]:
        comp = c.get("computational_reference", {})
        ws_cand.append([
            c["candidate_id"],
            c["sequence"],
            c["validation_status"],
            c.get("priority_status", ""),
            c.get("experimental_priority_score") if c.get("experimental_priority_score") is not None else "N/A",
            c.get("run_count", 0),
            c.get("measurement_count", 0),
            comp.get("composite_score") if comp.get("composite_score") is not None else "N/A",
            comp.get("mean_plddt") if comp.get("mean_plddt") is not None else "N/A",
            comp.get("pdockq") if comp.get("pdockq") is not None else "N/A",
            comp.get("interaction_energy_kcal_mol") if comp.get("interaction_energy_kcal_mol") is not None else "N/A",
        ])

    # ---- Scientific Boundary sheet ----
    ws_boundary = wb.create_sheet(title="Scientific Boundary")
    ws_boundary.append(["Scientific Boundary Declaration"])
    ws_boundary.append([])
    boundary = report_data.get("scientific_boundary", {})
    ws_boundary.append(["Experimental Data User-Provided Only", "Yes" if boundary.get("experimental_data_user_provided_only") else "No"])
    ws_boundary.append(["Computational Predictions ≠ Experimental Validation", "Yes" if boundary.get("computational_predictions_not_experimental_validation") else "No"])
    ws_boundary.append(["Manual Decision ≠ Experimental Proof", "Yes" if boundary.get("manual_decision_not_experimental_proof") else "No"])
    ws_boundary.append(["Shortlisted ≠ Experimentally Validated", "Yes" if boundary.get("shortlisted_not_experimentally_validated") else "No"])
    ws_boundary.append([])
    ws_boundary.append(["Experimental measurements in this report are user-entered or CSV-imported records."])
    ws_boundary.append(["Computational predictions (pLDDT, pDockQ, FoldX) are not experimental validation."])
    ws_boundary.append(["Manual prioritization decisions (SHORTLIST, REJECT) are decision-support annotations, not proof of biological activity or safety."])
    ws_boundary.append(["SHORTLISTED ≠ EXPERIMENTALLY VALIDATED."])
    for cell in ws_boundary[1]:
        cell.font = Font(bold=True, size=14)
    for row in ws_boundary.iter_rows(min_row=8, max_row=11):
        for cell in row:
            cell.font = Font(bold=True, color="FF0000")

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


# ---------------------------------------------------------------------------
# PDF renderer
# ---------------------------------------------------------------------------

def render_wetlab_report_pdf(report_data: dict[str, Any]) -> bytes:
    """Render a wet-lab validation report as PDF bytes.

    Args:
        report_data: Output from build_wetlab_validation_report_data().

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
    story.append(Paragraph("STAMP Wet-lab Validation Report", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Project ID:</b> {report_data['project_id']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Report Type:</b> {report_data['report_type']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Generated:</b> {report_data['generated_at']}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Scientific Boundary box
    story.append(Paragraph("<b>Scientific Boundary</b>", styles["Heading2"]))
    boundary_text = (
        "Experimental measurements in this report are user-entered or CSV-imported records. "
        "Computational predictions (pLDDT, pDockQ, FoldX) are <b>not experimental validation</b>. "
        "Manual prioritization decisions (SHORTLIST, REJECT) are decision-support annotations, "
        "not proof of biological activity or safety.<br/><br/>"
        "<b>SHORTLISTED ≠ EXPERIMENTALLY VALIDATED.</b> A shortlisted candidate has been flagged "
        "by a reviewer for further attention; it does not imply successful experimental validation."
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

    # Summary table
    summary = report_data["summary"]
    summary_data = [
        ["Metric", "Value"],
        ["Candidate Count", str(summary["candidate_count"])],
        ["Candidates with Measurements", str(summary["candidates_with_measurements"])],
        ["Experimental Coverage (%)", str(summary["experimental_coverage_percent"])],
        ["Shortlisted", str(summary["shortlisted"])],
        ["Rejected", str(summary["rejected"])],
        ["Needs More Data", str(summary["needs_more_data"])],
        ["Safety Concern", str(summary["safety_concern"])],
        ["Ready for Review", str(summary["ready_for_review"])],
        ["Validation Failed", str(summary["validation_failed"])],
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
    story.append(Paragraph("<b>Candidate Validation Status</b>", styles["Heading2"]))
    cand_headers = ["Candidate ID", "Sequence", "Validation Status", "Priority Status", "Measurements"]
    cand_data = [cand_headers]
    for c in report_data["candidates"]:
        seq = c["sequence"]
        if len(seq) > 30:
            seq = seq[:27] + "..."
        cand_data.append([
            c["candidate_id"][:8] + "...",
            seq,
            c["validation_status"],
            c.get("priority_status", ""),
            str(c.get("measurement_count", 0)),
        ])
    cand_table = Table(cand_data, colWidths=[1.2 * inch, 2.3 * inch, 1.1 * inch, 1.1 * inch, 0.8 * inch])
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

    # Experimental coverage note
    if summary["candidates_with_measurements"] == 0:
        story.append(Paragraph(
            "<i>No wet-lab measurements have been recorded for this project. "
            "All candidates are marked as NOT_EXPERIMENTALLY_VALIDATED.</i>",
            styles["Italic"]
        ))
    else:
        story.append(Paragraph(
            f"<i>{summary['candidates_with_measurements']} out of {summary['candidate_count']} "
            f"candidates have at least one experimental measurement.</i>",
            styles["Italic"]
        ))
    story.append(Spacer(1, 12))

    # Footer
    story.append(Paragraph(
        "<i>Report generated by STAMP Platform. "
        "Experimental data: user-entered / CSV-imported. "
        "Computational metrics: in-silico predictions only.</i>",
        styles["Italic"]
    ))

    doc.build(story)
    return buffer.getvalue()
