"""
STAMP Platform — Pipeline Orchestrator Tests (v1.6 P0)

Tests the automated front-half pipeline:
  TargetProtein → EpitopeScreening → PeptideGeneration → PeptideOptimization
  → STAMP Assembly → Batch Draft
"""

from __future__ import annotations

import os
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.orm import (
    EpitopeCandidate,
    EpitopeScan,
    PipelineRun,
    PipelineStep,
    StampCandidate,
    TargetProtein,
)
from app.services.pipeline_orchestrator import (
    STEP_ORDER,
    create_pipeline_run,
    create_pipeline_zip,
    list_pipeline_artifacts,
    retry_pipeline_from_step,
    run_epitope_screening_step,
    run_peptide_generation_step,
    run_peptide_optimization_step,
    run_stamp_assembly_step,
    run_target_input_step,
    run_structure_validation_ready_step,
    run_final_ranking_step,
    run_pipeline_once,
    read_pipeline_log,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///:memory:"
_test_engine = create_engine(
    TEST_DB_URL, echo=False, future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=_test_engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture
def demo_sequence() -> str:
    return "MKKLLPTAAAGLLLLAAQPAMA"


@pytest.fixture
def pipeline_run(db_session, demo_sequence: str) -> PipelineRun:
    run = create_pipeline_run(
        db=db_session,
        project_id=None,
        target_name="demo-target",
        target_sequence=demo_sequence,
    )
    return run


# ---------------------------------------------------------------------------
# PipelineRun creation
# ---------------------------------------------------------------------------


def test_create_pipeline_run_creates_steps(db_session, demo_sequence: str):
    run = create_pipeline_run(db_session, None, "test-target", demo_sequence)
    assert run.id is not None
    assert run.status == "PENDING"
    assert run.current_step == "TARGET_INPUT"

    steps = db_session.query(PipelineStep).filter(PipelineStep.pipeline_run_id == run.id).all()
    assert len(steps) == len(STEP_ORDER)
    for i, name in enumerate(STEP_ORDER):
        assert steps[i].step_name == name
        assert steps[i].status == "PENDING"
        assert steps[i].method is not None

    from app.services.pipeline_orchestrator import _artifact_dir
    root = _artifact_dir(run.id)
    assert os.path.isfile(os.path.join(root, "request.json"))
    assert os.path.isfile(os.path.join(root, "manifest.json"))
    assert os.path.isfile(os.path.join(root, "logs.jsonl"))
    with open(os.path.join(root, "request.json"), encoding="utf-8") as handle:
        request_data = json.load(handle)
    assert len(request_data["input_hash"]) == 64


def test_create_pipeline_run_empty_sequence(db_session):
    run = create_pipeline_run(db_session, None, "test", "")
    assert run.target_sequence == ""


# ---------------------------------------------------------------------------
# Target Input Step
# ---------------------------------------------------------------------------


def test_run_target_input_step_success(db_session, pipeline_run: PipelineRun):
    ok = run_target_input_step(db_session, pipeline_run)
    assert ok is True
    db_session.refresh(pipeline_run)
    assert pipeline_run.status != "FAILED"
    assert pipeline_run.current_step == "EPITOPE_SCREENING"

    step = db_session.query(PipelineStep).filter(
        PipelineStep.pipeline_run_id == pipeline_run.id,
        PipelineStep.step_name == "TARGET_INPUT",
    ).first()
    assert step.status == "SUCCEEDED"
    assert step.output_json is not None
    assert step.output_json.get("target_protein_id") is not None

    tp = db_session.query(TargetProtein).filter(
        TargetProtein.sequence == pipeline_run.target_sequence.upper().strip()
    ).first()
    assert tp is not None
    assert tp.length == len(pipeline_run.target_sequence)


def test_run_target_input_step_invalid_sequence(db_session):
    run = create_pipeline_run(db_session, None, "bad", "MKKXBZ123")
    ok = run_target_input_step(db_session, run)
    assert ok is False
    db_session.refresh(run)
    assert run.status == "FAILED"


# ---------------------------------------------------------------------------
# Epitope Screening Step
# ---------------------------------------------------------------------------


def test_run_epitope_screening_step_success(db_session, pipeline_run: PipelineRun):
    # Pre-requisite: target input
    assert run_target_input_step(db_session, pipeline_run) is True
    ok = run_epitope_screening_step(db_session, pipeline_run, top_k=5)
    assert ok is True
    db_session.refresh(pipeline_run)
    assert pipeline_run.current_step == "PEPTIDE_GENERATION"

    step = db_session.query(PipelineStep).filter(
        PipelineStep.pipeline_run_id == pipeline_run.id,
        PipelineStep.step_name == "EPITOPE_SCREENING",
    ).first()
    assert step.status == "SUCCEEDED"
    assert step.output_json["record_count"] == 5

    scan = db_session.query(EpitopeScan).filter(
        EpitopeScan.project_id == pipeline_run.project_id,
    ).order_by(EpitopeScan.created_at.desc()).first()
    assert scan is not None
    assert scan.status == "COMPLETED"

    candidates = db_session.query(EpitopeCandidate).filter(
        EpitopeCandidate.scan_id == scan.id
    ).all()
    assert len(candidates) == 5
    for c in candidates:
        assert c.sequence is not None
        assert len(c.sequence) >= 9
        assert c.ranking_score is not None


# ---------------------------------------------------------------------------
# Peptide Generation Step
# ---------------------------------------------------------------------------


def test_run_peptide_generation_step_success(db_session, pipeline_run: PipelineRun):
    assert run_target_input_step(db_session, pipeline_run) is True
    assert run_epitope_screening_step(db_session, pipeline_run, top_k=5) is True
    ok = run_peptide_generation_step(db_session, pipeline_run, peptides_per_epitope=3)
    assert ok is True
    db_session.refresh(pipeline_run)
    assert pipeline_run.current_step == "PEPTIDE_OPTIMIZATION"

    step = db_session.query(PipelineStep).filter(
        PipelineStep.pipeline_run_id == pipeline_run.id,
        PipelineStep.step_name == "PEPTIDE_GENERATION",
    ).first()
    assert step.status == "SUCCEEDED"
    assert step.output_json["record_count"] > 0


def test_selected_models_preserve_ready_results_when_one_runtime_is_missing(
    db_session, pipeline_run: PipelineRun, monkeypatch, tmp_path
):
    assert run_target_input_step(db_session, pipeline_run)
    assert run_epitope_screening_step(db_session, pipeline_run)
    request = dict((pipeline_run.output_json or {}).get("request") or {})
    request["selected_models"] = ["pepmlm", "pepprclip"]
    pipeline_run.output_json = {**(pipeline_run.output_json or {}), "request": request}
    db_session.commit()

    script = tmp_path / "runner.py"
    script.write_text(
        "import json,os,pathlib; p=pathlib.Path(os.environ['STAMP_RESULT_JSON']);"
        "p.parent.mkdir(parents=True,exist_ok=True);"
        "json.dump({'candidates':[{'sequence':'ACDEFGHIKLMN','score':0.9}]},open(p,'w'))",
        encoding="utf-8",
    )
    pepmlm_root = tmp_path / "pepmlm"
    pepmlm_root.mkdir()
    python = pepmlm_root / "python"
    checkpoint = pepmlm_root / "model.pt"
    python.write_text("fixture", encoding="utf-8")
    checkpoint.write_text("weights", encoding="utf-8")
    monkeypatch.setenv("STAMP_MODEL_RUNTIME_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("STAMP_PEPMLM_ROOT", str(pepmlm_root))
    monkeypatch.setenv("STAMP_PEPMLM_PYTHON", str(python))
    monkeypatch.setenv("STAMP_PEPMLM_CHECKPOINT", str(checkpoint))
    monkeypatch.setenv("STAMP_PEPMLM_RUNNER_COMMAND", json.dumps([os.sys.executable, str(script)]))
    monkeypatch.setenv("STAMP_PEPPRCLIP_ROOT", str(tmp_path / "missing-pepprclip"))

    assert run_peptide_generation_step(db_session, pipeline_run, peptides_per_epitope=1)
    step = db_session.query(PipelineStep).filter_by(
        pipeline_run_id=pipeline_run.id, step_name="PEPTIDE_GENERATION"
    ).one()
    execution = step.output_json["model_execution"]
    assert execution["status"] == "PARTIAL"
    assert {item["model_id"]: item["status"] for item in execution["jobs"]} == {
        "pepmlm": "SUCCEEDED", "pepprclip": "BLOCKED"
    }
    assert step.output_json["record_count"] == 1


# ---------------------------------------------------------------------------
# Peptide Optimization Step
# ---------------------------------------------------------------------------


def test_run_peptide_optimization_step_success(db_session, pipeline_run: PipelineRun):
    assert run_target_input_step(db_session, pipeline_run) is True
    assert run_epitope_screening_step(db_session, pipeline_run, top_k=5) is True
    assert run_peptide_generation_step(db_session, pipeline_run, peptides_per_epitope=3) is True
    ok = run_peptide_optimization_step(db_session, pipeline_run, top_k=50)
    assert ok is True
    db_session.refresh(pipeline_run)
    assert pipeline_run.current_step == "STAMP_ASSEMBLY"

    step = db_session.query(PipelineStep).filter(
        PipelineStep.pipeline_run_id == pipeline_run.id,
        PipelineStep.step_name == "PEPTIDE_OPTIMIZATION",
    ).first()
    assert step.status == "SUCCEEDED"
    assert step.output_json["record_count"] > 0


# ---------------------------------------------------------------------------
# STAMP Assembly Step
# ---------------------------------------------------------------------------


def test_run_stamp_assembly_step_success(db_session, pipeline_run: PipelineRun):
    assert run_target_input_step(db_session, pipeline_run) is True
    assert run_epitope_screening_step(db_session, pipeline_run, top_k=5) is True
    assert run_peptide_generation_step(db_session, pipeline_run, peptides_per_epitope=3) is True
    assert run_peptide_optimization_step(db_session, pipeline_run, top_k=50) is True
    ok = run_stamp_assembly_step(db_session, pipeline_run, top_k=20)
    assert ok is True
    db_session.refresh(pipeline_run)
    assert pipeline_run.current_step == "STRUCTURE_VALIDATION_READY"

    step = db_session.query(PipelineStep).filter(
        PipelineStep.pipeline_run_id == pipeline_run.id,
        PipelineStep.step_name == "STAMP_ASSEMBLY",
    ).first()
    assert step.status == "SUCCEEDED"
    assert step.output_json["record_count"] > 0

    stamp_candidates = db_session.query(StampCandidate).filter(
        StampCandidate.project_id == pipeline_run.project_id,
    ).all()
    assert len(stamp_candidates) > 0
    for sc in stamp_candidates:
        assert sc.full_sequence is not None
        assert len(sc.full_sequence) > 0
        assert sc.composite_score is not None


# ---------------------------------------------------------------------------
# Structure Validation Ready Step
# ---------------------------------------------------------------------------


def test_run_structure_validation_ready_step_success(db_session, pipeline_run: PipelineRun):
    assert run_target_input_step(db_session, pipeline_run) is True
    assert run_epitope_screening_step(db_session, pipeline_run, top_k=5) is True
    assert run_peptide_generation_step(db_session, pipeline_run, peptides_per_epitope=3) is True
    assert run_peptide_optimization_step(db_session, pipeline_run, top_k=50) is True
    assert run_stamp_assembly_step(db_session, pipeline_run, top_k=20) is True
    ok = run_structure_validation_ready_step(db_session, pipeline_run)
    assert ok is True
    db_session.refresh(pipeline_run)
    assert pipeline_run.current_step == "FINAL_RANKING"

    step = db_session.query(PipelineStep).filter(
        PipelineStep.pipeline_run_id == pipeline_run.id,
        PipelineStep.step_name == "STRUCTURE_VALIDATION_READY",
    ).first()
    assert step.status == "SUCCEEDED"
    assert step.output_json.get("record_count") > 0


# ---------------------------------------------------------------------------
# Final Ranking Step
# ---------------------------------------------------------------------------


def test_run_final_ranking_step_success(db_session, pipeline_run: PipelineRun):
    assert run_target_input_step(db_session, pipeline_run) is True
    assert run_epitope_screening_step(db_session, pipeline_run, top_k=5) is True
    assert run_peptide_generation_step(db_session, pipeline_run, peptides_per_epitope=3) is True
    assert run_peptide_optimization_step(db_session, pipeline_run, top_k=50) is True
    assert run_stamp_assembly_step(db_session, pipeline_run, top_k=20) is True
    assert run_structure_validation_ready_step(db_session, pipeline_run) is True
    ok = run_final_ranking_step(db_session, pipeline_run, top_k=20)
    assert ok is True
    db_session.refresh(pipeline_run)
    assert pipeline_run.current_step == "REPORT_EXPORT"

    step = db_session.query(PipelineStep).filter(
        PipelineStep.pipeline_run_id == pipeline_run.id,
        PipelineStep.step_name == "FINAL_RANKING",
    ).first()
    assert step.status == "SUCCEEDED"
    assert step.output_json.get("record_count") > 0
    ranked = step.output_json.get("final_ranking", [])
    assert len(ranked) > 0
    assert "final_rank_score" in ranked[0]


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def test_run_pipeline_once_full(db_session, demo_sequence: str):
    run = create_pipeline_run(db_session, None, "full-test", demo_sequence)
    result = run_pipeline_once(
        db_session, run.id,
        top_epitopes=5,
        peptides_per_epitope=2,
        top_stamp_candidates=10,
    )
    assert result.status == "SUCCEEDED"
    assert result.current_step == "FRONT_PIPELINE_TO_FINAL_RANKING_READY"

    # Verify artifacts exist
    artifacts = list_pipeline_artifacts(run.id)
    paths = [a["path"] for a in artifacts]
    assert any("target_summary.json" in p for p in paths)
    assert any("epitope_candidates.json" in p for p in paths)
    assert any("generated_peptides.json" in p for p in paths)
    assert any("optimized_peptides.json" in p for p in paths)
    assert any("stamp_candidates.json" in p for p in paths)
    assert any("structure_validation_manifest.json" in p for p in paths)
    assert any("final_ranking.json" in p for p in paths)
    assert any("pipeline_report.json" in p for p in paths)

    # Verify zip creation
    zip_path = create_pipeline_zip(run.id)
    assert os.path.exists(zip_path)
    assert os.path.getsize(zip_path) > 0

    logs = read_pipeline_log(run.id)
    assert logs
    assert logs[0]["message"] == "Pipeline execution started."
    assert logs[-1]["message"] == "Pipeline execution completed successfully."


def test_multiple_independent_runs_succeed(db_session, demo_sequence: str):
    """Regression: a successful first run must not poison later runs."""
    results = []
    for index in range(10):
        run = create_pipeline_run(db_session, None, f"repeat-{index}", demo_sequence)
        results.append(
            run_pipeline_once(
                db_session,
                run.id,
                top_epitopes=3,
                peptides_per_epitope=2,
                top_stamp_candidates=5,
            )
        )
    assert [result.status for result in results] == ["SUCCEEDED"] * 10
    assert len({result.id for result in results}) == 10


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------


def test_retry_pipeline_from_step(db_session, demo_sequence: str):
    run = create_pipeline_run(db_session, None, "retry-test", demo_sequence)
    run_pipeline_once(db_session, run.id, top_epitopes=3, peptides_per_epitope=2, top_stamp_candidates=5)

    retried = retry_pipeline_from_step(db_session, run.id, "PEPTIDE_GENERATION")
    assert retried.status == "PENDING"
    assert retried.current_step == "PEPTIDE_GENERATION"

    steps = db_session.query(PipelineStep).filter(
        PipelineStep.pipeline_run_id == run.id
    ).order_by(PipelineStep.step_order).all()

    for step in steps:
        if STEP_ORDER.index(step.step_name) >= STEP_ORDER.index("PEPTIDE_GENERATION"):
            assert step.status == "PENDING"
        else:
            assert step.status == "SUCCEEDED"


# ---------------------------------------------------------------------------
# Scientific boundary guards
# ---------------------------------------------------------------------------


def test_no_fake_structure_metrics(db_session, pipeline_run: PipelineRun):
    run_pipeline_once(db_session, pipeline_run.id, top_epitopes=3, peptides_per_epitope=2, top_stamp_candidates=5)

    # Ensure no fabricated pLDDT / ipTM / RMSD / RMSF / Rg / ΔG in any step output
    steps = db_session.query(PipelineStep).filter(
        PipelineStep.pipeline_run_id == pipeline_run.id
    ).all()
    for step in steps:
        out = step.output_json or {}
        text = str(out)
        assert "pLDDT" not in text or "NOT_AVAILABLE" in text
        assert "ipTM" not in text or "NOT_AVAILABLE" in text
        assert "ΔG" not in text or "NOT_AVAILABLE" in text
        assert step.scientific_boundary_note is not None
        note_lower = step.scientific_boundary_note.lower()

        assert any(k in note_lower for k in ("not experimentally validated", "sequence", "draft", "deterministic baseline", "not deep learning", "physicochemical", "no experimental validation", "computation pending", "downstream structure prediction", "structural score"))


def test_all_steps_have_methods(db_session, pipeline_run: PipelineRun):
    run_pipeline_once(db_session, pipeline_run.id, top_epitopes=3, peptides_per_epitope=2, top_stamp_candidates=5)
    steps = db_session.query(PipelineStep).filter(
        PipelineStep.pipeline_run_id == pipeline_run.id
    ).all()
    for step in steps:
        assert step.method is not None
        assert len(step.method) > 0


# ---------------------------------------------------------------------------
# Full pipeline to final ranking
# ---------------------------------------------------------------------------


def test_full_pipeline_to_final_ranking(db_session, pipeline_run: PipelineRun):
    result = run_pipeline_once(
        db_session, pipeline_run.id,
        top_epitopes=5, peptides_per_epitope=3, top_stamp_candidates=20,
    )
    assert result.status == "SUCCEEDED"
    assert result.current_step == "FRONT_PIPELINE_TO_FINAL_RANKING_READY"

    # Check final ranking step
    fr_step = db_session.query(PipelineStep).filter(
        PipelineStep.pipeline_run_id == pipeline_run.id,
        PipelineStep.step_name == "FINAL_RANKING",
    ).first()
    assert fr_step is not None
    assert fr_step.status == "SUCCEEDED"
    assert fr_step.output_json.get("record_count", 0) > 0
    ranked = fr_step.output_json.get("final_ranking", [])
    assert len(ranked) > 0
    assert "final_rank_score" in ranked[0]
    assert "warnings" in ranked[0]

    # Check report export step
    report_step = db_session.query(PipelineStep).filter(
        PipelineStep.pipeline_run_id == pipeline_run.id,
        PipelineStep.step_name == "REPORT_EXPORT",
    ).first()
    assert report_step is not None
    assert report_step.status == "SUCCEEDED"

    # Check artifacts
    artifacts = list_pipeline_artifacts(pipeline_run.id)
    paths = [a["path"] for a in artifacts]
    assert any("final_ranking.csv" in p for p in paths)
    assert any("final_ranking.json" in p for p in paths)
    assert any("pipeline_report.json" in p for p in paths)
    assert any("pipeline_report.md" in p for p in paths)
    assert any("structure_validation_manifest.json" in p for p in paths)


def test_peptide_optimization_warning_candidates(db_session, pipeline_run: PipelineRun):
    assert run_target_input_step(db_session, pipeline_run) is True
    assert run_epitope_screening_step(db_session, pipeline_run, top_k=5) is True
    assert run_peptide_generation_step(db_session, pipeline_run, peptides_per_epitope=3) is True
    ok = run_peptide_optimization_step(db_session, pipeline_run, top_k=50)
    assert ok is True

    step = db_session.query(PipelineStep).filter(
        PipelineStep.pipeline_run_id == pipeline_run.id,
        PipelineStep.step_name == "PEPTIDE_OPTIMIZATION",
    ).first()
    out = step.output_json or {}
    # Even if strict_pass_count is 0, step should succeed with warning candidates
    assert out.get("record_count", 0) > 0
    peptides = out.get("optimized_peptides", [])
    for p in peptides:
        assert "warning_flags" in p


def test_structure_validation_no_fake_metrics(db_session, pipeline_run: PipelineRun):
    assert run_target_input_step(db_session, pipeline_run) is True
    assert run_epitope_screening_step(db_session, pipeline_run, top_k=5) is True
    assert run_peptide_generation_step(db_session, pipeline_run, peptides_per_epitope=3) is True
    assert run_peptide_optimization_step(db_session, pipeline_run, top_k=50) is True
    assert run_stamp_assembly_step(db_session, pipeline_run, top_k=20) is True
    ok = run_structure_validation_ready_step(db_session, pipeline_run)
    assert ok is True

    step = db_session.query(PipelineStep).filter(
        PipelineStep.pipeline_run_id == pipeline_run.id,
        PipelineStep.step_name == "STRUCTURE_VALIDATION_READY",
    ).first()
    out = step.output_json or {}
    manifest = out.get("manifest", {})
    assert manifest.get("status") == "READY_FOR_VALIDATION"
    text = str(out)
    assert "pLDDT" not in text or "NOT_AVAILABLE" in text
    assert "ipTM" not in text or "NOT_AVAILABLE" in text
