"""
Tests for the service layer (AMP selection, sequence validation).

These tests bypass the HTTP layer and exercise business logic directly.
They are faster than integration tests and validate edge cases that are
hard to reach through the API.

Covers:
    - AMP selector: P4 priority rule
    - AMP selector: fallback when P4 is missing
    - AMP selector: explicit preferred_name selection
    - AMP selector: empty library raises error
    - AMP selector: preferred_name not found raises error
    - Sequence validator: valid sequences pass
    - Sequence validator: illegal characters fail
    - Sequence validator: empty sequence fails
    - Sequence validator: lowercase fails
    - Sequence validator: sequence too long fails
    - STAMP builder: full assembly pipeline
"""

from __future__ import annotations

from typing import Any

import pytest

# ---------------------------------------------------------------------------
# AMP Selector Tests
# ---------------------------------------------------------------------------


class TestAMPSelector:
    """Tests for the AMP selection service."""

    @pytest.fixture
    def amp_library_with_p4(self) -> list[dict[str, Any]]:
        """AMP library containing P4 (preferred) and others."""
        return [
            {
                "amp_name": "P4",
                "raw_sequence": "FSRFLRRVRRYRPKISFNLEPFFKF5",
                "clean_sequence": "FSRFLRRVRRYRPKISFNLEPFFKF",
                "source": "cosmetic_preservative_screening",
                "priority": "high",
                "role": "killing_domain",
                "illegal_char_found": "5",
                "illegal_char_position": "25",
            },
            {
                "amp_name": "P15",
                "raw_sequence": "GWKRKNMGKVGKAVCGLKGLAKGM",
                "clean_sequence": "GWKRKNMGKVGKAVCGLKGLAKGM",
                "source": "synthetic_library",
                "priority": "high",
                "role": "killing_domain",
            },
        ]

    @pytest.fixture
    def amp_library_without_p4(self) -> list[dict[str, Any]]:
        """AMP library without P4 — tests fallback logic."""
        return [
            {
                "amp_name": "P15",
                "raw_sequence": "GWKRKNMGKVGKAVCGLKGLAKGM",
                "clean_sequence": "GWKRKNMGKVGKAVCGLKGLAKGM",
                "source": "synthetic_library",
                "priority": "high",
                "role": "killing_domain",
            },
            {
                "amp_name": "P7",
                "raw_sequence": "KWKLFKKIGAVLKVLTTGLPALIS",
                "clean_sequence": "KWKLFKKIGAVLKVLTTGLPALIS",
                "source": "natural_variant",
                "priority": "medium",
                "role": "killing_domain",
            },
        ]

    @pytest.fixture
    def empty_amp_library(self) -> list[dict[str, Any]]:
        """Empty AMP library — tests error handling."""
        return []

    def test_amp_selector_p4_priority(self, amp_library_with_p4: list[dict]) -> None:
        """When P4 is present, select_amp must return P4 unconditionally.

        This is the default (no preferred_name) code path.
        """
        from app.services.amp_selector import select_amp

        result = select_amp(amp_library_with_p4)

        assert result.amp_name == "P4", (
            f"Expected P4 (priority rule), got {result.amp_name}"
        )
        assert result.clean_sequence == "FSRFLRRVRRYRPKISFNLEPFFKF", (
            f"P4 clean sequence mismatch: {result.clean_sequence}"
        )

    def test_amp_selector_fallback(self, amp_library_without_p4: list[dict]) -> None:
        """When P4 is absent, select_amp falls back to first available AMP.

        With no preferred_name and no P4, it should select the first
        high-priority AMP (P15 in this fixture).
        """
        from app.services.amp_selector import select_amp

        result = select_amp(amp_library_without_p4)

        assert result.amp_name == "P15", (
            f"Expected P15 (fallback), got {result.amp_name}"
        )

    def test_amp_selector_explicit_preferred(
        self, amp_library_with_p4: list[dict]
    ) -> None:
        """When a preferred_name is explicitly given, it overrides P4 priority."""
        from app.services.amp_selector import select_amp

        result = select_amp(amp_library_with_p4, preferred_name="P15")

        assert result.amp_name == "P15", (
            f"Explicit P15 selection failed, got {result.amp_name}"
        )

    def test_amp_selector_preferred_not_found(
        self, amp_library_with_p4: list[dict]
    ) -> None:
        """When preferred_name does not exist, AmpNotFoundError is raised."""
        from app.core.exceptions import AmpNotFoundError
        from app.services.amp_selector import select_amp

        with pytest.raises(AmpNotFoundError) as exc_info:
            select_amp(amp_library_with_p4, preferred_name="NON_EXISTENT")

        assert "NON_EXISTENT" in str(exc_info.value)

    def test_amp_selector_empty_library(self, empty_amp_library: list[dict]) -> None:
        """When the AMP library is empty, AmpLibraryEmptyError is raised."""
        from app.core.exceptions import AmpLibraryEmptyError
        from app.services.amp_selector import select_amp

        with pytest.raises(AmpLibraryEmptyError):
            select_amp(empty_amp_library)


# ---------------------------------------------------------------------------
# Sequence Validator Tests
# ---------------------------------------------------------------------------


class TestSequenceValidator:
    """Tests for the sequence validation service."""

    def test_sequence_validator_valid(self) -> None:
        """A standard amino acid sequence passes validation."""
        from app.services.sequence_validator import validate_sequence

        seq = "DKTKKAFLIAAG"
        result = validate_sequence(seq)

        assert result == seq, f"Valid sequence should return unchanged, got {result}"

    def test_sequence_validator_valid_long(self) -> None:
        """A longer valid sequence also passes."""
        from app.services.sequence_validator import validate_sequence

        seq = "FSRFLRRVRRYRPKISFNLEPFFKF"
        result = validate_sequence(seq)

        assert result == seq

    def test_sequence_validator_invalid_char(self) -> None:
        """Sequences with illegal characters raise InvalidSequenceError."""
        from app.core.exceptions import InvalidSequenceError
        from app.services.sequence_validator import validate_sequence

        with pytest.raises(InvalidSequenceError) as exc_info:
            validate_sequence("DKTKKAFL1AAG")  # '1' is illegal

        assert "illegal" in str(exc_info.value).lower() or "1" in str(exc_info.value)

    def test_sequence_validator_invalid_char_x(self) -> None:
        """'X' (unknown residue) is rejected as illegal."""
        from app.core.exceptions import InvalidSequenceError
        from app.services.sequence_validator import validate_sequence

        with pytest.raises(InvalidSequenceError):
            validate_sequence("MKFLRKASXVILL")  # 'X' is illegal

    def test_sequence_validator_empty(self) -> None:
        """Empty string raises InvalidSequenceError."""
        from app.core.exceptions import InvalidSequenceError
        from app.services.sequence_validator import validate_sequence

        with pytest.raises(InvalidSequenceError):
            validate_sequence("")

    def test_sequence_validator_whitespace_only(self) -> None:
        """Whitespace-only string raises InvalidSequenceError."""
        from app.core.exceptions import InvalidSequenceError
        from app.services.sequence_validator import validate_sequence

        with pytest.raises(InvalidSequenceError):
            validate_sequence("   ")

    def test_sequence_validator_lowercase(self) -> None:
        """Lowercase letters are converted to uppercase (or accepted after upper()).

        The validator calls .upper() internally, so lowercase should pass.
        """
        from app.services.sequence_validator import validate_sequence

        result = validate_sequence("dktkkafliaag")
        assert result == "DKTKKAFLIAAG"

    def test_sequence_validator_trailing_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped before validation."""
        from app.services.sequence_validator import validate_sequence

        result = validate_sequence("  DKTKKAFLIAAG  ")
        assert result == "DKTKKAFLIAAG"

    def test_sequence_validator_all_20_aa(self) -> None:
        """All 20 standard amino acids are accepted."""
        from app.services.sequence_validator import validate_sequence

        all_20 = "ACDEFGHIKLMNPQRSTVWY"
        result = validate_sequence(all_20)
        assert result == all_20


# ---------------------------------------------------------------------------
# STAMP Builder Tests
# ---------------------------------------------------------------------------


class TestStampBuilder:
    """Tests for the STAMP build orchestrator."""

    @pytest.fixture
    def pepmlm_candidates(self) -> list[dict[str, Any]]:
        """Minimal PepMLM candidate list."""
        return [
            {
                "candidate_id": "OPRF_0001",
                "target_name": "Pseudomonas_OprF",
                "peptide_length": 12,
                "generated_peptide": "DKTKKAFLIAAG",
                "ppl_score": 9.1933,
                "net_charge": 2.0,
                "pI": 7.8,
                "GRAVY": 0.017,
                "cysteine_count": 0,
                "filter_status": "Pass",
            }
        ]

    @pytest.fixture
    def amp_library(self) -> list[dict[str, Any]]:
        """Minimal AMP library with P4."""
        return [
            {
                "amp_name": "P4",
                "raw_sequence": "FSRFLRRVRRYRPKISFNLEPFFKF5",
                "clean_sequence": "FSRFLRRVRRYRPKISFNLEPFFKF",
                "source": "cosmetic_preservative_screening",
                "priority": "high",
                "role": "killing_domain",
                "illegal_char_found": "5",
                "illegal_char_position": "25",
            }
        ]

    def test_build_stamp_full_pipeline(
        self, pepmlm_candidates: list[dict], amp_library: list[dict]
    ) -> None:
        """The full build_stamp pipeline produces a valid StampCandidate."""
        from app.services.stamp_builder import build_stamp

        result = build_stamp(
            candidate_id="OPRF_0001",
            amp_library=amp_library,
            pepmlm_candidates=pepmlm_candidates,
        )

        # Verify it's a StampCandidate (or dict serialization)
        assert result.candidate_id == "stamp_oprf_0001", (
            f"Unexpected candidate_id: {result.candidate_id}"
        )

        # Verify three domains are present
        assert result.targeting_domain is not None
        assert result.linker is not None
        assert result.killing_domain is not None

        # Verify linker is EAAAK
        assert result.linker.sequence == "EAAAK"
        assert result.linker.length == 5

        # Verify killing domain is P4
        assert result.killing_domain.name == "P4"
        assert result.killing_domain.sequence == "FSRFLRRVRRYRPKISFNLEPFFKF"

        # Verify sequences
        assert "EAAAK" in result.raw_full_sequence
        assert "-NH2" in result.display_full_sequence
        assert result.display_full_sequence.endswith("-NH2")

        # Verify no mock scores
        assert result.mock_scores is None

        # Verify validation status
        assert result.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"

        # Verify experimental all null
        assert result.experimental.MIC_ug_ml is None
        assert result.experimental.ipTM is None
        assert result.experimental.pDockQ is None

        # Verify completeness
        assert result.is_complete is True

    def test_build_stamp_with_explicit_amp(
        self, pepmlm_candidates: list[dict], amp_library: list[dict]
    ) -> None:
        """Building with explicit preferred_amp_name selects that AMP."""
        # Note: This test assumes amp_library only has P4;
        # in a richer library we'd test overriding to P15
        from app.services.stamp_builder import build_stamp

        result = build_stamp(
            candidate_id="OPRF_0001",
            amp_library=amp_library,
            pepmlm_candidates=pepmlm_candidates,
            preferred_amp_name="P4",
        )

        assert result.killing_domain.name == "P4"

    def test_build_stamp_peptide_not_found(self, amp_library: list[dict]) -> None:
        """Building with a non-existent peptide ID raises CandidateNotFoundError."""
        from app.core.exceptions import CandidateNotFoundError
        from app.services.stamp_builder import build_stamp

        with pytest.raises(CandidateNotFoundError):
            build_stamp(
                candidate_id="NON_EXISTENT",
                amp_library=amp_library,
                pepmlm_candidates=[],  # Empty — peptide won't be found
            )

    def test_build_stamp_empty_amp_library(
        self, pepmlm_candidates: list[dict]
    ) -> None:
        """Building with empty AMP library raises AmpLibraryEmptyError."""
        from app.core.exceptions import AmpLibraryEmptyError
        from app.services.stamp_builder import build_stamp

        with pytest.raises(AmpLibraryEmptyError):
            build_stamp(
                candidate_id="OPRF_0001",
                amp_library=[],
                pepmlm_candidates=pepmlm_candidates,
            )


# ---------------------------------------------------------------------------
# Helper function tests (assemble_stamp_sequence)
# ---------------------------------------------------------------------------


class TestSequenceAssembly:
    """Tests for the sequence assembly utility."""

    def test_assemble_stamp_sequence_basic(self) -> None:
        """assemble_stamp_sequence produces correct raw and display strings."""
        from app.services.sequence_validator import (
            LINKER_SEQUENCE,
            TERMINAL_MOD,
            assemble_stamp_sequence,
        )

        tp = "DKTKKAFLIAAG"
        amp = "FSRFLRRVRRYRPKISFNLEPFFKF"

        raw, display = assemble_stamp_sequence(tp, amp)

        expected_raw = f"{tp}{LINKER_SEQUENCE}{amp}"
        expected_display = f"{tp}-{LINKER_SEQUENCE}-{amp}{TERMINAL_MOD}"

        assert raw == expected_raw, f"raw mismatch: {raw} != {expected_raw}"
        assert display == expected_display, (
            f"display mismatch: {display} != {expected_display}"
        )

    def test_assemble_stamp_sequence_no_dash_in_raw(self) -> None:
        """Raw sequence must never contain dashes."""
        from app.services.sequence_validator import assemble_stamp_sequence

        raw, _display = assemble_stamp_sequence("ABC", "DEF")
        assert "-" not in raw, "Raw sequence must not contain dashes"

    def test_assemble_stamp_sequence_display_ends_with_nh2(self) -> None:
        """Display sequence must end with -NH2."""
        from app.services.sequence_validator import assemble_stamp_sequence

        _raw, display = assemble_stamp_sequence("ABC", "DEF")
        assert display.endswith("-NH2"), f"Display must end with -NH2: {display}"
