"""Tests for experimental validation CSV import."""

from __future__ import annotations

import io

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud.projects import create_project
from app.crud.stamp_candidates import create_stamp_candidate, create_stamp_generation_run
from app.database import Base, get_db
from app.main import create_app
import app.models.orm  # noqa: F401
from app.schemas.project import ProjectCreate
from app.schemas.stamp import StampCandidateCreate, StampGenerationRunCreate

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
def test_project(db_session):
    return create_project(db_session, ProjectCreate(name="CSV Import Test Project"))


@pytest.fixture
def test_generation_run(db_session, test_project):
    return create_stamp_generation_run(
        db_session, StampGenerationRunCreate(project_id=test_project.id)
    )


@pytest.fixture
def test_candidate(db_session, test_project, test_generation_run):
    return create_stamp_candidate(
        db_session,
        StampCandidateCreate(
            project_id=test_project.id,
            generation_run_id=test_generation_run.id,
            targeting_peptide_seq="MKWVTFISLL",
            linker_seq="GGGGS",
            full_sequence="MKWVTFISLLGGGGS",
        ),
    )


@pytest.fixture
def test_app(db_session):
    Base.metadata.create_all(bind=db_session.bind)
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


def _csv_bytes(rows: list[dict]) -> bytes:
    """Build CSV bytes from row dicts."""
    header = "candidate_id,experiment_type,organism,strain,protocol_name,experiment_date,metric_name,value,unit,replicate_id,quality_flag,condition_json,notes"
    lines = [header]
    for row in rows:
        lines.append(
            f"{row.get('candidate_id','')},{row.get('experiment_type','')},{row.get('organism','')},"
            f"{row.get('strain','')},{row.get('protocol_name','')},{row.get('experiment_date','')},"
            f"{row.get('metric_name','')},{row.get('value','')},{row.get('unit','')},"
            f"{row.get('replicate_id','')},{row.get('quality_flag','')},{row.get('condition_json','')},"
            f"{row.get('notes','')}"
        )
    return "\n".join(lines).encode("utf-8")


# ---------------------------------------------------------------------------
# 1. CSV import MIC success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csv_import_mic_success(async_client, test_project, test_candidate):
    csv = _csv_bytes([{
        "candidate_id": test_candidate.id,
        "experiment_type": "MIC",
        "metric_name": "MIC_ug_ml",
        "value": "2.5",
        "unit": "ug/ml",
        "quality_flag": "PASS",
    }])
    resp = await async_client.post(
        f"/api/v1/experimental-validation/projects/{test_project.id}/import-measurements-csv",
        files={"file": ("test.csv", io.BytesIO(csv), "text/csv")},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["total_rows"] == 1
    assert data["success_count"] == 1
    assert data["failed_count"] == 0
    assert data["created_measurement_count"] == 1


# ---------------------------------------------------------------------------
# 2. CSV import MBC success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csv_import_mbc_success(async_client, test_project, test_candidate):
    csv = _csv_bytes([{
        "candidate_id": test_candidate.id,
        "experiment_type": "MBC",
        "metric_name": "MBC_ug_ml",
        "value": "5.0",
        "unit": "ug/ml",
    }])
    resp = await async_client.post(
        f"/api/v1/experimental-validation/projects/{test_project.id}/import-measurements-csv",
        files={"file": ("test.csv", io.BytesIO(csv), "text/csv")},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["success_count"] == 1
    assert data["created_measurement_count"] == 1


# ---------------------------------------------------------------------------
# 3. CSV import hemolysis success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csv_import_hemolysis_success(async_client, test_project, test_candidate):
    csv = _csv_bytes([{
        "candidate_id": test_candidate.id,
        "experiment_type": "HEMOLYSIS",
        "metric_name": "hemolysis_percent",
        "value": "12.5",
        "unit": "%",
    }])
    resp = await async_client.post(
        f"/api/v1/experimental-validation/projects/{test_project.id}/import-measurements-csv",
        files={"file": ("test.csv", io.BytesIO(csv), "text/csv")},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["success_count"] == 1


# ---------------------------------------------------------------------------
# 4. CSV candidate_id not found → row fails
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csv_import_unknown_candidate_fails(async_client, test_project, test_candidate):
    csv = _csv_bytes([{
        "candidate_id": "nonexistent-candidate",
        "experiment_type": "MIC",
        "metric_name": "MIC_ug_ml",
        "value": "2.0",
        "unit": "ug/ml",
    }])
    resp = await async_client.post(
        f"/api/v1/experimental-validation/projects/{test_project.id}/import-measurements-csv",
        files={"file": ("test.csv", io.BytesIO(csv), "text/csv")},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["success_count"] == 0
    assert data["failed_count"] == 1
    assert "nonexistent-candidate" in data["errors"][0]["reason"]


# ---------------------------------------------------------------------------
# 5. CSV negative MIC fails
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csv_import_negative_mic_fails(async_client, test_project, test_candidate):
    csv = _csv_bytes([{
        "candidate_id": test_candidate.id,
        "experiment_type": "MIC",
        "metric_name": "MIC_ug_ml",
        "value": "-1.0",
        "unit": "ug/ml",
    }])
    resp = await async_client.post(
        f"/api/v1/experimental-validation/projects/{test_project.id}/import-measurements-csv",
        files={"file": ("test.csv", io.BytesIO(csv), "text/csv")},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["success_count"] == 0
    assert data["failed_count"] == 1
    assert "must be >= 0" in data["errors"][0]["reason"]


# ---------------------------------------------------------------------------
# 6. CSV hemolysis >100 fails
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csv_import_hemolysis_over_100_fails(async_client, test_project, test_candidate):
    csv = _csv_bytes([{
        "candidate_id": test_candidate.id,
        "experiment_type": "HEMOLYSIS",
        "metric_name": "hemolysis_percent",
        "value": "150",
        "unit": "%",
    }])
    resp = await async_client.post(
        f"/api/v1/experimental-validation/projects/{test_project.id}/import-measurements-csv",
        files={"file": ("test.csv", io.BytesIO(csv), "text/csv")},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["success_count"] == 0
    assert data["failed_count"] == 1
    assert "between 0 and 100" in data["errors"][0]["reason"]


# ---------------------------------------------------------------------------
# 7. Partial failure does not affect successful rows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csv_import_partial_failure(async_client, test_project, test_candidate):
    csv = _csv_bytes([
        {
            "candidate_id": test_candidate.id,
            "experiment_type": "MIC",
            "metric_name": "MIC_ug_ml",
            "value": "2.0",
            "unit": "ug/ml",
        },
        {
            "candidate_id": test_candidate.id,
            "experiment_type": "MIC",
            "metric_name": "MIC_ug_ml",
            "value": "-5.0",
            "unit": "ug/ml",
        },
    ])
    resp = await async_client.post(
        f"/api/v1/experimental-validation/projects/{test_project.id}/import-measurements-csv",
        files={"file": ("test.csv", io.BytesIO(csv), "text/csv")},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["total_rows"] == 2
    assert data["success_count"] == 1
    assert data["failed_count"] == 1
    assert data["created_measurement_count"] == 1


# ---------------------------------------------------------------------------
# 8. Import result returns row-level errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csv_import_returns_row_level_errors(async_client, test_project, test_candidate):
    csv = _csv_bytes([
        {
            "candidate_id": "bad-id",
            "experiment_type": "MIC",
            "metric_name": "MIC_ug_ml",
            "value": "1.0",
            "unit": "ug/ml",
        },
        {
            "candidate_id": test_candidate.id,
            "experiment_type": "HEMOLYSIS",
            "metric_name": "hemolysis_percent",
            "value": "200",
            "unit": "%",
        },
    ])
    resp = await async_client.post(
        f"/api/v1/experimental-validation/projects/{test_project.id}/import-measurements-csv",
        files={"file": ("test.csv", io.BytesIO(csv), "text/csv")},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["failed_count"] == 2
    errors = data["errors"]
    assert any("bad-id" in e["reason"] for e in errors)
    assert any("between 0 and 100" in e["reason"] for e in errors)


# ---------------------------------------------------------------------------
# 9. Import updates experimental priority score
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csv_import_updates_priority(async_client, test_project, test_candidate):
    csv = _csv_bytes([
        {
            "candidate_id": test_candidate.id,
            "experiment_type": "MIC",
            "metric_name": "MIC_ug_ml",
            "value": "1.0",
            "unit": "ug/ml",
            "quality_flag": "PASS",
        },
        {
            "candidate_id": test_candidate.id,
            "experiment_type": "HEMOLYSIS",
            "metric_name": "hemolysis_percent",
            "value": "5.0",
            "unit": "%",
            "quality_flag": "PASS",
        },
    ])
    resp = await async_client.post(
        f"/api/v1/experimental-validation/projects/{test_project.id}/import-measurements-csv",
        files={"file": ("test.csv", io.BytesIO(csv), "text/csv")},
    )
    assert resp.status_code == status.HTTP_200_OK
    import_data = resp.json()["data"]
    assert import_data["success_count"] == 2

    # Check priority reflects imported data
    priority_resp = await async_client.get(
        f"/api/v1/experimental-validation/candidates/{test_candidate.id}/priority"
    )
    assert priority_resp.status_code == status.HTTP_200_OK
    priority = priority_resp.json()["data"]
    assert priority["has_experimental_data"] is True
    assert priority["experimental_priority_score"] is not None


# ---------------------------------------------------------------------------
# 10. Candidate report still distinguishes computational vs experimental
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csv_import_does_not_fake_validated(async_client, test_project, test_candidate):
    csv = _csv_bytes([{
        "candidate_id": test_candidate.id,
        "experiment_type": "MIC",
        "metric_name": "MIC_ug_ml",
        "value": "2.0",
        "unit": "ug/ml",
    }])
    resp = await async_client.post(
        f"/api/v1/experimental-validation/projects/{test_project.id}/import-measurements-csv",
        files={"file": ("test.csv", io.BytesIO(csv), "text/csv")},
    )
    assert resp.status_code == status.HTTP_200_OK

    # Candidate should NOT be auto-marked EXPERIMENTALLY_VALIDATED from a single MIC
    # (needs both activity + safety + PASS + COMPLETED runs)
    summary_resp = await async_client.get(
        f"/api/v1/experimental-validation/candidates/{test_candidate.id}/validation"
    )
    assert summary_resp.status_code == status.HTTP_200_OK
    summary = summary_resp.json()["data"]
    assert summary["overall_validation_status"] != "EXPERIMENTALLY_VALIDATED"
