"""Mock tests for EvoBind2 wrapper skeleton (P2N).

No subprocess calls. No server access. Pure unit tests.
"""

from __future__ import annotations

import os

import pytest

from app.services.compute_wrappers.evobind2_wrapper import (
    ALLOWED_MODEL_NAMES,
    BLOCKED_MODEL_NAMES,
    DEFAULT_MODEL_NAME,
    EVOBIND_ENV,
    EVOBIND_ROOT,
    EVOBIND2_ENV_PYTHON,
    HHBLITS_BIN,
    EvoBind2Input,
    build_environment,
    build_mc_design_command,
    build_run_paths,
    dry_run_plan,
    normalize_output_dir,
    validate_model_name,
)


# ---------------------------------------------------------------------------
# Model name validation
# ---------------------------------------------------------------------------


def test_validate_model_1_passes():
    valid, error = validate_model_name("model_1")
    assert valid is True
    assert error is None


def test_validate_model_1_ptm_passes():
    valid, error = validate_model_name("model_1_ptm")
    assert valid is True
    assert error is None


def test_validate_model_1_multimer_v3_blocked():
    valid, error = validate_model_name("model_1_multimer_v3")
    assert valid is False
    assert "mc_design.py/config.py path does not support it" in error


def test_validate_unknown_model_invalid():
    valid, error = validate_model_name("model_99_fantasy")
    assert valid is False
    assert "Invalid model name" in error
    assert "model_99_fantasy" in error


# ---------------------------------------------------------------------------
# normalize_output_dir
# ---------------------------------------------------------------------------


def test_normalize_output_dir_adds_slash():
    assert normalize_output_dir("/some/path/output") == "/some/path/output/"


def test_normalize_output_dir_idempotent():
    assert normalize_output_dir("/some/path/output/") == "/some/path/output/"


def test_normalize_output_dir_strips_multiple():
    assert normalize_output_dir("/some/path/output///") == "/some/path/output/"


# ---------------------------------------------------------------------------
# build_run_paths
# ---------------------------------------------------------------------------


def test_build_run_paths_structure():
    paths = build_run_paths("p2n_test_001")
    # Merged Phase 9A wrapper uses the centralized artifact root from model_paths.
    assert paths["run_dir"].endswith("/artifacts/evobind2/p2n_test_001")
    assert paths["input_dir"].endswith("/artifacts/evobind2/p2n_test_001/input")
    assert paths["output_dir"].endswith("/artifacts/evobind2/p2n_test_001/output/")
    assert paths["logs_dir"].endswith("/artifacts/evobind2/p2n_test_001/logs")
    assert paths["metrics_csv"].endswith("/artifacts/evobind2/p2n_test_001/output/metrics.csv")
    assert paths["pdb"].endswith("/artifacts/evobind2/p2n_test_001/output/unrelaxed_true.pdb")
    assert paths["jax_precheck_log"].endswith("/artifacts/evobind2/p2n_test_001/logs/jax_gpu_precheck.log")


# ---------------------------------------------------------------------------
# build_environment
# ---------------------------------------------------------------------------


def test_build_environment_gpu():
    env = build_environment(selected_gpu=0)
    assert env["CUDA_VISIBLE_DEVICES"] == "0"
    assert env["XLA_PYTHON_CLIENT_PREALLOCATE"] == "false"
    assert env["TF_FORCE_GPU_ALLOW_GROWTH"] == "true"
    assert env["TF_CPP_MIN_LOG_LEVEL"] == "2"
    # Source directory must be on PYTHONPATH for EvoBind2 / AF2 imports.
    assert EVOBIND_ROOT in env["PYTHONPATH"]
    # HHblits binary directory must be on PATH (not the source root).
    assert os.path.dirname(HHBLITS_BIN) in env["PATH"]


def test_build_environment_no_empty_cuda_visible():
    """GPU env must not set CUDA_VISIBLE_DEVICES to empty string."""
    env = build_environment(selected_gpu=0)
    assert env.get("CUDA_VISIBLE_DEVICES") != ""
    assert env.get("CUDA_VISIBLE_DEVICES") != '""'


def test_build_environment_cpu_fallback():
    env = build_environment(selected_gpu=None)
    assert "CUDA_VISIBLE_DEVICES" not in env


# ---------------------------------------------------------------------------
# build_mc_design_command
# ---------------------------------------------------------------------------


def test_build_command_has_model_name():
    inp = EvoBind2Input(
        run_id="test_001",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
        model_name="model_1_ptm",
    )
    paths = build_run_paths("test_001")
    cmd = build_mc_design_command(paths, inp)
    assert any("--model_names=model_1_ptm" in token for token in cmd)


def test_build_command_output_dir_ends_with_slash():
    inp = EvoBind2Input(
        run_id="test_001",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
    )
    paths = build_run_paths("test_001")
    cmd = build_mc_design_command(paths, inp)
    output_token = [t for t in cmd if t.startswith("--output_dir=")][0]
    assert output_token.endswith("/")


def test_build_command_peptide_sequence():
    inp = EvoBind2Input(
        run_id="test_001",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
    )
    paths = build_run_paths("test_001")
    cmd = build_mc_design_command(paths, inp)
    assert any("--peptide_sequence=AAAAAAAAAA" in token for token in cmd)


def test_build_command_predict_only_true():
    inp = EvoBind2Input(
        run_id="test_001",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
        mode="predict_only",
    )
    paths = build_run_paths("test_001")
    cmd = build_mc_design_command(paths, inp)
    assert any("--predict_only=True" in token for token in cmd)


def test_build_command_uses_conda_run():
    inp = EvoBind2Input(
        run_id="test_001",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
    )
    paths = build_run_paths("test_001")
    cmd = build_mc_design_command(paths, inp)
    assert cmd[0] == EVOBIND2_ENV_PYTHON
    assert cmd[1] == f"{EVOBIND_ROOT}/src/mc_design.py"


# ---------------------------------------------------------------------------
# dry_run_plan
# ---------------------------------------------------------------------------


def test_dry_run_model_1_ptm_ready():
    inp = EvoBind2Input(
        run_id="p2n_dry_001",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
        model_name="model_1_ptm",
    )
    out = dry_run_plan(inp)
    assert out.status == "READY"
    assert out.model_name == "model_1_ptm"
    assert out.used_gpu is True
    assert out.selected_gpu == 0
    assert out.artifacts["metrics_csv"] is not None
    assert out.artifacts["pdb"] is not None
    assert out.command_preview is not None
    assert len(out.command_preview) > 0


def test_dry_run_blocked_multimer():
    inp = EvoBind2Input(
        run_id="p2n_dry_002",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
        model_name="model_1_multimer_v3",
    )
    out = dry_run_plan(inp)
    assert out.status == "BLOCKED"
    assert "mc_design.py/config.py path does not support it" in out.error_message


def test_dry_run_blocked_design_mode():
    inp = EvoBind2Input(
        run_id="p2n_dry_003",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
        mode="design",
    )
    out = dry_run_plan(inp)
    assert out.status == "BLOCKED"
    assert "Design mode is not yet supported" in out.error_message


def test_dry_run_safety_flags_default():
    inp = EvoBind2Input(
        run_id="p2n_dry_004",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
    )
    out = dry_run_plan(inp)
    assert out.safety_flags["is_candidate_generation"] is False
    assert out.safety_flags["is_scientific_result"] is False
    assert out.safety_flags["uses_uniref30"] is False


def test_dry_run_auto_gpu_defaults_to_zero():
    inp = EvoBind2Input(
        run_id="p2n_dry_005",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
        selected_gpu="auto",
    )
    out = dry_run_plan(inp)
    assert out.selected_gpu == 0


def test_dry_run_explicit_gpu_one():
    inp = EvoBind2Input(
        run_id="p2n_dry_006",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
        selected_gpu=1,
    )
    out = dry_run_plan(inp)
    assert out.selected_gpu == 1


def test_dry_run_env_preview_contains_key_vars():
    inp = EvoBind2Input(
        run_id="p2n_dry_007",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
    )
    out = dry_run_plan(inp)
    assert out.env_preview["XLA_PYTHON_CLIENT_PREALLOCATE"] == "false"
    assert "CUDA_VISIBLE_DEVICES" in out.env_preview


# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------


def test_default_model_is_model_1_ptm():
    assert DEFAULT_MODEL_NAME == "model_1_ptm"


def test_allowed_models():
    assert ALLOWED_MODEL_NAMES == {"model_1", "model_1_ptm"}


def test_blocked_models():
    assert BLOCKED_MODEL_NAMES == {"model_1_multimer_v3"}


# ---------------------------------------------------------------------------
# Phase 9A predict_only peptide_sequence contract
# ---------------------------------------------------------------------------


def test_dry_run_predict_only_requires_peptide_sequence():
    inp = EvoBind2Input(
        run_id="p9a_seq_001",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_length=10,
        mode="predict_only",
    )
    out = dry_run_plan(inp)
    assert out.status == "BLOCKED"
    assert "peptide_sequence is required" in out.error_message


def test_dry_run_predict_only_rejects_empty_peptide_sequence():
    inp = EvoBind2Input(
        run_id="p9a_seq_002",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_length=10,
        mode="predict_only",
        peptide_sequence="",
    )
    out = dry_run_plan(inp)
    assert out.status == "BLOCKED"
    assert "peptide_sequence is required" in out.error_message


def test_dry_run_predict_only_rejects_invalid_peptide_characters():
    inp = EvoBind2Input(
        run_id="p9a_seq_003",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_length=10,
        mode="predict_only",
        peptide_sequence="AAAAAAA123",
    )
    out = dry_run_plan(inp)
    assert out.status == "BLOCKED"
    assert "peptide_sequence contains invalid characters" in out.error_message


def test_dry_run_predict_only_rejects_length_mismatch():
    inp = EvoBind2Input(
        run_id="p9a_seq_004",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_length=10,
        mode="predict_only",
        peptide_sequence="AAAAAAAAA",  # 9 residues
    )
    out = dry_run_plan(inp)
    assert out.status == "BLOCKED"
    assert "peptide_sequence length" in out.error_message


def test_dry_run_predict_only_rejects_peptide_length_over_50():
    inp = EvoBind2Input(
        run_id="p9a_seq_005",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_length=51,
        mode="predict_only",
        peptide_sequence="A" * 51,
    )
    out = dry_run_plan(inp)
    assert out.status == "BLOCKED"
    assert "peptide_length" in out.error_message


def test_dry_run_predict_only_valid_sequence_in_command_preview():
    inp = EvoBind2Input(
        run_id="p9a_seq_006",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_length=10,
        mode="predict_only",
        peptide_sequence="MKTAAYIAKQ",
    )
    out = dry_run_plan(inp)
    assert out.status == "READY"
    assert out.command_preview is not None
    assert any("--peptide_sequence=MKTAAYIAKQ" in token for token in out.command_preview)


def test_build_environment_sets_tmpdir_and_home():
    env = build_environment(selected_gpu=0)
    assert env["TMPDIR"] == "/home/xh/kxc/stampup/cache/tmp"
    assert env["HOME"] == "/home/xh/kxc/stampup/cache/tmp"
