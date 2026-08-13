"""
Tests for rule-based targeting peptide generator.

Covers:
  - Service: generate_targeting_peptides() returns 20 candidates
  - All candidates have required fields
  - All candidates have Cys count = 0
  - All candidates have length 8-15
  - Router: POST /api/v1/targeting-peptide/generate returns 200
  - Validation status and mode are correct
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models.targeting_peptide import (  # noqa: E402
    SourceEpitope,
)
from app.services.targeting_peptide_generator import generate_targeting_peptides  # noqa: E402

OPRF_15 = "MKKTAIAIAIVAAGV"


class TestServiceUnit:
    """Direct service function tests (no HTTP)."""

    REQUIRED_FIELDS = [
        "candidate_id",
        "source_epitope_id",
        "sequence",
        "length",
        "net_charge",
        "pI",
        "GRAVY",
        "cys_count",
        "complementarity_note",
        "filter_status",
        "ranking_score",
        "validation_status",
        "mode",
    ]

    def test_returns_20_candidates(self):
        source = SourceEpitope(
            candidate_id="epi_1_15",
            sequence=OPRF_15,
            start=1,
            end=15,
            target_name="OprF",
            species="Pseudomonas aeruginosa",
        )
        result = generate_targeting_peptides(source, requested_count=20)
        assert len(result["candidates"]) == 20

    def test_all_candidates_have_required_fields(self):
        source = SourceEpitope(
            candidate_id="epi_1_15",
            sequence=OPRF_15,
            start=1,
            end=15,
        )
        result = generate_targeting_peptides(source, requested_count=20)
        for c in result["candidates"]:
            for field in self.REQUIRED_FIELDS:
                assert field in c, f"Missing field: {field}"

    def test_all_candidates_cys_count_zero(self):
        source = SourceEpitope(
            candidate_id="epi_1_15",
            sequence=OPRF_15,
            start=1,
            end=15,
        )
        result = generate_targeting_peptides(source, requested_count=20)
        for c in result["candidates"]:
            assert c["cys_count"] == 0, f"Candidate {c['candidate_id']} has Cys"

    def test_all_candidates_length_8_to_15(self):
        source = SourceEpitope(
            candidate_id="epi_1_15",
            sequence=OPRF_15,
            start=1,
            end=15,
        )
        result = generate_targeting_peptides(source, requested_count=20)
        for c in result["candidates"]:
            assert 8 <= c["length"] <= 15, (
                f"Candidate {c['candidate_id']} length {c['length']} out of range"
            )

    def test_validation_status_and_mode(self):
        source = SourceEpitope(
            candidate_id="epi_1_15",
            sequence=OPRF_15,
            start=1,
            end=15,
        )
        result = generate_targeting_peptides(source, requested_count=20)
        assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
        assert result["mode"] == "RULE_BASED_TARGETING_PEPTIDE_GENERATION"

    def test_input_summary_present(self):
        source = SourceEpitope(
            candidate_id="epi_1_15",
            sequence=OPRF_15,
            start=1,
            end=15,
            target_name="OprF",
            species="Pseudomonas aeruginosa",
        )
        result = generate_targeting_peptides(source, requested_count=20)
        summary = result["input_summary"]
        assert summary["source_epitope_id"] == "epi_1_15"
        assert summary["source_sequence"] == OPRF_15
        assert summary["requested_count"] == 20

    def test_candidate_id_format(self):
        source = SourceEpitope(
            candidate_id="epi_1_15",
            sequence=OPRF_15,
            start=1,
            end=15,
        )
        result = generate_targeting_peptides(source, requested_count=20)
        for i, c in enumerate(result["candidates"]):
            expected_id = f"tp_{i + 1:03d}"
            assert c["candidate_id"] == expected_id

    def test_short_epitope_still_produces_20(self):
        """Even a 10-aa epitope should produce 20 candidates via pool generation."""
        source = SourceEpitope(
            candidate_id="epi_1_10",
            sequence="MKKTAIAIAI",
            start=1,
            end=10,
        )
        result = generate_targeting_peptides(source, requested_count=20)
        assert len(result["candidates"]) == 20

    def test_epitope_with_cysteine_handled(self):
        """Epitope containing C should still yield Cys=0 candidates."""
        source = SourceEpitope(
            candidate_id="epi_1_12",
            sequence="ACDEFGHIKLMN",
            start=1,
            end=12,
        )
        result = generate_targeting_peptides(source, requested_count=20)
        for c in result["candidates"]:
            assert c["cys_count"] == 0


@pytest.mark.asyncio
class TestRouterIntegration:
    """HTTP-level integration tests via async client."""

    async def test_post_generate_returns_200(self, client):
        payload = {
            "source_epitope": {
                "candidate_id": "epi_1_15",
                "sequence": OPRF_15,
                "start": 1,
                "end": 15,
                "target_name": "OprF",
                "species": "Pseudomonas aeruginosa",
            }
        }
        response = await client.post("/api/v1/targeting-peptide/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["message"] == "success"
        assert len(data["candidates"]) == 20
        assert data["mode"] == "RULE_BASED_TARGETING_PEPTIDE_GENERATION"

    async def test_post_generate_invalid_sequence(self, client):
        payload = {
            "source_epitope": {
                "candidate_id": "epi_1_15",
                "sequence": "MKKTAIAIAIVAAGV123",
                "start": 1,
                "end": 15,
            }
        }
        response = await client.post("/api/v1/targeting-peptide/generate", json=payload)
        assert response.status_code == 422
