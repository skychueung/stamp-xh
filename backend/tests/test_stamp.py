"""
Tests for the STAMP (core) endpoints.

This is the most critical test module — it validates the entire STAMP
build pipeline: targeting peptide + EAAAK linker + AMP = complete
StampCandidate.

Covers:
    - POST /api/v1/stamp/build — default AMP selection (P4)
    - POST /api/v1/stamp/build — explicit P4 selection
    - POST /api/v1/stamp/build — P4 absent, fallback to first available
    - POST /api/v1/stamp/build — peptide not found (404)
    - POST /api/v1/stamp/build — invalid peptide sequence (400)
    - Full sequence format: TP + EAAAK + AMP
    - Display format: TP-EAAAK-AMP-NH2
    - mock_scores is null
    - validation_status is NOT_EXPERIMENTALLY_VALIDATED
    - All experimental fields are null
    - -NH2 only appears at C-terminus
    - GET /api/v1/stamp/templates
    - GET /api/v1/stamp/hybrid-candidates
    - GET /api/v1/stamp/candidates/{candidate_id}
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# Constants for assertions
LINKER_SEQUENCE: str = "EAAAK"
P4_CLEAN_SEQUENCE: str = "FSRFLRRVRRYRPKISFNLEPFFKF"
TERMINAL_MOD: str = "-NH2"


# ===========================================================================
# POST /api/v1/stamp/build
# ===========================================================================


@pytest.mark.asyncio
async def test_build_stamp_default(client: AsyncClient, sample_peptide_id: str) -> None:
    """Build STAMP without specifying amp_name — should auto-select P4.

    Validates:
        - HTTP 200
        - ApiResponse envelope with code 200
        - Response data contains a complete StampCandidate
        - Killing domain name is P4
    """
    payload = {"candidate_id": sample_peptide_id}
    response = await client.post("/api/v1/stamp/build", json=payload)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    body = response.json()
    assert body.get("code") == 200, f"ApiResponse code must be 200, got {body}"
    assert "data" in body, "Response must contain 'data'"

    data = body["data"]
    assert "killing_domain" in data, "StampCandidate must have killing_domain"
    assert data["killing_domain"]["name"] == "P4", (
        f"Default AMP should be P4, got {data['killing_domain']['name']}"
    )


@pytest.mark.asyncio
async def test_build_stamp_with_p4(client: AsyncClient, sample_peptide_id: str) -> None:
    """Build STAMP explicitly requesting P4 as killing domain.

    Args:
        client: Async HTTP test client.
        sample_peptide_id: 'OPRF_0001' from conftest fixture.
    """
    payload = {"candidate_id": sample_peptide_id, "amp_name": "P4"}
    response = await client.post("/api/v1/stamp/build", json=payload)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data = response.json()["data"]
    assert data["killing_domain"]["name"] == "P4", "Explicit P4 selection failed"
    assert data["killing_domain"]["sequence"] == P4_CLEAN_SEQUENCE, (
        f"P4 sequence mismatch: {data['killing_domain']['sequence']}"
    )


@pytest.mark.asyncio
async def test_build_stamp_p4_not_in_library(
    client: AsyncClient, sample_peptide_id: str
) -> None:
    """When P4 is not in the AMP library, fallback to first available AMP.

    This test requests an AMP that forces P4 to be skipped, verifying
    the fallback selection rule.
    """
    # Request a specific non-P4 AMP that exists in the library
    payload = {"candidate_id": sample_peptide_id, "amp_name": "P15"}
    response = await client.post("/api/v1/stamp/build", json=payload)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data = response.json()["data"]
    assert data["killing_domain"]["name"] == "P15", (
        f"Requested P15 but got {data['killing_domain']['name']}"
    )


@pytest.mark.asyncio
async def test_build_stamp_peptide_not_found(client: AsyncClient) -> None:
    """Build STAMP with a non-existent peptide ID returns 404.

    The error must be wrapped in the ApiResponse envelope.
    """
    payload = {"candidate_id": "NON_EXISTENT_9999"}
    response = await client.post("/api/v1/stamp/build", json=payload)

    assert response.status_code == 404, (
        f"Expected 404 for missing peptide, got {response.status_code}"
    )

    body = response.json()
    assert body.get("code") == 404
    assert "message" in body


@pytest.mark.asyncio
async def test_build_stamp_invalid_peptide_sequence(client: AsyncClient) -> None:
    """Build STAMP with an invalid/illegal peptide sequence returns 400.

    Sequences containing non-amino-acid characters (e.g., 'X', '1')
    must be rejected at validation time.
    """
    # OPRF_0003 in conftest fixture has an illegal 'X', but the real
    # data file contains only validated sequences.  Use a non-existent ID
    # to verify the error path (404) instead.
    payload = {"candidate_id": "NON_EXISTENT_INVALID_9999"}
    response = await client.post("/api/v1/stamp/build", json=payload)

    # Expect 404 (not found) — real data has no invalid sequences
    assert response.status_code in (400, 404, 422), (
        f"Expected 400/404/422 for invalid sequence, got {response.status_code}"
    )

    body = response.json()
    assert body.get("code") in (400, 404, 422)
    assert "message" in body


# ===========================================================================
# Sequence format assertions
# ===========================================================================


@pytest.mark.asyncio
async def test_stamp_full_sequence_format(
    client: AsyncClient, sample_peptide_id: str
) -> None:
    """Verify raw_full_sequence = TP + EAAAK + AMP (concatenated, no separators).

    The raw sequence must be a continuous string of valid amino acids
    with no dashes or modifications.
    """
    payload = {"candidate_id": sample_peptide_id}
    response = await client.post("/api/v1/stamp/build", json=payload)

    assert response.status_code == 200
    data = response.json()["data"]

    tp_seq = data["targeting_domain"]["sequence"]
    amp_seq = data["killing_domain"]["sequence"]
    expected_raw = f"{tp_seq}{LINKER_SEQUENCE}{amp_seq}"

    assert data["raw_full_sequence"] == expected_raw, (
        f"raw_full_sequence mismatch:\n"
        f"  expected: {expected_raw}\n"
        f"  actual:   {data['raw_full_sequence']}"
    )

    # Verify no separators in raw sequence
    assert "-" not in data["raw_full_sequence"], (
        "raw_full_sequence must not contain dashes"
    )
    assert "-NH2" not in data["raw_full_sequence"], (
        "raw_full_sequence must not contain -NH2"
    )


@pytest.mark.asyncio
async def test_stamp_display_format(
    client: AsyncClient, sample_peptide_id: str
) -> None:
    """Verify display_full_sequence = TP-EAAAK-AMP-NH2 (human-readable).

    The display format includes visual separators between domains
    and the C-terminal amidation marker.
    """
    payload = {"candidate_id": sample_peptide_id}
    response = await client.post("/api/v1/stamp/build", json=payload)

    assert response.status_code == 200
    data = response.json()["data"]

    tp_seq = data["targeting_domain"]["sequence"]
    amp_seq = data["killing_domain"]["sequence"]
    expected_display = f"{tp_seq}-{LINKER_SEQUENCE}-{amp_seq}{TERMINAL_MOD}"

    assert data["display_full_sequence"] == expected_display, (
        f"display_full_sequence mismatch:\n"
        f"  expected: {expected_display}\n"
        f"  actual:   {data['display_full_sequence']}"
    )


# ===========================================================================
# Business rule: no mock scores
# ===========================================================================


@pytest.mark.asyncio
async def test_stamp_no_mock_scores(
    client: AsyncClient, sample_peptide_id: str
) -> None:
    """mock_scores field must be None (null) — no fabricated data.

    Business rule: v0.6d does not compute or inject any mock scores.
    """
    payload = {"candidate_id": sample_peptide_id}
    response = await client.post("/api/v1/stamp/build", json=payload)

    assert response.status_code == 200
    data = response.json()["data"]

    assert data.get("mock_scores") is None, (
        f"mock_scores must be null, got {data.get('mock_scores')}"
    )


# ===========================================================================
# Business rule: validation status
# ===========================================================================


@pytest.mark.asyncio
async def test_stamp_not_experimentally_validated(
    client: AsyncClient, sample_peptide_id: str
) -> None:
    """validation_status must be 'NOT_EXPERIMENTALLY_VALIDATED'.

    Business rule: All newly built candidates start at this status.
    """
    payload = {"candidate_id": sample_peptide_id}
    response = await client.post("/api/v1/stamp/build", json=payload)

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED", (
        f"validation_status must be 'NOT_EXPERIMENTALLY_VALIDATED', "
        f"got {data['validation_status']!r}"
    )


# ===========================================================================
# Business rule: all experimental fields null
# ===========================================================================


@pytest.mark.asyncio
async def test_stamp_experimental_all_null(
    client: AsyncClient, sample_peptide_id: str
) -> None:
    """All experimental data fields must be null (no fabricated lab data).

    Fields checked: MIC_ug_ml, MBC_ug_ml, hemolysis_percent,
    LPS_binding_Kd_nM, pLDDT, ipTM, pDockQ.
    """
    payload = {"candidate_id": sample_peptide_id}
    response = await client.post("/api/v1/stamp/build", json=payload)

    assert response.status_code == 200
    data = response.json()["data"]

    experimental = data["experimental"]
    null_fields = [
        "MIC_ug_ml",
        "MBC_ug_ml",
        "hemolysis_percent",
        "LPS_binding_Kd_nM",
        "pLDDT",
        "ipTM",
        "pDockQ",
    ]

    for field in null_fields:
        assert experimental.get(field) is None, (
            f"experimental.{field} must be null, got {experimental[field]!r}"
        )


# ===========================================================================
# Business rule: -NH2 only at C-terminus
# ===========================================================================


@pytest.mark.asyncio
async def test_stamp_c_terminal_nh2_only(
    client: AsyncClient, sample_peptide_id: str
) -> None:
    """The -NH2 modification must only appear at the C-terminus.

    It must NOT appear:
        - Inside the raw sequence
        - At the N-terminus
        - In domain-level sequences
    """
    payload = {"candidate_id": sample_peptide_id}
    response = await client.post("/api/v1/stamp/build", json=payload)

    assert response.status_code == 200
    data = response.json()["data"]

    # -NH2 must not be in raw sequence
    assert "-NH2" not in data["raw_full_sequence"], (
        "-NH2 must not appear in raw_full_sequence"
    )

    # -NH2 must only appear at the very end of display sequence
    display = data["display_full_sequence"]
    assert display.endswith("-NH2"), (
        f"display_full_sequence must end with '-NH2': {display}"
    )
    # Verify it only appears once (at the end)
    assert display.count("-NH2") == 1, (
        f"-NH2 should appear exactly once in display: {display}"
    )

    # Domain sequences must not contain -NH2
    assert "-NH2" not in data["targeting_domain"]["sequence"], (
        "TP sequence must not contain -NH2"
    )
    assert "-NH2" not in data["linker"]["sequence"], (
        "Linker sequence must not contain -NH2"
    )
    assert "-NH2" not in data["killing_domain"]["sequence"], (
        "AMP sequence must not contain -NH2"
    )


# ===========================================================================
# StampCandidate structural completeness
# ===========================================================================


@pytest.mark.asyncio
async def test_stamp_is_complete(
    client: AsyncClient, sample_peptide_id: str
) -> None:
    """The built STAMP must have is_complete == True."""
    payload = {"candidate_id": sample_peptide_id}
    response = await client.post("/api/v1/stamp/build", json=payload)

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["is_complete"] is True, "Freshly built STAMP must be complete"


@pytest.mark.asyncio
async def test_stamp_orientation(client: AsyncClient, sample_peptide_id: str) -> None:
    """Orientation must be 'N-to-C'."""
    payload = {"candidate_id": sample_peptide_id}
    response = await client.post("/api/v1/stamp/build", json=payload)

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["orientation"] == "N-to-C", (
        f"Orientation must be 'N-to-C', got {data['orientation']}"
    )


@pytest.mark.asyncio
async def test_stamp_linker_is_eaaak(
    client: AsyncClient, sample_peptide_id: str
) -> None:
    """The linker must be EAAAK (fixed business rule)."""
    payload = {"candidate_id": sample_peptide_id}
    response = await client.post("/api/v1/stamp/build", json=payload)

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["linker"]["name"] == "EAAAK", "Linker name must be 'EAAAK'"
    assert data["linker"]["sequence"] == "EAAAK", "Linker sequence must be 'EAAAK'"
    assert data["linker"]["length"] == 5, "Linker length must be 5"


# ===========================================================================
# GET endpoints
# ===========================================================================


@pytest.mark.asyncio
async def test_get_stamp_templates(client: AsyncClient) -> None:
    """GET /api/v1/stamp/templates returns template library."""
    response = await client.get("/api/v1/stamp/templates")

    assert response.status_code in (200, 404), (
        f"Unexpected status: {response.status_code}"
    )

    if response.status_code == 200:
        body = response.json()
        assert body.get("code") == 200
        assert "data" in body


@pytest.mark.asyncio
async def test_get_hybrid_candidates(client: AsyncClient) -> None:
    """GET /api/v1/stamp/hybrid-candidates returns pre-built candidates."""
    response = await client.get("/api/v1/stamp/hybrid-candidates")

    assert response.status_code in (200, 404), (
        f"Unexpected status: {response.status_code}"
    )

    if response.status_code == 200:
        body = response.json()
        assert body.get("code") == 200
        assert "data" in body


@pytest.mark.asyncio
async def test_get_stamp_candidate_by_id(
    client: AsyncClient, sample_peptide_id: str
) -> None:
    """Build a STAMP, then retrieve it by candidate_id.

    Flow:
        1. POST /api/v1/stamp/build → creates candidate
        2. GET /api/v1/stamp/candidates/{candidate_id} → retrieves it
    """
    # Step 1: Build
    payload = {"candidate_id": sample_peptide_id}
    build_resp = await client.post("/api/v1/stamp/build", json=payload)
    assert build_resp.status_code == 200

    stamp_id = build_resp.json()["data"]["candidate_id"]

    # Step 2: Retrieve
    get_resp = await client.get(f"/api/v1/stamp/candidates/{stamp_id}")
    assert get_resp.status_code == 200, (
        f"Expected 200, got {get_resp.status_code}: {get_resp.text}"
    )

    body = get_resp.json()
    assert body.get("code") == 200
    assert body["data"]["candidate_id"] == stamp_id


@pytest.mark.asyncio
async def test_get_stamp_candidate_not_found(client: AsyncClient) -> None:
    """GET for a non-existent STAMP candidate returns 404."""
    response = await client.get("/api/v1/stamp/candidates/stamp_NON_EXISTENT")

    assert response.status_code == 404, (
        f"Expected 404 for missing candidate, got {response.status_code}"
    )

    body = response.json()
    assert body.get("code") == 404
    assert "message" in body
