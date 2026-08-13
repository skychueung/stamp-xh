"""Tests for FlexPepDock Runner (v1.5 P2).

Rules:
- Must verify FAILED when inputs are missing
- Must verify BLOCKED when env is missing or server unreachable
- Must verify SUCCEEDED only when real artifacts exist
- Must NOT write fake scores
- Must NOT claim SUCCEEDED without real artifacts
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.flexpepdock_runner import (
    create_workdir,
    dispatch,
    dry_run,
    run_single_docking,
    smoke_run,
    validate_input,
)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_validate_input_empty():
    ok, err = validate_input({})
    assert ok is False
    assert "empty" in err.lower() or "receptor_pdb" in err.lower()


def test_validate_input_missing_receptor():
    ok, err = validate_input({"peptide_pdb": "/tmp/fake.pdb"})
    assert ok is False
    assert "receptor_pdb" in err.lower()


def test_validate_input_missing_peptide():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as rec:
        rec.write("ATOM    1  N   ALA A   1      10.000  10.000  10.000  1.00 20.00           N\n")
        rec_path = rec.name
    try:
        ok, err = validate_input({"receptor_pdb": rec_path})
        assert ok is False
        assert "peptide" in err.lower()
    finally:
        os.unlink(rec_path)


def test_validate_input_receptor_not_found():
    ok, err = validate_input(
        {"receptor_pdb": "/nonexistent/receptor.pdb", "peptide_pdb": "/tmp/fake.pdb"}
    )
    assert ok is False
    assert "not found" in err.lower()


def test_validate_input_valid():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as rec:
        rec.write(
            "ATOM    1  N   ALA A   1      10.000  10.000  10.000  1.00 20.00           N\n"
        )
        rec_path = rec.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as pep:
        pep.write(
            "ATOM    1  N   GLY B   1      10.000  10.000  10.000  1.00 20.00           N\n"
        )
        pep_path = pep.name
    try:
        ok, err = validate_input(
            {
                "receptor_pdb": rec_path,
                "peptide_pdb": pep_path,
                "receptor_chain": "A",
                "peptide_chain": "B",
            }
        )
        assert ok is True
        assert err is None
    finally:
        os.unlink(rec_path)
        os.unlink(pep_path)


# ---------------------------------------------------------------------------
# Workdir creation
# ---------------------------------------------------------------------------

def test_create_workdir():
    workdir = create_workdir("batch-test-123", "item-test-456")
    assert os.path.isdir(workdir)
    for sub in ("inputs", "prepared", "runs", "scores", "logs", "artifacts"):
        assert os.path.isdir(os.path.join(workdir, sub))


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------

def test_dry_run_no_fake_score():
    result = dry_run(
        "batch-1",
        "item-1",
        {"receptor_pdb": "/tmp/rec.pdb", "peptide_pdb": "/tmp/pep.pdb"},
    )
    assert result["dry_run"] is True
    assert "command" in result
    assert "score" not in result  # no fabricated scores


# ---------------------------------------------------------------------------
# Smoke run
# ---------------------------------------------------------------------------

def test_smoke_run_missing_env():
    original = os.environ.get("ROSETTA_ENV_SCRIPT")
    os.environ["ROSETTA_ENV_SCRIPT"] = "/nonexistent/rosetta_env.sh"
    try:
        success, error = smoke_run()
        assert success is False
        assert "not found" in error.lower()
    finally:
        if original is not None:
            os.environ["ROSETTA_ENV_SCRIPT"] = original
        else:
            os.environ.pop("ROSETTA_ENV_SCRIPT", None)


# ---------------------------------------------------------------------------
# P2: Real single-sample docking (SSH to server)
# ---------------------------------------------------------------------------

def _make_temp_pdb(name: str = "test") -> str:
    """Create a minimal temp PDB file and return its path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False)
    f.write("ATOM    1  N   ALA A   1      10.000  10.000  10.000  1.00 20.00           N\n")
    f.close()
    return f.name


@patch("app.services.flexpepdock_runner.subprocess.run")
@patch("app.services.flexpepdock_runner._run_server_command")
@patch("app.services.flexpepdock_runner._scp_upload")
@patch("app.services.flexpepdock_runner._scp_download")
def test_run_single_docking_server_unreachable(
    mock_download, mock_upload, mock_server_cmd, mock_ssh
):
    """P2: Unreachable server returns BLOCKED."""
    proc = MagicMock()
    proc.returncode = 1
    proc.stdout = ""
    proc.stderr = "Connection timed out"
    mock_ssh.return_value = proc

    rec_path = _make_temp_pdb("receptor")
    pep_path = _make_temp_pdb("peptide")
    try:
        status, error, output = run_single_docking(
            "batch-p2-001",
            "item-p2-001",
            {
                "receptor_pdb": rec_path,
                "peptide_pdb": pep_path,
                "receptor_chain": "A",
                "peptide_chain": "B",
                "nstruct": 1,
            },
        )
        assert status == "BLOCKED"
        assert "unreachable" in error.lower() or "reachability" in error.lower()
        assert output is None
    finally:
        os.unlink(rec_path)
        os.unlink(pep_path)


@patch("app.services.flexpepdock_runner.subprocess.run")
@patch("app.services.flexpepdock_runner._run_server_command")
@patch("app.services.flexpepdock_runner._scp_upload")
@patch("app.services.flexpepdock_runner._scp_download")
def test_run_single_docking_missing_rosetta_on_server(
    mock_download, mock_upload, mock_server_cmd, mock_ssh
):
    """P2: Missing Rosetta env on server returns BLOCKED."""
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = "ok"
    mock_ssh.return_value = proc

    # Rosetta env check fails
    mock_server_cmd.return_value = (0, "no", "")

    rec_path = _make_temp_pdb("receptor")
    pep_path = _make_temp_pdb("peptide")
    try:
        status, error, output = run_single_docking(
            "batch-p2-002",
            "item-p2-002",
            {
                "receptor_pdb": rec_path,
                "peptide_pdb": pep_path,
                "receptor_chain": "A",
                "peptide_chain": "B",
                "nstruct": 1,
            },
        )
        assert status == "BLOCKED"
        assert "Rosetta env script not found" in error
        assert output is None
    finally:
        os.unlink(rec_path)
        os.unlink(pep_path)


@patch("app.services.flexpepdock_runner.subprocess.run")
@patch("app.services.flexpepdock_runner._run_server_command")
@patch("app.services.flexpepdock_runner._scp_upload")
@patch("app.services.flexpepdock_runner._scp_download")
def test_run_single_docking_upload_failure(
    mock_download, mock_upload, mock_server_cmd, mock_ssh
):
    """P2: SCP upload failure returns FAILED."""
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = "ok"
    mock_ssh.return_value = proc

    # Server command responses:
    # 1. env check -> yes
    # 2. mkdir -> ok
    mock_server_cmd.side_effect = [
        (0, "yes", ""),  # env check
        (0, "", ""),     # mkdir
    ]
    mock_upload.return_value = False  # upload fails

    rec_path = _make_temp_pdb("receptor")
    pep_path = _make_temp_pdb("peptide")
    try:
        status, error, output = run_single_docking(
            "batch-p2-003",
            "item-p2-003",
            {
                "receptor_pdb": rec_path,
                "peptide_pdb": pep_path,
                "receptor_chain": "A",
                "peptide_chain": "B",
                "nstruct": 1,
            },
        )
        assert status == "FAILED"
        assert "upload" in error.lower()
    finally:
        os.unlink(rec_path)
        os.unlink(pep_path)


@patch("app.services.flexpepdock_runner.subprocess.run")
@patch("app.services.flexpepdock_runner._run_server_command")
@patch("app.services.flexpepdock_runner._scp_upload")
@patch("app.services.flexpepdock_runner._scp_download")
def test_run_single_docking_success(
    mock_download, mock_upload, mock_server_cmd, mock_ssh, tmp_path: Path
):
    """P2: Full success path with real local scorefile."""
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = "ok"
    mock_ssh.return_value = proc

    # Server command responses:
    # 1. env check -> yes
    # 2. mkdir -> ok
    # 3. which binary -> /fake/rosetta/FlexPepDocking
    # 4. run docking -> ok
    mock_server_cmd.side_effect = [
        (0, "yes", ""),
        (0, "", ""),
        (0, "/fake/rosetta/FlexPepDocking.default.linuxgccrelease", ""),
        (0, "", ""),
    ]
    mock_upload.return_value = True
    mock_download.return_value = True

    rec_path = _make_temp_pdb("receptor")
    pep_path = _make_temp_pdb("peptide")

    try:
        # Pre-create the workdir and scorefile that _verify_outputs expects
        workdir = create_workdir("batch-p2-004", "item-p2-004")
        scorefile = Path(workdir) / "scores" / "score_item-p2-004.sc"
        scorefile.parent.mkdir(parents=True, exist_ok=True)
        # Write a real Rosetta scorefile
        scorefile.write_text(
            "SCORE: total_score       I_sc    description\n"
            "SCORE:      -312.45      -8.23   flexpepdock_0001\n",
            encoding="utf-8",
        )

        status, error, output = run_single_docking(
            "batch-p2-004",
            "item-p2-004",
            {
                "receptor_pdb": rec_path,
                "peptide_pdb": pep_path,
                "receptor_chain": "A",
                "peptide_chain": "B",
                "nstruct": 1,
            },
        )

        assert status == "SUCCEEDED"
        assert error is None
        assert output is not None
        assert output["workdir"] == workdir
        assert "score_data" in output
        assert output["score_data"]["status"] == "SUCCEEDED"
        assert output["prediction_status"] == "COMPUTATIONAL_DOCKING_ESTIMATE_ONLY"
        assert output["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
        # Verify no fabricated docking_score
        metrics = output["score_data"].get("metrics", {})
        assert "docking_score" not in metrics
    finally:
        os.unlink(rec_path)
        os.unlink(pep_path)


@patch("app.services.flexpepdock_runner.subprocess.run")
@patch("app.services.flexpepdock_runner._run_server_command")
@patch("app.services.flexpepdock_runner._scp_upload")
@patch("app.services.flexpepdock_runner._scp_download")
def test_run_single_docking_missing_outputs(
    mock_download, mock_upload, mock_server_cmd, mock_ssh, tmp_path: Path
):
    """P2: When outputs are missing after download, return FAILED."""
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = "ok"
    mock_ssh.return_value = proc

    mock_server_cmd.side_effect = [
        (0, "yes", ""),
        (0, "", ""),
        (0, "/fake/rosetta/FlexPepDocking.default.linuxgccrelease", ""),
        (0, "", ""),
    ]
    mock_upload.return_value = True
    mock_download.return_value = True

    rec_path = _make_temp_pdb("receptor")
    pep_path = _make_temp_pdb("peptide")

    try:
        status, error, output = run_single_docking(
            "batch-p2-005",
            "item-p2-005",
            {
                "receptor_pdb": rec_path,
                "peptide_pdb": pep_path,
                "receptor_chain": "A",
                "peptide_chain": "B",
                "nstruct": 1,
            },
        )

        assert status == "FAILED"
        assert "Missing output files" in error
    finally:
        os.unlink(rec_path)
        os.unlink(pep_path)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def test_dispatch_fails_validation():
    status, err, out = dispatch("b1", "i1", {})
    assert status == "FAILED"
    assert err is not None


@patch("app.services.flexpepdock_runner.subprocess.run")
@patch("app.services.flexpepdock_runner._run_server_command")
@patch("app.services.flexpepdock_runner._scp_upload")
@patch("app.services.flexpepdock_runner._scp_download")
def test_dispatch_blocked_no_server(mock_download, mock_upload, mock_server_cmd, mock_ssh):
    proc = MagicMock()
    proc.returncode = 1
    proc.stdout = ""
    mock_ssh.return_value = proc

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".pdb", delete=False
    ) as rec:
        rec.write(
            "ATOM    1  N   ALA A   1      10.000  10.000  10.000  1.00 20.00           N\n"
        )
        rec_path = rec.name
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".pdb", delete=False
    ) as pep:
        pep.write(
            "ATOM    1  N   GLY B   1      10.000  10.000  10.000  1.00 20.00           N\n"
        )
        pep_path = pep.name
    try:
        status, err, out = dispatch(
            "b1",
            "i1",
            {
                "receptor_pdb": rec_path,
                "peptide_pdb": pep_path,
                "receptor_chain": "A",
                "peptide_chain": "B",
            },
        )
        # Should be BLOCKED because server is unreachable
        assert status == "BLOCKED"
        assert err is not None
    finally:
        os.unlink(rec_path)
        os.unlink(pep_path)


# ---------------------------------------------------------------------------
# Scientific boundary: never claim success without real artifacts
# ---------------------------------------------------------------------------

def test_finalize_empty_artifacts_is_failed():
    """This test documents the existing behavior in batch_compute_runner.py.

    finalize_batch_item downgrades success=True to FAILED when artifact_dir is empty.
    """
    from unittest.mock import MagicMock

    from app.services.batch_compute_runner import finalize_batch_item

    item = MagicMock()
    item.artifact_dir = "/tmp/empty_dir_for_test_flexpepdock"
    item.id = "test-item"
    item.status = "RUNNING"
    item.error_message = None
    item.output_json = None
    item.finished_at = None

    db = MagicMock()

    # Create empty dir
    os.makedirs(item.artifact_dir, exist_ok=True)
    try:
        result = finalize_batch_item(
            db, item, success=True, output_json={"score": -12.34}
        )
        assert result.status == "FAILED"
        assert "No real artifacts" in result.error_message
    finally:
        os.rmdir(item.artifact_dir)
