#!/usr/bin/env python3
"""P6l: Prepare batch complex prediction inputs (FASTA + manifest).

Run this on the server after the backend DB has stamp candidates ready.

Usage:
    python3 P6L_PREPARE_BATCH_COMPLEX_INPUTS.py <project_id> [--top-n 3] [--output-dir DIR]

Requires:
    - Backend Python environment with app.services.complex_batch_queue
    - Access to the STAMP database
"""

import argparse
import json
import sys
from pathlib import Path

# Add backend to path so we can import app modules
SCRIPT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.services.complex_batch_queue import (
    build_batch_manifest,
    prepare_batch_fastas,
    select_top_candidates_for_complex_batch,
)


def main():
    parser = argparse.ArgumentParser(description="Prepare batch complex prediction inputs")
    parser.add_argument("project_id", help="STAMP project ID")
    parser.add_argument("--top-n", type=int, default=3, help="Number of top candidates (default: 3)")
    parser.add_argument("--output-dir", default="~/kxc/p6l_batch_complex_prediction", help="Output directory")
    parser.add_argument("--target-sequence", default=None, help="Target protein sequence (optional)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser()
    input_dir = output_dir / "input"
    manifest_dir = output_dir / "manifests"
    input_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        # 1. Select top candidates
        selection = select_top_candidates_for_complex_batch(
            db,
            args.project_id,
            top_n=args.top_n,
            target_sequence=args.target_sequence,
        )
        target_sequence = selection["target_sequence"]
        candidates = selection["candidates"]

        print(f"[P6L-PREPARE] Selected {len(candidates)} candidates for project {args.project_id}")
        print(f"[P6L-PREPARE] Target sequence length: {len(target_sequence)}")
        for c in candidates:
            print(f"  rank={c['rank']} id={c['candidate_id']} score={c['composite_score']} peptide={c['peptide_sequence'][:20]}...")

        # 2. Generate FASTA files
        enriched = prepare_batch_fastas(candidates, target_sequence, str(input_dir))
        print(f"[P6L-PREPARE] Wrote {len(enriched)} FASTA files to {input_dir}")

        # 3. Build manifest
        manifest = build_batch_manifest(
            args.project_id,
            enriched,
            target_sequence,
            str(input_dir),
            args.top_n,
        )
        manifest_path = manifest_dir / f"batch_manifest_{args.project_id}_top{args.top_n}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"[P6L-PREPARE] Wrote manifest to {manifest_path}")

        # 4. Write target sequence reference
        target_ref_path = manifest_dir / f"target_sequence_{args.project_id}.txt"
        target_ref_path.write_text(target_sequence, encoding="utf-8")
        print(f"[P6L-PREPARE] Wrote target sequence reference to {target_ref_path}")

        print("[P6L-PREPARE] DONE")

    finally:
        db.close()


if __name__ == "__main__":
    main()
