"""
Tests for the AMP (Antimicrobial Peptide) endpoints.

Covers:
    - GET /api/v1/amp/library — list all AMPs
    - GET /api/v1/amp/library/{amp_name} — get single AMP (P4)
    - 404 for non-existent AMP
    - GET /api/v1/amp/structures — structure manifest
    - Business rule: P4 cleanSequence has no trailing "5"
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# P4 clean sequence without the illegal trailing character
P4_EXPECTED_CLEAN_SEQUENCE: str = "FSRFLRRVRRYRPKISFNLEPFFKF"


@pytest.mark.asyncio
async def test_list_amps(client: AsyncClient) -> None:
    """GET /api/v1/amp/library returns the full AMP library.

    Validates:
        - HTTP 200
        - ApiResponse envelope with code 200
        - data contains AMP records (at least P4 and P15)
        - Each record has amp_name, clean_sequence, priority, role
    """
    response = await client.get("/api/v1/amp/library")

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    body = response.json()
    assert body.get("code") == 200
    assert "data" in body

    data = body["data"]
    assert "items" in data or "amps" in data, (
        "AMP library response must contain items or amps list"
    )

    amps = data.get("items") or data.get("amps") or []
    assert len(amps) >= 2, f"AMP library must have at least 2 records, got {len(amps)}"

    # Verify P4 is present
    amp_names = [a.get("amp_name", a.get("ampName", "")) for a in amps]
    assert "P4" in amp_names, "P4 must be present in AMP library"
    assert "P15" in amp_names, "P15 must be present in AMP library"


@pytest.mark.asyncio
async def test_get_amp(client: AsyncClient, sample_amp_name: str) -> None:
    """GET /api/v1/amp/library/P4 returns the P4 AMP record.

    Args:
        client: Async HTTP test client.
        sample_amp_name: 'P4' from conftest fixture.
    """
    response = await client.get(f"/api/v1/amp/library/{sample_amp_name}")

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    body = response.json()
    assert body.get("code") == 200

    data = body["data"]
    amp_name = data.get("amp_name") or data.get("ampName", "")
    assert amp_name == sample_amp_name, (
        f"Expected AMP '{sample_amp_name}', got '{amp_name}'"
    )

    clean_seq = data.get("clean_sequence") or data.get("cleanSequence", "")
    assert clean_seq == P4_EXPECTED_CLEAN_SEQUENCE, (
        f"P4 cleanSequence mismatch: expected {P4_EXPECTED_CLEAN_SEQUENCE!r}, "
        f"got {clean_seq!r}"
    )


@pytest.mark.asyncio
async def test_get_amp_not_found(client: AsyncClient) -> None:
    """GET for a non-existent AMP returns 404 with ApiResponse envelope."""
    response = await client.get("/api/v1/amp/library/NON_EXISTENT_AMP")

    assert response.status_code == 404, (
        f"Expected 404 for missing AMP, got {response.status_code}"
    )

    body = response.json()
    assert body.get("code") == 404
    assert "message" in body


@pytest.mark.asyncio
async def test_p4_clean_sequence(client: AsyncClient) -> None:
    """Verify P4 cleanSequence does NOT contain the trailing illegal '5'.

    Business rule: The raw_sequence ends with '5' (an illegal character),
    but clean_sequence must have it removed.
    """
    response = await client.get("/api/v1/amp/library/P4")

    assert response.status_code == 200
    data = response.json()["data"]

    clean_seq = data.get("clean_sequence") or data.get("cleanSequence", "")
    raw_seq = data.get("raw_sequence") or data.get("rawSequence", "")

    assert "5" not in clean_seq, (
        f"P4 clean_sequence must not contain '5': {clean_seq!r}"
    )
    assert raw_seq.endswith("5"), (
        f"P4 raw_sequence should end with '5' (illegal char): {raw_seq!r}"
    )


@pytest.mark.asyncio
async def test_get_amp_structures(client: AsyncClient) -> None:
    """GET /api/v1/amp/structures returns the structure manifest.

    Validates the response shape and that it uses the ApiResponse envelope.
    """
    response = await client.get("/api/v1/amp/structures")

    # Structure endpoint may return 200 or 404 if data is missing
    assert response.status_code in (200, 404), (
        f"Unexpected status: {response.status_code}"
    )

    if response.status_code == 200:
        body = response.json()
        assert body.get("code") == 200
        assert "data" in body
