#!/usr/bin/env python3
"""Execute and verify the three required real PepPrCLIP acceptance runs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


AA = set("ACDEFGHIKLMNPQRSTVWY")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-sequence", default="MKKLLPTAAAGLLLLAAQPAMA")
    parser.add_argument("--peptide-length", type=int, default=12)
    parser.add_argument("--num-candidates", type=int, default=3)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--runtime-root", type=Path,
                        default=Path("/home/xh/kxc/runtime/five-model-unified-acceptance"))
    parser.add_argument("--database", type=Path,
                        default=Path("reports/pepprclip-real-acceptance.db"))
    parser.add_argument("--output", type=Path,
                        default=Path("reports/pepprclip_real_3x_results.json"))
    args = parser.parse_args()

    os.environ["STAMP_MODEL_RUNTIME_ROOT"] = str(args.runtime_root.resolve())
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.services.production_model_registry import production_registry
    from app.services.unified_model_runtime import (
        job_paths,
        process_model_job,
        read_job_logs,
        submit_model_job,
    )

    probe = production_registry.get("pepprclip").probe()
    if probe["state"] != "ready":
        raise SystemExit(json.dumps({"error": "PEPPRCLIP_NOT_READY", "probe": probe}, indent=2))

    args.database.parent.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{args.database.resolve()}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    run_id = f"pepprclip_real_3x_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    results: list[dict[str, object]] = []
    artifact_roots: set[str] = set()
    try:
        for seed in (41, 42, 43):
            payload = {
                "target_sequence": args.target_sequence,
                "peptide_length": args.peptide_length,
                "num_candidates": args.num_candidates,
                "seed": seed,
                "device": args.device,
            }
            job = submit_model_job(session, "pepprclip", payload, run_id=run_id)
            process_model_job(session, job)
            session.refresh(job)
            paths = job_paths(run_id, "pepprclip", job.id)
            logs = read_job_logs(job, limit=1000)
            output = job.output_json or {}
            candidates = output.get("candidates") or []
            valid_candidates = bool(candidates) and all(
                row.get("sequence") and not (set(str(row["sequence"])) - AA)
                for row in candidates
            )
            result_file_ok = False
            if paths["result_path"].is_file() and paths["result_path"].stat().st_size:
                result_file_ok = bool(json.loads(paths["result_path"].read_text(encoding="utf-8")))
            checks = {
                "succeeded": job.status == "SUCCEEDED",
                "real_provenance": output.get("provenance") == "real_model",
                "checkpoint_sha256_present": bool(output.get("checkpoint_sha256")),
                "valid_candidates": valid_candidates,
                "result_json_nonempty": result_file_ok,
                "structured_logs_present": bool(logs),
                "inference_event_present": any(row.get("event") == "INFERENCE_STARTED" for row in logs),
                "gpu_lock_released": not paths["lock_path"].exists(),
                "busy_marker_released": not paths["busy_path"].exists(),
            }
            artifact_root = str(paths["artifact_dir"])
            artifact_roots.add(artifact_root)
            results.append({
                "seed": seed,
                "job_id": job.id,
                "status": job.status,
                "checks": checks,
                "checkpoint_sha256": output.get("checkpoint_sha256"),
                "duration_seconds": output.get("duration_seconds"),
                "candidate_count": len(candidates),
                "candidate_sequences": [row.get("sequence") for row in candidates],
                "artifact_root": artifact_root,
                "artifact_count": len(output.get("artifacts") or []),
                "log_count": len(logs),
                "error": job.error_json,
            })
    finally:
        session.close()

    passed = sum(1 for row in results if all(row["checks"].values()))
    report = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "model_id": "pepprclip",
        "probe": probe,
        "expected_runs": 3,
        "passed_runs": passed,
        "artifact_isolation": len(artifact_roots) == 3,
        "results": results,
        "verdict": "PASS" if passed == 3 and len(artifact_roots) == 3 else "FAIL",
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
