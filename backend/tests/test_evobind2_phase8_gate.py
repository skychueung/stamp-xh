"""Phase 8 security tests for EvoBind2 fail-closed gate and runner.

These tests verify:
  - gate default-closed behavior
  - gate content/run_id/expiry validation
  - symlink / path traversal / permission rejection
  - runner input guards (FASTA, run_id, model, parameter limits)
  - runner does not write files or call subprocess when gate is closed
  - dry-run preview remains safe and gate-independent
  - cleanup/rollback path guards

No real EvoBind2/HHblits/AlphaFold2 execution is performed.
"""

from __future__ import annotations

import json
import os
import re
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.compute_wrappers.evobind2_gate import (
    DEFAULT_GATE_ROOT,
    GateClosedError,
    GatePathUnsafeError,
    _get_gate_root,
    check_run_gate,
    create_run_gate,
    require_run_gate,
    run_gate_context,
    validate_run_id,
)
from app.services.compute_wrappers.evobind2_runner import (
    ALLOWED_ROOTS,
    EvoBind2ExecutionError,
    cleanup_run_artifacts,
    execute_evobind2_run,
    preview_run_command,
    rollback_run,
    validate_fasta,
    validate_run_input,
)
from app.services.compute_wrappers.evobind2_wrapper import (
    EvoBind2Input,
    build_run_paths,
    dry_run_plan,
    validate_fasta_local,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gate_root(tmp_path: Path) -> Path:
    return tmp_path / "gates"


@pytest.fixture
def valid_run_id() -> str:
    return "phase8_run_001"


@pytest.fixture
def valid_fasta() -> str:
    return ">receptor\nMKTAYIAKQR\n"


@pytest.fixture
def valid_input(valid_run_id: str, valid_fasta: str) -> EvoBind2Input:
    return EvoBind2Input(
        run_id=valid_run_id,
        receptor_fasta=valid_fasta,
        peptide_length=12,
        mode="predict_only",
        peptide_sequence="AAAAAAAAAAAA",
        model_name="model_1_ptm",
        max_recycles=1,
        num_iterations=1,
        use_gpu=True,
        selected_gpu="auto",
        msa_mode="single_sequence",
    )


@pytest.fixture
def work_root(tmp_path: Path) -> Path:
    root = tmp_path / "work"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# run_id validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "run_id,expected_ok",
    [
        ("phase8_run_001", True),
        ("a-b_c.d", True),
        ("", False),
        ("../../etc/passwd", False),
        ("run/id", False),
        ("run\\id", False),
        ("run..id", True),
        ("a" * 129, False),
        ("a" * 128, True),
        ("con", False),
        ("CON.txt", False),
        ("nul.dat", False),
    ],
)
def test_validate_run_id(run_id: str, expected_ok: bool):
    ok, error = validate_run_id(run_id)
    assert ok is expected_ok, f"run_id={run_id!r}: {error}"


# ---------------------------------------------------------------------------
# FASTA validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fasta,expected_ok",
    [
        (">r\nMKTAYIAKQR\n", True),
        (">r\nMKTAYIAKQRX\n", True),
        (">r\n", False),
        ("no header\nMKTAYIAKQR\n", False),
        (">r\nMKTAY123QR\n", False),
        (">r\nMKTAY\x00IAKQR\n", False),
        ("", False),
        ("   ", False),
    ],
)
def test_validate_fasta(fasta: str, expected_ok: bool):
    ok, error = validate_fasta(fasta)
    assert ok is expected_ok, f"fasta={fasta!r}: {error}"
    ok2, _ = validate_fasta_local(fasta)
    assert ok2 is expected_ok


def test_gate_default_root_is_fixed():
    assert DEFAULT_GATE_ROOT.as_posix() == "/home/xh/kxc/stampup/run_gates/evobind2"


def test_get_gate_root_allows_explicit_default_path(monkeypatch):
    """EVOBIND2_GATE_ROOT may be set to the fixed default root."""
    monkeypatch.setenv("EVOBIND2_GATE_ROOT", "/home/xh/kxc/stampup/run_gates/evobind2")
    root = _get_gate_root()
    posix = re.sub(r"^[A-Za-z]:", "", root.as_posix())
    assert posix == "/home/xh/kxc/stampup/run_gates/evobind2"


def test_get_gate_root_rejects_forbidden_tmp_env_override(monkeypatch):
    """Generic /tmp fallbacks must be rejected."""
    monkeypatch.setenv("EVOBIND2_GATE_ROOT", "/tmp/evobind2_run_gates")
    with pytest.raises(GatePathUnsafeError):
        _get_gate_root()


def test_get_gate_root_allows_explicit_subdir_of_default(monkeypatch):
    monkeypatch.setenv("EVOBIND2_GATE_ROOT", "/home/xh/kxc/stampup/run_gates/evobind2/operator_override")
    root = _get_gate_root()
    # Normalize Windows drive letter for assertion portability.
    posix = re.sub(r"^[A-Za-z]:", "", root.as_posix())
    assert posix.startswith("/home/xh/kxc/stampup/run_gates/evobind2")


# ---------------------------------------------------------------------------
# Gate default-closed
# ---------------------------------------------------------------------------


def test_gate_closed_when_file_missing(gate_root: Path, valid_run_id: str):
    status = check_run_gate(valid_run_id, gate_root)
    assert status.closed is True
    assert (
        "missing" in status.reason.lower()
        or "cannot read" in status.reason.lower()
        or "cannot be resolved" in status.reason.lower()
    )


def test_require_run_gate_raises_when_closed(gate_root: Path, valid_run_id: str):
    with pytest.raises(GateClosedError):
        require_run_gate(valid_run_id, gate_root)


# ---------------------------------------------------------------------------
# Gate creation and opening
# ---------------------------------------------------------------------------


def test_create_and_check_gate(gate_root: Path, valid_run_id: str):
    path = create_run_gate(
        valid_run_id,
        authorized_by="operator",
        purpose="phase8 test",
        gate_root=gate_root,
    )
    assert path.exists()

    status = check_run_gate(valid_run_id, gate_root)
    assert status.open_ is True
    assert status.authorized_by == "operator"


def test_gate_must_be_boolean_true(gate_root: Path, valid_run_id: str):
    gate_root.mkdir(parents=True, exist_ok=True)
    path = gate_root / f"evobind2_run_gate_{valid_run_id}.json"
    # String "true" is not accepted
    path.write_text(json.dumps({"enabled": "true", "run_id": valid_run_id}), encoding="utf-8")
    if os.name != "nt":
        os.chmod(path, 0o600)
    status = check_run_gate(valid_run_id, gate_root)
    assert status.closed is True
    assert "boolean true" in status.reason


def test_gate_run_id_mismatch(gate_root: Path, valid_run_id: str):
    # Create a gate file whose filename matches other_run_id but content
    # references valid_run_id, so the file exists and content mismatch fires.
    other_run_id = "other_run_id"
    ok, _ = validate_run_id(other_run_id)
    assert ok is True
    gate_root.mkdir(parents=True, exist_ok=True)
    path = gate_root / f"evobind2_run_gate_{other_run_id}.json"
    content = {
        "enabled": True,
        "run_id": valid_run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "authorized_by": "op",
        "purpose": "test",
    }
    path.write_text(json.dumps(content), encoding="utf-8")
    if os.name != "nt":
        os.chmod(path, 0o600)
    status = check_run_gate(other_run_id, gate_root)
    assert status.closed is True
    assert "run_id mismatch" in status.reason


def test_gate_expired(gate_root: Path, valid_run_id: str):
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    create_run_gate(
        valid_run_id,
        authorized_by="operator",
        purpose="phase8 test",
        ttl_seconds=3600,
        gate_root=gate_root,
        now=now,
    )
    later = now + timedelta(seconds=4000)
    status = check_run_gate(valid_run_id, gate_root, now=later)
    assert status.closed is True
    assert "expired" in status.reason


def test_gate_not_yet_valid(gate_root: Path, valid_run_id: str):
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    future = now + timedelta(hours=1)
    gate_root.mkdir(parents=True, exist_ok=True)
    path = gate_root / f"evobind2_run_gate_{valid_run_id}.json"
    content = {
        "enabled": True,
        "run_id": valid_run_id,
        "created_at": future.isoformat(),
        "expires_at": (future + timedelta(hours=1)).isoformat(),
        "authorized_by": "operator",
        "purpose": "test",
    }
    path.write_text(json.dumps(content), encoding="utf-8")
    if os.name != "nt":
        os.chmod(path, 0o600)
    status = check_run_gate(valid_run_id, gate_root, now=now)
    assert status.closed is True
    assert "not yet valid" in status.reason


# ---------------------------------------------------------------------------
# Gate path safety
# ---------------------------------------------------------------------------


def test_gate_rejects_symlink(gate_root: Path, valid_run_id: str, tmp_path: Path):
    create_run_gate(valid_run_id, "op", "test", gate_root=gate_root)
    real_gate = gate_root / f"evobind2_run_gate_{valid_run_id}.json"
    outside = tmp_path / "stolen_gate.json"
    outside.write_text(real_gate.read_text(), encoding="utf-8")
    real_gate.unlink()
    try:
        real_gate.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation requires privileges on this platform")

    status = check_run_gate(valid_run_id, gate_root)
    assert status.closed is True
    assert "symlink" in status.reason


def test_gate_rejects_path_traversal(gate_root: Path, tmp_path: Path):
    # Create a gate file outside the gate root using traversal in run_id
    malicious_run_id = "../../../etc/passwd_is_not_a_run_id"
    ok, _ = validate_run_id(malicious_run_id)
    assert ok is False


def test_gate_rejects_world_writable(gate_root: Path, valid_run_id: str):
    if os.name == "nt":
        pytest.skip("chmod permission test skipped on Windows")
    create_run_gate(valid_run_id, "op", "test", gate_root=gate_root)
    path = gate_root / f"evobind2_run_gate_{valid_run_id}.json"
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IWOTH)

    status = check_run_gate(valid_run_id, gate_root)
    assert status.closed is True
    assert "permissions" in status.reason


# ---------------------------------------------------------------------------
# Gate context manager
# ---------------------------------------------------------------------------


def test_run_gate_context_closes_on_exit(gate_root: Path, valid_run_id: str):
    create_run_gate(valid_run_id, "op", "test", gate_root=gate_root)
    with run_gate_context(valid_run_id, gate_root, close_on_exit=True) as status:
        assert status.open_ is True
    assert check_run_gate(valid_run_id, gate_root).closed is True


def test_run_gate_context_keeps_open_by_default(gate_root: Path, valid_run_id: str):
    create_run_gate(valid_run_id, "op", "test", gate_root=gate_root)
    with run_gate_context(valid_run_id, gate_root) as status:
        assert status.open_ is True
    assert check_run_gate(valid_run_id, gate_root).open_ is True


def test_run_gate_context_closes_on_exception(gate_root: Path, valid_run_id: str):
    create_run_gate(valid_run_id, "op", "test", gate_root=gate_root)
    with pytest.raises(RuntimeError):
        with run_gate_context(valid_run_id, gate_root, close_on_exit=True):
            raise RuntimeError("boom")
    assert check_run_gate(valid_run_id, gate_root).closed is True


# ---------------------------------------------------------------------------
# Runner input guards
# ---------------------------------------------------------------------------


def test_validate_run_input_rejects_long_peptide(valid_input: EvoBind2Input):
    valid_input.peptide_length = 200
    ok, error = validate_run_input(valid_input)
    assert ok is False
    assert "peptide_length" in error


def test_validate_run_input_rejects_design_mode(valid_input: EvoBind2Input):
    valid_input.mode = "design"
    ok, error = validate_run_input(valid_input)
    assert ok is False
    assert "predict_only" in error


def test_validate_run_input_rejects_blocked_model(valid_input: EvoBind2Input):
    valid_input.model_name = "model_1_multimer_v3"
    ok, error = validate_run_input(valid_input)
    assert ok is False


def test_validate_run_input_rejects_excessive_iterations(valid_input: EvoBind2Input):
    valid_input.num_iterations = 200
    ok, error = validate_run_input(valid_input)
    assert ok is False
    assert "num_iterations" in error


# ---------------------------------------------------------------------------
# Runner gate behavior
# ---------------------------------------------------------------------------


def test_execute_evobind2_run_blocked_without_gate(
    valid_input: EvoBind2Input, gate_root: Path, tmp_path: Path
):
    # Override work roots to tmp_path so no real server paths are touched
    with patch.dict(
        ALLOWED_ROOTS,
        {
            "work": tmp_path / "work",
            "artifact": tmp_path / "artifact",
            "log": tmp_path / "log",
        },
    ):
        with pytest.raises(GateClosedError):
            execute_evobind2_run(valid_input, gate_root=gate_root)


def test_execute_evobind2_run_no_subprocess_when_gate_closed(
    valid_input: EvoBind2Input, gate_root: Path, tmp_path: Path
):
    with patch("app.services.compute_wrappers.evobind2_runner.subprocess.Popen") as mock_popen:
        with patch.dict(
            ALLOWED_ROOTS,
            {
                "work": tmp_path / "work",
                "artifact": tmp_path / "artifact",
                "log": tmp_path / "log",
            },
        ):
            with pytest.raises(GateClosedError):
                execute_evobind2_run(valid_input, gate_root=gate_root)
    mock_popen.assert_not_called()


def test_execute_evobind2_run_no_writes_when_gate_closed(
    valid_input: EvoBind2Input, gate_root: Path, tmp_path: Path
):
    work = tmp_path / "work"
    with patch.dict(
        ALLOWED_ROOTS,
        {
            "work": work,
            "artifact": tmp_path / "artifact",
            "log": tmp_path / "log",
        },
    ):
        with pytest.raises(GateClosedError):
            execute_evobind2_run(valid_input, gate_root=gate_root)
    assert not list(work.rglob("*"))


def test_execute_evobind2_run_rejects_invalid_input_before_gate(
    valid_input: EvoBind2Input, gate_root: Path, tmp_path: Path
):
    valid_input.peptide_length = 200
    with patch("app.services.compute_wrappers.evobind2_runner.require_run_gate") as mock_gate:
        with patch.dict(
            ALLOWED_ROOTS,
            {
                "work": tmp_path / "work",
                "artifact": tmp_path / "artifact",
                "log": tmp_path / "log",
            },
        ):
            with pytest.raises(EvoBind2ExecutionError):
                execute_evobind2_run(valid_input, gate_root=gate_root)
    mock_gate.assert_not_called()


def test_execute_evobind2_run_with_open_gate_writes_fasta_and_calls_subprocess(
    valid_input: EvoBind2Input, gate_root: Path, tmp_path: Path
):
    create_run_gate(valid_input.run_id, "op", "test", gate_root=gate_root)
    work = tmp_path / "work"
    log = tmp_path / "log"
    with patch.dict(
        ALLOWED_ROOTS,
        {"work": work, "artifact": tmp_path / "artifact", "log": log},
    ):
        with patch(
            "app.services.compute_wrappers.evobind2_runner.subprocess.Popen"
        ) as mock_popen:
            mock_proc = mock_popen.return_value
            mock_proc.wait.return_value = 0
            result = execute_evobind2_run(valid_input, gate_root=gate_root)

    assert result["status"] == "completed"
    assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    fasta_path = work / valid_input.run_id / "input" / "receptor.fasta"
    assert fasta_path.exists()
    mock_popen.assert_called_once()


# ---------------------------------------------------------------------------
# Dry-run preview remains gate-independent
# ---------------------------------------------------------------------------


def test_preview_run_command_no_gate_check(valid_input: EvoBind2Input):
    preview = preview_run_command(valid_input)
    assert preview["status"] == "READY"
    assert preview["command_preview"]
    assert preview["safety_flags"]["is_scientific_result"] is False


def test_dry_run_plan_blocks_path_traversal_run_id(valid_fasta: str):
    out = dry_run_plan(
        EvoBind2Input(
            run_id="../../etc/passwd",
            receptor_fasta=valid_fasta,
        )
    )
    assert out.status == "BLOCKED"


def test_dry_run_plan_blocks_invalid_fasta(valid_run_id: str):
    out = dry_run_plan(
        EvoBind2Input(
            run_id=valid_run_id,
            receptor_fasta="no header\nMKTAYIAKQR",
        )
    )
    assert out.status == "BLOCKED"


# ---------------------------------------------------------------------------
# Path guards
# ---------------------------------------------------------------------------


def test_build_run_paths_rejects_traversal(valid_fasta: str):
    with pytest.raises(ValueError):
        build_run_paths("../escape")


# ---------------------------------------------------------------------------
# Cleanup / rollback guards
# ---------------------------------------------------------------------------


def test_cleanup_run_artifacts_validates_run_id():
    with pytest.raises(ValueError):
        cleanup_run_artifacts("../../etc")


def test_cleanup_run_artifacts_removes_only_under_allowed_root(
    gate_root: Path, valid_run_id: str, tmp_path: Path
):
    work = tmp_path / "work"
    work.mkdir()
    run_dir = work / valid_run_id
    run_dir.mkdir()
    (run_dir / "keep.txt").write_text("data", encoding="utf-8")

    with patch.dict(ALLOWED_ROOTS, {"work": work}):
        result = cleanup_run_artifacts(valid_run_id)
    assert result["removed"]
    assert not run_dir.exists()


def test_rollback_run_closes_gate_and_cleans(
    gate_root: Path, valid_run_id: str, tmp_path: Path
):
    create_run_gate(valid_run_id, "op", "test", gate_root=gate_root)
    work = tmp_path / "work"
    work.mkdir()
    run_dir = work / valid_run_id
    run_dir.mkdir()

    with patch.dict(ALLOWED_ROOTS, {"work": work}):
        result = rollback_run(valid_run_id, gate_root=gate_root)

    assert result["gate_closed"] is True
    assert result["removed"]
    assert not run_dir.exists()


# ---------------------------------------------------------------------------
# Schema-level guards (integration with wrapper validation)
# ---------------------------------------------------------------------------


def test_dry_run_request_validates_run_id_pattern():
    from app.schemas.evobind2 import EvoBind2DryRunRequest

    with pytest.raises(ValueError):
        EvoBind2DryRunRequest(run_id="bad/run", receptor_fasta=">r\nMKT\n")


def test_dry_run_request_validates_fasta():
    from app.schemas.evobind2 import EvoBind2DryRunRequest

    with pytest.raises(ValueError):
        EvoBind2DryRunRequest(run_id="ok_run", receptor_fasta="no header")


def test_job_submit_request_validates_target_sequence():
    from app.schemas.evobind2 import EvoBind2JobSubmitRequest

    with pytest.raises(ValueError):
        EvoBind2JobSubmitRequest(
            project_id="p1",
            target_sequence="no header\nMKT",
        )


# ---------------------------------------------------------------------------
# Phase 9A predict_only peptide_sequence contract (runner/schema)
# ---------------------------------------------------------------------------


def test_validate_run_input_rejects_missing_peptide_sequence(valid_input: EvoBind2Input):
    valid_input.peptide_sequence = None
    ok, error = validate_run_input(valid_input)
    assert ok is False
    assert "peptide_sequence is required" in error


def test_validate_run_input_rejects_empty_peptide_sequence(valid_input: EvoBind2Input):
    valid_input.peptide_sequence = ""
    ok, error = validate_run_input(valid_input)
    assert ok is False
    assert "peptide_sequence is required" in error


def test_validate_run_input_rejects_invalid_peptide_characters(valid_input: EvoBind2Input):
    valid_input.peptide_sequence = "AAAA123AAA"
    ok, error = validate_run_input(valid_input)
    assert ok is False
    assert "peptide_sequence contains invalid characters" in error


def test_validate_run_input_rejects_peptide_length_mismatch(valid_input: EvoBind2Input):
    valid_input.peptide_sequence = "AAAAAAAAA"  # 9 vs peptide_length=12
    ok, error = validate_run_input(valid_input)
    assert ok is False
    assert "peptide_sequence length" in error


def test_execute_evobind2_run_rejects_missing_peptide_before_gate(
    valid_input: EvoBind2Input, gate_root: Path, tmp_path: Path
):
    """Invalid peptide_sequence must fail before any gate check or filesystem write."""
    valid_input.peptide_sequence = None
    with patch("app.services.compute_wrappers.evobind2_runner.require_run_gate") as mock_gate:
        with patch("app.services.compute_wrappers.evobind2_runner.subprocess.Popen") as mock_popen:
            with patch.dict(
                ALLOWED_ROOTS,
                {
                    "work": tmp_path / "work",
                    "artifact": tmp_path / "artifact",
                    "log": tmp_path / "log",
                },
            ):
                with pytest.raises(EvoBind2ExecutionError):
                    execute_evobind2_run(valid_input, gate_root=gate_root)
    mock_gate.assert_not_called()
    mock_popen.assert_not_called()


def test_execute_evobind2_run_invalid_input_creates_no_directories(
    valid_input: EvoBind2Input, gate_root: Path, tmp_path: Path
):
    """Invalid input must not create run directories."""
    valid_input.peptide_sequence = None
    work = tmp_path / "work"
    with patch("app.services.compute_wrappers.evobind2_runner.require_run_gate") as mock_gate:
        with patch("app.services.compute_wrappers.evobind2_runner.subprocess.Popen") as mock_popen:
            with patch.dict(
                ALLOWED_ROOTS,
                {
                    "work": work,
                    "artifact": tmp_path / "artifact",
                    "log": tmp_path / "log",
                },
            ):
                with pytest.raises(EvoBind2ExecutionError):
                    execute_evobind2_run(valid_input, gate_root=gate_root)
    mock_gate.assert_not_called()
    mock_popen.assert_not_called()
    assert not work.exists() or not list(work.rglob("*"))


def test_preview_run_command_blocks_invalid_peptide_sequence(valid_fasta: str):
    """Preview must block on invalid peptide_sequence without touching gate/subprocess."""
    inp = EvoBind2Input(
        run_id="p9a_preview_001",
        receptor_fasta=valid_fasta,
        peptide_length=10,
        mode="predict_only",
        peptide_sequence="AAAA123AAA",
    )
    preview = preview_run_command(inp)
    assert preview["status"] == "BLOCKED"
    assert "peptide_sequence contains invalid characters" in preview["error_message"]


def test_gate_root_never_falls_back_to_tmp(monkeypatch):
    """Default gate root is /home/xh/kxc/stampup/run_gates/evobind2; /tmp fallbacks are rejected."""
    from app.services.compute_wrappers.evobind2_gate import DEFAULT_GATE_ROOT, GatePathUnsafeError, _get_gate_root

    assert DEFAULT_GATE_ROOT.as_posix() == "/home/xh/kxc/stampup/run_gates/evobind2"
    monkeypatch.setenv("EVOBIND2_GATE_ROOT", "/tmp/evobind2_run_gates")
    with pytest.raises(GatePathUnsafeError):
        _get_gate_root()


def test_dry_run_request_enforces_peptide_sequence_length_match():
    from app.schemas.evobind2 import EvoBind2DryRunRequest

    with pytest.raises(ValueError) as exc_info:
        EvoBind2DryRunRequest(
            run_id="ok_run",
            receptor_fasta=">r\nMKTAYIAKQR",
            peptide_length=10,
            peptide_sequence="AAAAAAAAA",
        )
    assert "peptide_sequence length" in str(exc_info.value)


def test_dry_run_request_rejects_peptide_length_over_50():
    from app.schemas.evobind2 import EvoBind2DryRunRequest

    with pytest.raises(ValueError):
        EvoBind2DryRunRequest(
            run_id="ok_run",
            receptor_fasta=">r\nMKTAYIAKQR",
            peptide_length=51,
            peptide_sequence="A" * 51,
        )
