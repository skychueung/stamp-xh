"""Tests for structure_prediction_import (v0.10-P6c).

Validates that real LocalColabFold metrics can be loaded, normalized,
and imported into the Job system without fabricating any wet-lab metrics.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.structure_prediction_import import (
    FORBIDDEN_METRIC_KEYS,
    REQUIRED_PREDICTION_STATUS,
    REQUIRED_VALIDATION_STATUS,
    load_localcolabfold_metrics,
    normalize_localcolabfold_metrics,
    validate_no_fabricated_structure_metrics,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "localcolabfold_smoke"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def parsed_metrics_path() -> Path:
    return FIXTURE_DIR / "parsed_metrics.json"


@pytest.fixture
def raw_metrics(parsed_metrics_path: Path) -> dict:
    with open(parsed_metrics_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# load_localcolabfold_metrics
# ---------------------------------------------------------------------------


def test_load_parsed_metrics_reads_file(parsed_metrics_path: Path):
    """parsed_metrics.json must be readable from fixture dir."""
    result = load_localcolabfold_metrics(FIXTURE_DIR)
    assert result["status"] == "success"


def test_load_mean_plddt_is_real_numeric(parsed_metrics_path: Path):
    """mean_plddt=65.23 must be preserved as a real numeric value."""
    result = load_localcolabfold_metrics(FIXTURE_DIR)
    assert result["mean_plddt"] == 65.23
    assert isinstance(result["mean_plddt"], (int, float))


def test_load_ptm_is_real_numeric(parsed_metrics_path: Path):
    """ptm=0.28 must be preserved as a real numeric value."""
    result = load_localcolabfold_metrics(FIXTURE_DIR)
    assert result["ptm"] == 0.28
    assert isinstance(result["ptm"], (int, float))


def test_load_iptm_is_null(parsed_metrics_path: Path):
    """iptm must be null for monomer run (not fabricated)."""
    result = load_localcolabfold_metrics(FIXTURE_DIR)
    assert result["iptm"] is None


def test_load_structure_file_points_to_pdb(parsed_metrics_path: Path):
    """best_model_pdb must point to a .pdb file."""
    result = load_localcolabfold_metrics(FIXTURE_DIR)
    pdb = result.get("best_model_pdb") or result.get("structure_file")
    assert pdb is not None
    assert pdb.endswith(".pdb")


def test_load_pae_file_exists(parsed_metrics_path: Path):
    """pae_file must point to a real file path."""
    result = load_localcolabfold_metrics(FIXTURE_DIR)
    assert result["pae_file"] is not None
    assert "pae" in result["pae_file"].lower()


def test_load_validation_status(parsed_metrics_path: Path):
    """validation_status must be NOT_EXPERIMENTALLY_VALIDATED."""
    result = load_localcolabfold_metrics(FIXTURE_DIR)
    assert result["validation_status"] == REQUIRED_VALIDATION_STATUS


def test_load_prediction_status(parsed_metrics_path: Path):
    """prediction_status must be COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY."""
    result = load_localcolabfold_metrics(FIXTURE_DIR)
    assert result["prediction_status"] == REQUIRED_PREDICTION_STATUS


def test_load_metrics_are_real(parsed_metrics_path: Path):
    """metrics_are_real must be true."""
    result = load_localcolabfold_metrics(FIXTURE_DIR)
    assert result["metrics_are_real"] is True


def test_load_missing_file_raises():
    """Missing parsed_metrics.json must raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_localcolabfold_metrics(FIXTURE_DIR / "nonexistent")


def test_load_null_mean_plddt_raises(tmp_path: Path):
    """mean_plddt=null must raise ValueError."""
    bad = {"mean_plddt": None, "metrics_are_real": True,
           "validation_status": REQUIRED_VALIDATION_STATUS,
           "prediction_status": REQUIRED_PREDICTION_STATUS}
    path = tmp_path / "parsed_metrics.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="mean_plddt"):
        load_localcolabfold_metrics(tmp_path)


def test_load_bad_validation_status_raises(tmp_path: Path):
    """Wrong validation_status must raise ValueError."""
    bad = {"mean_plddt": 65.23, "metrics_are_real": True,
           "validation_status": "EXPERIMENTALLY_VALIDATED",
           "prediction_status": REQUIRED_PREDICTION_STATUS}
    path = tmp_path / "parsed_metrics.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="validation_status"):
        load_localcolabfold_metrics(tmp_path)


# ---------------------------------------------------------------------------
# normalize_localcolabfold_metrics
# ---------------------------------------------------------------------------


def test_normalize_preserves_real_metrics(raw_metrics: dict):
    """Real metrics must be preserved in normalized output."""
    out = normalize_localcolabfold_metrics(raw_metrics)
    assert out["mean_plddt"] == 65.23
    assert out["ptm"] == 0.28
    assert out["iptm"] is None


def test_normalize_job_type_and_mode(raw_metrics: dict):
    """Normalized output must have correct job_type and mode."""
    out = normalize_localcolabfold_metrics(raw_metrics)
    assert out["job_type"] == "structure_prediction"
    assert out["mode"] == "LOCALCOLABFOLD_IMPORTED_RESULT"


def test_normalize_forbidden_metrics_are_null(raw_metrics: dict):
    """Forbidden metrics must be explicitly null."""
    out = normalize_localcolabfold_metrics(raw_metrics)
    forbidden = out.get("forbidden_metrics", {})
    for key in FORBIDDEN_METRIC_KEYS:
        assert forbidden.get(key) is None


def test_normalize_structure_file(raw_metrics: dict):
    """structure_file must be populated from best_model_pdb."""
    out = normalize_localcolabfold_metrics(raw_metrics)
    assert out["structure_file"] is not None
    assert out["structure_file"].endswith(".pdb")


def test_normalize_source_result_dir(raw_metrics: dict):
    """source_result_dir must reflect the original output directory."""
    out = normalize_localcolabfold_metrics(raw_metrics)
    assert "gpu_attempt" in out["source_result_dir"]


# ---------------------------------------------------------------------------
# validate_no_fabricated_structure_metrics
# ---------------------------------------------------------------------------


def test_validate_passes_for_clean_output(raw_metrics: dict):
    """Clean normalized output must pass validation."""
    out = normalize_localcolabfold_metrics(raw_metrics)
    validate_no_fabricated_structure_metrics(out)  # should not raise


def test_validate_rejects_non_null_pdockq(raw_metrics: dict):
    """Non-null pDockQ must raise ValueError."""
    out = normalize_localcolabfold_metrics(raw_metrics)
    out["pDockQ"] = 0.5
    with pytest.raises(ValueError, match="pDockQ"):
        validate_no_fabricated_structure_metrics(out)


def test_validate_rejects_non_null_delta_g(raw_metrics: dict):
    """Non-null delta_G must raise ValueError."""
    out = normalize_localcolabfold_metrics(raw_metrics)
    out["delta_G"] = -8.5
    with pytest.raises(ValueError, match="delta_G"):
        validate_no_fabricated_structure_metrics(out)


def test_validate_rejects_non_null_docking_score(raw_metrics: dict):
    """Non-null docking_score must raise ValueError."""
    out = normalize_localcolabfold_metrics(raw_metrics)
    out["docking_score"] = -7.2
    with pytest.raises(ValueError, match="docking_score"):
        validate_no_fabricated_structure_metrics(out)


def test_validate_rejects_experimental_validation(raw_metrics: dict):
    """Experimentally-validated claim must raise ValueError."""
    out = normalize_localcolabfold_metrics(raw_metrics)
    out["validation_status"] = "EXPERIMENTALLY_VALIDATED"
    with pytest.raises(ValueError, match="experimental"):
        validate_no_fabricated_structure_metrics(out)


# ---------------------------------------------------------------------------
# Integration: end-to-end import flow
# ---------------------------------------------------------------------------


def test_end_to_end_import_flow(parsed_metrics_path: Path):
    """Full flow: load -> normalize -> validate must succeed for fixture."""
    raw = load_localcolabfold_metrics(FIXTURE_DIR)
    out = normalize_localcolabfold_metrics(raw)
    validate_no_fabricated_structure_metrics(out)
    assert out["metrics_are_real"] is True
    assert out["mean_plddt"] == 65.23
