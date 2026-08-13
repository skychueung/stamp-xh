#!/usr/bin/env python3
"""P6l: Parse batch ColabFold complex outputs.

Usage:
    python3 P6L_PARSE_BATCH_OUTPUTS.py [BATCH_OUTPUT_DIR]

Default BATCH_OUTPUT_DIR: ~/kxc/p6l_batch_complex_prediction/output
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.services.complex_batch_queue import parse_batch_outputs


def main():
    parser = argparse.ArgumentParser(description="Parse batch ColabFold outputs")
    parser.add_argument("--output-dir", default="~/kxc/p6l_batch_complex_prediction/output", help="Batch output directory")
    parser.add_argument("--report", default="~/kxc/p6l_batch_complex_prediction/batch_parse_report.json", help="Report output path")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser()
    report_path = Path(args.report).expanduser()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[P6L-PARSE] Parsing outputs in {output_dir}")
    results = parse_batch_outputs(str(output_dir))

    success = sum(1 for r in results if r["success"])
    failed = sum(1 for r in results if not r["success"])

    report = {
        "stage": "batch_parse",
        "output_dir": str(output_dir),
        "total": len(results),
        "success": success,
        "failed": failed,
        "results": results,
    }

    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[P6L-PARSE] Total: {len(results)}, Success: {success}, Failed: {failed}")
    print(f"[P6L-PARSE] Report written to {report_path}")


if __name__ == "__main__":
    main()
