"""STAMP Platform — PepMLM Sidecar Adapter (v0.10-P3a).

HTTP client for the PepMLM generation sidecar.
All outputs are explicitly marked as stub-only until a real model is loaded.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_SIDEcar_URL = "http://127.0.0.1:5011"
DEFAULT_TIMEOUT = 30.0


class PepMLMSidecarError(Exception):
    """Raised when the PepMLM sidecar returns an error or is unreachable."""


# ---------------------------------------------------------------------------
# Health / Info
# ---------------------------------------------------------------------------


def check_pepmlm_sidecar_health(base_url: str = DEFAULT_SIDEcar_URL, timeout: float = 5.0) -> dict:
    """Check sidecar health. Returns parsed JSON or raises."""
    url = f"{base_url}/api/health"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError as exc:
        raise PepMLMSidecarError(f"[SIDECAR_UNAVAILABLE] Cannot connect to PepMLM sidecar at {url}") from exc
    except requests.exceptions.Timeout as exc:
        raise PepMLMSidecarError(f"[SIDECAR_TIMEOUT] PepMLM sidecar health check timed out after {timeout}s") from exc
    except Exception as exc:
        raise PepMLMSidecarError(f"[SIDECAR_ERROR] PepMLM sidecar health check failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------


def call_pepmlm_sidecar(
    epitope_sequence: str,
    base_url: str = DEFAULT_SIDEcar_URL,
    top_k: int = 10,
    linker_seq: str = "GGGGS",
    parameters: Optional[dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> dict:
    """Call PepMLM sidecar /api/generate.

    Args:
        epitope_sequence: Source epitope amino-acid sequence.
        base_url: Sidecar base URL.
        top_k: Number of candidates to request.
        linker_seq: Linker sequence.
        parameters: Optional extra model parameters.
        timeout: Request timeout in seconds.

    Returns:
        Raw sidecar JSON response.

    Raises:
        PepMLMSidecarError: on connection, timeout, or HTTP error.
    """
    url = f"{base_url}/api/generate"
    payload = {
        "epitope_sequence": epitope_sequence,
        "top_k": top_k,
        "linker_seq": linker_seq,
        "params": parameters or {},
    }

    effective_timeout = timeout if timeout is not None else DEFAULT_TIMEOUT

    try:
        resp = requests.post(url, json=payload, timeout=effective_timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError as exc:
        raise PepMLMSidecarError(
            f"[SIDECAR_UNAVAILABLE] Cannot connect to PepMLM sidecar at {url}"
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise PepMLMSidecarError(
            f"[SIDECAR_TIMEOUT] PepMLM sidecar timeout after {effective_timeout}s"
        ) from exc
    except requests.exceptions.HTTPError as exc:
        raise PepMLMSidecarError(
            f"[SIDECAR_HTTP_ERROR] PepMLM sidecar returned HTTP {exc.response.status_code}"
        ) from exc
    except Exception as exc:
        raise PepMLMSidecarError(f"[SIDECAR_ERROR] PepMLM request failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Response normalization
# ---------------------------------------------------------------------------


def normalize_pepmlm_response(
    raw_result: dict,
    *,
    sidecar_url: str = DEFAULT_SIDEcar_URL,
) -> dict:
    """Normalize PepMLM sidecar response into job output_json shape.

    Distinguishes between REAL_MODEL and STUB_ONLY responses.
    Preserves all validation boundaries regardless of mode.
    """
    generated = raw_result.get("generated_peptides", [])
    candidate_count = raw_result.get("candidate_count", len(generated))
    sidecar_mode = raw_result.get("mode", "PEPMLM_STUB_ONLY")
    real_model_loaded = raw_result.get("real_model_loaded", False)

    if sidecar_mode == "PEPMLM_REAL_MODEL" and real_model_loaded:
        stamp_mode = "PEPMLM_HTTP_SIDECAR_REAL"
        generation_status = "COMPUTATIONAL_GENERATION_ONLY"
    else:
        stamp_mode = "PEPMLM_HTTP_SIDECAR_STUB"
        generation_status = "COMPUTATIONAL_GENERATION_STUB_ONLY"

    return {
        "job_type": "pepmlm_generation",
        "mode": stamp_mode,
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "generation_status": generation_status,
        "real_model_loaded": real_model_loaded,
        "candidate_count": candidate_count,
        "generated_peptides_preview": [
            {
                "sequence": p.get("sequence"),
                "score": p.get("score"),
                "rank": p.get("rank"),
                "source": p.get("source", "pepmlm_stub"),
                "is_stub": p.get("is_stub", True),
                "ppl": p.get("ppl"),
                "charge": p.get("charge"),
                "pi": p.get("pi"),
                "gravy": p.get("gravy"),
                "hydrophobicity": p.get("hydrophobicity"),
                "warnings": p.get("warnings"),
            }
            for p in generated
        ],
        "raw_result_summary": {
            "sidecar_status": raw_result.get("status", "unknown"),
            "candidate_count": candidate_count,
            "mode": sidecar_mode,
            "real_model_loaded": real_model_loaded,
            "model_name": raw_result.get("model_info", {}).get("model_name") if raw_result.get("model_info") else None,
            "fallback_reason": raw_result.get("fallback_reason"),
        },
        "sidecar_url": sidecar_url,
    }
