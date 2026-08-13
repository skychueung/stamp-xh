"""Tests for complex prediction input preparation (v0.10-P6g).

Validates that target + peptide multi-chain FASTA generation,
sequence validation, and manifest construction are correct and
enforce the scientific-integrity boundary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.complex_prediction_input import (
    PEPTIDE_MAX_LEN,
    PEPTIDE_MIN_LEN,
    TARGET_MAX_LEN,
    TARGET_MIN_LEN,
    ComplexInputError,
    build_complex_prediction_manifest,
    build_multimer_fasta,
    validate_peptide_sequence,
    validate_protein_sequence,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_TARGET = (
    "MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFPDWQNYTPGPGTRYPAGQFGP"
    "KPGDKFDNSFKDNENLQLQDSVKNVQKQDDSIVSQSKQSSQKTQADSSSQDTQPQTSQ"
    "SNTQPQQTPQNPQQSQQQPQQQPQQQPQQQPQQQPQQQPQQQPQQQPQQQPQQQPQQQ"
    "PQQQPQQQPQQQPQQQPQQQPQQQPQQQPQQQPQQQPQQQPQQQPQQQPQQQPQQQPQ"
)

SAMPLE_PEPTIDE = "MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFP"

SAMPLE_SHORT_PEPTIDE = "ACDEF"


# ---------------------------------------------------------------------------
# validate_protein_sequence
# ---------------------------------------------------------------------------


def test_validate_target_accepts_standard_sequence():
    """A standard 20-AA target sequence must pass validation."""
    validate_protein_sequence(SAMPLE_TARGET)  # should not raise


def test_validate_target_rejects_empty():
    """Empty target sequence must raise ComplexInputError."""
    with pytest.raises(ComplexInputError, match="empty"):
        validate_protein_sequence("")


def test_validate_target_rejects_too_short():
    """Target shorter than TARGET_MIN_LEN must raise."""
    short = "A" * (TARGET_MIN_LEN - 1)
    with pytest.raises(ComplexInputError, match="too short"):
        validate_protein_sequence(short)


def test_validate_target_rejects_too_long():
    """Target longer than TARGET_MAX_LEN must raise."""
    long_seq = "A" * (TARGET_MAX_LEN + 1)
    with pytest.raises(ComplexInputError, match="too long"):
        validate_protein_sequence(long_seq)


def test_validate_target_rejects_forbidden_u():
    """Target containing 'U' must raise."""
    with pytest.raises(ComplexInputError, match="forbidden"):
        validate_protein_sequence("A" * TARGET_MIN_LEN + "U")


def test_validate_target_rejects_forbidden_o():
    """Target containing 'O' must raise."""
    with pytest.raises(ComplexInputError, match="forbidden"):
        validate_protein_sequence("A" * TARGET_MIN_LEN + "O")


def test_validate_target_rejects_forbidden_b():
    """Target containing 'B' must raise."""
    with pytest.raises(ComplexInputError, match="forbidden"):
        validate_protein_sequence("A" * TARGET_MIN_LEN + "B")


def test_validate_target_rejects_forbidden_z():
    """Target containing 'Z' must raise."""
    with pytest.raises(ComplexInputError, match="forbidden"):
        validate_protein_sequence("A" * TARGET_MIN_LEN + "Z")


def test_validate_target_rejects_forbidden_j():
    """Target containing 'J' must raise."""
    with pytest.raises(ComplexInputError, match="forbidden"):
        validate_protein_sequence("A" * TARGET_MIN_LEN + "J")


def test_validate_target_rejects_forbidden_x():
    """Target containing 'X' must raise."""
    with pytest.raises(ComplexInputError, match="forbidden"):
        validate_protein_sequence("A" * TARGET_MIN_LEN + "X")


# ---------------------------------------------------------------------------
# validate_peptide_sequence
# ---------------------------------------------------------------------------


def test_validate_peptide_accepts_standard_sequence():
    """A standard 20-AA peptide must pass validation."""
    validate_peptide_sequence(SAMPLE_PEPTIDE)  # should not raise


def test_validate_peptide_rejects_empty():
    """Empty peptide sequence must raise ComplexInputError."""
    with pytest.raises(ComplexInputError, match="empty"):
        validate_peptide_sequence("")


def test_validate_peptide_rejects_too_short():
    """Peptide shorter than PEPTIDE_MIN_LEN must raise."""
    short = "A" * (PEPTIDE_MIN_LEN - 1)
    with pytest.raises(ComplexInputError, match="too short"):
        validate_peptide_sequence(short)


def test_validate_peptide_rejects_too_long():
    """Peptide longer than PEPTIDE_MAX_LEN must raise."""
    long_seq = "A" * (PEPTIDE_MAX_LEN + 1)
    with pytest.raises(ComplexInputError, match="too long"):
        validate_peptide_sequence(long_seq)


def test_validate_peptide_rejects_forbidden_residues():
    """Peptide containing forbidden residues must raise."""
    for bad in ("U", "O", "B", "Z", "J", "X"):
        seq = "ACDEF" + bad
        with pytest.raises(ComplexInputError, match="forbidden|non-standard"):
            validate_peptide_sequence(seq)


# ---------------------------------------------------------------------------
# build_multimer_fasta
# ---------------------------------------------------------------------------


def test_fasta_has_one_record():
    """FASTA must contain exactly one record for ColabFold complex mode."""
    fasta = build_multimer_fasta(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    headers = [line for line in fasta.splitlines() if line.startswith(">")]
    assert len(headers) == 1


def test_fasta_header_contains_chain_ids():
    """Header must contain both chain identifiers separated by '|'."""
    fasta = build_multimer_fasta(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    assert ">target_chain_A|candidate_peptide_chain_B" in fasta


def test_fasta_sequences_colon_separated():
    """Target and peptide must be separated by ':' on the sequence line."""
    fasta = build_multimer_fasta(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    lines = [line for line in fasta.splitlines() if not line.startswith(">") and line]
    assert len(lines) == 1
    assert lines[0] == f"{SAMPLE_TARGET.upper()}:{SAMPLE_PEPTIDE.upper()}"


def test_fasta_target_sequence_intact():
    """Target sequence must appear exactly as provided (uppercased)."""
    fasta = build_multimer_fasta(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    assert SAMPLE_TARGET.upper() in fasta


def test_fasta_peptide_sequence_intact():
    """Peptide sequence must appear exactly as provided (uppercased)."""
    fasta = build_multimer_fasta(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    assert SAMPLE_PEPTIDE.upper() in fasta


def test_fasta_custom_chain_ids():
    """Custom chain IDs must appear in the single header."""
    fasta = build_multimer_fasta(
        SAMPLE_TARGET, SAMPLE_PEPTIDE, target_chain_id="C", peptide_chain_id="D"
    )
    assert ">target_chain_C|candidate_peptide_chain_D" in fasta


def test_fasta_rejects_duplicate_chain_ids():
    """Duplicate chain IDs must raise ComplexInputError."""
    with pytest.raises(ComplexInputError, match="must differ"):
        build_multimer_fasta(
            SAMPLE_TARGET, SAMPLE_PEPTIDE, target_chain_id="A", peptide_chain_id="A"
        )


def test_fasta_rejects_invalid_chain_id():
    """Non-single-letter chain IDs must raise."""
    with pytest.raises(ComplexInputError, match="single uppercase letter"):
        build_multimer_fasta(
            SAMPLE_TARGET, SAMPLE_PEPTIDE, target_chain_id="AA", peptide_chain_id="B"
        )


# ---------------------------------------------------------------------------
# build_complex_prediction_manifest
# ---------------------------------------------------------------------------


def test_manifest_has_correct_job_type():
    """Manifest job_type must be complex_structure_prediction."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    assert manifest["job_type"] == "complex_structure_prediction"


def test_manifest_stage_is_input_preparation_only():
    """Manifest stage must be input_preparation_only."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    assert manifest["stage"] == "input_preparation_only"


def test_manifest_prediction_type():
    """Manifest prediction_type must be complex_structure_prediction_input_only."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    assert manifest["prediction_type"] == "complex_structure_prediction_input_only"


def test_manifest_validation_status():
    """Manifest validation_status must be NOT_EXPERIMENTALLY_VALIDATED."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    assert manifest["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_manifest_prediction_status():
    """Manifest prediction_status must be COMPUTATIONAL_COMPLEX_PREDICTION_INPUT_ONLY."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    assert manifest["prediction_status"] == "COMPUTATIONAL_COMPLEX_PREDICTION_INPUT_ONLY"


def test_manifest_metrics_are_real_is_false():
    """Manifest metrics_are_real must be False (input prep, not real prediction)."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    assert manifest["metrics_are_real"] is False


def test_manifest_chain_mapping():
    """Manifest chain_mapping must have A=target, B=peptide."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    cm = manifest["chain_mapping"]
    assert cm["A"] == "target"
    assert cm["B"] == "peptide"


def test_manifest_chain_mapping_custom_ids():
    """Custom chain IDs must be reflected in chain_mapping."""
    manifest = build_complex_prediction_manifest(
        SAMPLE_TARGET, SAMPLE_PEPTIDE, target_chain_id="C", peptide_chain_id="D"
    )
    cm = manifest["chain_mapping"]
    assert cm["C"] == "target"
    assert cm["D"] == "peptide"


def test_manifest_contains_fasta_content():
    """Manifest must contain the generated FASTA string."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    assert "fasta_content" in manifest
    assert ">target_chain_A|candidate_peptide_chain_B" in manifest["fasta_content"]


def test_manifest_target_metadata():
    """Manifest target block must have correct metadata."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    t = manifest["target"]
    assert t["chain_id"] == "A"
    assert t["name"] == "target"
    assert t["sequence_length"] == len(SAMPLE_TARGET)
    assert t["sequence"] == SAMPLE_TARGET.upper()


def test_manifest_peptide_metadata():
    """Manifest peptide block must have correct metadata."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    p = manifest["peptide"]
    assert p["chain_id"] == "B"
    assert p["name"] == "candidate_peptide"
    assert p["sequence_length"] == len(SAMPLE_PEPTIDE)
    assert p["sequence"] == SAMPLE_PEPTIDE.upper()


def test_manifest_has_no_pdockq():
    """Manifest must not contain a pDockQ field at top level."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    assert "pDockQ" not in manifest


def test_manifest_has_no_delta_g():
    """Manifest must not contain a delta_G field at top level."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    assert "delta_G" not in manifest


def test_manifest_has_no_docking_score():
    """Manifest must not contain a docking_score field at top level."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    assert "docking_score" not in manifest


def test_manifest_forbidden_metrics_are_null():
    """Manifest forbidden_metrics must have pDockQ/delta_G/docking_score as null."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_PEPTIDE)
    fm = manifest["forbidden_metrics"]
    assert fm["pDockQ"] is None
    assert fm["delta_G"] is None
    assert fm["docking_score"] is None


def test_manifest_includes_candidate_id_when_provided():
    """Manifest must include candidate_id when passed."""
    manifest = build_complex_prediction_manifest(
        SAMPLE_TARGET, SAMPLE_PEPTIDE, candidate_id="cand-123"
    )
    assert manifest["candidate_id"] == "cand-123"


def test_manifest_includes_job_id_when_provided():
    """Manifest must include source_job_id when passed."""
    manifest = build_complex_prediction_manifest(
        SAMPLE_TARGET, SAMPLE_PEPTIDE, job_id="job-456"
    )
    assert manifest["source_job_id"] == "job-456"


# ---------------------------------------------------------------------------
# Fixtures persistence
# ---------------------------------------------------------------------------


def test_fixture_files_match_manifest(tmp_path: Path):
    """Write fixture FASTA and manifest to disk and verify round-trip."""
    manifest = build_complex_prediction_manifest(SAMPLE_TARGET, SAMPLE_SHORT_PEPTIDE)
    fasta = manifest["fasta_content"]

    fasta_path = tmp_path / "sample_target_peptide_multimer.fasta"
    manifest_path = tmp_path / "sample_complex_prediction_manifest.json"

    fasta_path.write_text(fasta, encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Round-trip verification
    loaded_fasta = fasta_path.read_text(encoding="utf-8")
    loaded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert loaded_fasta == fasta
    assert loaded_manifest["job_type"] == "complex_structure_prediction"
    assert loaded_manifest["chain_mapping"]["A"] == "target"
    assert loaded_manifest["chain_mapping"]["B"] == "peptide"
    assert ">target_chain_A|candidate_peptide_chain_B" in loaded_fasta
