"""
STAMP Platform — JSON Data Loader

Loads static JSON data files shipped with the application.  All loads are
eager on module import (small datasets, < 1 MB total) and cached in module
globals for the lifetime of the process.

If a file is missing the loader raises ``DataLoadError`` so that the
problem surfaces immediately on startup rather than at request time.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from app.core.config import settings
from app.core.exceptions import DataLoadError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Any:
    """Load and parse a JSON file.

    Args:
        path: Absolute filesystem path.

    Returns:
        Parsed JSON (usually ``list[dict]``).

    Raises:
        DataLoadError: If the file is missing, unreadable, or malformed.
    """
    if not path.exists():
        raise DataLoadError(str(path), "File does not exist")
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise DataLoadError(str(path), f"Invalid JSON: {exc}")
    except OSError as exc:
        raise DataLoadError(str(path), str(exc))


def _extract_array(data: Any, path: Path, *keys: str) -> list[dict[str, Any]]:
    """Extract a list of records from parsed JSON data.

    Handles both:
        - Direct list: ``[{"id": 1}, {"id": 2}]``
        - Wrapped dict: ``{"candidates": [{"id": 1}, ...]}``

    Args:
        data: Parsed JSON (list or dict).
        path: Path used for error messages.
        *keys: Candidate keys to look for in dict wrappers
               (e.g. "candidates", "amps").

    Returns:
        List of dict records.

    Raises:
        DataLoadError: If no usable array can be extracted.
    """
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in keys:
            if key in data and isinstance(data[key], list):
                return data[key]
        # Fallback: try common wrapper keys
        for fallback in ("candidates", "amps", "items", "data", "records"):
            if fallback in data and isinstance(data[fallback], list):
                return data[fallback]

    raise DataLoadError(
        str(path),
        f"Expected a list or a dict wrapping a list under {keys!r}, got {type(data).__name__}",
    )


# ---------------------------------------------------------------------------
# Cached accessors — called once, then memoised
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_pepmlm_candidates() -> list[dict[str, Any]]:
    """Load PepMLM generated targeting peptide candidates."""
    logger.info("Loading PepMLM candidates from %s", settings.pepmlm_candidates_path)
    raw = _load_json(settings.pepmlm_candidates_path)
    return _extract_array(raw, settings.pepmlm_candidates_path, "candidates")


@lru_cache(maxsize=1)
def get_priority_amp_library() -> list[dict[str, Any]]:
    """Load the priority AMP library (P4, P15, …)."""
    logger.info("Loading priority AMP library from %s", settings.priority_amp_library_path)
    raw = _load_json(settings.priority_amp_library_path)
    return _extract_array(raw, settings.priority_amp_library_path, "amps")


@lru_cache(maxsize=1)
def get_stamp_hybrid_candidates() -> list[dict[str, Any]]:
    """Load existing STAMP hybrid candidates (reference format)."""
    logger.info("Loading hybrid candidates from %s", settings.stamp_hybrid_candidates_path)
    raw = _load_json(settings.stamp_hybrid_candidates_path)
    return _extract_array(raw, settings.stamp_hybrid_candidates_path, "candidates")


@lru_cache(maxsize=1)
def get_amp_structure_manifest() -> list[dict[str, Any]]:
    """Load AMP structure manifest."""
    logger.info("Loading AMP structure manifest from %s", settings.amp_structure_manifest_path)
    raw = _load_json(settings.amp_structure_manifest_path)
    return _extract_array(raw, settings.amp_structure_manifest_path, "structures", "entries")


@lru_cache(maxsize=1)
def get_real_amp_candidates() -> list[dict[str, Any]]:
    """Load real AMP candidates (P4, P15)."""
    logger.info("Loading real AMP candidates from %s", settings.real_amp_candidates_path)
    raw = _load_json(settings.real_amp_candidates_path)
    return _extract_array(raw, settings.real_amp_candidates_path, "amps", "candidates")


@lru_cache(maxsize=1)
def get_stamp_template_library() -> list[dict[str, Any]]:
    """Load STAMP template library."""
    logger.info("Loading STAMP template library from %s", settings.stamp_template_library_path)
    raw = _load_json(settings.stamp_template_library_path)
    return _extract_array(raw, settings.stamp_template_library_path, "templates", "candidates")


@lru_cache(maxsize=1)
def get_pepmlm_oprf_top10() -> list[dict[str, Any]]:
    """Load simplified OprF Top-10 candidates."""
    logger.info("Loading OprF Top-10 from %s", settings.pepmlm_oprf_top10_path)
    raw = _load_json(settings.pepmlm_oprf_top10_path)
    return _extract_array(raw, settings.pepmlm_oprf_top10_path, "candidates", "top10")


# ---------------------------------------------------------------------------
# Eager-load flag (set to True in main.py lifespan to fail fast on startup)
# ---------------------------------------------------------------------------

def eager_load_all() -> None:
    """Touch every cached loader so that missing files raise immediately.

    Call this inside the application's ``lifespan`` context manager.
    """
    get_pepmlm_candidates()
    get_priority_amp_library()
    get_stamp_hybrid_candidates()
    get_amp_structure_manifest()
    get_real_amp_candidates()
    get_stamp_template_library()
    get_pepmlm_oprf_top10()
    logger.info("All data files loaded successfully.")
