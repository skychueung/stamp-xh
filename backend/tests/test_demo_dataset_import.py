"""Tests for v1.0 demo dataset validation.

Scientific boundary assertions:
- All candidates must be NOT_EXPERIMENTALLY_VALIDATED.
- official_mm_gbsa_delta_g must be null.
- No fabricated experimental metrics.
"""

from __future__ import annotations

import json
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent / "fixtures"
DEMO_DATASET = FIXTURES_DIR / "v1.0_demo_dataset.json"


class TestDemoDatasetExists:
    def test_file_exists(self):
        assert DEMO_DATASET.exists(), f"Demo dataset not found: {DEMO_DATASET}"

    def test_valid_json(self):
        text = DEMO_DATASET.read_text(encoding="utf-8")
        data = json.loads(text)
        assert isinstance(data, dict)


class TestDemoDatasetSchema:
    def test_version(self):
        data = json.loads(DEMO_DATASET.read_text(encoding="utf-8"))
        assert data.get("version") == "1.0"

    def test_has_projects(self):
        data = json.loads(DEMO_DATASET.read_text(encoding="utf-8"))
        assert data.get("projects")
        assert len(data["projects"]) >= 1

    def test_has_target_proteins(self):
        data = json.loads(DEMO_DATASET.read_text(encoding="utf-8"))
        assert data.get("target_proteins")
        assert len(data["target_proteins"]) >= 1

    def test_has_epitope_candidates(self):
        data = json.loads(DEMO_DATASET.read_text(encoding="utf-8"))
        assert data.get("epitope_candidates")
        assert len(data["epitope_candidates"]) >= 1

    def test_has_stamp_candidates(self):
        data = json.loads(DEMO_DATASET.read_text(encoding="utf-8"))
        assert data.get("stamp_candidates")
        assert len(data["stamp_candidates"]) >= 1


class TestScientificBoundary:
    def test_all_candidates_not_experimentally_validated(self):
        data = json.loads(DEMO_DATASET.read_text(encoding="utf-8"))
        for c in data.get("stamp_candidates", []):
            assert c["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"

    def test_official_mm_gbsa_delta_g_is_null(self):
        data = json.loads(DEMO_DATASET.read_text(encoding="utf-8"))
        for c in data.get("stamp_candidates", []):
            mmpbsa = c.get("metrics", {}).get("mmpbsa", {})
            assert mmpbsa.get("official_mm_gbsa_delta_g") is None

    def test_no_fabricated_mic(self):
        data = json.loads(DEMO_DATASET.read_text(encoding="utf-8"))
        for c in data.get("stamp_candidates", []):
            metrics = c.get("metrics", {})
            assert "MIC_ug_ml" not in metrics
            assert "MBC_ug_ml" not in metrics

    def test_run_type_is_pilot(self):
        data = json.loads(DEMO_DATASET.read_text(encoding="utf-8"))
        for c in data.get("stamp_candidates", []):
            mmpbsa = c.get("metrics", {}).get("mmpbsa", {})
            assert mmpbsa.get("run_type") in ("PILOT", "SMOKE")

    def test_convergence_status_pilot_only(self):
        data = json.loads(DEMO_DATASET.read_text(encoding="utf-8"))
        for c in data.get("stamp_candidates", []):
            mmpbsa = c.get("metrics", {}).get("mmpbsa", {})
            assert "PILOT" in mmpbsa.get("convergence_status", "")
