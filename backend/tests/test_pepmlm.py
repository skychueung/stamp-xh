"""
Tests for the PepMLM Candidate endpoints.

Covers:
    - GET /api/v1/pepmlm/candidates — list with pagination
    - GET /api/v1/pepmlm/candidates?filter_status=Pass — status filtering
    - GET /api/v1/pepmlm/candidates/{candidate_id} — single lookup
    - 404 when candidate does not exist
    - Pagination boundary conditions (page > total, page_size limits)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_candidates(client: AsyncClient) -> None:
    """GET /api/v1/pepmlm/candidates returns a paginated list.

    Validates:
        - HTTP 200 status
        - Response uses ApiResponse envelope with code 200
        - data.items is a non-empty list of candidates
        - data.total reflects total candidate count
        - data.page and data.page_size are present and valid
        - Each candidate has required fields (candidate_id, target_name,
          peptide_length, generated_peptide, ppl_score, filter_status)
    """
    response = await client.get("/api/v1/pepmlm/candidates")

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    body = response.json()
    assert body.get("code") == 200, f"ApiResponse code must be 200, got {body}"
    assert "data" in body, "Response must contain 'data' key"

    data = body["data"]
    assert "items" in data, "Paginated data must contain 'items'"
    assert "total" in data, "Paginated data must contain 'total'"
    assert "page" in data, "Paginated data must contain 'page'"
    assert "page_size" in data, "Paginated data must contain 'page_size'"

    assert data["page"] == 1, "Default page must be 1"
    assert data["page_size"] == 20, "Default page_size must be 20"
    assert data["total"] >= 3, "Test data should have at least 3 candidates"
    assert len(data["items"]) > 0, "Items list must not be empty"

    # Validate candidate fields
    first = data["items"][0]
    assert "candidate_id" in first, "Candidate must have candidate_id"
    assert "target_name" in first, "Candidate must have target_name"
    assert "peptide_length" in first, "Candidate must have peptide_length"
    assert "generated_peptide" in first, "Candidate must have generated_peptide"
    assert "ppl_score" in first, "Candidate must have ppl_score"
    assert "filter_status" in first, "Candidate must have filter_status"


@pytest.mark.asyncio
async def test_list_candidates_filter_status_pass(client: AsyncClient) -> None:
    """Filter by 'Pass' status returns only passing candidates.

    Every item in the response must have filter_status == 'Pass'.
    """
    response = await client.get("/api/v1/pepmlm/candidates?filter_status=Pass")

    assert response.status_code == 200
    body = response.json()
    data = body["data"]

    for item in data["items"]:
        assert item["filter_status"] == "Pass", (
            f"Expected filter_status='Pass', got {item['filter_status']}"
        )


@pytest.mark.asyncio
async def test_list_candidates_filter_status_warning(client: AsyncClient) -> None:
    """Filter by 'Warning' status returns only warning candidates."""
    response = await client.get("/api/v1/pepmlm/candidates?filter_status=Warning")

    assert response.status_code == 200
    body = response.json()
    data = body["data"]

    for item in data["items"]:
        assert item["filter_status"] == "Warning", (
            f"Expected filter_status='Warning', got {item['filter_status']}"
        )


@pytest.mark.asyncio
async def test_list_candidates_filter_status_fail(client: AsyncClient) -> None:
    """Filter by 'Fail' status returns only failed candidates."""
    response = await client.get("/api/v1/pepmlm/candidates?filter_status=Fail")

    assert response.status_code == 200
    body = response.json()
    data = body["data"]

    for item in data["items"]:
        assert item["filter_status"] == "Fail", (
            f"Expected filter_status='Fail', got {item['filter_status']}"
        )


@pytest.mark.asyncio
async def test_list_candidates_pagination(client: AsyncClient) -> None:
    """Pagination parameters (page, page_size) are respected.

    Requesting page=2 with page_size=1 should skip the first candidate.
    """
    # Get first page
    r1 = await client.get("/api/v1/pepmlm/candidates?page=1&page_size=1")
    assert r1.status_code == 200
    data1 = r1.json()["data"]
    assert len(data1["items"]) == 1
    first_id = data1["items"][0]["candidate_id"]

    # Get second page
    r2 = await client.get("/api/v1/pepmlm/candidates?page=2&page_size=1")
    assert r2.status_code == 200
    data2 = r2.json()["data"]
    assert len(data2["items"]) == 1
    second_id = data2["items"][0]["candidate_id"]

    assert first_id != second_id, (
        "Page 2 should return a different candidate than page 1"
    )


@pytest.mark.asyncio
async def test_list_candidates_out_of_range_page(client: AsyncClient) -> None:
    """Requesting a page beyond total items returns empty items list."""
    response = await client.get("/api/v1/pepmlm/candidates?page=9999&page_size=10")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["items"] == [], "Out-of-range page should return empty items"


@pytest.mark.asyncio
async def test_get_candidate(client: AsyncClient, sample_peptide_id: str) -> None:
    """GET /api/v1/pepmlm/candidates/{candidate_id} returns a single candidate.

    Args:
        client: Async HTTP test client.
        sample_peptide_id: 'OPRF_0001' from conftest fixture.
    """
    response = await client.get(f"/api/v1/pepmlm/candidates/{sample_peptide_id}")

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    body = response.json()
    assert body.get("code") == 200

    data = body["data"]
    assert data["candidate_id"] == sample_peptide_id
    assert "target_name" in data
    assert "generated_peptide" in data
    assert "peptide_length" in data
    assert "ppl_score" in data
    assert "filter_status" in data


@pytest.mark.asyncio
async def test_get_candidate_not_found(client: AsyncClient) -> None:
    """GET for a non-existent candidate returns 404 with ApiResponse envelope."""
    response = await client.get("/api/v1/pepmlm/candidates/NON_EXISTENT_9999")

    assert response.status_code == 404, (
        f"Expected 404 for missing candidate, got {response.status_code}"
    )

    body = response.json()
    assert body.get("code") == 404, "ApiResponse code must be 404"
    assert "message" in body, "Error response must include 'message'"
