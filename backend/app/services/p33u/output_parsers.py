"""P33U per-model output parsers.

Each parser reads a model's output directory and extracts:
    - candidate sequences (list[str])
    - structure PDBs (list[str])
    - metrics (dict[str, float])
    - logs (list[str])
    - empty (bool)  -> True if no usable artifacts found

Empty output is NEVER marked success: the runner closes the gate FAILED when
`empty` is True.

These parsers are pure file I/O + CSV/JSON parsing. They do NOT import torch,
do NOT call GPU/8189, do NOT load checkpoints. Tests use fixed fixtures
written into tmp_path — never real model output.

All parsed results are tagged NOT_EXPERIMENTALLY_VALIDATED /
COMPUTATIONAL_PREDICTION_ONLY via the runner's provenance writer.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from typing import Any

from .config import PREDICTION_TAG, VALIDATION_STATUS


@dataclass
class ParsedOutput:
    model_id: str
    candidates: list[str] = field(default_factory=list)
    pdbs: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    empty: bool = True
    validation_status: str = VALIDATION_STATUS
    prediction_tag: str = PREDICTION_TAG

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "candidates": self.candidates,
            "pdbs": self.pdbs,
            "metrics": self.metrics,
            "logs": self.logs,
            "empty": self.empty,
            "validation_status": self.validation_status,
            "prediction_tag": self.prediction_tag,
        }


def _list_files(root: str, suffix: str) -> list[str]:
    if not os.path.isdir(root):
        return []
    out: list[str] = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.endswith(suffix):
                out.append(os.path.join(dirpath, f))
    return sorted(out)


def _read_csv_rows(path: str) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# PepMLM — candidate_sequences.csv
# ---------------------------------------------------------------------------
def parse_pepmlm(output_dir: str) -> ParsedOutput:
    """PepMLM writes output/candidate_sequences.csv with a 'sequence' column."""
    out = ParsedOutput(model_id="pepmlm")
    csv_path = os.path.join(output_dir, "candidate_sequences.csv")
    logs = _list_files(output_dir, ".log")
    out.logs = logs
    if os.path.isfile(csv_path) and os.path.getsize(csv_path) > 0:
        try:
            rows = _read_csv_rows(csv_path)
        except Exception:
            return out
        for r in rows:
            seq = r.get("sequence") or r.get("peptide") or r.get("candidate")
            if seq:
                out.candidates.append(seq.strip())
        # metrics: any numeric columns
        for r in rows[:1]:
            for k, v in r.items():
                if k in ("sequence", "peptide", "candidate"):
                    continue
                try:
                    out.metrics[k] = float(v)
                except (TypeError, ValueError):
                    pass
    out.empty = len(out.candidates) == 0
    return out


# ---------------------------------------------------------------------------
# DiffPepBuilder — postprocess_results.csv + inference PDBs
# ---------------------------------------------------------------------------
def parse_diffpepbuilder(output_dir: str) -> ParsedOutput:
    """DiffPepBuilder writes runs/inference/postprocess_results.csv and
    per-case PDB files. The runner copies these into output_dir; the parser
    looks in both output_dir and output_dir/runs/inference."""
    out = ParsedOutput(model_id="diffpepbuilder")
    logs = _list_files(output_dir, ".log")
    out.logs = logs
    candidates: list[str] = []
    for csv_name in ("postprocess_results.csv", "metadata_test.csv"):
        for base in (output_dir, os.path.join(output_dir, "runs", "inference")):
            p = os.path.join(base, csv_name)
            if os.path.isfile(p) and os.path.getsize(p) > 0:
                try:
                    rows = _read_csv_rows(p)
                except Exception:
                    continue
                for r in rows:
                    seq = r.get("sequence") or r.get("peptide") or r.get("design")
                    if seq:
                        candidates.append(seq.strip())
                    for k, v in r.items():
                        if k in ("sequence", "peptide", "design", "case", "sample", "pdb"):
                            continue
                        try:
                            out.metrics[k] = float(v)
                        except (TypeError, ValueError):
                            pass
                break
    out.candidates = candidates
    out.pdbs = _list_files(output_dir, ".pdb")
    out.empty = len(out.candidates) == 0 and len(out.pdbs) == 0
    return out


# ---------------------------------------------------------------------------
# PepFlow — outputs.csv + outputs/*.pt
# ---------------------------------------------------------------------------
def parse_pepflow(output_dir: str) -> ParsedOutput:
    """PepFlow writes output/outputs.csv (tran/rot/aar/len) and output/outputs/<id>.pt."""
    out = ParsedOutput(model_id="pepflow")
    logs = _list_files(output_dir, ".log")
    out.logs = logs
    csv_path = os.path.join(output_dir, "outputs.csv")
    pts = _list_files(os.path.join(output_dir, "outputs"), ".pt")
    out.pdbs = pts  # .pt trajectories (no PDB per se; reuse field)
    if os.path.isfile(csv_path) and os.path.getsize(csv_path) > 0:
        try:
            rows = _read_csv_rows(csv_path)
        except Exception:
            rows = []
        for r in rows:
            for k, v in r.items():
                try:
                    out.metrics[k] = float(v)
                except (TypeError, ValueError):
                    pass
        # PepFlow outputs structures; a non-empty csv counts as non-empty.
        out.candidates = [str(r.get("name", "")) for r in rows if r.get("name")]
    out.empty = len(out.metrics) == 0 and len(pts) == 0
    return out


# ---------------------------------------------------------------------------
# PepHAR — test.csv + gen_*.pdb / gt.pdb
# ---------------------------------------------------------------------------
def parse_pephar(output_dir: str) -> ParsedOutput:
    """PepHAR writes <project_root>/<pdb_path>/test.csv (rmsd/recovery/...) and
    <name>/gen_*.pdb, <name>/gt.pdb. The runner redirects project_root to
    output_dir, so the parser looks there."""
    out = ParsedOutput(model_id="pephar")
    logs = _list_files(output_dir, ".log")
    out.logs = logs
    # find test.csv anywhere under output_dir
    test_csv = ""
    for dirpath, _d, files in os.walk(output_dir):
        if "test.csv" in files:
            test_csv = os.path.join(dirpath, "test.csv")
            break
    if test_csv and os.path.getsize(test_csv) > 0:
        try:
            rows = _read_csv_rows(test_csv)
        except Exception:
            rows = []
        for r in rows:
            for k, v in r.items():
                try:
                    out.metrics[k] = float(v)
                except (TypeError, ValueError):
                    pass
    out.pdbs = _list_files(output_dir, ".pdb")
    # gen PDB filenames encode the designed structure; treat as candidates
    out.candidates = [os.path.basename(p) for p in out.pdbs if "gen" in os.path.basename(p)]
    out.empty = len(out.metrics) == 0 and len(out.pdbs) == 0
    return out


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_PARSERS = {
    "pepmlm": parse_pepmlm,
    "diffpepbuilder": parse_diffpepbuilder,
    "pepflow": parse_pepflow,
    "pephar": parse_pephar,
}


def parse_output(model_id: str, output_dir: str) -> dict[str, Any]:
    if model_id not in _PARSERS:
        raise KeyError(f"no parser for {model_id!r}")
    return _PARSERS[model_id](output_dir).to_dict()
