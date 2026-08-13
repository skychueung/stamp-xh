"""
Tests for STAMP three-part assembler (v0.7-P1c).

Covers:
  - Service: assemble_stamp() returns correct structure
  - Full sequence = TP + linker + AMP
  - display_full_sequence ends with terminal modification
  - Biophysical properties are computed
  - Router: POST /api/v1/stamp/assemble-v0.7 returns 200
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models.stamp_assembly import StampAssembleRequest  # noqa: E402
from app.services.stamp_assembler import assemble_stamp  # noqa: E402

TP_SEQ = "EEDDAEEDAEDDAEE"
LINKER = "EAAAK"
AMP_SEQ = "FSRFLRRVRRYRPKISFNLEPFFKF"


class TestServiceUnit:
    """Direct service function tests (no HTTP)."""

    def test_assemble_returns_correct_structure(self):
        req = StampAssembleRequest(
            targeting_peptide={"candidate_id": "tp_001", "sequence": TP_SEQ},
        )
        result = assemble_stamp(req)
        assert result["code"] == 200
        assert result["message"] == "success"
        assert result["mode"] == "REAL_STAMP_ASSEMBLY_V0_7"
        assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
        assert "candidate_id" in result
        assert result["candidate_id"].startswith("STAMP_V07_")
        assert "created_at" in result

    def test_raw_full_sequence_is_concatenation(self):
        req = StampAssembleRequest(
            targeting_peptide={"candidate_id": "tp_001", "sequence": TP_SEQ},
            linker=LINKER,
            amp_sequence=AMP_SEQ,
        )
        result = assemble_stamp(req)
        expected = TP_SEQ + LINKER + AMP_SEQ
        assert result["raw_full_sequence"] == expected

    def test_display_full_sequence_ends_with_terminal(self):
        req = StampAssembleRequest(
            targeting_peptide={"candidate_id": "tp_001", "sequence": TP_SEQ},
            linker=LINKER,
            amp_sequence=AMP_SEQ,
            terminal_modification="-NH2",
        )
        result = assemble_stamp(req)
        assert result["display_full_sequence"].endswith("-NH2")
        assert result["display_full_sequence"] == (TP_SEQ + LINKER + AMP_SEQ + "-NH2")

    def test_linker_is_eaaak_by_default(self):
        req = StampAssembleRequest(
            targeting_peptide={"candidate_id": "tp_001", "sequence": TP_SEQ},
        )
        result = assemble_stamp(req)
        assert result["linker"]["sequence"] == "EAAAK"
        assert result["linker"]["length"] == 5

    def test_amp_is_p4_by_default(self):
        req = StampAssembleRequest(
            targeting_peptide={"candidate_id": "tp_001", "sequence": TP_SEQ},
        )
        result = assemble_stamp(req)
        assert result["amp"]["name"] == "P4"
        assert result["amp"]["sequence"] == AMP_SEQ

    def test_length_matches_raw_sequence(self):
        req = StampAssembleRequest(
            targeting_peptide={"candidate_id": "tp_001", "sequence": TP_SEQ},
            linker=LINKER,
            amp_sequence=AMP_SEQ,
        )
        result = assemble_stamp(req)
        expected_len = len(TP_SEQ) + len(LINKER) + len(AMP_SEQ)
        assert result["length"] == expected_len

    def test_biophysical_properties_present(self):
        req = StampAssembleRequest(
            targeting_peptide={"candidate_id": "tp_001", "sequence": TP_SEQ},
        )
        result = assemble_stamp(req)
        assert isinstance(result["net_charge"], float)
        assert isinstance(result["pI"], float)
        assert isinstance(result["GRAVY"], float)
        assert isinstance(result["cys_count"], int)

    def test_created_at_is_iso_string(self):
        req = StampAssembleRequest(
            targeting_peptide={"candidate_id": "tp_001", "sequence": TP_SEQ},
        )
        result = assemble_stamp(req)
        assert "created_at" in result
        assert isinstance(result["created_at"], str)
        assert "T" in result["created_at"]

    def test_targeting_domain_metadata(self):
        req = StampAssembleRequest(
            targeting_peptide={"candidate_id": "tp_001", "sequence": TP_SEQ},
        )
        result = assemble_stamp(req)
        assert result["targeting_domain"]["name"] == "tp_001"
        assert result["targeting_domain"]["sequence"] == TP_SEQ
        assert result["targeting_domain"]["length"] == len(TP_SEQ)

    def test_custom_linker_and_amp(self):
        req = StampAssembleRequest(
            targeting_peptide={"candidate_id": "tp_001", "sequence": "KKKK"},
            linker="GGGGS",
            amp_name="P2",
            amp_sequence="AAAA",
            terminal_modification="-COOH",
        )
        result = assemble_stamp(req)
        assert result["linker"]["sequence"] == "GGGGS"
        assert result["amp"]["name"] == "P2"
        assert result["display_full_sequence"].endswith("-COOH")


@pytest.mark.asyncio
class TestRouterIntegration:
    """HTTP-level integration tests via async client."""

    async def test_post_assemble_returns_200(self, client):
        payload = {
            "targeting_peptide": {
                "candidate_id": "tp_001",
                "sequence": TP_SEQ,
            },
            "linker": LINKER,
            "amp_name": "P4",
            "amp_sequence": AMP_SEQ,
            "terminal_modification": "-NH2",
        }
        response = await client.post("/api/v1/stamp/assemble-v0.7", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["mode"] == "REAL_STAMP_ASSEMBLY_V0_7"
        assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
        assert data["linker"]["sequence"] == LINKER
        assert data["amp"]["name"] == "P4"
        assert data["display_full_sequence"].endswith("-NH2")

    async def test_post_assemble_invalid_peptide(self, client):
        payload = {
            "targeting_peptide": {
                "candidate_id": "tp_001",
                "sequence": "",
            },
        }
        response = await client.post("/api/v1/stamp/assemble-v0.7", json=payload)
        assert response.status_code == 422
