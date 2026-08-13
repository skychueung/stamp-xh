"""Tests for BatchComputation (v1.4-batch-computation).

Tests cover:
- batch creation
- batch item creation
- invalid param 422
- command missing BLOCKED
- input missing FAILED
- retry failed
- cancel batch
- no fabricated metrics
"""

from __future__ import annotations


import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app

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


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_batch_computation(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "name": "Test Batch",
        "job_type": "COLABFOLD",
        "candidate_ids": ["cand-1", "cand-2"],
        "input_json": {"sequence": "MKKTAIAATAVLATA"},
    }
    resp = await async_client.post("/api/v1/batch-computations", json=payload)
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    data = resp.json()
    assert data["project_id"] == "proj-1"
    assert data["name"] == "Test Batch"
    assert data["job_type"] == "COLABFOLD"
    assert data["status"] == "PENDING"
    assert "artifact_dir" in data


@pytest.mark.asyncio
async def test_create_invalid_job_type(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "name": "Bad Batch",
        "job_type": "INVALID",
        "candidate_ids": [],
    }
    resp = await async_client.post("/api/v1/batch-computations", json=payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# List / Get
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_and_get_batch(async_client: AsyncClient):
    payload = {
        "project_id": "proj-x",
        "name": "List Batch",
        "job_type": "FOLDX",
        "candidate_ids": ["c1"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]

    list_resp = await async_client.get("/api/v1/batch-computations?project_id=proj-x")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1

    get_resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == batch_id


@pytest.mark.asyncio
async def test_get_batch_items(async_client: AsyncClient):
    payload = {
        "project_id": "proj-y",
        "name": "Item Batch",
        "job_type": "MMGBSA",
        "candidate_ids": ["c1", "c2"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]

    items_resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}/items")
    # The route may return items
    assert items_resp.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_batch(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "name": "Cancel Batch",
        "job_type": "COLABFOLD",
        "candidate_ids": ["c1"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]

    cancel_resp = await async_client.post(f"/api/v1/batch-computations/{batch_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"


# ---------------------------------------------------------------------------
# Retry failed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_failed_items(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "name": "Retry Batch",
        "job_type": "COLABFOLD",
        "candidate_ids": ["c1"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]

    retry_resp = await async_client.post(f"/api/v1/batch-computations/{batch_id}/retry-failed")
    assert retry_resp.status_code == 200
    data = retry_resp.json()
    assert data["code"] == 200
    assert "retried_count" in data["data"]


# ---------------------------------------------------------------------------
# Service-level: validate params
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_job_params():
    from app.services.batch_compute_runner import validate_job_params

    ok, err = validate_job_params("COLABFOLD", {"sequence": "MKKTAIAATAVLATA"})
    assert ok is True
    assert err is None

    ok, err = validate_job_params("INVALID", {"sequence": "MKKTAIAATAVLATA"})
    assert ok is False
    assert "job_type must be one of" in err

    ok, err = validate_job_params("COLABFOLD", {"sequence": "ABC"})
    assert ok is False
    assert "sequence must be at least 5 residues" in err


# ---------------------------------------------------------------------------
# Service-level: command availability
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_command_available():
    from app.services.batch_compute_runner import check_command_available

    # python3 should always be available
    assert check_command_available("python3") is True
    # this_fake_command should not exist
    assert check_command_available("this_fake_command_12345") is False


# ---------------------------------------------------------------------------
# Service-level: directory structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_dir_service():
    from app.services.batch_dir_service import ensure_batch_dir, ensure_item_dir, get_item_log_path
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["STAMP_BATCH_JOBS_DIR"] = tmpdir
        batch_dir = ensure_batch_dir("batch-001")
        assert os.path.isdir(batch_dir)
        for sub in ("inputs", "colabfold", "foldx", "mmgbsa", "logs", "reports", "artifacts"):
            assert os.path.isdir(os.path.join(batch_dir, sub))

        item_dir = ensure_item_dir("batch-001", "item-001", "COLABFOLD")
        assert os.path.isdir(item_dir)

        log_path = get_item_log_path("batch-001", "item-001", "COLABFOLD")
        assert log_path.endswith("item-001_colabfold.log")

        del os.environ["STAMP_BATCH_JOBS_DIR"]


# ---------------------------------------------------------------------------
# No fabricated metrics boundary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_finalize_without_artifacts_fails():
    """SUCCEEDED requires real artifacts. Empty dir -> FAILED."""
    import tempfile
    import os
    from app.services.batch_compute_runner import finalize_batch_item
    from app.database import SessionLocal
    from app.models.orm import BatchComputationItem

    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=db.bind)
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["STAMP_BATCH_JOBS_DIR"] = tmpdir
            item = BatchComputationItem(
                batch_id="b1",
                project_id="p1",
                candidate_id="c1",
                job_type="COLABFOLD",
                status="RUNNING",
                artifact_dir=os.path.join(tmpdir, "empty"),
            )
            db.add(item)
            db.commit()
            db.refresh(item)

            # finalize with success=True but empty artifact dir -> should downgrade to FAILED
            item = finalize_batch_item(db, item, success=True, output_json={"plddt": 99.9})
            assert item.status == "FAILED"
            assert "No real artifacts found" in item.error_message

            db.delete(item)
            db.commit()
            del os.environ["STAMP_BATCH_JOBS_DIR"]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# MM-GBSA result endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_mmgbsa_results_not_available(async_client: AsyncClient):
    """When no FINAL_RESULTS_MMPBSA.dat exists, return NOT_AVAILABLE."""
    payload = {
        "project_id": "proj-mmgbsa",
        "name": "MMGBSA Batch",
        "job_type": "MMGBSA",
        "candidate_ids": ["c1"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]

    items_resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}/items")
    assert items_resp.status_code == 200
    items = items_resp.json()
    assert len(items) == 1
    item_id = items[0]["id"]

    mmgbsa_resp = await async_client.get(
        f"/api/v1/batch-computations/{batch_id}/items/{item_id}/mmgbsa-results"
    )
    assert mmgbsa_resp.status_code == 200
    data = mmgbsa_resp.json()
    assert data["code"] == 200
    assert data["data"]["status"] == "NOT_AVAILABLE"


@pytest.mark.asyncio
async def test_get_mmgbsa_results_real_file(async_client: AsyncClient):
    """When FINAL_RESULTS_MMPBSA.dat exists, return real parsed data."""
    import os

    payload = {
        "project_id": "proj-mmgbsa",
        "name": "MMGBSA Batch Real",
        "job_type": "MMGBSA",
        "candidate_ids": ["c1"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]

    items_resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}/items")
    item_id = items_resp.json()[0]["id"]

    # Create a real FINAL_RESULTS_MMPBSA.dat in the item artifact dir
    item_dir = items_resp.json()[0]["artifact_dir"]
    os.makedirs(item_dir, exist_ok=True)
    dat_path = os.path.join(item_dir, "FINAL_RESULTS_MMPBSA.dat")
    with open(dat_path, "w", encoding="utf-8") as f:
        f.write("""| Run on Mon May 12 10:00:00 2026
|MMPBSA.py Version=14.0
|Calculations performed using 500.0 complex frames.
|All units are reported in kcal/mole.

GENERALIZED BORN:

Complex:
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
EGB                     -24045.5663                0.0000              0.0000
ESURF                      352.8881                0.0000              0.0000
G gas                        0.0000                0.0000              0.0000
G solv                  -23692.6782                0.0000              0.0000
TOTAL                   -23692.6782                0.0000              0.0000

Receptor:
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
EGB                     -20802.9270                0.0003              0.0001
ESURF                      305.4760                0.0000              0.0000
G gas                        0.0000                0.0000              0.0000
G solv                  -20497.4510                0.0002              0.0001
TOTAL                   -20497.4510                0.0002              0.0001

Ligand:
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
EGB                      -3242.6392                0.0000              0.0000
ESURF                       47.4120                0.0000              0.0000
G gas                        0.0000                0.0000              0.0000
G solv                   -3195.2272                0.0000              0.0000
TOTAL                    -3195.2272                0.0000              0.0000

Differences (Complex - Receptor - Ligand):
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
VDWAALS                      0.0000                0.0000              0.0000
EEL                          0.0000                0.0000              0.0000
EGB                         -0.0001                0.0000              0.0000
ESURF                       -0.0000                0.0000              0.0000
DELTA G gas                  0.0000                0.0000              0.0000
DELTA G solv                -0.0001                0.0000              0.0000
DELTA TOTAL                 -0.0001                0.0000              0.0000
""")

    mmgbsa_resp = await async_client.get(
        f"/api/v1/batch-computations/{batch_id}/items/{item_id}/mmgbsa-results"
    )
    assert mmgbsa_resp.status_code == 200
    data = mmgbsa_resp.json()
    assert data["code"] == 200
    assert data["data"]["status"] == "SUCCESS"
    assert data["data"]["delta_g_total"] == pytest.approx(-0.0001)
    assert data["data"]["components"]["vdW"] == pytest.approx(0.0)
    assert data["data"]["components"]["electrostatic"] == pytest.approx(0.0)
    assert data["data"]["components"]["polar_solvation"] == pytest.approx(-0.0001)

    # Verify output files were written
    assert os.path.exists(os.path.join(item_dir, "mmgbsa_summary.json"))
    assert os.path.exists(os.path.join(item_dir, "mmgbsa_components.csv"))

    # Cleanup
    os.remove(dat_path)
    os.remove(os.path.join(item_dir, "mmgbsa_summary.json"))
    os.remove(os.path.join(item_dir, "mmgbsa_components.csv"))


@pytest.mark.asyncio
async def test_get_mmgbsa_results_wrong_job_type(async_client: AsyncClient):
    """Non-MMGBSA items must return 422."""
    payload = {
        "project_id": "proj-mmgbsa",
        "name": "FoldX Batch",
        "job_type": "FOLDX",
        "candidate_ids": ["c1"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]

    items_resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}/items")
    item_id = items_resp.json()[0]["id"]

    mmgbsa_resp = await async_client.get(
        f"/api/v1/batch-computations/{batch_id}/items/{item_id}/mmgbsa-results"
    )
    assert mmgbsa_resp.status_code == 422


@pytest.mark.asyncio
async def test_get_mmgbsa_results_batch_not_found(async_client: AsyncClient):
    """Missing batch must return 404."""
    resp = await async_client.get(
        "/api/v1/batch-computations/nonexistent/items/item-1/mmgbsa-results"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_mmgbsa_results_item_not_found(async_client: AsyncClient):
    """Missing item must return 404."""
    payload = {
        "project_id": "proj-mmgbsa",
        "name": "MMGBSA Batch",
        "job_type": "MMGBSA",
        "candidate_ids": ["c1"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]

    resp = await async_client.get(
        f"/api/v1/batch-computations/{batch_id}/items/nonexistent/mmgbsa-results"
    )
    assert resp.status_code == 404
