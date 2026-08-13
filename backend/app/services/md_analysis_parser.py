"""MD Analysis Parser Service (v1.5 P3).

Parses real MD output files (GROMACS .xvg) to extract RMSD, RMSF, Rg.

Scientific boundaries:
- No fabricated metrics.
- Only parses files that exist.
- Returns None for missing files.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("stamp")


@dataclass
class XvgData:
    """Parsed data from a GROMACS .xvg file."""
    title: Optional[str]
    xlabel: Optional[str]
    ylabel: Optional[str]
    legend: list[str]
    time: list[float]
    columns: list[list[float]]

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "xlabel": self.xlabel,
            "ylabel": self.ylabel,
            "legend": self.legend,
            "time": self.time,
            "columns": self.columns,
        }


def parse_xvg(xvg_path: str) -> Optional[XvgData]:
    """Parse a GROMACS .xvg file.

    Returns None if file does not exist or is empty.
    """
    if not os.path.isfile(xvg_path):
        return None

    title: Optional[str] = None
    xlabel: Optional[str] = None
    ylabel: Optional[str] = None
    legend: list[str] = []
    time: list[float] = []
    columns: list[list[float]] = []

    try:
        with open(xvg_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    continue
                if line.startswith("@"):
                    parts = line[1:].strip().split(None, 1)
                    if len(parts) >= 2:
                        key = parts[0]
                        value = parts[1].strip('"')
                        if key == "title":
                            title = value
                        elif key == "xaxis":
                            xlabel = value
                        elif key == "yaxis":
                            ylabel = value
                        elif key == "legend":
                            legend.append(value)
                    continue
                # Data line
                vals = [float(v) for v in line.split()]
                if len(vals) >= 2:
                    time.append(vals[0])
                    if not columns:
                        columns = [[] for _ in range(len(vals) - 1)]
                    for i, v in enumerate(vals[1:]):
                        columns[i].append(v)
    except (OSError, ValueError) as exc:
        logger.warning("Failed to parse %s: %s", xvg_path, exc)
        return None

    if not time:
        return None

    return XvgData(
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
        legend=legend,
        time=time,
        columns=columns,
    )


@dataclass
class MdAnalysisResult:
    """Result of MD analysis for a completed MD simulation."""
    status: str  # "SUCCEEDED" | "FAILED" | "BLOCKED"
    rmsd: Optional[dict]  # XvgData.to_dict()
    rmsf: Optional[dict]  # XvgData.to_dict()
    rg: Optional[dict]    # XvgData.to_dict()
    error: Optional[str]
    artifact_dir: str

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "rmsd": self.rmsd,
            "rmsf": self.rmsf,
            "rg": self.rg,
            "error": self.error,
            "artifact_dir": self.artifact_dir,
        }


def analyze_md_pilot(artifact_dir: str) -> MdAnalysisResult:
    """Analyze MD pilot artifacts in the given directory.

    Expected files:
      - analysis/rmsd.xvg
      - analysis/rmsf.xvg
      - analysis/rg.xvg

    Returns SUCCEEDED only if all files exist and parse successfully.
    """
    rmsd_path = os.path.join(artifact_dir, "analysis", "rmsd.xvg")
    rmsf_path = os.path.join(artifact_dir, "analysis", "rmsf.xvg")
    rg_path = os.path.join(artifact_dir, "analysis", "rg.xvg")

    missing: list[str] = []
    for label, path in (("rmsd", rmsd_path), ("rmsf", rmsf_path), ("rg", rg_path)):
        if not os.path.isfile(path):
            missing.append(label)

    if missing:
        err = f"Missing analysis files: {', '.join(missing)}"
        logger.warning("MD analysis BLOCKED: %s", err)
        return MdAnalysisResult(
            status="BLOCKED",
            rmsd=None,
            rmsf=None,
            rg=None,
            error=err,
            artifact_dir=artifact_dir,
        )

    rmsd_data = parse_xvg(rmsd_path)
    rmsf_data = parse_xvg(rmsf_path)
    rg_data = parse_xvg(rg_path)

    failed: list[str] = []
    if rmsd_data is None:
        failed.append("rmsd")
    if rmsf_data is None:
        failed.append("rmsf")
    if rg_data is None:
        failed.append("rg")

    if failed:
        err = f"Failed to parse: {', '.join(failed)}"
        logger.warning("MD analysis FAILED: %s", err)
        return MdAnalysisResult(
            status="FAILED",
            rmsd=rmsd_data.to_dict() if rmsd_data else None,
            rmsf=rmsf_data.to_dict() if rmsf_data else None,
            rg=rg_data.to_dict() if rg_data else None,
            error=err,
            artifact_dir=artifact_dir,
        )

    logger.info("MD analysis SUCCEEDED for %s", artifact_dir)
    return MdAnalysisResult(
        status="SUCCEEDED",
        rmsd=rmsd_data.to_dict(),
        rmsf=rmsf_data.to_dict(),
        rg=rg_data.to_dict(),
        error=None,
        artifact_dir=artifact_dir,
    )
