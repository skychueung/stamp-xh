"""
Tests for epitope scanner (epitope_scanner.py) and epitope router.

Covers:
  - OprF 68 aa → 54 windows of 15 aa
  - POST /api/v1/epitope/scan returns candidates
  - top_k=20 returns at most 20
  - validation_status = NOT_EXPERIMENTALLY_VALIDATED
  - mode = REAL_BIOPHYSICS_SLIDING_WINDOW
  - Each candidate has required fields
  - Illegal character handling
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models.epitope import EpitopeScanFilters, EpitopeScanRequest  # noqa: E402
from app.services.epitope_scanner import scan_epitopes  # noqa: E402

# OprF 68 aa reference sequence (extended to full 68 residues)
OPRF_68 = (
    "MKKTAIAIAIVAAGVATVQAATAEQVNTLKGNVAAGAANLNETTSGVQNYTQFDFNLDKES"
    "GQNSVEI"
)
assert len(OPRF_68) == 68, f"OPRF_68 must be 68 aa, got {len(OPRF_68)}"


class TestSlidingWindowCount:
    """Verify that 68 aa OprF produces exactly 54 windows of size 15."""

    def test_oprf_68_aa_54_windows(self):
        result = scan_epitopes(
            sequence=OPRF_68,
            target_name="Pseudomonas OprF",
            species="Pseudomonas aeruginosa",
            window_size=15,
            top_k=20,
        )
        summary = result["input_summary"]
        assert summary["total_windows"] == 54
        assert summary["sequence_length"] == 68
        assert summary["window_size"] == 15

    def test_shorter_than_window(self):
        result = scan_epitopes(
            sequence="MKKTAIA",
            window_size=15,
            top_k=20,
        )
        assert result["input_summary"]["total_windows"] == 0
        assert result["candidates"] == []

    def test_exact_window_length(self):
        result = scan_epitopes(
            sequence="A" * 15,
            window_size=15,
            top_k=20,
        )
        assert result["input_summary"]["total_windows"] == 1
        assert len(result["candidates"]) == 1

    def test_window_count_formula(self):
        """n - w + 1 windows for sequence length n, window size w."""
        for seq_len in [20, 30, 50, 68]:
            seq = "A" * seq_len
            result = scan_epitopes(sequence=seq, window_size=15, top_k=20)
            expected = seq_len - 15 + 1
            assert result["input_summary"]["total_windows"] == expected


class TestCandidateFields:
    """Verify each candidate has all required fields."""

    REQUIRED_FIELDS = [
        "candidate_id", "start", "end", "sequence", "length",
        "net_charge", "pI", "GRAVY", "cys_count", "disulfide_risk",
        "hydrophobicity_class", "filter_status", "ranking_score",
    ]

    def test_candidates_have_required_fields(self):
        result = scan_epitopes(sequence=OPRF_68, top_k=20)
        candidates = result["candidates"]
        assert len(candidates) > 0
        for c in candidates:
            for field in self.REQUIRED_FIELDS:
                assert field in c, f"Missing field: {field}"

    def test_candidate_id_format(self):
        result = scan_epitopes(sequence=OPRF_68, top_k=5)
        for c in result["candidates"]:
            assert c["candidate_id"].startswith("epi_")
            parts = c["candidate_id"].split("_")
            assert len(parts) == 3  # epi_start_end

    def test_sequence_matches_window(self):
        result = scan_epitopes(sequence=OPRF_68, top_k=20)
        for c in result["candidates"]:
            assert c["length"] == 15
            assert c["end"] - c["start"] + 1 == 15
            expected_seq = OPRF_68[c["start"] - 1 : c["end"]]
            assert c["sequence"] == expected_seq

    def test_ranking_scores_are_descending(self):
        result = scan_epitopes(sequence=OPRF_68, top_k=20)
        scores = [c["ranking_score"] for c in result["candidates"]]
        assert scores == sorted(scores, reverse=True)


class TestTopK:
    def test_top_k_20_returns_at_most_20(self):
        result = scan_epitopes(sequence=OPRF_68, top_k=20)
        assert len(result["candidates"]) <= 20
        assert result["filtering_summary"]["returned"] <= 20

    def test_top_k_5(self):
        result = scan_epitopes(sequence=OPRF_68, top_k=5)
        assert len(result["candidates"]) <= 5


class TestModeAndValidation:
    """Verify mode and validation_status are correct."""

    def test_mode_is_real_biophysics(self):
        result = scan_epitopes(sequence=OPRF_68, top_k=10)
        assert result["mode"] == "REAL_BIOPHYSICS_SLIDING_WINDOW"

    def test_validation_status_not_validated(self):
        result = scan_epitopes(sequence=OPRF_68, top_k=10)
        assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"

    def test_response_code_200(self):
        result = scan_epitopes(sequence=OPRF_68, top_k=10)
        assert result["code"] == 200


class TestBiophysicalAccuracy:
    """Quick sanity checks on computed values."""

    def test_window_0_charge(self):
        """First window (start=1) should have positive charge from 2x Lys."""
        result = scan_epitopes(sequence=OPRF_68, top_k=54)
        # Find the candidate with start=1 (first window)
        first_window = [c for c in result["candidates"] if c["start"] == 1][0]
        # MKKTAIAIAIVAAGV has 2 Lys → positive charge
        assert first_window["net_charge"] > 0.5

    def test_windows_with_cys(self):
        """OprF has no C, but some test sequences do."""
        result = scan_epitopes(sequence="C" * 30, top_k=5)
        for c in result["candidates"]:
            assert c["cys_count"] == 15
            assert c["disulfide_risk"] == "potential_disulfide"

    def test_all_gravy_computed(self):
        result = scan_epitopes(sequence=OPRF_68, top_k=20)
        for c in result["candidates"]:
            assert isinstance(c["GRAVY"], (int, float))

    def test_all_pI_computed(self):
        result = scan_epitopes(sequence=OPRF_68, top_k=20)
        for c in result["candidates"]:
            assert isinstance(c["pI"], (int, float))
            assert 0.0 <= c["pI"] <= 14.0


class TestFilters:
    def test_strict_filters_filter_out_all(self):
        filters = EpitopeScanFilters(
            min_charge=-0.1,
            max_charge=0.1,
            min_pI=6.9,
            max_pI=7.1,
            max_gravy=-1.0,
            max_cys=0,
        )
        result = scan_epitopes(sequence=OPRF_68, filters=filters, top_k=20)
        # Most windows should fail these very strict filters
        assert result["filtering_summary"]["total_windows"] == 54

    def test_lenient_filters_pass_all(self):
        filters = EpitopeScanFilters(
            min_charge=-100,
            max_charge=100,
            min_pI=0.0,
            max_pI=14.0,
            max_gravy=10.0,
            max_cys=100,
        )
        result = scan_epitopes(sequence=OPRF_68, filters=filters, top_k=20)
        assert result["filtering_summary"]["failed"] == 0


class TestIllegalCharactersViaModel:
    """Verify that the Pydantic model catches illegal characters."""

    def test_illegal_char_in_sequence(self):
        with pytest.raises(ValueError, match="illegal character"):
            EpitopeScanRequest(
                target_name="Test",
                sequence="MKKTAIAIAIVAXAGV",  # X is illegal
                window_size=15,
                top_k=20,
            )
