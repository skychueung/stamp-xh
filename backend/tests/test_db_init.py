"""
STAMP Platform — Database Init Tests (P5-lite)

Verifies that all 6 ORM tables can be created and written to
using a temporary in-memory SQLite database.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.orm import (
    EpitopeCandidate,
    EpitopeScan,
    Project,
    StampCandidate,
    StampGenerationRun,
    TargetProtein,
)
from app.schemas import (
    EpitopeCandidateCreate,
    EpitopeScanCreate,
    ProjectCreate,
    StampCandidateCreate,
    StampGenerationRunCreate,
    TargetProteinCreate,
)
from app.crud import (
    create_epitope_candidate,
    create_epitope_scan,
    create_project,
    create_stamp_candidate,
    create_stamp_generation_run,
    create_target_protein,
)

# ---------------------------------------------------------------------------
# Test DB fixture
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(TEST_DB_URL, echo=False, future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# 1. projects
# ---------------------------------------------------------------------------


def test_create_project(db_session):
    proj_in = ProjectCreate(name="Test Project", description="A test project")
    proj = create_project(db_session, proj_in)
    assert proj.id is not None
    assert len(proj.id) == 36  # UUID string
    assert proj.name == "Test Project"
    assert proj.created_at is not None


# ---------------------------------------------------------------------------
# 2. target_proteins
# ---------------------------------------------------------------------------


def test_create_target_protein(db_session):
    proj = create_project(db_session, ProjectCreate(name="TP Test"))
    tp_in = TargetProteinCreate(
        project_id=proj.id,
        name="Spike Protein",
        sequence="MKWVTFISLLFLFSSAYSRGVFRRDAHKSEVAHRFKDLGEENFKALVLIAFAQYLQQCPFEDHVKLVNEVTEFAKTCVADESAENCDKSLHTLFGDKLCTVATLRETYGEMADCCAKQEPERNECFLQHKDDNPNLPRLVRPEVDVMCTAFHDNEETFLKKYLYEIARRHPYFYAPELLFFAKRYKAAFTECCQAADKAACLLPKLDELRDEGKASSAKQRLKCASLQKFGERAFKAWAVARLSQRFPKAEFAEVSKLVTDLTKVHKECCHGDLLECADDRADLAKYICENQDSISSKLKECCEKPLLEKSHCIAEVENDEMPADLPSLAADFVESKDVCKNYAEAKDVFLGMFLYEYARRHPDYSVVLLLRLAKTYETTLEKCCAAADPHECYAKVFDEFKPLVEEPQNLIKQNCELFEQLGEYKFQNALLVRYTKKVPQVSTPTLVEVSRNLGKVGSKCCKHPEAKRMPCAEDYLSVVLNQLCVLHEKTPVSDRVTKCCTESLVNRRPCFSALTPDETYVPKAFDEKLFTFHADICTLPDTEKQIKKQTALVELVKHKPKATKEQLKAVMDDFAAFVEKCCKADDKETCFAEEGKKLVAASQAALGL",
        sequence_hash="a1b2c3d4e5f6",
        length=200,
        source_type="manual",
    )
    tp = create_target_protein(db_session, tp_in)
    assert tp.id is not None
    assert tp.project_id == proj.id
    assert tp.sequence_hash == "a1b2c3d4e5f6"
    assert tp.length == 200


# ---------------------------------------------------------------------------
# 3. epitope_scans
# ---------------------------------------------------------------------------


def test_create_epitope_scan(db_session):
    proj = create_project(db_session, ProjectCreate(name="Scan Test"))
    tp = create_target_protein(
        db_session,
        TargetProteinCreate(
            project_id=proj.id,
            name="Test Protein",
            sequence="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            sequence_hash="hash123",
            length=26,
            source_type="manual",
        ),
    )
    scan_in = EpitopeScanCreate(
        project_id=proj.id,
        target_protein_id=tp.id,
        algorithm="heuristic_v1",
    )
    scan = create_epitope_scan(db_session, scan_in)
    assert scan.id is not None
    assert scan.project_id == proj.id
    assert scan.status == "PENDING"


# ---------------------------------------------------------------------------
# 4. epitope_candidates
# ---------------------------------------------------------------------------


def test_create_epitope_candidate(db_session):
    proj = create_project(db_session, ProjectCreate(name="Candidate Test"))
    tp = create_target_protein(
        db_session,
        TargetProteinCreate(
            project_id=proj.id,
            name="Test Protein",
            sequence="ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 10,
            sequence_hash="hash456",
            length=260,
            source_type="manual",
        ),
    )
    scan = create_epitope_scan(
        db_session,
        EpitopeScanCreate(
            project_id=proj.id,
            target_protein_id=tp.id,
            algorithm="heuristic_v1",
        ),
    )
    cand_in = EpitopeCandidateCreate(
        scan_id=scan.id,
        start=1,
        end=15,
        sequence="ABCDEFGHIJKLMNO",
        net_charge=2.5,
        hydrophobicity=0.3,
        pi=7.4,
        cys_count=0,
        ranking_score=0.85,
        filter_status="PASS",
    )
    cand = create_epitope_candidate(db_session, cand_in)
    assert cand.id is not None
    assert cand.scan_id == scan.id
    assert cand.sequence == "ABCDEFGHIJKLMNO"


# ---------------------------------------------------------------------------
# 5. stamp_generation_runs
# ---------------------------------------------------------------------------


def test_create_stamp_generation_run(db_session):
    proj = create_project(db_session, ProjectCreate(name="Run Test"))
    run_in = StampGenerationRunCreate(
        project_id=proj.id,
        generator_name="manual",
    )
    run = create_stamp_generation_run(db_session, run_in)
    assert run.id is not None
    assert run.project_id == proj.id
    assert run.status == "PENDING"


# ---------------------------------------------------------------------------
# 6. stamp_candidates + validation_status default
# ---------------------------------------------------------------------------


def test_create_stamp_candidate_and_validation_status_default(db_session):
    """Ensure validation_status defaults to NOT_EXPERIMENTALLY_VALIDATED."""
    proj = create_project(db_session, ProjectCreate(name="Stamp Test"))
    run = create_stamp_generation_run(
        db_session,
        StampGenerationRunCreate(project_id=proj.id, generator_name="manual"),
    )
    stamp_in = StampCandidateCreate(
        project_id=proj.id,
        generation_run_id=run.id,
        targeting_peptide_seq="EEDDAEEDAEDDAEE",
        linker_seq="EAAAK",
        full_sequence="EEDDAEEDAEDDAEEEAAAKFSRFLRRVRRYRPKISFNLEPFFKF",
        composite_score=0.72,
    )
    stamp = create_stamp_candidate(db_session, stamp_in)
    assert stamp.id is not None
    assert stamp.project_id == proj.id
    assert stamp.generation_run_id == run.id
    # SCIENTIFIC INTEGRITY CHECK
    assert stamp.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"


# ---------------------------------------------------------------------------
# Cascade delete
# ---------------------------------------------------------------------------


def test_project_cascade_delete(db_session):
    """Deleting a project must cascade-delete its target_proteins."""
    proj = create_project(db_session, ProjectCreate(name="Cascade Test"))
    tp = create_target_protein(
        db_session,
        TargetProteinCreate(
            project_id=proj.id,
            name="Cascade Protein",
            sequence="ABCDE" * 50,
            sequence_hash="cascade_hash",
            length=250,
            source_type="manual",
        ),
    )
    db_session.delete(proj)
    db_session.commit()

    assert db_session.query(Project).filter(Project.id == proj.id).first() is None
    assert (
        db_session.query(TargetProtein).filter(TargetProtein.id == tp.id).first()
        is None
    )
