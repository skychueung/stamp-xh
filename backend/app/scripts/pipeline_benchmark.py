"""Run a reproducible lightweight pipeline benchmark and emit JSON/CSV."""

from __future__ import annotations

import argparse
import csv
import json
import tempfile
import time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services.pipeline_orchestrator import create_pipeline_run, read_pipeline_log, run_pipeline_once

GOLDEN_TARGETS = [
    ("golden-signal", "MKKLLPTAAAGLLLLAAQPAMA"),
    ("golden-enzyme", "MKTAYIAKQRQISFVKSHFSRQ"),
]


def run_benchmark(repetitions: int, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = Path(tempfile.mkdtemp(prefix="stamp-benchmark-")) / "benchmark.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    rows: list[dict] = []
    with Session() as db:
        for target_name, sequence in GOLDEN_TARGETS:
            for repetition in range(repetitions):
                started = time.perf_counter()
                run = create_pipeline_run(db, None, f"{target_name}-{repetition}", sequence)
                result = run_pipeline_once(
                    db, run.id, top_epitopes=3, peptides_per_epitope=2, top_stamp_candidates=5
                )
                elapsed = time.perf_counter() - started
                logs = read_pipeline_log(run.id)
                ranking = next((step for step in result.steps if step.step_name == "FINAL_RANKING"), None)
                ranked = list((ranking.output_json or {}).get("final_ranking", [])) if ranking else []
                sequences = [str(candidate.get("stamp_sequence", "")) for candidate in ranked]
                rows.append(
                    {
                        "target": target_name,
                        "repetition": repetition,
                        "run_id": run.id,
                        "status": result.status,
                        "elapsed_seconds": round(elapsed, 4),
                        "log_records": len(logs),
                        "candidate_count": len(sequences),
                        "valid_count": sum(bool(sequence) and sequence.isalpha() for sequence in sequences),
                        "duplicate_rate": round(1 - len(set(sequences)) / len(sequences), 6) if sequences else 0,
                        "diversity": round(len(set(sequences)) / len(sequences), 6) if sequences else 0,
                        "recovery_success": result.status == "SUCCEEDED",
                    }
                )
    successful = sum(row["status"] == "SUCCEEDED" for row in rows)
    report = {
        "schema_version": 1,
        "repetitions": repetitions,
        "runs": len(rows),
        "successful_runs": successful,
        "failure_rate": round(1 - successful / len(rows), 6) if rows else 0,
        "mean_elapsed_seconds": round(sum(row["elapsed_seconds"] for row in rows) / len(rows), 4),
        "rows": rows,
    }
    (output_dir / "pipeline_benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (output_dir / "pipeline_benchmark.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark-results"))
    args = parser.parse_args()
    print(json.dumps(run_benchmark(args.repetitions, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
