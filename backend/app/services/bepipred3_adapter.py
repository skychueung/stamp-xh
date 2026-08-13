"""STAMP Platform - BepiPred3 HTTP Sidecar Adapter (v0.10-P1b-fix-2).

Interfaces with the BepiPred3 sidecar via a synchronous HTTP endpoint:
  POST {sidecar_url}/api/predict

Does NOT run the BepiPred3 model inside this backend.
All predictions are explicitly marked NOT_EXPERIMENTALLY_VALIDATED.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from app.crud import get_target_protein
from app.schemas import BepiPred3JobInput

logger = logging.getLogger(__name__)

DEFAULT_SIDECAR_URL = "http://127.0.0.1:5001/api/predict"

# Dynamic timeout policy (v0.10-P2c)
MAX_TIMEOUT_SECONDS = 600.0


def calculate_bepipred3_timeout(
    sequence_length: int,
    override_timeout: float | None = None,
) -> float:
    """Calculate a safe timeout for BepiPred3 sidecar based on sequence length.

    Strategy:
      - <= 100 aa  : 60s
      - 101–500 aa : 180s
      - > 500 aa   : 300s
      - override_timeout : use caller value, clamped to MAX_TIMEOUT_SECONDS
    """
    if override_timeout is not None:
        return min(float(override_timeout), MAX_TIMEOUT_SECONDS)

    if sequence_length <= 100:
        return 60.0
    elif sequence_length <= 500:
        return 180.0
    else:
        return 300.0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class BepiPred3SidecarError(Exception):
    """Raised when the BepiPred3 sidecar cannot be reached or returns an error."""

    pass


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def _extract_base_url(url: str) -> str:
    """Strip predict-path suffix so we can append /api/health or /health."""
    url = url.rstrip("/")
    for suffix in ("/api/predict", "/predict"):
        if url.endswith(suffix):
            return url[: -len(suffix)]
    return url


def check_bepipred3_sidecar_health(
    base_url: str | None = None,
    timeout: float = 5.0,
) -> bool:
    """Ping the sidecar health endpoint.

    Tries /api/health first, then falls back to /health.

    Returns True if the sidecar responds with 2xx.
    """
    url = _extract_base_url(base_url or DEFAULT_SIDECAR_URL)
    for health_path in ("/api/health", "/health"):
        health_url = f"{url}{health_path}"
        try:
            response = httpx.get(health_url, timeout=timeout)
            if response.status_code < 300:
                return True
        except Exception:
            continue
    return False


# ---------------------------------------------------------------------------
# Sequence resolver
# ---------------------------------------------------------------------------


def resolve_sequence(
    db: Session,
    input_data: BepiPred3JobInput,
) -> str:
    """Resolve the protein sequence for a BepiPred3 job.

    Priority:
      1. If ``sequence`` is provided directly, use it.
      2. If ``target_protein_id`` is provided, look up from DB.
      3. If neither is available, raise ValueError.

    Returns:
        The resolved amino-acid sequence.

    Raises:
        ValueError: if no sequence can be resolved.
    """
    if input_data.sequence and len(input_data.sequence) >= 10:
        return input_data.sequence

    if input_data.target_protein_id:
        tp = get_target_protein(db, input_data.target_protein_id)
        if tp is None:
            raise ValueError(
                f"Target protein '{input_data.target_protein_id}' not found in database"
            )
        if not tp.sequence or len(tp.sequence) < 10:
            raise ValueError(
                f"Target protein '{input_data.target_protein_id}' has invalid sequence"
            )
        return tp.sequence

    raise ValueError(
        "BepiPred3 job requires either 'sequence' or 'target_protein_id' in input_json"
    )


# ---------------------------------------------------------------------------
# Sidecar synchronous call
# ---------------------------------------------------------------------------


def call_bepipred3_sidecar(
    sequence: str,
    base_url: str | None = None,
    timeout: float | None = None,
    parameters: Optional[dict] = None,
) -> dict[str, Any]:
    """Call the BepiPred3 sidecar predict endpoint synchronously.

    Args:
        sequence: Protein amino-acid sequence.
        base_url: Sidecar predict URL (e.g. http://127.0.0.1:5001/api/predict).
        timeout: Max time to wait for response (seconds). If None, computed
                 from sequence length via calculate_bepipred3_timeout().
        parameters: Optional extra parameters forwarded to the sidecar.
                    May include 'timeout' to override the computed value.

    Returns:
        Raw sidecar response dict.

    Raises:
        BepiPred3SidecarError: on connection failure, timeout, or HTTP error.
    """
    url = (base_url or DEFAULT_SIDECAR_URL).rstrip("/")
    params = parameters or {}

    # Dynamic timeout (v0.10-P2c)
    seq_len = len(sequence)
    override = params.get("timeout")
    effective_timeout = calculate_bepipred3_timeout(
        seq_len,
        override_timeout=override if override is not None else timeout,
    )

    payload = {
        "name": params.get("name", "input_sequence"),
        "sequence": sequence,
        "params": params,
    }

    try:
        response = httpx.post(url, json=payload, timeout=effective_timeout)
    except httpx.TimeoutException as exc:
        raise BepiPred3SidecarError(
            f"Sidecar timeout after {effective_timeout}s for sequence length {seq_len}. "
            f"CPU inference may be too slow for this sequence. Consider GPU or shorter input."
        ) from exc
    except httpx.ConnectError as exc:
        raise BepiPred3SidecarError(f"Sidecar connection refused: {exc}") from exc
    except Exception as exc:
        raise BepiPred3SidecarError(
            f"Sidecar request failed: {type(exc).__name__}: {exc}"
        ) from exc

    if response.status_code >= 400:
        raise BepiPred3SidecarError(
            f"Sidecar returned HTTP {response.status_code}: {response.text[:500]}"
        )

    try:
        data = response.json()
    except Exception as exc:
        raise BepiPred3SidecarError(
            f"Sidecar returned invalid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise BepiPred3SidecarError(
            f"Invalid sidecar response: expected dict, got {type(data).__name__}"
        )

    return data


# ---------------------------------------------------------------------------
# Result normalizer
# ---------------------------------------------------------------------------


def _map_peptide_fields(raw_item: dict[str, Any]) -> dict[str, Any]:
    """Map various sidecar peptide field names to standard preview fields."""
    # Resolve sequence
    seq = raw_item.get("sequence") or raw_item.get("peptide") or raw_item.get("fragment")

    # Resolve start position
    start = raw_item.get("start") or raw_item.get("Start_Position")

    # Resolve end position
    end = raw_item.get("end") or raw_item.get("End_Position")

    # Resolve score
    score = raw_item.get("score") or raw_item.get("Score") or raw_item.get("ranking_score")

    # Convert numeric strings to numbers where possible
    if isinstance(start, str):
        try:
            start = int(start)
        except (ValueError, TypeError):
            pass
    if isinstance(end, str):
        try:
            end = int(end)
        except (ValueError, TypeError):
            pass
    if isinstance(score, str):
        try:
            score = float(score)
        except (ValueError, TypeError):
            pass

    return {
        "sequence": seq,
        "start": start,
        "end": end,
        "score": score,
    }


def normalize_bepipred3_response(
    raw: dict[str, Any],
    target_protein_id: Optional[str] = None,
    sidecar_url: str = DEFAULT_SIDECAR_URL,
) -> dict[str, Any]:
    """Normalize a raw sidecar response into the standard Job output_json shape.

    Ensures all required metadata fields are present for scientific-integrity
    tracking.
    """
    if not isinstance(raw, dict):
        raise BepiPred3SidecarError(
            f"Invalid sidecar response: expected dict, got {type(raw).__name__}"
        )

    ranked_peptides = raw.get("ranked_peptides", [])
    if not isinstance(ranked_peptides, list):
        ranked_peptides = []

    retained_count = raw.get("retained_count")
    dropped_count = raw.get("dropped_count")

    candidate_count = len(ranked_peptides)

    # Build preview (first 5)
    preview = []
    for item in ranked_peptides[:5]:
        if isinstance(item, dict):
            preview.append(_map_peptide_fields(item))

    raw_summary: dict[str, Any] = {
        "sidecar_status": "success",
        "candidate_count": candidate_count,
        "retained_count": retained_count,
        "dropped_count": dropped_count,
    }

    if "ranked_peptides" not in raw:
        raw_summary["missing_ranked_peptides"] = True

    return {
        "job_type": "bepipred3_scan",
        "mode": "BEPIPRED3_HTTP_SIDECAR",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "prediction_status": "COMPUTATIONAL_PREDICTION_ONLY",
        "candidate_count": candidate_count,
        "raw_result_summary": raw_summary,
        "ranked_peptides_preview": preview,
        "sidecar_url": sidecar_url,
    }
