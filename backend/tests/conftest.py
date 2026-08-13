"""
Pytest fixtures for the STAMP platform test suite.

Provides shared setup for:
    - In-memory JSON data fixtures (pepmlm candidates, AMP library)
    - FastAPI test client (AsyncClient via ASGITransport)
    - Common sample IDs used across multiple test modules

All fixtures are scoped at ``session`` level where possible to avoid
re-loading data for every test function.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Ensure backend/app is on sys.path so ``import app.*`` resolves
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATA_DIR = BACKEND_DIR / "data"

# Sample identifiers reused across tests
SAMPLE_PEPTIDE_ID: str = "OPRF_0001"
SAMPLE_AMP_NAME: str = "P4"

# Fixed linker sequence (business rule)
LINKER_SEQUENCE: str = "EAAAK"

# P4 clean sequence without trailing "5"
P4_CLEAN_SEQUENCE: str = "FSRFLRRVRRYRPKISFNLEPFFKF"


# ---------------------------------------------------------------------------
# Minimal in-memory JSON data (avoids filesystem dependency for unit tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sample_pepmlm_candidates() -> list[dict[str, Any]]:
    """Return a minimal list of PepMLM candidates for testing."""
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
            "validation_warning": None,
        },
        {
            "candidate_id": "OPRF_0002",
            "target_name": "Pseudomonas_OprF",
            "peptide_length": 14,
            "generated_peptide": "GVIKDWKSFIKDKL",
            "ppl_score": 10.5,
            "net_charge": 3.0,
            "pI": 8.2,
            "GRAVY": -0.15,
            "cysteine_count": 0,
            "filter_status": "Warning",
            "validation_warning": "Check hydrophobicity",
        },
        {
            "candidate_id": "OPRF_0003",
            "target_name": "Pseudomonas_OprF",
            "peptide_length": 13,
            "generated_peptide": "MKFLRKASXVILL",  # Contains illegal char 'X'
            "ppl_score": 15.0,
            "net_charge": 1.0,
            "pI": 6.5,
            "GRAVY": 0.3,
            "cysteine_count": 0,
            "filter_status": "Fail",
            "validation_warning": "Contains illegal residue",
        },
    ]


@pytest.fixture(scope="session")
def sample_amp_library() -> list[dict[str, Any]]:
    """Return a minimal AMP library for testing."""
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
            "illegal_char_found": None,
            "illegal_char_position": None,
        },
        {
            "amp_name": "P7",
            "raw_sequence": "KWKLFKKIGAVLKVLTTGLPALIS",
            "clean_sequence": "KWKLFKKIGAVLKVLTTGLPALIS",
            "source": "natural_variant",
            "priority": "medium",
            "role": "killing_domain",
            "illegal_char_found": None,
            "illegal_char_position": None,
        },
    ]


@pytest.fixture(scope="session")
def sample_stamp_hybrid_candidates() -> list[dict[str, Any]]:
    """Return minimal pre-built STAMP hybrid candidates."""
    return [
        {
            "candidate_id": "stamp_oprf_0001",
            "target_molecule": "Pseudomonas aeruginosa OprF",
            "targeting_domain": {
                "name": "OPRF_0001",
                "sequence": "DKTKKAFLIAAG",
                "length": 12,
                "net_charge": 2.0,
                "gravy": 0.017,
            },
            "linker": {
                "name": "EAAAK",
                "sequence": "EAAAK",
                "length": 5,
                "type": "rigid",
            },
            "killing_domain": {
                "name": "P4",
                "sequence": "FSRFLRRVRRYRPKISFNLEPFFKF",
                "length": 25,
                "net_charge": 7.0,
                "gravy": -0.592,
            },
            "orientation": "N-to-C",
            "terminal_modification": "-NH2",
            "raw_full_sequence": "DKTKKAFLIAAGEAAAKFSRFLRRVRRYRPKISFNLEPFFKF",
            "display_full_sequence": "DKTKKAFLIAAG-EAAAK-FSRFLRRVRRYRPKISFNLEPFFKF-NH2",
            "is_complete": True,
            "biophysical": {
                "length": 42,
                "net_charge": 9.0,
                "pI": None,
                "GRAVY": None,
                "hydrophobicity_fraction": None,
            },
            "mock_scores": None,
            "experimental": {
                "MIC_ug_ml": None,
                "MBC_ug_ml": None,
                "hemolysis_percent": None,
                "LPS_binding_Kd_nM": None,
                "pLDDT": None,
                "ipTM": None,
                "pDockQ": None,
                "note": "Reserved for real experimental data",
            },
            "structure_status": {
                "monomer_predicted": False,
                "complex_predicted": False,
                "experimental_structure": False,
            },
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        }
    ]


# ---------------------------------------------------------------------------
# Data directory fixture (creates temp JSON files for integration tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def data_dir() -> Path:
    """Return the path to the backend data directory."""
    return DATA_DIR


# ---------------------------------------------------------------------------
# FastAPI application fixture (lazy import to avoid early import errors)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def app() -> Any:
    """Create and configure the FastAPI application for testing.

    Returns:
        Configured FastAPI app instance with all routers mounted.
    """
    from fastapi import FastAPI
    from app.core.exceptions import (
        generic_exception_handler,
        stamp_exception_handler,
    )
    from app.models.schemas import ApiResponse

    # Import routers (these will be implemented during task execution)
    # For now, we create a minimal app that can be extended
    application = FastAPI(
        title="STAMP Platform API (Test)",
        version="0.6.0",
    )

    # Register exception handlers
    from app.core.exceptions import StampException

    application.add_exception_handler(StampException, stamp_exception_handler)
    application.add_exception_handler(Exception, generic_exception_handler)

    # Attempt to import and include routers individually so missing ones
    # don't prevent working ones from being registered.
    _routers = [
        ("app.routers.health", "health"),
        ("app.routers.pepmlm", "pepmlm"),
        ("app.routers.amp", "amp"),
        ("app.routers.stamp", "stamp"),
        ("app.routers.epitope", "epitope"),
        ("app.routers.targeting_peptide", "targeting_peptide"),
        ("app.routers.stamp_assembly", "stamp_assembly"),
        ("app.routers.final_ranking", "final_ranking"),
    ]
    for module_name, attr_name in _routers:
        try:
            mod = __import__(module_name, fromlist=[attr_name])
            application.include_router(getattr(mod, "router"))
        except (ImportError, AttributeError):
            pass

    return application


# ---------------------------------------------------------------------------
# Test client fixture (httpx.AsyncClient)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def client(app: Any) -> Any:
    """Yield an async HTTP test client for the STAMP API.

    Usage::

        async def test_health(client):
            resp = await client.get("/health")
            assert resp.status_code == 200
    """
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Simple fixture aliases for readability
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sample_peptide_id() -> str:
    """Return a valid PepMLM candidate ID for use in STAMP build tests."""
    return SAMPLE_PEPTIDE_ID


@pytest.fixture(scope="session")
def sample_amp_name() -> str:
    """Return the canonical AMP name (P4) used throughout tests."""
    return SAMPLE_AMP_NAME
