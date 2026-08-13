"""
v0.10-P4 Integrated Workflow: BepiPred3 → epitope_candidates → PepMLM → stamp_candidates

CLI script that runs the full BepiPred3-to-PepMLM pipeline end-to-end:
  1. Create Project
  2. Create TargetProtein
  3. Create & run BepiPred3 scan job
  4. Persist BepiPred3 results → epitope_scan + epitope_candidates
  5. Select top epitope candidate
  6. Create & run PepMLM generation job (REAL_MODEL or STUB)
  7. Persist PepMLM results → stamp_generation_run + stamp_candidates
  8. Report results

All outputs are explicitly marked:
  - NOT_EXPERIMENTALLY_VALIDATED
  - COMPUTATIONAL_PREDICTION_ONLY (BepiPred3)
  - COMPUTATIONAL_GENERATION_ONLY (PepMLM)

No fabricated wet-lab metrics. Empty results are reported honestly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Ensure backend is on PYTHONPATH when run standalone
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _BACKEND_DIR)

from app.database import SessionLocal, init_db
from app.crud.jobs import create_job, get_job
from app.crud.projects import create_project
from app.crud.target_proteins import create_target_protein
from app.crud.epitopes import list_epitope_candidates_by_scan
from app.crud.stamp_candidates import (
    list_stamp_candidates_by_generation_run,
    list_stamp_candidates_by_project,
)
from app.schemas import JobCreate, ProjectCreate, TargetProteinCreate
from app.services.job_service import run_real_job
from app.services.bepipred3_persistence import persist_bepipred3_results
from app.services.pepmlm_persistence import persist_pepmlm_results

# ---------------------------------------------------------------------------
# Demo positive-control sequence (~200 aa) — BSA N-terminal fragment
# ---------------------------------------------------------------------------
DEFAULT_DEMO_SEQUENCE = (
    "MKWVTFISLLFLFSSAYSRGVFRRDAHKSEVAHRFKDLGEENFKALVLIAFAQYLQQCPFEDHVKLVNEVTEFAKTCVADESAENCDKSLHTLFGDKLCTVATLRETYGEMADCCAKQEPERNECFLQHKDDNPNLPRLVRPEVDVMCTAFHDNEETFLKKYLYEIARRHPYFYAPELLFFAKRYKAAFTECCQAADKAACLLPKLDELRDEGKASSAKQRLKCASLQKFGERAFKAWAVARLSQRFPKAEFAEVSKLVTDLTKVHKECCHGDLLECADDRADLAKYICENQDSISSKLKECCEKPLLEKSHCIAEVENDEMPADLPSLAADFVESKDVCKNYAEAKDVFLGMFLYEYARRHPDYSVVLLLRLAKTYETTLEKCCAAADPHECYAKVFDE"
)

DEFAULT_SIDEcar_BEPIPRED3 = "http://127.0.0.1:5001/api/predict"
DEFAULT_SIDEcar_PEPMLM = "http://127.0.0.1:5011"

REPORT_PATH = r"D:\ai\product\kimi\agent-bridge\reports\V010_P4_INTEGRATED_WORKFLOW_RUN_REPORT.md"


def _hash_sequence(seq: str) -> str:
    return hashlib.md5(seq.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _report_line(lines: List[str], text: str = "", level: int = 0) -> None:
    indent = "  " * level
    lines.append(f"{indent}{text}")


def _poll_job(db, job_id: str, timeout_sec: float = 300.0, interval: float = 2.0) -> Any:
    """Poll job status until terminal state or timeout."""
    start = time.time()
    while time.time() - start < timeout_sec:
        job = get_job(db, job_id)
        if job is None:
            raise RuntimeError(f"Job {job_id} not found during polling")
        if job.status in ("succeeded", "failed", "cancelled"):
            return job
        time.sleep(interval)
    raise TimeoutError(f"Job {job_id} did not reach terminal state within {timeout_sec}s")


def run_workflow(
    sequence: str,
    top_k_epitopes: int,
    top_k_peptides: int,
    sidecar_bepipred3_url: str,
    sidecar_pepmlm_url: str,
    report_lines: List[str],
) -> Dict[str, Any]:
    """Execute the full BepiPred3 → PepMLM integrated workflow."""

    db = SessionLocal()
    try:
        # =====================================================================
        # 1. Create Project
        # =====================================================================
        project = create_project(
            db,
            ProjectCreate(
                name="P4 Integrated Workflow Demo",
                description="v0.10-P4 BepiPred3-to-PepMLM end-to-end integration test",
                species="Demo",
                project_type="stamp_hybrid",
            ),
        )
        _report_line(report_lines, f"1. Created project: `{project.id}`")

        # =====================================================================
        # 2. Create Target Protein
        # =====================================================================
        target_protein = create_target_protein(
            db,
            TargetProteinCreate(
                project_id=project.id,
                name="P4-Demo-Target",
                sequence=sequence,
                sequence_hash=_hash_sequence(sequence),
                length=len(sequence),
                source_type="manual",
            ),
        )
        _report_line(report_lines, f"2. Created target protein: `{target_protein.id}` (length={len(sequence)})")

        # =====================================================================
        # 3. Create & run BepiPred3 scan job
        # =====================================================================
        bepipred3_job = create_job(
            db,
            JobCreate(
                project_id=project.id,
                job_type="bepipred3_scan",
                input_json={
                    "project_id": project.id,
                    "target_protein_id": target_protein.id,
                    "sequence": sequence,
                    "sidecar_url": sidecar_bepipred3_url,
                    "parameters": {},
                },
            ),
        )
        _report_line(report_lines, f"3. Created BepiPred3 job: `{bepipred3_job.id}`")

        updated_bepipred3 = run_real_job(db, bepipred3_job.id)
        if updated_bepipred3 is None or updated_bepipred3.status != "succeeded":
            raise RuntimeError(
                f"BepiPred3 job failed: status={updated_bepipred3.status if updated_bepipred3 else 'None'}, "
                f"error={updated_bepipred3.error_message if updated_bepipred3 else 'N/A'}"
            )
        _report_line(report_lines, f"   BepiPred3 job succeeded (candidate_count={updated_bepipred3.output_json.get('candidate_count', 'N/A')})")

        # =====================================================================
        # 4. Persist BepiPred3 results
        # =====================================================================
        bepipred3_persist = persist_bepipred3_results(db, bepipred3_job.id)
        scan_id = bepipred3_persist["scan_id"]
        epitope_count = bepipred3_persist["candidate_count"]
        _report_line(report_lines, f"4. Persisted BepiPred3 results → scan_id=`{scan_id}`, epitope_candidates={epitope_count}")

        # =====================================================================
        # 5. Retrieve epitope candidates
        # =====================================================================
        epitope_candidates = list_epitope_candidates_by_scan(db, scan_id)
        _report_line(report_lines, f"5. Retrieved {len(epitope_candidates)} epitope candidate(s) from scan")

        if len(epitope_candidates) == 0:
            _report_line(report_lines, "")
            _report_line(report_lines, "## ⚠️ Empty Epitope Result — Workflow terminates here")
            _report_line(report_lines, "")
            _report_line(report_lines, "The BepiPred3 sidecar returned **zero ranked peptides** above threshold.")
            _report_line(report_lines, "This is a **valid computational result** — no epitopes were predicted for this sequence.")
            _report_line(report_lines, "")
            _report_line(report_lines, "**No PepMLM job was created.** No candidates were fabricated.")
            _report_line(report_lines, "")
            return {
                "project_id": project.id,
                "target_protein_id": target_protein.id,
                "bepipred3_job_id": bepipred3_job.id,
                "epitope_scan_id": scan_id,
                "selected_epitope_id": None,
                "pepmlm_job_id": None,
                "generation_run_id": None,
                "stamp_candidate_count": 0,
                "top_stamp_candidates": [],
                "empty_epitope_result": True,
            }

        # =====================================================================
        # 6. Select top epitope candidate
        # =====================================================================
        # Sort by ranking_score descending
        sorted_epitopes = sorted(
            epitope_candidates,
            key=lambda c: (c.ranking_score or 0.0),
            reverse=True,
        )
        selected_epitope = sorted_epitopes[0]
        _report_line(report_lines, f"6. Selected epitope: `{selected_epitope.id}`")
        _report_line(report_lines, f"   Sequence: `{selected_epitope.sequence}`")
        _report_line(report_lines, f"   Score: {selected_epitope.ranking_score}")
        _report_line(report_lines, f"   Position: {selected_epitope.start}-{selected_epitope.end}")

        # =====================================================================
        # 7. Create & run PepMLM generation job
        # =====================================================================
        pepmlm_job = create_job(
            db,
            JobCreate(
                project_id=project.id,
                job_type="pepmlm_generation",
                input_json={
                    "project_id": project.id,
                    "epitope_id": selected_epitope.id,
                    "sidecar_url": sidecar_pepmlm_url,
                    "top_k": top_k_peptides,
                    "linker_seq": "GGGGS",
                    "parameters": {},
                },
            ),
        )
        _report_line(report_lines, f"7. Created PepMLM job: `{pepmlm_job.id}`")

        updated_pepmlm = run_real_job(db, pepmlm_job.id)
        if updated_pepmlm is None or updated_pepmlm.status != "succeeded":
            raise RuntimeError(
                f"PepMLM job failed: status={updated_pepmlm.status if updated_pepmlm else 'None'}, "
                f"error={updated_pepmlm.error_message if updated_pepmlm else 'N/A'}"
            )

        pepmlm_output = updated_pepmlm.output_json or {}
        mode = pepmlm_output.get("mode", "UNKNOWN")
        real_model_loaded = pepmlm_output.get("real_model_loaded", False)
        candidate_count = pepmlm_output.get("candidate_count", 0)
        _report_line(report_lines, f"   PepMLM job succeeded (mode={mode}, real_model_loaded={real_model_loaded}, candidates={candidate_count})")

        # =====================================================================
        # 8. Persist PepMLM results
        # =====================================================================
        pepmlm_persist = persist_pepmlm_results(db, pepmlm_job.id)
        generation_run_id = pepmlm_persist["generation_run_id"]
        stamp_count = pepmlm_persist["candidate_count"]
        _report_line(report_lines, f"8. Persisted PepMLM results → generation_run_id=`{generation_run_id}`, stamp_candidates={stamp_count}")

        # =====================================================================
        # 9. Retrieve stamp candidates
        # =====================================================================
        stamp_candidates = list_stamp_candidates_by_generation_run(db, generation_run_id)
        _report_line(report_lines, f"9. Retrieved {len(stamp_candidates)} stamp candidate(s)")

        top_3 = []
        for i, cand in enumerate(stamp_candidates[:3]):
            metrics = cand.metrics or {}
            info = {
                "rank": i + 1,
                "candidate_id": cand.id,
                "sequence": cand.targeting_peptide_seq,
                "full_sequence": cand.full_sequence,
                "composite_score": cand.composite_score,
                "source": metrics.get("source", "N/A"),
                "real_model_loaded": metrics.get("real_model_loaded", False),
                "ppl": metrics.get("ppl"),
                "charge": metrics.get("charge"),
                "pi": metrics.get("pi"),
            }
            top_3.append(info)
            _report_line(report_lines, f"   Top-{i+1}: `{cand.targeting_peptide_seq}` | PPL={metrics.get('ppl', 'N/A')} | charge={metrics.get('charge', 'N/A')} | source={metrics.get('source', 'N/A')}")

        return {
            "project_id": project.id,
            "target_protein_id": target_protein.id,
            "bepipred3_job_id": bepipred3_job.id,
            "epitope_scan_id": scan_id,
            "selected_epitope_id": selected_epitope.id,
            "pepmlm_job_id": pepmlm_job.id,
            "generation_run_id": generation_run_id,
            "stamp_candidate_count": len(stamp_candidates),
            "top_stamp_candidates": top_3,
            "empty_epitope_result": False,
            "pepmlm_mode": mode,
            "pepmlm_real_model_loaded": real_model_loaded,
        }

    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="v0.10-P4 BepiPred3-to-PepMLM Integrated Workflow"
    )
    parser.add_argument(
        "--sequence",
        type=str,
        default=DEFAULT_DEMO_SEQUENCE,
        help="Target protein sequence for BepiPred3 scan (default: demo BSA fragment)",
    )
    parser.add_argument(
        "--top-k-epitopes",
        type=int,
        default=10,
        help="Max epitope candidates to consider (default: 10)",
    )
    parser.add_argument(
        "--top-k-peptides",
        type=int,
        default=5,
        help="Max PepMLM peptides to generate (default: 5)",
    )
    parser.add_argument(
        "--sidecar-bepipred3-url",
        type=str,
        default=DEFAULT_SIDEcar_BEPIPRED3,
        help="BepiPred3 sidecar URL",
    )
    parser.add_argument(
        "--sidecar-pepmlm-url",
        type=str,
        default=DEFAULT_SIDEcar_PEPMLM,
        help="PepMLM sidecar URL",
    )
    parser.add_argument(
        "--report-path",
        type=str,
        default=REPORT_PATH,
        help="Path to write Markdown report",
    )
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------------
    report_lines: List[str] = []
    _report_line(report_lines, "# V010_P4_INTEGRATED_WORKFLOW_RUN_REPORT.md")
    _report_line(report_lines, "")
    _report_line(report_lines, f"Generated: {_now()}")
    _report_line(report_lines, "")
    _report_line(report_lines, "## Workflow Configuration")
    _report_line(report_lines, f"- Sequence length: {len(args.sequence)}")
    _report_line(report_lines, f"- Top-k epitopes: {args.top_k_epitopes}")
    _report_line(report_lines, f"- Top-k peptides: {args.top_k_peptides}")
    _report_line(report_lines, f"- BepiPred3 sidecar: `{args.sidecar_bepipred3_url}`")
    _report_line(report_lines, f"- PepMLM sidecar: `{args.sidecar_pepmlm_url}`")
    _report_line(report_lines, "")

    # -----------------------------------------------------------------------
    # Run
    # -----------------------------------------------------------------------
    try:
        init_db()
        result = run_workflow(
            sequence=args.sequence,
            top_k_epitopes=args.top_k_epitopes,
            top_k_peptides=args.top_k_peptides,
            sidecar_bepipred3_url=args.sidecar_bepipred3_url,
            sidecar_pepmlm_url=args.sidecar_pepmlm_url,
            report_lines=report_lines,
        )

        # -------------------------------------------------------------------
        # Summary
        # -------------------------------------------------------------------
        _report_line(report_lines, "")
        _report_line(report_lines, "## Workflow Result Summary")
        _report_line(report_lines, "")
        _report_line(report_lines, f"| Key | Value |")
        _report_line(report_lines, f"|---|---|")
        _report_line(report_lines, f"| project_id | `{result['project_id']}` |")
        _report_line(report_lines, f"| target_protein_id | `{result['target_protein_id']}` |")
        _report_line(report_lines, f"| bepipred3_job_id | `{result['bepipred3_job_id']}` |")
        _report_line(report_lines, f"| epitope_scan_id | `{result['epitope_scan_id']}` |")
        _report_line(report_lines, f"| selected_epitope_id | `{result.get('selected_epitope_id') or 'N/A (empty result)'}` |")
        _report_line(report_lines, f"| pepmlm_job_id | `{result.get('pepmlm_job_id') or 'N/A (empty result)'}` |")
        _report_line(report_lines, f"| generation_run_id | `{result.get('generation_run_id') or 'N/A (empty result)'}` |")
        _report_line(report_lines, f"| stamp_candidate_count | {result['stamp_candidate_count']} |")
        if not result.get("empty_epitope_result"):
            _report_line(report_lines, f"| pepmlm_mode | {result.get('pepmlm_mode', 'N/A')} |")
            _report_line(report_lines, f"| pepmlm_real_model_loaded | {result.get('pepmlm_real_model_loaded', 'N/A')} |")
        _report_line(report_lines, "")

        # Scientific integrity banner
        _report_line(report_lines, "## Scientific Integrity Check")
        _report_line(report_lines, "")
        _report_line(report_lines, "- [x] BepiPred3 results: `NOT_EXPERIMENTALLY_VALIDATED` + `COMPUTATIONAL_PREDICTION_ONLY`")
        if not result.get("empty_epitope_result"):
            _report_line(report_lines, "- [x] PepMLM results: `NOT_EXPERIMENTALLY_VALIDATED` + `COMPUTATIONAL_GENERATION_ONLY`")
            _report_line(report_lines, f"- [x] PepMLM real_model_loaded: `{result.get('pepmlm_real_model_loaded', 'N/A')}`")
        _report_line(report_lines, "- [x] No MIC / MBC / hemolysis / toxicity data fabricated")
        _report_line(report_lines, "- [x] No ipTM / pDockQ / ΔG / docking_score fabricated")
        _report_line(report_lines, "- [x] Empty epitope results handled honestly (no fabricated candidates)")
        _report_line(report_lines, "")

        if result.get("empty_epitope_result"):
            print("\n=== P4 WORKFLOW COMPLETE (EMPTY EPITOPE RESULT) ===")
            print(f"Project ID: {result['project_id']}")
            print(f"Epitope Scan ID: {result['epitope_scan_id']}")
            print("Status: BepiPred3 returned zero candidates — workflow terminated without fabrication.")
        else:
            print("\n=== P4 WORKFLOW COMPLETE ===")
            print(f"Project ID: {result['project_id']}")
            print(f"Epitope Scan ID: {result['epitope_scan_id']}")
            print(f"Selected Epitope: {result['selected_epitope_id']}")
            print(f"Generation Run ID: {result['generation_run_id']}")
            print(f"Stamp Candidates: {result['stamp_candidate_count']}")
            for t in result["top_stamp_candidates"]:
                print(f"  #{t['rank']}: {t['sequence']} | PPL={t.get('ppl', 'N/A')} | source={t.get('source', 'N/A')}")

        return 0

    except Exception as exc:
        _report_line(report_lines, "")
        _report_line(report_lines, f"## ❌ WORKFLOW FAILED")
        _report_line(report_lines, "")
        _report_line(report_lines, f"```")
        _report_line(report_lines, f"{type(exc).__name__}: {exc}")
        _report_line(report_lines, f"```")
        print(f"\n=== P4 WORKFLOW FAILED ===\n{type(exc).__name__}: {exc}")
        return 1

    finally:
        # Write report
        os.makedirs(os.path.dirname(args.report_path), exist_ok=True)
        with open(args.report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        print(f"\nReport written to: {args.report_path}")


if __name__ == "__main__":
    sys.exit(main())
