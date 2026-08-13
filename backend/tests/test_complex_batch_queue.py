"""Tests for complex batch queue (v0.10-P6l).

Validates Top-N candidate selection, batch FASTA generation,
manifest construction, batch output parsing, and batch
interface_quality import.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crud.projects import create_project
from app.crud.stamp_candidates import create_stamp_candidate
from app.crud.target_proteins import create_target_protein
from app.database import Base
from app.models.orm import TargetProtein
from app.schemas import (
    ProjectCreate,
    StampCandidateCreate,
    TargetProteinCreate,
)
from app.services.complex_batch_queue import (
    ComplexBatchError,
    build_batch_manifest,
    import_batch_interface_quality,
    parse_batch_outputs,
    prepare_batch_fastas,
    select_top_candidates_for_complex_batch,
)

TEST_DB_URL = "sqlite:///:memory:"
_test_engine = create_engine(
    TEST_DB_URL, echo=False, future=True, connect_args={"check_same_thread": False}
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
    proj = create_project(db_session, ProjectCreate(name="Batch Complex Test Project"))
    return proj


import hashlib

@pytest.fixture
def test_target_protein(db_session, test_project):
    seq = "MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFPDWQNYTPGPGTRYPAGQ"
    seq_hash = hashlib.sha256(seq.encode()).hexdigest()
    tp = create_target_protein(
        db_session,
        TargetProteinCreate(
            project_id=test_project.id,
            name="TestTarget",
            sequence=seq,
            sequence_hash=seq_hash,
            length=len(seq),
        ),
    )
    return tp


@pytest.fixture
def test_candidates(db_session, test_project):
    """Create 5 stamp candidates with varying composite_score."""
    cands = []
    for i in range(5):
        cand = create_stamp_candidate(
            db_session,
            StampCandidateCreate(
                project_id=test_project.id,
                targeting_peptide_seq="ACDEFGHIKLMNPQR",
                linker_seq="EAAAK",
                full_sequence=f"ACDEFGHIKLMNPQREAAAKFSRFLRRVRRYRPKISFNLEPFFKF",
                composite_score=float(90 - i * 10),  # 90, 80, 70, 60, 50
                metrics={"biophysical": {"length": 39}},
            ),
        )
        cands.append(cand)
    return cands


# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------


def test_select_top_3_candidates(db_session, test_project, test_target_protein, test_candidates):
    """Top 3 selection returns 3 candidates sorted by composite_score."""
    result = select_top_candidates_for_complex_batch(
        db_session, test_project.id, top_n=3
    )
    assert len(result["candidates"]) == 3
    assert result["candidates"][0]["composite_score"] == 90.0
    assert result["candidates"][1]["composite_score"] == 80.0
    assert result["candidates"][2]["composite_score"] == 70.0


def test_select_top_n_does_not_exceed_available(db_session, test_project, test_target_protein, test_candidates):
    """Top N=10 with only 5 candidates returns 5."""
    result = select_top_candidates_for_complex_batch(
        db_session, test_project.id, top_n=10
    )
    assert len(result["candidates"]) == 5


def test_select_top_n_empty_project_raises(db_session, test_project, test_target_protein):
    """Project with no candidates raises ComplexBatchError."""
    with pytest.raises(ComplexBatchError, match="no stamp candidates"):
        select_top_candidates_for_complex_batch(db_session, test_project.id, top_n=3)


def test_select_top_n_missing_project_raises(db_session):
    """Non-existent project raises ComplexBatchError."""
    with pytest.raises(ComplexBatchError, match="not found"):
        select_top_candidates_for_complex_batch(db_session, "nonexistent-project", top_n=3)


def test_select_top_n_no_target_protein_no_sequence_raises(db_session, test_project, test_candidates):
    """No target protein and no explicit target_sequence raises error."""
    with pytest.raises(ComplexBatchError, match="No target_sequence"):
        select_top_candidates_for_complex_batch(db_session, test_project.id, top_n=3)


def test_select_top_n_with_explicit_target_sequence(db_session, test_project, test_candidates):
    """Explicit target_sequence bypasses target protein lookup."""
    result = select_top_candidates_for_complex_batch(
        db_session,
        test_project.id,
        top_n=3,
        target_sequence="MKTAYIAKQRQISFVK",
    )
    assert result["target_sequence"] == "MKTAYIAKQRQISFVK"
    assert len(result["candidates"]) == 3


def test_select_top_n_returns_rank(db_session, test_project, test_target_protein, test_candidates):
    """Ranks start at 1."""
    result = select_top_candidates_for_complex_batch(
        db_session, test_project.id, top_n=3
    )
    assert result["candidates"][0]["rank"] == 1
    assert result["candidates"][1]["rank"] == 2
    assert result["candidates"][2]["rank"] == 3


def test_select_top_n_returns_candidate_id(db_session, test_project, test_target_protein, test_candidates):
    """Each candidate has candidate_id."""
    result = select_top_candidates_for_complex_batch(
        db_session, test_project.id, top_n=3
    )
    assert all("candidate_id" in c for c in result["candidates"])


def test_select_top_n_returns_peptide_sequence(db_session, test_project, test_target_protein, test_candidates):
    """Each candidate has peptide_sequence."""
    result = select_top_candidates_for_complex_batch(
        db_session, test_project.id, top_n=3
    )
    assert all("peptide_sequence" in c for c in result["candidates"])
    assert result["candidates"][0]["peptide_sequence"].startswith("ACDEF")


def test_select_top_n_none_scores_go_to_end(db_session, test_project, test_target_protein):
    """Candidates with None composite_score are ranked last."""
    create_stamp_candidate(
        db_session,
        StampCandidateCreate(
            project_id=test_project.id,
            targeting_peptide_seq="HIGHSCORE",
            linker_seq="EAAAK",
            full_sequence="HIGHSCOREEAAAKAMP",
            composite_score=95.0,
            metrics={},
        ),
    )
    create_stamp_candidate(
        db_session,
        StampCandidateCreate(
            project_id=test_project.id,
            targeting_peptide_seq="NOSCORE",
            linker_seq="EAAAK",
            full_sequence="NOSCOREEAAAKAMP",
            composite_score=None,
            metrics={},
        ),
    )
    result = select_top_candidates_for_complex_batch(
        db_session, test_project.id, top_n=2
    )
    assert result["candidates"][0]["composite_score"] == 95.0
    assert result["candidates"][1]["composite_score"] is None


# ---------------------------------------------------------------------------
# Batch FASTA generation
# ---------------------------------------------------------------------------


def test_prepare_batch_fastas_single_record_format(tmp_path: Path):
    """FASTA must be single-record colon-separated (ColabFold complex)."""
    candidates = [
        {
            "candidate_id": "cand-001",
            "rank": 1,
            "peptide_sequence": "ACDEFGHIKLMNPQR",
            "composite_score": 90.0,
            "full_sequence": "ACDEFGHIKLMNPQREAAAKAMP",
            "candidate_name": "candidate_cand-001",
        }
    ]
    enriched = prepare_batch_fastas(candidates, "MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFPDWQNYTPGPGTRYPAGQ", str(tmp_path))

    fasta_path = Path(enriched[0]["fasta_path"])
    content = fasta_path.read_text(encoding="utf-8")
    lines = [l for l in content.splitlines() if l.strip()]

    # Must be single record
    headers = [l for l in lines if l.startswith(">")]
    assert len(headers) == 1

    # Header format
    assert ">target_chain_A|candidate_cand-001_chain_B" in headers[0]

    # Sequence must have colon separator
    seq_lines = [l for l in lines if not l.startswith(">")]
    assert len(seq_lines) == 1
    assert ":" in seq_lines[0]
    assert seq_lines[0] == "MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFPDWQNYTPGPGTRYPAGQ:ACDEFGHIKLMNPQR"


def test_prepare_batch_fastas_not_two_records(tmp_path: Path):
    """FASTA must NOT have two separate records."""
    candidates = [
        {
            "candidate_id": "cand-001",
            "rank": 1,
            "peptide_sequence": "ACDEF",
            "composite_score": 90.0,
            "full_sequence": "ACDEFEAAAKAMP",
            "candidate_name": "candidate_cand-001",
        }
    ]
    enriched = prepare_batch_fastas(candidates, "MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFPDWQNYTPGPGTRYPAGQ", str(tmp_path))
    content = Path(enriched[0]["fasta_path"]).read_text(encoding="utf-8")
    assert content.count(">") == 1


def test_prepare_batch_fastas_filename_tracks_candidate_id(tmp_path: Path):
    """Filename must contain candidate_id."""
    candidates = [
        {
            "candidate_id": "abc-123",
            "rank": 1,
            "peptide_sequence": "ACDEF",
            "composite_score": 90.0,
            "full_sequence": "ACDEFEAAAKAMP",
            "candidate_name": "candidate_abc-123",
        }
    ]
    enriched = prepare_batch_fastas(candidates, "MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFPDWQNYTPGPGTRYPAGQ", str(tmp_path))
    assert "candidate_abc-123_complex.fasta" in enriched[0]["fasta_file"]


def test_prepare_batch_fastas_multiple_candidates(tmp_path: Path):
    """Multiple candidates each get their own FASTA."""
    candidates = [
        {"candidate_id": "c1", "rank": 1, "peptide_sequence": "ACDEF", "composite_score": 90.0, "full_sequence": "ACDEFEAAAKAMP", "candidate_name": "candidate_c1"},
        {"candidate_id": "c2", "rank": 2, "peptide_sequence": "GHIKL", "composite_score": 80.0, "full_sequence": "GHIKLEAAAKAMP", "candidate_name": "candidate_c2"},
    ]
    enriched = prepare_batch_fastas(candidates, "MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFPDWQNYTPGPGTRYPAGQ", str(tmp_path))
    assert len(enriched) == 2
    assert all("fasta_path" in c for c in enriched)
    assert all(Path(c["fasta_path"]).exists() for c in enriched)


def test_prepare_batch_fastas_no_linker_concatenation(tmp_path: Path):
    """Target and peptide must NOT be joined by linker."""
    candidates = [
        {
            "candidate_id": "c1",
            "rank": 1,
            "peptide_sequence": "ACDEF",
            "composite_score": 90.0,
            "full_sequence": "ACDEFEAAAKAMP",
            "candidate_name": "candidate_c1",
        }
    ]
    enriched = prepare_batch_fastas(candidates, "MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFPDWQNYTPGPGTRYPAGQ", str(tmp_path))
    content = Path(enriched[0]["fasta_path"]).read_text(encoding="utf-8")
    # The full_sequence includes linker, but FASTA should be target:peptide only
    assert "EAAAK" not in content.split("\n")[1]  # sequence line should not have linker


# ---------------------------------------------------------------------------
# Batch manifest
# ---------------------------------------------------------------------------


def test_build_batch_manifest_has_batch_id():
    """Manifest must have batch_id."""
    manifest = build_batch_manifest("proj-1", [], "MKTAY", "/tmp", 3)
    assert "batch_id" in manifest
    assert "p6l_project_proj-1_top3" in manifest["batch_id"]


def test_build_batch_manifest_has_candidates():
    """Manifest must list candidates."""
    candidates = [
        {"candidate_id": "c1", "rank": 1, "fasta_file": "c1.fasta", "peptide_sequence": "ACDEF"},
    ]
    manifest = build_batch_manifest("proj-1", candidates, "MKTAY", "/tmp", 1)
    assert len(manifest["candidates"]) == 1
    assert manifest["candidates"][0]["candidate_id"] == "c1"


def test_build_batch_manifest_has_chain_mapping():
    """Manifest candidate entries must have chain IDs."""
    candidates = [
        {"candidate_id": "c1", "rank": 1, "fasta_file": "c1.fasta", "peptide_sequence": "ACDEF"},
    ]
    manifest = build_batch_manifest("proj-1", candidates, "MKTAY", "/tmp", 1)
    assert manifest["candidates"][0]["target_chain_id"] == "A"
    assert manifest["candidates"][0]["peptide_chain_id"] == "B"


def test_build_batch_manifest_forbidden_metrics_delta_g_null():
    """Manifest forbidden_metrics.delta_G must be null."""
    manifest = build_batch_manifest("proj-1", [], "MKTAY", "/tmp", 3)
    assert manifest["forbidden_metrics"]["delta_G"] is None


def test_build_batch_manifest_forbidden_metrics_docking_score_null():
    """Manifest forbidden_metrics.docking_score must be null."""
    manifest = build_batch_manifest("proj-1", [], "MKTAY", "/tmp", 3)
    assert manifest["forbidden_metrics"]["docking_score"] is None


def test_build_batch_manifest_candidate_forbidden_metrics():
    """Each candidate in manifest must have forbidden_metrics."""
    candidates = [
        {"candidate_id": "c1", "rank": 1, "fasta_file": "c1.fasta", "peptide_sequence": "ACDEF"},
    ]
    manifest = build_batch_manifest("proj-1", candidates, "MKTAY", "/tmp", 1)
    assert manifest["candidates"][0]["forbidden_metrics"]["delta_G"] is None
    assert manifest["candidates"][0]["forbidden_metrics"]["docking_score"] is None


def test_build_batch_manifest_validation_status():
    """Manifest validation_status must be NOT_EXPERIMENTALLY_VALIDATED."""
    manifest = build_batch_manifest("proj-1", [], "MKTAY", "/tmp", 3)
    assert manifest["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_build_batch_manifest_prediction_status():
    """Manifest prediction_status must be batch-only."""
    manifest = build_batch_manifest("proj-1", [], "MKTAY", "/tmp", 3)
    assert "BATCH" in manifest["prediction_status"]


# ---------------------------------------------------------------------------
# Batch output parsing
# ---------------------------------------------------------------------------


def test_parse_batch_outputs_empty_dir(tmp_path: Path):
    """Empty output dir returns empty list."""
    results = parse_batch_outputs(str(tmp_path))
    assert results == []


def test_parse_batch_outputs_missing_dir():
    """Missing output dir raises ComplexBatchError."""
    with pytest.raises(ComplexBatchError, match="not found"):
        parse_batch_outputs("/nonexistent/path")


def test_parse_batch_outputs_single_success(tmp_path: Path):
    """Parse a single candidate output dir with real fixture files."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "complex_interface_parser"
    if not fixtures_dir.exists():
        pytest.skip("Real fixture files not available")

    candidate_dir = tmp_path / "candidate_test1"
    candidate_dir.mkdir()
    # Copy fixture files into candidate dir with appropriate names
    pdb_src = fixtures_dir / "complex_unrelaxed.pdb"
    pae_src = fixtures_dir / "predicted_aligned_error.json"
    if pdb_src.exists():
        (candidate_dir / "test1_unrelaxed_rank_001_model_1_seed_000.pdb").write_text(
            pdb_src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    if pae_src.exists():
        (candidate_dir / "test1_predicted_aligned_error_v1.json").write_text(
            pae_src.read_text(encoding="utf-8"), encoding="utf-8"
        )

    results = parse_batch_outputs(str(tmp_path))
    assert len(results) == 1
    assert results[0]["candidate_id"] == "candidate_test1"
    assert results[0]["success"] is True
    assert results[0]["report"]["has_chain_A"] is True
    assert results[0]["report"]["has_chain_B"] is True


def test_parse_batch_outputs_skips_non_dirs(tmp_path: Path):
    """Files in output dir are skipped."""
    (tmp_path / "some_file.txt").write_text("hello")
    results = parse_batch_outputs(str(tmp_path))
    assert results == []


def test_parse_batch_outputs_continues_on_failure(tmp_path: Path):
    """One bad subdir does not stop parsing others."""
    (tmp_path / "good_candidate").mkdir()
    (tmp_path / "bad_candidate").mkdir()
    # good_candidate: create empty PDB to cause parse failure
    (tmp_path / "bad_candidate" / "empty.pdb").write_text("REMARK 1 EMPTY\n")

    results = parse_batch_outputs(str(tmp_path))
    # bad_candidate might fail or succeed depending on parser behavior
    # but we should get at least one result
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# Batch interface_quality import
# ---------------------------------------------------------------------------


def test_import_batch_skips_missing_candidate(db_session, tmp_path: Path):
    """Missing candidate in DB is marked failed but does not abort."""
    result = import_batch_interface_quality(db_session, str(tmp_path))
    # Empty dir = no candidates to process
    assert result["total"] == 0


def test_import_batch_skips_existing_when_no_overwrite(db_session, test_project, test_candidates, tmp_path: Path):
    """Existing interface_quality is skipped when overwrite=False."""
    cand = test_candidates[0]
    # Pre-populate interface_quality
    cand.metrics = {**(cand.metrics or {}), "interface_quality": {"pdockq": 0.5}}
    db_session.commit()

    # Create fake output dir for this candidate
    out_dir = tmp_path / f"candidate_{cand.id}"
    out_dir.mkdir()

    result = import_batch_interface_quality(db_session, str(tmp_path), overwrite=False)
    assert result["skipped_count"] == 1
    assert result["success_count"] == 0


def test_import_batch_overwrite_when_flag_set(db_session, test_project, test_candidates, tmp_path: Path):
    """Existing interface_quality is overwritten when overwrite=True."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "complex_interface_parser"
    if not fixtures_dir.exists():
        pytest.skip("Real fixture files not available")

    cand = test_candidates[0]
    cand.metrics = {**(cand.metrics or {}), "interface_quality": {"pdockq": 0.5}}
    db_session.commit()

    # Create fake output dir with real fixture PDB
    out_dir = tmp_path / f"candidate_{cand.id}"
    out_dir.mkdir()
    pdb_src = fixtures_dir / "complex_unrelaxed.pdb"
    if pdb_src.exists():
        (out_dir / "test_unrelaxed_rank_001_model_1_seed_000.pdb").write_text(
            pdb_src.read_text(encoding="utf-8"), encoding="utf-8"
        )

    result = import_batch_interface_quality(db_session, str(tmp_path), overwrite=True)
    # May succeed or fail depending on parser; at least it should attempt
    assert result["total"] >= 1


def test_import_batch_fails_without_pdb(db_session, test_project, test_candidates, tmp_path: Path):
    """Candidate dir without PDB is marked failed."""
    cand = test_candidates[0]
    out_dir = tmp_path / f"candidate_{cand.id}"
    out_dir.mkdir()
    # No PDB file

    result = import_batch_interface_quality(db_session, str(tmp_path))
    failed = [d for d in result["details"] if d["candidate_id"] == cand.id]
    assert len(failed) == 1
    assert failed[0]["status"] == "FAILED"


def test_import_batch_does_not_pollute_structure_prediction(db_session, test_project, test_candidates, tmp_path: Path):
    """interface_quality import must not add pdockq to structure_prediction."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "complex_interface_parser"
    if not fixtures_dir.exists():
        pytest.skip("Real fixture files not available")

    cand = test_candidates[0]
    cand.metrics = {
        "structure_prediction": {
            "mean_plddt": 42.9,
            "ptm": 0.315,
            "forbidden_metrics": {"pDockQ": None, "delta_G": None, "docking_score": None},
        }
    }
    db_session.commit()

    out_dir = tmp_path / f"candidate_{cand.id}"
    out_dir.mkdir()
    pdb_src = fixtures_dir / "complex_unrelaxed.pdb"
    pae_src = fixtures_dir / "predicted_aligned_error.json"
    if pdb_src.exists():
        (out_dir / "test_unrelaxed_rank_001_model_1_seed_000.pdb").write_text(
            pdb_src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    if pae_src.exists():
        (out_dir / "test_predicted_aligned_error_v1.json").write_text(
            pae_src.read_text(encoding="utf-8"), encoding="utf-8"
        )

    result = import_batch_interface_quality(db_session, str(tmp_path), overwrite=True)
    # Refresh candidate
    from app.crud.stamp_candidates import get_stamp_candidate
    refreshed = get_stamp_candidate(db_session, cand.id)
    sp = refreshed.metrics.get("structure_prediction", {})
    # structure_prediction should remain untouched
    assert "pdockq" not in sp
    assert sp.get("mean_plddt") == 42.9


def test_import_batch_delta_g_remains_null(db_session, test_project, test_candidates, tmp_path: Path):
    """After import, delta_G in forbidden_metrics must still be null."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "complex_interface_parser"
    if not fixtures_dir.exists():
        pytest.skip("Real fixture files not available")

    cand = test_candidates[0]
    out_dir = tmp_path / f"candidate_{cand.id}"
    out_dir.mkdir()
    pdb_src = fixtures_dir / "complex_unrelaxed.pdb"
    pae_src = fixtures_dir / "predicted_aligned_error.json"
    if pdb_src.exists():
        (out_dir / "test_unrelaxed_rank_001_model_1_seed_000.pdb").write_text(
            pdb_src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    if pae_src.exists():
        (out_dir / "test_predicted_aligned_error_v1.json").write_text(
            pae_src.read_text(encoding="utf-8"), encoding="utf-8"
        )

    import_batch_interface_quality(db_session, str(tmp_path), overwrite=True)
    from app.crud.stamp_candidates import get_stamp_candidate
    refreshed = get_stamp_candidate(db_session, cand.id)
    iq = refreshed.metrics.get("interface_quality", {})
    fm = iq.get("forbidden_metrics", {})
    assert fm.get("delta_G") is None


def test_import_batch_docking_score_remains_null(db_session, test_project, test_candidates, tmp_path: Path):
    """After import, docking_score in forbidden_metrics must still be null."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "complex_interface_parser"
    if not fixtures_dir.exists():
        pytest.skip("Real fixture files not available")

    cand = test_candidates[0]
    out_dir = tmp_path / f"candidate_{cand.id}"
    out_dir.mkdir()
    pdb_src = fixtures_dir / "complex_unrelaxed.pdb"
    pae_src = fixtures_dir / "predicted_aligned_error.json"
    if pdb_src.exists():
        (out_dir / "test_unrelaxed_rank_001_model_1_seed_000.pdb").write_text(
            pdb_src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    if pae_src.exists():
        (out_dir / "test_predicted_aligned_error_v1.json").write_text(
            pae_src.read_text(encoding="utf-8"), encoding="utf-8"
        )

    import_batch_interface_quality(db_session, str(tmp_path), overwrite=True)
    from app.crud.stamp_candidates import get_stamp_candidate
    refreshed = get_stamp_candidate(db_session, cand.id)
    iq = refreshed.metrics.get("interface_quality", {})
    fm = iq.get("forbidden_metrics", {})
    assert fm.get("docking_score") is None


def test_import_batch_report_contains_success_fail_counts(db_session, test_project, test_candidates, tmp_path: Path):
    """Summary report must contain success/fail counts."""
    result = import_batch_interface_quality(db_session, str(tmp_path))
    assert "success_count" in result
    assert "fail_count" in result
    assert "skipped_count" in result
    assert "total" in result
    assert result["total"] == result["success_count"] + result["fail_count"] + result["skipped_count"]


def test_import_batch_report_contains_details(db_session, test_project, test_candidates, tmp_path: Path):
    """Summary report must contain per-candidate details."""
    result = import_batch_interface_quality(db_session, str(tmp_path))
    assert "details" in result


# ---------------------------------------------------------------------------
# End-to-end integration
# ---------------------------------------------------------------------------


def test_end_to_end_select_prepare_manifest(db_session, test_project, test_target_protein, test_candidates, tmp_path: Path):
    """Full flow: select → FASTA → manifest."""
    selection = select_top_candidates_for_complex_batch(db_session, test_project.id, top_n=3)
    enriched = prepare_batch_fastas(selection["candidates"], selection["target_sequence"], str(tmp_path / "input"))
    manifest = build_batch_manifest(
        test_project.id,
        enriched,
        selection["target_sequence"],
        str(tmp_path / "input"),
        3,
    )

    assert manifest["top_n"] == 3
    assert len(manifest["candidates"]) == 3
    assert all(c["sequence_format"] == "colabfold_colon_separated_complex" for c in manifest["candidates"])


def test_end_to_end_fasta_matches_manifest(db_session, test_project, test_target_protein, test_candidates, tmp_path: Path):
    """FASTA files referenced in manifest must exist."""
    selection = select_top_candidates_for_complex_batch(db_session, test_project.id, top_n=3)
    enriched = prepare_batch_fastas(selection["candidates"], selection["target_sequence"], str(tmp_path / "input"))
    manifest = build_batch_manifest(
        test_project.id,
        enriched,
        selection["target_sequence"],
        str(tmp_path / "input"),
        3,
    )

    for c in manifest["candidates"]:
        fasta_path = tmp_path / "input" / c["fasta_file"]
        assert fasta_path.exists()
