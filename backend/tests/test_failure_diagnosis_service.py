"""Tests for Failure Diagnosis Service (v1.5).

Covers:
- Error category detection from error_message and error_json
- Cause text generation for all supported job types
- Suggestion lists
- Log and artifact path guessing
- Router integration (smoke)
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.services.failure_diagnosis_service import (
    _detect_category,
    _build_cause,
    _build_suggestions,
    _guess_log_paths,
    _guess_artifacts,
    diagnose_job,
    ERROR_CATEGORIES,
    _FIX_SUGGESTIONS,
)


# ---------------------------------------------------------------------------
# Category detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("msg,expected", [
    ("gpu lock held by job xyz", "gpu_locked"),
    ("CUDA out of memory", "gpu_locked"),
    ("command not found: gmx", "tool_missing"),
    ("colabfold_batch not found in PATH", "tool_missing"),
    ("conda env not found: stamp-md", "tool_missing"),
    ("input_pdb not found: /data/test.pdb", "input_missing"),
    ("missing input file: /data/seq.fasta", "input_missing"),
    ("Input validation failed: required field", "invalid_parameter"),
    ("422 Unprocessable Entity", "invalid_parameter"),
    ("command failed with rc=1", "command_failed"),
    ("subprocess returned non-zero", "command_failed"),
    ("no real artifacts found in output directory", "artifact_missing"),
    ("missing output files: score.sc", "artifact_missing"),
    ("permission denied: /data/out", "permission_denied"),
    ("access denied", "permission_denied"),
    ("disk full, no space left", "storage_unwritable"),
    ("read-only file system", "storage_unwritable"),
    ("sidecar timeout after 30s", "external_api_failed"),
    ("connection refused to 192.168.31.218", "external_api_failed"),
    ("ssh command failed", "external_api_failed"),
    ("some random text without patterns", "unknown"),
    (None, "unknown"),
])
def test_detect_category(msg, expected):
    assert _detect_category(msg, None) == expected


def test_detect_category_from_error_json():
    error_json = {"error_code": "GPU_LOCK_FAILED", "detail": "cuda out of memory"}
    assert _detect_category("execution failed", error_json) == "gpu_locked"


# ---------------------------------------------------------------------------
# Cause text
# ---------------------------------------------------------------------------

def test_build_cause_with_job_type_hint():
    cause = _build_cause("tool_missing", "production_md", None)
    assert "GROMACS" in cause or "stamp-md" in cause


def test_build_cause_falls_back_to_generic():
    cause = _build_cause("tool_missing", "unknown_job_type", None)
    assert "software" in cause.lower() or "tool" in cause.lower()


def test_build_cause_gpu_locked():
    cause = _build_cause("gpu_locked", "production_md", None)
    assert "GPU" in cause


def test_build_cause_external_api_flexpepdock():
    cause = _build_cause("external_api_failed", "flexpepdock", None)
    assert "SSH" in cause or "server" in cause.lower()


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------

def test_build_suggestions_tool_missing():
    sugg = _build_suggestions("tool_missing", "epitope_scan")
    assert any("smoke" in s.lower() or "path" in s.lower() for s in sugg)


def test_build_suggestions_gpu_locked():
    sugg = _build_suggestions("gpu_locked", "production_md")
    assert any("lock" in s.lower() for s in sugg)


def test_build_suggestions_flexpepdock_ssh():
    sugg = _build_suggestions("external_api_failed", "flexpepdock")
    assert any("SSH" in s for s in sugg)


# ---------------------------------------------------------------------------
# Log path guessing
# ---------------------------------------------------------------------------

def test_guess_log_paths_from_output_json():
    job = MagicMock()
    job.output_json = {"log_path": "/data/batch_001/logs/job.log"}
    job.artifacts_json = None
    job.batch_id = None
    job.id = "job-123"
    paths = _guess_log_paths(job)
    assert "/data/batch_001/logs/job.log" in paths


def test_guess_log_paths_empty():
    job = MagicMock()
    job.output_json = {}
    job.artifacts_json = None
    job.batch_id = None
    job.id = "job-123"
    paths = _guess_log_paths(job)
    assert isinstance(paths, list)


# ---------------------------------------------------------------------------
# Artifact guessing
# ---------------------------------------------------------------------------

def test_guess_artifacts_from_output_json():
    job = MagicMock()
    job.output_json = {"scorefile_path": "/data/score.sc", "silent_file_path": "/data/out.silent"}
    job.artifacts_json = None
    arts = _guess_artifacts(job)
    assert any(a["path"] == "/data/score.sc" for a in arts)
    assert any(a["path"] == "/data/out.silent" for a in arts)


def test_guess_artifacts_from_artifacts_json():
    job = MagicMock()
    job.output_json = {}
    job.artifacts_json = {"pdb": ["/data/model.pdb"]}
    arts = _guess_artifacts(job)
    assert any(a["path"] == "/data/model.pdb" for a in arts)


# ---------------------------------------------------------------------------
# Full diagnose_job
# ---------------------------------------------------------------------------

def test_diagnose_job_failed_flexpepdock():
    job = MagicMock()
    job.id = "job-abc"
    job.job_type = "flexpepdock"
    job.status = "FAILED"
    job.error_message = "SSH command failed: connection refused"
    job.error_json = {}
    job.output_json = {"workdir": "/data/flex/001"}
    job.artifacts_json = None
    job.batch_id = None

    result = diagnose_job(job)
    assert result["job_id"] == "job-abc"
    assert result["error_category"] == "external_api_failed"
    assert result["status"] == "FAILED"
    assert len(result["suggestions"]) > 0
    assert any("SSH" in s for s in result["suggestions"])


def test_diagnose_job_blocked_md_tool_missing():
    job = MagicMock()
    job.id = "job-md-1"
    job.job_type = "production_md"
    job.status = "BLOCKED"
    job.error_message = "gmx not found in PATH"
    job.error_json = {"error_code": "ENV_MISSING"}
    job.output_json = {}
    job.artifacts_json = None
    job.batch_id = "batch-md-1"
    job.id = "item-md-1"

    result = diagnose_job(job)
    assert result["error_category"] == "tool_missing"
    assert "GROMACS" in result["cause"] or "stamp-md" in result["cause"]
    assert result["status"] == "BLOCKED"


def test_diagnose_job_gpu_locked():
    job = MagicMock()
    job.id = "job-gpu-1"
    job.job_type = "production_md"
    job.status = "FAILED"
    job.error_message = "GPU lock held by job other"
    job.error_json = {}
    job.output_json = {}
    job.artifacts_json = None
    job.batch_id = None

    result = diagnose_job(job)
    assert result["error_category"] == "gpu_locked"
    assert "GPU" in result["cause"]


def test_diagnose_job_422_validation():
    job = MagicMock()
    job.id = "job-val-1"
    job.job_type = "peptide_generation"
    job.status = "FAILED"
    job.error_message = "Input validation failed: required field"
    job.error_json = {}
    job.output_json = {}
    job.artifacts_json = None
    job.batch_id = None

    result = diagnose_job(job)
    assert result["error_category"] == "invalid_parameter"


def test_diagnose_job_none_raises():
    with pytest.raises(ValueError):
        diagnose_job(None)


def test_diagnose_job_unknown_error():
    job = MagicMock()
    job.id = "job-unk"
    job.job_type = "epitope_scan"
    job.status = "FAILED"
    job.error_message = "completely unrecognizable gibberish xyz123"
    job.error_json = None
    job.output_json = {}
    job.artifacts_json = None
    job.batch_id = None

    result = diagnose_job(job)
    assert result["error_category"] == "unknown"
    assert result["raw_error_message"] == "completely unrecognizable gibberish xyz123"


# ---------------------------------------------------------------------------
# All categories covered
# ---------------------------------------------------------------------------

def test_all_categories_have_generic_hint():
    for cat in ERROR_CATEGORIES:
        if cat == "unknown":
            continue
        sugg = _FIX_SUGGESTIONS.get(cat)
        assert sugg is not None and len(sugg) > 0, f"Missing fix suggestions for {cat}"
