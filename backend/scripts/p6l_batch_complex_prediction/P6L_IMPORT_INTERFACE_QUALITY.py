#!/usr/bin/env python3
"""P6l: Import interface_quality for all candidates in a batch output directory.

Runs P6i interface parser + P6j pDockQ calculator + persistence for each.

Usage:
    python3 P6L_IMPORT_INTERFACE_QUALITY.py [BATCH_OUTPUT_DIR] [--overwrite]

Default BATCH_OUTPUT_DIR: ~/kxc/p6l_batch_complex_prediction/output
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.services.complex_batch_queue import import_batch_interface_quality


def main():
    parser = argparse.ArgumentParser(description="Import batch interface_quality")
    parser.add_argument("--output-dir", default="~/kxc/p6l_batch_complex_prediction/output", help="Batch output directory")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing interface_quality")
    parser.add_argument("--report", default="~/kxc/p6l_batch_complex_prediction/batch_import_report.json", help="Report output path")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser()
    report_path = Path(args.report).expanduser()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        print(f"[P6L-IMPORT] Importing interface_quality from {output_dir}")
        summary = import_batch_interface_quality(
            db,
            str(output_dir),
            overwrite=args.overwrite,
        )

        report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"[P6L-IMPORT] Total: {summary['total']}, Success: {summary['success_count']}, Failed: {summary['fail_count']}, Skipped: {summary['skipped_count']}")
        print(f"[P6L-IMPORT] Report written to {report_path}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
