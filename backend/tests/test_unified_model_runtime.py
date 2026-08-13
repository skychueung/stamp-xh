from __future__ import annotations

import json
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.orm import Job
from app.services.production_model_registry import MODEL_IDS, ProductionModelRegistry
from app.services.unified_model_runtime import (
    job_paths,
    process_model_job,
    read_job_logs,
    recover_interrupted_model_jobs,
    model_jobs_for_run,
    resolve_job_artifact,
    submit_model_job,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def configured_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("STAMP_MODEL_RUNTIME_ROOT", str(tmp_path / "runtime"))
    script = tmp_path / "runner.py"
    script.write_text(
        "import json,os,pathlib\n"
        "out=pathlib.Path(os.environ['STAMP_RESULT_JSON'])\n"
        "out.parent.mkdir(parents=True,exist_ok=True)\n"
        "seed=int(json.load(open(os.environ['STAMP_OUTPUT_DIR']+'/../input/request.json'))['seed'])\n"
        "seq=('ACDEFGHIKLMNPQRSTVWY'*2)[seed%10:seed%10+12]\n"
        "json.dump({'candidates':[{'sequence':seq,'score':0.9}]},open(out,'w'))\n",
        encoding="utf-8",
    )
    for model_id in MODEL_IDS:
        root = tmp_path / "models" / model_id
        root.mkdir(parents=True)
        python = root / "python"
        checkpoint = root / "model.pt"
        python.write_text("fixture", encoding="utf-8")
        checkpoint.write_text("weights", encoding="utf-8")
        monkeypatch.setenv(f"STAMP_{model_id.upper()}_ROOT", str(root))
        monkeypatch.setenv(f"STAMP_{model_id.upper()}_PYTHON", str(python))
        monkeypatch.setenv(f"STAMP_{model_id.upper()}_CHECKPOINT", str(checkpoint))
        monkeypatch.setenv(
            f"STAMP_{model_id.upper()}_RUNNER_COMMAND",
            json.dumps([sys.executable, str(script)]),
        )
    return tmp_path


def _payload(seed=41):
    return {"target_sequence": "MKKLLPTAAAGLLLLAAQPAMA", "peptide_length": 12,
            "num_candidates": 1, "seed": seed, "device": "cpu"}


def test_model_registry_exact_five():
    assert MODEL_IDS == ("pepmlm", "pepprclip", "evobind2", "pephar", "pepflow")


def test_every_model_has_executable_adapter():
    registry = ProductionModelRegistry()
    for model_id in MODEL_IDS:
        adapter = registry.get(model_id)
        for method in ("submit", "status", "cancel", "collect_artifacts", "normalize_result"):
            assert callable(getattr(adapter, method))


def test_all_models_repeatable_result_logs_and_artifact_isolation(db, configured_runtime):
    ids = set()
    for model_id in MODEL_IDS:
        for seed in (41, 42, 43):
            job = submit_model_job(db, model_id, _payload(seed), run_id="acceptance_repeat")
            process_model_job(db, job)
            db.refresh(job)
            assert job.status == "SUCCEEDED", job.error_json
            assert job.output_json["provenance"] == "real_model"
            assert job.output_json["candidates"][0]["source_model"] == model_id
            assert job.output_json["candidates"][0]["sequence"]
            paths = job_paths("acceptance_repeat", model_id, job.id)
            assert paths["result_path"].is_file()
            assert not paths["busy_path"].exists()
            assert not paths["lock_path"].exists()
            assert read_job_logs(job)
            ids.add(str(paths["artifact_dir"]))
    assert len(ids) == 15


def test_second_run_after_failure(db, configured_runtime, monkeypatch):
    command_name = "STAMP_PEPMLM_RUNNER_COMMAND"
    good = __import__("os").environ[command_name]
    monkeypatch.setenv(command_name, json.dumps([sys.executable, "-c", "raise SystemExit(3)"]))
    first = submit_model_job(db, "pepmlm", _payload(), run_id="failure_recovery")
    process_model_job(db, first)
    assert first.status == "FAILED"
    monkeypatch.setenv(command_name, good)
    second = submit_model_job(db, "pepmlm", _payload(42), run_id="failure_recovery")
    process_model_job(db, second)
    assert second.status == "SUCCEEDED"


def test_restart_recovery(db, configured_runtime):
    job = submit_model_job(db, "pepflow", _payload(), run_id="restart")
    job.status = "RUNNING"
    db.commit()
    assert recover_interrupted_model_jobs(db) == [job.id]
    db.refresh(job)
    assert job.status == "QUEUED"


def test_model_jobs_for_run_filters_other_runs(db, configured_runtime):
    wanted = submit_model_job(db, "pepmlm", _payload(), run_id="wanted")
    submit_model_job(db, "pepflow", _payload(), run_id="other")
    assert [job.id for job in model_jobs_for_run(db, "wanted")] == [wanted.id]


def test_secret_redaction(db, configured_runtime):
    job = submit_model_job(db, "pephar", {**_payload(), "token": "TOPSECRET", "password": "TOPSECRET"})
    assert "TOPSECRET" not in json.dumps(job.input_json)
    assert "REDACTED" in json.dumps(job.input_json)


def test_artifact_resolver_rejects_traversal(db, configured_runtime):
    job = submit_model_job(db, "pepmlm", _payload(), run_id="artifact_resolver")
    process_model_job(db, job)
    assert resolve_job_artifact(job, "output/result.json").is_file()
    with pytest.raises(ValueError, match="INVALID_ARTIFACT_PATH"):
        resolve_job_artifact(job, "../../etc/passwd")
