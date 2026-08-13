from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.orm import PipelineRun
from app.services.pipeline_orchestrator import create_pipeline_run
from app.workers.pipeline_worker import claim_next, enqueue_pipeline, recover_stale_runs


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_enqueue_is_idempotent_and_claims_once(db_session):
    run = create_pipeline_run(db_session, None, "queue", "MKKLLPTAAAGLLLLAAQPAMA")
    enqueue_pipeline(db_session, run, top_epitopes=3, peptides_per_epitope=2, top_stamp_candidates=5)
    enqueue_pipeline(db_session, run, top_epitopes=99, peptides_per_epitope=9, top_stamp_candidates=99)
    db_session.refresh(run)
    assert run.status == "QUEUED"
    assert run.output_json["queue"]["parameters"]["top_epitopes"] == 3
    claimed = claim_next(db_session)
    assert claimed.id == run.id
    assert claimed.status == "RUNNING"
    assert claim_next(db_session) is None


def test_expired_worker_lease_is_requeued(db_session):
    run = create_pipeline_run(db_session, None, "recover", "MKKLLPTAAAGLLLLAAQPAMA")
    enqueue_pipeline(db_session, run, top_epitopes=3, peptides_per_epitope=2, top_stamp_candidates=5)
    run.status = "RUNNING"
    metadata = dict(run.output_json)
    metadata["queue"] = {
        **metadata["queue"],
        "state": "claimed",
        "lease_expires_at": (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(),
    }
    run.output_json = metadata
    db_session.commit()
    assert recover_stale_runs(db_session) == 1
    recovered = db_session.query(PipelineRun).filter(PipelineRun.id == run.id).one()
    assert recovered.status == "QUEUED"
    assert recovered.output_json["queue"]["state"] == "queued"
