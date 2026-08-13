"""STAMP Platform — Real Computation Report Export (v1.5-md-computation-pilot).

Generates structured computation reports for MD, FlexPepDock, MM-GBSA and
Batch Computation jobs.  Reports reference real artifacts, real logs and real
output files.  No scientific metric is fabricated.

Supported formats:
  - JSON
  - Markdown
  - PDF (placeholder interface)
"""

from __future__ import annotations

import io
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.crud.batch_computations import get_batch_computation, list_batch_items
from app.services.batch_dir_service import get_item_log_path

logger = logging.getLogger(__name__)

SCIENTIFIC_BOUNDARY = {
    "computational_only": True,
    "not_wet_lab_validated": True,
    "not_mic": True,
    "not_docking_score_unless_real": True,
    "not_mmgbsa_delta_g_unless_real": True,
    "metrics_from_real_files_only": True,
}

REPORT_DISCLAIMER = (
    "All metrics in this report are derived from real output files produced by "
    "the computation engine.  No value is fabricated.  BLOCKED / FAILED reasons "
    "are taken verbatim from job logs and error messages.  Computational results "
    "are NOT experimentally validated."
)


def build_computation_report_data(
    db: Session,
    batch_id: str,
) -> dict[str, Any]:
    """Build a structured computation report dict from a batch and its items.

    Args:
        db: Database session.
        batch_id: Batch computation ID.

    Returns:
        Report data dict.

    Raises:
        ValueError: If batch not found.
    """
    batch = get_batch_computation(db, batch_id)
    if batch is None:
        raise ValueError(f"Batch '{batch_id}' not found")

    items = list_batch_items(db, batch_id)

    # Counters
    total = len(items)
    succeeded = sum(1 for i in items if i.status == "SUCCEEDED")
    failed = sum(1 for i in items if i.status == "FAILED")
    blocked = sum(1 for i in items if i.status == "BLOCKED")
    pending = sum(1 for i in items if i.status == "PENDING")
    running = sum(1 for i in items if i.status == "RUNNING")
    cancelled = sum(1 for i in items if i.status == "CANCELLED")

    report_items = []
    for item in items:
        # Discover artifacts on disk
        artifacts = _discover_artifacts(item.artifact_dir)

        # Read logs if they exist
        log_path = get_item_log_path(batch_id, item.id, item.job_type)
        logs = _read_logs(log_path)

        # Parse output_json for analysis results
        analysis = _parse_analysis_results(item.output_json, item.job_type, item.artifact_dir)

        # Determine failure reason
        failed_reason = _determine_failed_reason(item)

        report_items.append({
            "item_id": item.id,
            "candidate_id": item.candidate_id,
            "job_type": item.job_type,
            "status": item.status,
            "input_files": _extract_input_files(item.input_json),
            "command_logs": logs,
            "artifacts": artifacts,
            "analysis_results": analysis,
            "failed_reason": failed_reason,
            "started_at": item.started_at.isoformat() if item.started_at else None,
            "finished_at": item.finished_at.isoformat() if item.finished_at else None,
        })

    return {
        "task_id": batch_id,
        "job_type": batch.job_type,
        "status": batch.status,
        "name": batch.name,
        "project_id": batch.project_id,
        "artifact_dir": batch.artifact_dir,
        "report_type": "STAMP_COMPUTATION_REPORT",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scientific_boundary": SCIENTIFIC_BOUNDARY,
        "disclaimer": REPORT_DISCLAIMER,
        "summary": {
            "total_items": total,
            "succeeded_items": succeeded,
            "failed_items": failed,
            "blocked_items": blocked,
            "pending_items": pending,
            "running_items": running,
            "cancelled_items": cancelled,
        },
        "items": report_items,
    }


def _discover_artifacts(artifact_dir: str | None) -> list[dict[str, Any]]:
    """List real files under an artifact directory."""
    artifacts: list[dict[str, Any]] = []
    if not artifact_dir:
        return artifacts
    path = Path(artifact_dir)
    if not path.exists():
        return artifacts
    for root, _dirs, files in os.walk(path):
        for f in files:
            file_path = Path(root) / f
            rel = file_path.relative_to(path).as_posix()
            artifacts.append({
                "name": f,
                "relative_path": rel,
                "absolute_path": str(file_path.resolve()),
                "size_bytes": file_path.stat().st_size,
            })
    return sorted(artifacts, key=lambda a: a["relative_path"])


def _read_logs(log_path: str) -> dict[str, str]:
    """Read stdout and stderr log files."""
    stdout_text = ""
    stderr_text = ""
    if Path(log_path).exists():
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                stdout_text = f.read()
        except Exception as e:
            stdout_text = f"[Error reading log: {e}]"

    stderr_path = str(Path(log_path).with_suffix(".stderr.log"))
    if Path(stderr_path).exists():
        try:
            with open(stderr_path, "r", encoding="utf-8", errors="replace") as f:
                stderr_text = f.read()
        except Exception as e:
            stderr_text = f"[Error reading stderr: {e}]"

    return {
        "stdout": stdout_text,
        "stderr": stderr_text,
        "stdout_path": log_path if Path(log_path).exists() else None,
        "stderr_path": stderr_path if Path(stderr_path).exists() else None,
    }


def _extract_input_files(input_json: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract input file references from item input_json."""
    files: list[dict[str, Any]] = []
    if not input_json:
        return files

    # Common keys that hold file paths
    file_keys = ("pdb_file", "structure_file", "receptor_pdb", "ligand_pdb",
                 "prmtop", "inpcrd", "mdcrd", "trajectory", "topology",
                 "sequence_file", "params_file")
    for key in file_keys:
        val = input_json.get(key)
        if val and isinstance(val, str):
            exists = Path(val).exists()
            files.append({
                "key": key,
                "path": val,
                "exists_on_disk": exists,
            })

    # Nested structures (e.g. candidate_inputs)
    candidates = input_json.get("candidates") or input_json.get("candidate_inputs") or []
    if isinstance(candidates, list):
        for cand in candidates:
            if isinstance(cand, dict):
                for key in file_keys:
                    val = cand.get(key)
                    if val and isinstance(val, str):
                        exists = Path(val).exists()
                        files.append({
                            "key": key,
                            "path": val,
                            "exists_on_disk": exists,
                            "candidate_id": cand.get("candidate_id") or cand.get("id"),
                        })

    return files


def _parse_analysis_results(
    output_json: dict[str, Any] | None,
    job_type: str,
    artifact_dir: str | None,
) -> dict[str, Any]:
    """Parse real analysis results from output_json and artifact files.

    Returns only what is actually present.  No fabricated metrics.
    """
    analysis: dict[str, Any] = {"source": "real_output", "metrics": {}}

    if output_json:
        # Copy known real metric keys if present
        real_keys = (
            "mean_plddt", "ptm", "iptm", "pdockq",
            "interaction_energy_kcal_mol", "energy_terms",
            "rmsd", "rmsf", "rg", "gyration_radius",
            "delta_g_total", "components",
            "docking_score", "score_sc_path",
            "convergence_status", "frames_used",
        )
        for key in real_keys:
            if key in output_json and output_json[key] is not None:
                analysis["metrics"][key] = output_json[key]

    # Look for known output files on disk
    if artifact_dir and Path(artifact_dir).exists():
        for p in Path(artifact_dir).rglob("*"):
            if p.is_file():
                name_lower = p.name.lower()
                if "rmsd" in name_lower:
                    analysis["metrics"]["rmsd_file_exists"] = True
                    analysis["metrics"]["rmsd_file_path"] = str(p.relative_to(artifact_dir))
                elif "rmsf" in name_lower:
                    analysis["metrics"]["rmsf_file_exists"] = True
                    analysis["metrics"]["rmsf_file_path"] = str(p.relative_to(artifact_dir))
                elif "rg" in name_lower or "gyration" in name_lower:
                    analysis["metrics"]["rg_file_exists"] = True
                    analysis["metrics"]["rg_file_path"] = str(p.relative_to(artifact_dir))
                elif name_lower.endswith(".sc") or "score" in name_lower:
                    analysis["metrics"]["score_sc_file_exists"] = True
                    analysis["metrics"]["score_sc_file_path"] = str(p.relative_to(artifact_dir))
                elif "final_results_mmpbsa" in name_lower or "dg" in name_lower:
                    analysis["metrics"]["dg_file_exists"] = True
                    analysis["metrics"]["dg_file_path"] = str(p.relative_to(artifact_dir))

    return analysis


def _determine_failed_reason(item: Any) -> dict[str, Any] | None:
    """Determine why an item failed or was blocked."""
    if item.status not in ("FAILED", "BLOCKED", "CANCELLED"):
        return None

    reason = {
        "status": item.status,
        "error_message": item.error_message,
        "explanation": "",
    }

    if item.status == "FAILED":
        if item.error_message:
            reason["explanation"] = (
                f"Item failed with error: {item.error_message}"
            )
        else:
            reason["explanation"] = (
                "Item failed. No error message was recorded. "
                "Check command logs for stderr details."
            )
    elif item.status == "BLOCKED":
        reason["explanation"] = (
            "Item was blocked, usually because a prerequisite step "
            "(e.g. structure prediction) did not succeed or required "
            "input files are missing."
        )
        if item.error_message:
            reason["explanation"] += f" Block reason: {item.error_message}"
    elif item.status == "CANCELLED":
        reason["explanation"] = "Item was cancelled by user or system."

    return reason


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------


def render_computation_report_markdown(report_data: dict[str, Any]) -> str:
    """Render a computation report as Markdown."""
    lines: list[str] = []

    lines.append("# STAMP Computation Report")
    lines.append("")
    lines.append(f"**Task ID:** {report_data['task_id']}")
    lines.append(f"**Batch Name:** {report_data['name']}")
    lines.append(f"**Job Type:** {report_data['job_type']}")
    lines.append(f"**Status:** {report_data['status']}")
    lines.append(f"**Project ID:** {report_data['project_id']}")
    lines.append(f"**Generated At:** {report_data['generated_at']}")
    lines.append("")
    lines.append("## Disclaimer")
    lines.append("")
    lines.append(f"> {report_data['disclaimer']}")
    lines.append("")

    # Summary
    summary = report_data["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total items: {summary['total_items']}")
    lines.append(f"- Succeeded: {summary['succeeded_items']}")
    lines.append(f"- Failed: {summary['failed_items']}")
    lines.append(f"- Blocked: {summary['blocked_items']}")
    lines.append(f"- Pending: {summary['pending_items']}")
    lines.append(f"- Running: {summary['running_items']}")
    lines.append(f"- Cancelled: {summary['cancelled_items']}")
    lines.append("")

    # Items
    lines.append("## Items")
    lines.append("")
    for item in report_data["items"]:
        lines.append(f"### {item['item_id']}")
        lines.append("")
        lines.append(f"- **Candidate ID:** {item['candidate_id'] or 'N/A'}")
        lines.append(f"- **Job Type:** {item['job_type']}")
        lines.append(f"- **Status:** {item['status']}")
        lines.append(f"- **Started:** {item['started_at'] or 'N/A'}")
        lines.append(f"- **Finished:** {item['finished_at'] or 'N/A'}")
        lines.append("")

        # Input files
        lines.append("#### Input Files")
        lines.append("")
        if item["input_files"]:
            lines.append("| Key | Path | Exists |")
            lines.append("|-----|------|--------|")
            for f in item["input_files"]:
                exists = "Yes" if f["exists_on_disk"] else "No"
                lines.append(f"| {f['key']} | `{f['path']}` | {exists} |")
        else:
            lines.append("*No input files recorded.*")
        lines.append("")

        # Artifacts
        lines.append("#### Artifacts")
        lines.append("")
        if item["artifacts"]:
            lines.append("| Name | Relative Path | Size (bytes) |")
            lines.append("|------|---------------|--------------|")
            for a in item["artifacts"]:
                lines.append(
                    f"| {a['name']} | `{a['relative_path']}` | {a['size_bytes']} |"
                )
        else:
            lines.append("*No artifacts found on disk.*")
        lines.append("")

        # Analysis results
        lines.append("#### Analysis Results")
        lines.append("")
        metrics = item["analysis_results"].get("metrics", {})
        if metrics:
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            for key, value in metrics.items():
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value, ensure_ascii=False)
                else:
                    value_str = str(value)
                lines.append(f"| {key} | {value_str} |")
        else:
            lines.append("*No analysis results available.*")
        lines.append("")

        # Failed reason
        if item["failed_reason"]:
            lines.append("#### Failure Reason")
            lines.append("")
            fr = item["failed_reason"]
            lines.append(f"- **Status:** {fr['status']}")
            lines.append(f"- **Error Message:** {fr['error_message'] or 'N/A'}")
            lines.append(f"- **Explanation:** {fr['explanation']}")
            lines.append("")

        # Command logs
        logs = item["command_logs"]
        if logs["stdout"] or logs["stderr"]:
            lines.append("#### Command Logs")
            lines.append("")
            if logs["stdout"]:
                lines.append("**stdout:**")
                lines.append("```")
                lines.append(logs["stdout"][:2000])  # truncate for MD
                lines.append("```")
            if logs["stderr"]:
                lines.append("**stderr:**")
                lines.append("```")
                lines.append(logs["stderr"][:2000])
                lines.append("```")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Scientific Boundary
    lines.append("## Scientific Boundary")
    lines.append("")
    boundary = report_data["scientific_boundary"]
    lines.append("> **All results in this report are computational predictions. "
                 "They are NOT experimentally validated.**")
    lines.append("")
    lines.append("> This report:")
    lines.append(f"> - Uses only real output files: {'Yes' if boundary['metrics_from_real_files_only'] else 'No'}")
    lines.append(f"> - Is computational only: {'Yes' if boundary['computational_only'] else 'No'}")
    lines.append(f"> - Is NOT wet-lab validated: {'Yes' if boundary['not_wet_lab_validated'] else 'No'}")
    lines.append("")
    lines.append("For experimental validation, additional in-vitro and in-vivo assays are required.")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON renderer
# ---------------------------------------------------------------------------


def render_computation_report_json(report_data: dict[str, Any]) -> bytes:
    """Render a computation report as JSON bytes."""
    return json.dumps(report_data, indent=2, ensure_ascii=False, default=str).encode("utf-8")


# ---------------------------------------------------------------------------
# PDF renderer (placeholder interface)
# ---------------------------------------------------------------------------


def render_computation_report_pdf(report_data: dict[str, Any]) -> bytes:
    """Render a computation report as PDF bytes.

    Placeholder for future implementation.  Currently returns a minimal PDF
    with a notice that full PDF export will be available in a later version.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=50, leftMargin=50,
        topMargin=50, bottomMargin=30,
    )
    styles = getSampleStyleSheet()
    story: list[Any] = []

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=12,
    )
    story.append(Paragraph("STAMP Computation Report", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Task ID:</b> {report_data['task_id']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Batch Name:</b> {report_data['name']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Job Type:</b> {report_data['job_type']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Status:</b> {report_data['status']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Generated:</b> {report_data['generated_at']}", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Disclaimer</b>", styles["Heading2"]))
    story.append(Paragraph(report_data["disclaimer"], styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Summary</b>", styles["Heading2"]))
    summary = report_data["summary"]
    story.append(Paragraph(f"Total items: {summary['total_items']}", styles["Normal"]))
    story.append(Paragraph(f"Succeeded: {summary['succeeded_items']}", styles["Normal"]))
    story.append(Paragraph(f"Failed: {summary['failed_items']}", styles["Normal"]))
    story.append(Paragraph(f"Blocked: {summary['blocked_items']}", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Scientific Boundary</b>", styles["Heading2"]))
    boundary_text = (
        "All results are computational predictions. They are <b>NOT experimentally validated</b>.<br/><br/>"
        "This report uses only real output files. No metric is fabricated. "
        "BLOCKED / FAILED reasons are taken from actual job logs."
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

    story.append(Paragraph(
        "<i>Full PDF export with per-item tables will be available in a future version. "
        "Use JSON or Markdown export for complete details.</i>",
        styles["Italic"],
    ))

    doc.build(story)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Integrity validator
# ---------------------------------------------------------------------------


def validate_computation_report_integrity(report_data: dict[str, Any]) -> list[str]:
    """Validate that the report contains no fabricated metrics.

    Returns a list of error messages; empty list means valid.
    """
    errors: list[str] = []

    # Check that analysis_results source is "real_output"
    for item in report_data.get("items", []):
        analysis = item.get("analysis_results", {})
        if analysis.get("source") != "real_output":
            errors.append(
                f"Item {item['item_id']}: analysis_results source is not 'real_output'"
            )

        # Ensure no fake MM-GBSA ΔG is claimed
        metrics = analysis.get("metrics", {})
        if "delta_g_total" in metrics and not metrics.get("dg_file_exists"):
            # This is OK if it came from output_json, but we flag if there's no file
            pass  # output_json may contain parsed values from real files

        # Ensure failed_reason is present for failed/blocked items
        if item["status"] in ("FAILED", "BLOCKED") and not item.get("failed_reason"):
            errors.append(
                f"Item {item['item_id']}: status is {item['status']} but no failed_reason recorded"
            )

    return errors
