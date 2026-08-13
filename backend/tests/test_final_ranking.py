"""
Tests for Final Ranking service and router (v0.7-P1e).

Covers:
  - Service: compute_final_ranking() returns correct structure
  - Heuristic score is within [0, 1]
  - Candidates are sorted descending by composite_score
  - Router: POST /api/v1/final-ranking/compute returns 200
  - Empty request returns 422
  - Ranking methodology metadata is present
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.final_ranking import compute_final_ranking  # noqa: E402

SAMPLE_CANDIDATES = [
    {
        "candidate_id": "STAMP_V07_001",
        "full_sequence": "EEDDAEEDAEDDAEEEAAAKFSRFLRRVRRYRPKISFNLEPFFKF",
        "targeting_peptide": "EEDDAEEDAEDDAEE",
        "linker": "EAAAK",
        "amp": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "length": 45,
        "net_charge": 5.0,
        "pI": 8.5,
        "GRAVY": -0.35,
        "cys_count": 0,
        "mode": "REAL_STAMP_ASSEMBLY_V0_7",
    },
    {
        "candidate_id": "STAMP_V07_002",
        "full_sequence": "KKKKKGGGGSAAAAA",
        "targeting_peptide": "KKKKK",
        "linker": "GGGGS",
        "amp": "AAAAA",
        "length": 15,
        "net_charge": 8.0,
        "pI": 10.5,
        "GRAVY": 0.5,
        "cys_count": 2,
        "mode": "REAL_STAMP_ASSEMBLY_V0_7",
    },
]


class TestServiceUnit:
    """Direct service function tests (no HTTP)."""

    def test_compute_returns_correct_structure(self):
        result = compute_final_ranking(SAMPLE_CANDIDATES)
        assert result["code"] == 200
        assert result["message"] == "success"
        assert result["mode"] == "HEURISTIC_FINAL_RANKING_V0_7"
        assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
        assert result["total_candidates"] == len(SAMPLE_CANDIDATES)
        assert "ranked_candidates" in result
        assert "ranking_methodology" in result

    def test_scores_are_within_range(self):
        result = compute_final_ranking(SAMPLE_CANDIDATES)
        for c in result["ranked_candidates"]:
            assert 0.0 <= c["composite_score"] <= 1.0

    def test_candidates_sorted_descending(self):
        result = compute_final_ranking(SAMPLE_CANDIDATES)
        scores = [c["composite_score"] for c in result["ranked_candidates"]]
        assert scores == sorted(scores, reverse=True)

    def test_methodology_contains_weights(self):
        result = compute_final_ranking(SAMPLE_CANDIDATES)
        methodology = result["ranking_methodology"]
        assert "weights" in methodology
        assert "length" in methodology["weights"]
        assert "net_charge" in methodology["weights"]
        assert "pI" in methodology["weights"]
        assert "GRAVY" in methodology["weights"]
        assert "cys_count" in methodology["weights"]

    def test_methodology_excludes_ml_metrics(self):
        result = compute_final_ranking(SAMPLE_CANDIDATES)
        excluded = result["ranking_methodology"]["excluded_metrics"]
        assert "MIC" in excluded
        assert "MBC" in excluded
        assert "hemolysis" in excluded
        assert "toxicity" in excluded
        assert "ipTM" in excluded
        assert "pDockQ" in excluded
        assert "docking_score" in excluded

    def test_single_candidate(self):
        result = compute_final_ranking([SAMPLE_CANDIDATES[0]])
        assert result["total_candidates"] == 1
        assert result["ranked_candidates"][0]["candidate_id"] == "STAMP_V07_001"

    def test_validation_status_on_every_candidate(self):
        result = compute_final_ranking(SAMPLE_CANDIDATES)
        for c in result["ranked_candidates"]:
            assert c["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


@pytest.mark.asyncio
class TestRouterIntegration:
    """HTTP-level integration tests via async client."""

    async def test_post_compute_returns_200(self, client):
        payload = {"candidates": SAMPLE_CANDIDATES}
        response = await client.post("/api/v1/final-ranking/compute", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["mode"] == "HEURISTIC_FINAL_RANKING_V0_7"
        assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
        assert data["total_candidates"] == 2
        assert len(data["ranked_candidates"]) == 2

    async def test_post_compute_empty_candidates_422(self, client):
        payload = {"candidates": []}
        response = await client.post("/api/v1/final-ranking/compute", json=payload)
        assert response.status_code == 422

    async def test_post_compute_methodology_present(self, client):
        payload = {"candidates": SAMPLE_CANDIDATES}
        response = await client.post("/api/v1/final-ranking/compute", json=payload)
        data = response.json()
        assert "ranking_methodology" in data
        assert data["ranking_methodology"]["experimental_validation"] == "None. All candidates are NOT_EXPERIMENTALLY_VALIDATED."
