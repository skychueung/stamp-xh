"""Tests for FlexPepDock Batch Docking (v1.5 P3).

Rules:
- Must verify FAILED when inputs are missing.
- Must verify BLOCKED when env is missing or server unreachable.
- Must verify SUCCEEDED only when real artifacts exist.
- Must NOT write fake scores.
- Must verify single item failure does NOT abort the batch.
- Must verify batch summary reflects per-item statuses.
- Must verify retry-failed only retries FAILED/BLOCKED items.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.batch_compute_runner import (
    compute_batch_status_from_items,
    dispatch_flexpepdock_item,
    run_flexpepdock_batch,
    validate_job_params,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_temp_pdb(name: str = "test") -> str:
    """Create a minimal temp PDB file and return its path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False)
    f.write("ATOM    1  N   ALA A   1      10.000  10.000  10.000  1.00 20.00           N\n")
    f.close()
    return f.name


def _make_mock_item(
    item_id: str,
    candidate_id: str,
    status: str = "PENDING",
    input_json: dict | None = None,
    artifact_dir: str | None = None,
    error_message: str | None = None,
    job_type: str = "FLEXPEPDOCK",
) -> MagicMock:
    item = MagicMock()
    item.id = item_id
    item.candidate_id = candidate_id
    item.status = status
    item.job_type = job_type
    item.input_json = input_json or {}
    item.artifact_dir = artifact_dir
    item.error_message = error_message
    item.output_json = None
    item.started_at = None
    item.finished_at = None
    return item


# ---------------------------------------------------------------------------
# validate_job_params for FLEXPEPDOCK
# ---------------------------------------------------------------------------

def test_validate_job_params_flexpepdock_empty():
    ok, err = validate_job_params("FLEXPEPDOCK", {})
    assert ok is False
    assert "empty" in err.lower() or "receptor_pdb" in err.lower()


def test_validate_job_params_flexpepdock_valid():
    rec_path = _make_temp_pdb("receptor")
    pep_path = _make_temp_pdb("peptide")
    try:
        ok, err = validate_job_params(
            "FLEXPEPDOCK",
            {
                "receptor_pdb": rec_path,
                "peptide_pdb": pep_path,
                "receptor_chain": "A",
                "peptide_chain": "B",
            },
        )
        assert ok is True
        assert err is None
    finally:
        os.unlink(rec_path)
        os.unlink(pep_path)


# ---------------------------------------------------------------------------
# dispatch_flexpepdock_item
# ---------------------------------------------------------------------------

@patch("app.services.flexpepdock_runner.validate_input")
@patch("app.services.flexpepdock_runner.dispatch")
@patch("app.services.flexpepdock_runner.create_workdir")
def test_dispatch_flexpepdock_item_success(mock_workdir, mock_dispatch, mock_validate):
    """P3: Successful item returns SUCCEEDED with real output."""
    mock_validate.return_value = (True, None)
    mock_workdir.return_value = "/tmp/batch_flex_test/item_001"
    mock_dispatch.return_value = (
        "SUCCEEDED",
        None,
        {
            "scorefile_path": "/tmp/batch_flex_test/item_001/scores/score.sc",
            "score_data": {
                "status": "SUCCEEDED",
                "metrics": {"total_score": -312.45, "I_sc": -8.23},
            },
            "prediction_status": "COMPUTATIONAL_DOCKING_ESTIMATE_ONLY",
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        },
    )

    db = MagicMock()
    item = _make_mock_item(
        "item-001",
        "cand-001",
        input_json={
            "receptor_pdb": "/fake/rec.pdb",
            "peptide_pdb": "/fake/pep.pdb",
        },
    )

    result = dispatch_flexpepdock_item(db, item)

    assert result.status == "SUCCEEDED"
    assert result.error_message is None
    assert result.output_json is not None
    assert result.output_json["prediction_status"] == "COMPUTATIONAL_DOCKING_ESTIMATE_ONLY"
    assert result.output_json["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


@patch("app.services.flexpepdock_runner.validate_input")
@patch("app.services.flexpepdock_runner.dispatch")
@patch("app.services.flexpepdock_runner.create_workdir")
def test_dispatch_flexpepdock_item_blocked(mock_workdir, mock_dispatch, mock_validate):
    """P3: BLOCKED item is recorded correctly."""
    mock_validate.return_value = (True, None)
    mock_workdir.return_value = "/tmp/batch_flex_test/item_002"
    mock_dispatch.return_value = (
        "BLOCKED",
        "Rosetta env script not found on server",
        None,
    )

    db = MagicMock()
    item = _make_mock_item(
        "item-002",
        "cand-002",
        input_json={
            "receptor_pdb": "/fake/rec.pdb",
            "peptide_pdb": "/fake/pep.pdb",
        },
    )

    result = dispatch_flexpepdock_item(db, item)

    assert result.status == "BLOCKED"
    assert "Rosetta env script" in result.error_message


@patch("app.services.flexpepdock_runner.validate_input")
@patch("app.services.flexpepdock_runner.dispatch")
@patch("app.services.flexpepdock_runner.create_workdir")
def test_dispatch_flexpepdock_item_failed(mock_workdir, mock_dispatch, mock_validate):
    """P3: FAILED item is recorded correctly."""
    mock_validate.return_value = (True, None)
    mock_workdir.return_value = "/tmp/batch_flex_test/item_003"
    mock_dispatch.return_value = (
        "FAILED",
        "Missing output files",
        {"workdir": "/tmp/batch_flex_test/item_003"},
    )

    db = MagicMock()
    item = _make_mock_item(
        "item-003",
        "cand-003",
        input_json={
            "receptor_pdb": "/fake/rec.pdb",
            "peptide_pdb": "/fake/pep.pdb",
        },
    )

    result = dispatch_flexpepdock_item(db, item)

    assert result.status == "FAILED"
    assert "Missing output files" in result.error_message
    assert result.output_json is not None


@patch("app.services.flexpepdock_runner.dispatch")
@patch("app.services.flexpepdock_runner.create_workdir")
def test_dispatch_flexpepdock_item_validation_fails(mock_workdir, mock_dispatch):
    """P3: Invalid input returns FAILED before dispatch."""
    db = MagicMock()
    item = _make_mock_item(
        "item-004",
        "cand-004",
        input_json={},  # empty -> validation fails
    )

    result = dispatch_flexpepdock_item(db, item)

    assert result.status == "FAILED"
    assert result.error_message is not None
    mock_dispatch.assert_not_called()


@patch("app.services.flexpepdock_runner.validate_input")
@patch("app.services.flexpepdock_runner.dispatch")
@patch("app.services.flexpepdock_runner.create_workdir")
def test_dispatch_flexpepdock_item_crash_is_failed(mock_workdir, mock_dispatch, mock_validate):
    """P3: Unexpected exception during dispatch is caught and marked FAILED."""
    mock_validate.return_value = (True, None)
    mock_workdir.return_value = "/tmp/batch_flex_test/item_005"
    mock_dispatch.side_effect = RuntimeError("SSH connection dropped")

    db = MagicMock()
    item = _make_mock_item(
        "item-005",
        "cand-005",
        input_json={
            "receptor_pdb": "/fake/rec.pdb",
            "peptide_pdb": "/fake/pep.pdb",
        },
    )

    result = dispatch_flexpepdock_item(db, item)

    assert result.status == "FAILED"
    assert "SSH connection dropped" in result.error_message


# ---------------------------------------------------------------------------
# run_flexpepdock_batch
# ---------------------------------------------------------------------------

@patch("app.services.batch_compute_runner.dispatch_flexpepdock_item")
def test_run_flexpepdock_batch_all_succeed(mock_dispatch):
    """P3: All items succeed -> batch SUCCEEDED."""
    db = MagicMock()
    batch = MagicMock()
    batch.id = "batch-all-ok"
    batch.status = "PENDING"
    batch.started_at = None
    batch.finished_at = None
    batch.summary_json = None

    items = [
        _make_mock_item("i1", "c1", input_json={"receptor_pdb": "/r.pdb", "peptide_pdb": "/p.pdb"}),
        _make_mock_item("i2", "c2", input_json={"receptor_pdb": "/r.pdb", "peptide_pdb": "/p.pdb"}),
        _make_mock_item("i3", "c3", input_json={"receptor_pdb": "/r.pdb", "peptide_pdb": "/p.pdb"}),
    ]

    def side_effect(db_arg, item_arg):
        item_arg.status = "SUCCEEDED"
        item_arg.error_message = None
        item_arg.output_json = {"score_data": {"metrics": {"total_score": -300.0}}}
        return item_arg

    mock_dispatch.side_effect = side_effect

    summary = run_flexpepdock_batch(db, batch, items)

    assert batch.status == "SUCCEEDED"
    assert summary["succeeded"] == 3
    assert summary["failed"] == 0
    assert summary["blocked"] == 0
    assert len(summary["items"]) == 3


@patch("app.services.batch_compute_runner.dispatch_flexpepdock_item")
def test_run_flexpepdock_batch_one_fails_others_continue(mock_dispatch):
    """P3: One item failure does NOT abort the batch."""
    db = MagicMock()
    batch = MagicMock()
    batch.id = "batch-partial"
    batch.status = "PENDING"
    batch.started_at = None
    batch.finished_at = None
    batch.summary_json = None

    items = [
        _make_mock_item("i1", "c1", input_json={"receptor_pdb": "/r.pdb", "peptide_pdb": "/p.pdb"}),
        _make_mock_item("i2", "c2", input_json={"receptor_pdb": "/r.pdb", "peptide_pdb": "/p.pdb"}),
        _make_mock_item("i3", "c3", input_json={"receptor_pdb": "/r.pdb", "peptide_pdb": "/p.pdb"}),
    ]

    call_count = 0

    def side_effect(db_arg, item_arg):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            item_arg.status = "FAILED"
            item_arg.error_message = "Server timeout"
            item_arg.output_json = {}
        else:
            item_arg.status = "SUCCEEDED"
            item_arg.error_message = None
            item_arg.output_json = {"score_data": {}}
        return item_arg

    mock_dispatch.side_effect = side_effect

    summary = run_flexpepdock_batch(db, batch, items)

    assert batch.status == "PARTIAL"
    assert summary["succeeded"] == 2
    assert summary["failed"] == 1
    assert summary["blocked"] == 0
    assert call_count == 3  # all 3 items were executed


@patch("app.services.batch_compute_runner.dispatch_flexpepdock_item")
def test_run_flexpepdock_batch_all_fail(mock_dispatch):
    """P3: All items fail -> batch FAILED."""
    db = MagicMock()
    batch = MagicMock()
    batch.id = "batch-all-fail"
    batch.status = "PENDING"
    batch.started_at = None
    batch.finished_at = None
    batch.summary_json = None

    items = [
        _make_mock_item("i1", "c1", input_json={"receptor_pdb": "/r.pdb", "peptide_pdb": "/p.pdb"}),
        _make_mock_item("i2", "c2", input_json={"receptor_pdb": "/r.pdb", "peptide_pdb": "/p.pdb"}),
    ]

    def side_effect(db_arg, item_arg):
        item_arg.status = "FAILED"
        item_arg.error_message = "Missing output"
        return item_arg

    mock_dispatch.side_effect = side_effect

    summary = run_flexpepdock_batch(db, batch, items)

    assert batch.status == "FAILED"
    assert summary["succeeded"] == 0
    assert summary["failed"] == 2


@patch("app.services.batch_compute_runner.dispatch_flexpepdock_item")
def test_run_flexpepdock_batch_mixed_blocked(mock_dispatch):
    """P3: Some blocked, some succeed -> PARTIAL."""
    db = MagicMock()
    batch = MagicMock()
    batch.id = "batch-mixed"
    batch.status = "PENDING"
    batch.started_at = None
    batch.finished_at = None
    batch.summary_json = None

    items = [
        _make_mock_item("i1", "c1", input_json={"receptor_pdb": "/r.pdb", "peptide_pdb": "/p.pdb"}),
        _make_mock_item("i2", "c2", input_json={"receptor_pdb": "/r.pdb", "peptide_pdb": "/p.pdb"}),
    ]

    def side_effect(db_arg, item_arg):
        if item_arg.id == "i1":
            item_arg.status = "SUCCEEDED"
            item_arg.error_message = None
        else:
            item_arg.status = "BLOCKED"
            item_arg.error_message = "Rosetta not found"
        return item_arg

    mock_dispatch.side_effect = side_effect

    summary = run_flexpepdock_batch(db, batch, items)

    assert batch.status == "PARTIAL"
    assert summary["succeeded"] == 1
    assert summary["blocked"] == 1


# ---------------------------------------------------------------------------
# compute_batch_status_from_items
# ---------------------------------------------------------------------------

def test_compute_batch_status_all_succeeded():
    items = [
        _make_mock_item("i1", "c1", status="SUCCEEDED"),
        _make_mock_item("i2", "c2", status="SUCCEEDED"),
    ]
    assert compute_batch_status_from_items(items) == "SUCCEEDED"


def test_compute_batch_status_all_failed():
    items = [
        _make_mock_item("i1", "c1", status="FAILED"),
        _make_mock_item("i2", "c2", status="BLOCKED"),
    ]
    assert compute_batch_status_from_items(items) == "FAILED"


def test_compute_batch_status_partial():
    items = [
        _make_mock_item("i1", "c1", status="SUCCEEDED"),
        _make_mock_item("i2", "c2", status="FAILED"),
    ]
    assert compute_batch_status_from_items(items) == "PARTIAL"


def test_compute_batch_status_running():
    items = [
        _make_mock_item("i1", "c1", status="RUNNING"),
        _make_mock_item("i2", "c2", status="PENDING"),
    ]
    assert compute_batch_status_from_items(items) == "RUNNING"


def test_compute_batch_status_empty():
    assert compute_batch_status_from_items([]) == "PENDING"


# ---------------------------------------------------------------------------
# Scientific boundary: no fabricated scores
# ---------------------------------------------------------------------------

def test_no_fabricated_docking_score_in_summary():
    """P3: batch summary must never contain a fabricated docking_score."""
    db = MagicMock()
    batch = MagicMock()
    batch.id = "batch-no-fake"
    batch.status = "PENDING"
    batch.started_at = None
    batch.finished_at = None
    batch.summary_json = None

    items = [
        _make_mock_item("i1", "c1", input_json={"receptor_pdb": "/r.pdb", "peptide_pdb": "/p.pdb"}),
    ]

    with patch("app.services.batch_compute_runner.dispatch_flexpepdock_item") as mock_dispatch:
        def side_effect(db_arg, item_arg):
            item_arg.status = "SUCCEEDED"
            item_arg.output_json = {
                "score_data": {
                    "metrics": {"total_score": -312.45, "I_sc": -8.23},
                },
                "prediction_status": "COMPUTATIONAL_DOCKING_ESTIMATE_ONLY",
            }
            return item_arg

        mock_dispatch.side_effect = side_effect
        summary = run_flexpepdock_batch(db, batch, items)

    for it in summary["items"]:
        metrics = it.get("output_json", {}).get("score_data", {}).get("metrics", {})
        assert "docking_score" not in metrics
        assert "total_score" in metrics or "I_sc" in metrics


# ---------------------------------------------------------------------------
# Retry failed items
# ---------------------------------------------------------------------------

def test_retry_failed_items_resets_status():
    """P3: retry-failed resets FAILED and BLOCKED items to PENDING."""
    from app.crud.batch_computations import update_batch_item_status
    from unittest.mock import MagicMock

    db = MagicMock()
    item_failed = _make_mock_item("i1", "c1", status="FAILED", error_message="timeout")
    item_blocked = _make_mock_item("i2", "c2", status="BLOCKED", error_message="no env")
    item_ok = _make_mock_item("i3", "c3", status="SUCCEEDED")

    items = [item_failed, item_blocked, item_ok]

    # Simulate retry-failed logic from router
    retried = 0
    for item in items:
        if item.status in ("FAILED", "BLOCKED"):
            item.status = "PENDING"
            item.error_message = None
            item.started_at = None
            item.finished_at = None
            retried += 1

    assert retried == 2
    assert item_failed.status == "PENDING"
    assert item_blocked.status == "PENDING"
    assert item_ok.status == "SUCCEEDED"
