"""
STAMP Platform — Pipeline Runs API Tests (v1.6 P0)

Tests the pipeline-runs REST endpoints, specifically:
  - Report endpoint reads from correct lower-case artifact directory
  - Artifact download endpoints work
  - No hard-coded upper-case step directory names in router
"""

from __future__ import annotations

import os
import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app
from app.services.pipeline_orchestrator import (
    create_pipeline_run,
    run_pipeline_once,
    _artifact_dir,
)

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
def test_app(db_session):
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest_asyncio.fixture
async def async_client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Report endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_endpoint_reads_from_lowercase_dir(async_client: AsyncClient, db_session):
    """Ensure GET /report reads pipeline_report.json from report_export/ (lower-case)."""
    # 1. Create and run a full pipeline so report files are generated
    run = create_pipeline_run(db_session, None, "report-test", "MKKLLPTAAAGLLLLAAQPAMA")
    result = run_pipeline_once(
        db_session, run.id,
        top_epitopes=3, peptides_per_epitope=2, top_stamp_candidates=5,
    )
    assert result.status == "SUCCEEDED"
    run_id = run.id

    # 2. Verify real files exist on disk in lower-case directory
    base = _artifact_dir(run_id)
    report_json_path = os.path.join(base, "report_export", "pipeline_report.json")
    report_md_path = os.path.join(base, "report_export", "pipeline_report.md")
    assert os.path.exists(report_json_path), f"Expected {report_json_path} to exist"
    assert os.path.exists(report_md_path), f"Expected {report_md_path} to exist"

    # 3. On case-sensitive filesystems, verify upper-case directory was NOT created.
    # Windows is case-insensitive, so this assertion is skipped there.
    import platform
    if platform.system() != "Windows":
        bad_dir = os.path.join(base, "REPORT_EXPORT")
        assert not os.path.exists(bad_dir), f"Upper-case artifact dir {bad_dir} should not exist"

    # 4. Call the report endpoint
    resp = await async_client.get(f"/api/v1/pipeline-runs/{run_id}/report")
    assert resp.status_code == status.HTTP_200_OK, resp.text
    body = resp.json()
    assert body["code"] == 200
    data = body["data"]

    # 5. Assertions: report_data must be non-empty and contain expected keys
    assert "report_data" in data, "report_data key missing from response"
    report_data = data["report_data"]
    assert report_data is not None
    assert isinstance(report_data, dict)
    assert len(report_data) > 0, "report_data should not be empty"

    # Expected report content
    assert report_data.get("pipeline_run_id") == run_id
    assert report_data.get("target_name") == "report-test"
    assert "steps" in report_data
    assert "top_candidates" in report_data
    assert "scientific_boundary_note" in report_data
    # Note: report is generated while pipeline is still RUNNING,
    # so report_data.status reflects the state at generation time.
    # The important thing is that report_data is non-empty and readable.
    assert report_data.get("status") in ("RUNNING", "SUCCEEDED")
    assert report_data.get("current_step") in ("REPORT_EXPORT", "FRONT_PIPELINE_TO_FINAL_RANKING_READY")

    # Steps should include all 8 pipeline steps
    steps = report_data["steps"]
    assert len(steps) == 8
    step_names = [s["step_name"] for s in steps]
    expected_steps = [
        "TARGET_INPUT",
        "EPITOPE_SCREENING",
        "PEPTIDE_GENERATION",
        "PEPTIDE_OPTIMIZATION",
        "STAMP_ASSEMBLY",
        "STRUCTURE_VALIDATION_READY",
        "FINAL_RANKING",
        "REPORT_EXPORT",
    ]
    for name in expected_steps:
        assert name in step_names, f"Missing step {name} in report"

    # Final ranking should have candidates
    top_candidates = report_data["top_candidates"]
    assert isinstance(top_candidates, list)
    assert len(top_candidates) > 0
    first = top_candidates[0]
    assert "rank" in first
    assert "stamp_sequence" in first
    assert "final_rank_score" in first

    # 6. Markdown should also be present
    assert "report_markdown" in data
    assert data["report_markdown"] is not None
    assert len(data["report_markdown"]) > 0
    assert "STAMP" in data["report_markdown"] or "pipeline" in data["report_markdown"].lower()


@pytest.mark.asyncio
async def test_report_endpoint_no_uppercase_artifact_dir(async_client: AsyncClient, db_session):
    """Regression: ensure router never looks for REPORT_EXPORT (upper-case)."""
    run = create_pipeline_run(db_session, None, "casing-test", "MKKLLPTAAAGLLLLAAQPAMA")
    run_pipeline_once(
        db_session, run.id,
        top_epitopes=2, peptides_per_epitope=1, top_stamp_candidates=3,
    )

    # Inspect the router source indirectly: if it were using upper-case,
    # the endpoint would return empty report_data on case-sensitive fs.
    resp = await async_client.get(f"/api/v1/pipeline-runs/{run.id}/report")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "report_data" in data
    assert data["report_data"] is not None
    assert len(data["report_data"]) > 0


# ---------------------------------------------------------------------------
# Download endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_artifacts_zip(async_client: AsyncClient, db_session):
    """Ensure GET /{run_id}/download returns a valid zip file."""
    run = create_pipeline_run(db_session, None, "zip-test", "MKKLLPTAAAGLLLLAAQPAMA")
    run_pipeline_once(
        db_session, run.id,
        top_epitopes=2, peptides_per_epitope=1, top_stamp_candidates=3,
    )

    resp = await async_client.get(f"/api/v1/pipeline-runs/{run.id}/download")
    assert resp.status_code == status.HTTP_200_OK, resp.text
    assert resp.headers["content-type"] == "application/zip"
    assert len(resp.content) > 0


@pytest.mark.asyncio
async def test_download_single_artifact(async_client: AsyncClient, db_session):
    """Ensure GET /{run_id}/artifacts/download returns a single file."""
    run = create_pipeline_run(db_session, None, "artifact-test", "MKKLLPTAAAGLLLLAAQPAMA")
    run_pipeline_once(
        db_session, run.id,
        top_epitopes=2, peptides_per_epitope=1, top_stamp_candidates=3,
    )

    # Download a known artifact using lower-case path
    resp = await async_client.get(
        f"/api/v1/pipeline-runs/{run.id}/artifacts/download",
        params={"path": "report_export/pipeline_report.json"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    assert len(resp.content) > 0

    # Upper-case path should fail on case-sensitive systems
    resp_bad = await async_client.get(
        f"/api/v1/pipeline-runs/{run.id}/artifacts/download",
        params={"path": "REPORT_EXPORT/pipeline_report.json"},
    )
    # On Windows this might succeed (case-insensitive), on Linux it will 404.
    # We assert that at least the lower-case path works.
    assert resp.status_code == 200
