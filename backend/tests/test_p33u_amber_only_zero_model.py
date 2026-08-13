"""P33U-D4R zero-model tests for the DiffPepBuilder Amber-only additive chain.

Runs with NO checkpoint loading, NO real subprocess, NO GPU, NO 8189 call.
``P33U_BLOCK_ALL_EXECUTION`` is set so the real subprocess path refuses; all
execution tests inject ``MockProcessRunner`` — no real process is spawned.

These tests prove (per P33U-D4R §二.5) that the REAL execution entry
(``contract.execute`` -> ``runner.execute_run`` -> ``contract.command_preview``)
uses ``amber_only_postprocess.py`` and does NOT reference ``run_postprocess.py``,
``--rosetta_relax``, or ``pyrosetta`` — i.e. the binding is not cosmetic on
``command_preview`` alone.

Also asserts:
- The frozen ``runner_contracts.py`` SHA is unchanged (d9ce8ac6...).
- The frozen ``get_contract('diffpepbuilder')`` still returns the original
  ``DiffPepBuilderContract`` (additive registry does not alter the frozen one).
- ``amber_only_postprocess.py`` source contains no forbidden tokens.
- Rosetta ddG stays ``unavailable_with_reason``.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.p33u import config, gate, runner, runner_contracts, state  # noqa: E402
from app.services.p33u.additive_amber_only import (  # noqa: E402
    DiffPepBuilderAmberOnlyContract,
    ROSETTA_DDG_UNAVAILABLE_REASON,
    all_amber_only_contracts,
    get_contract_amber_only,
)

# Zero-model mode for the whole session: real subprocess path must refuse.
os.environ["P33U_BLOCK_ALL_EXECUTION"] = "1"

VALID_SHA = "a" * 64

FROZEN_RUNNER_CONTRACTS_SHA = (
    "d9ce8ac6e0502a9e89840cfee371cfe69237d39b7d33586a285a6bb9c2f74e5b"
)

FORBIDDEN_TOKENS = ("run_postprocess.py", "--rosetta_relax", "pyrosetta")


@pytest.fixture(autouse=True)
def _isolate_gate_and_gpu(tmp_path, monkeypatch):
    """Redirect P33U gate root + GPU lock to tmp_path for every test."""
    monkeypatch.setattr(gate, "GATE_ROOT", str(tmp_path / "gates"))
    monkeypatch.setattr(config, "GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))
    monkeypatch.setattr(runner, "GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))


def _forbidden_in(tokens_or_str) -> list[str]:
    blob = " ".join(tokens_or_str) if isinstance(tokens_or_str, (list, tuple)) else tokens_or_str
    return [t for t in FORBIDDEN_TOKENS if t in blob]


# ===========================================================================
# Frozen-state invariants
# ===========================================================================
def test_frozen_runner_contracts_sha_unchanged():
    """The frozen runner_contracts.py must not have been modified by D4R."""
    p = BACKEND_DIR / "app" / "services" / "p33u" / "runner_contracts.py"
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    assert h == FROZEN_RUNNER_CONTRACTS_SHA, (
        f"frozen runner_contracts.py SHA changed: {h} != {FROZEN_RUNNER_CONTRACTS_SHA}"
    )


def test_frozen_registry_returns_original_diffpepbuilder_contract():
    """The frozen get_contract('diffpepbuilder') still returns the rosetta-step
    contract — the additive Amber-only registry does NOT alter it."""
    c = runner_contracts.get_contract("diffpepbuilder")
    assert type(c).__name__ == "DiffPepBuilderContract"
    # And the Amber-only variant is a distinct class.
    assert type(get_contract_amber_only("diffpepbuilder")).__name__ == (
        "DiffPepBuilderAmberOnlyContract"
    )


# ===========================================================================
# command_preview — step 3 is Amber-only
# ===========================================================================
def test_amber_only_command_preview_step3_uses_amber_only_script():
    c = get_contract_amber_only("diffpepbuilder")
    steps = c.command_preview("r1", "/in", "/out")
    assert len(steps) == 3
    step3 = steps[2]
    assert any("amber_only_postprocess.py" in t for t in step3)
    assert _forbidden_in(step3) == [], f"forbidden tokens in step3: {_forbidden_in(step3)}"


def test_amber_only_command_preview_no_forbidden_tokens_anywhere():
    c = get_contract_amber_only("diffpepbuilder")
    steps = c.command_preview("r1", "/in", "/out")
    flat = sum(steps, [])
    assert _forbidden_in(flat) == [], f"forbidden tokens in command: {_forbidden_in(flat)}"


def test_amber_only_command_preview_steps1_and2_unchanged():
    """Steps 1 (preprocess) and 2 (torchrun inference) must match the frozen
    contract — only step 3 is overridden."""
    frozen = runner_contracts.get_contract("diffpepbuilder")
    amber = get_contract_amber_only("diffpepbuilder")
    f_steps = frozen.command_preview("r1", "/in", "/out")
    a_steps = amber.command_preview("r1", "/in", "/out")
    assert a_steps[0] == f_steps[0]  # preprocess
    assert a_steps[1] == f_steps[1]  # torchrun inference
    assert a_steps[2] != f_steps[2]  # postprocess differs


# ===========================================================================
# REAL execution entry uses the Amber-only script (not just command_preview)
# ===========================================================================
def _diffpepbuilder_input(tmp_path):
    """target.pdb (no '_' in basename) + de_novo_cases.json. Points source at
    a tmp dir so the SSbuilder/SSBLIB precheck is skipped (no SSbuilder dir)."""
    fake_src = tmp_path / "fake_src"
    fake_src.mkdir()
    ind = tmp_path / "in"
    ind.mkdir()
    (ind / "target.pdb").write_text("ATOM  1  CA  ALA A   1     1.0  2.0  3.0\n",
                                    encoding="utf-8")
    (ind / "de_novo_cases.json").write_text('{"cases":[]}', encoding="utf-8")
    return str(ind), str(fake_src)


def test_real_execution_entry_uses_amber_only_script(tmp_path, monkeypatch):
    """contract.execute -> runner.execute_run -> command_preview -> transport.run
    must spawn a command whose step 3 is amber_only_postprocess.py. The mock
    records the exact argv; this proves the binding is real, not cosmetic."""
    in_dir, fake_src = _diffpepbuilder_input(tmp_path)
    # Redirect the contract's source so validate_input skips the SSbuilder check.
    monkeypatch.setitem(config.MODEL_BY_ID["diffpepbuilder"], "source", fake_src)

    c = get_contract_amber_only("diffpepbuilder")
    st = state.P33UState(state_path=str(tmp_path / "state.json"))
    mock = runner.MockProcessRunner(returncode=0, pid=4242)

    out = c.execute(
        run_id="r_amber", input_dir=in_dir, output_dir=str(tmp_path / "out"),
        manifest_sha=VALID_SHA, authorized_manifest_sha=VALID_SHA, state=st,
        process_transport=mock,
        mock_artifacts={
            "runs/inference/postprocess_results.csv": b"design,rosetta_ddg\nACDEFGHIK,unavailable_with_reason\n",
            "runs/inference/case_sample/sample_0.pdb": b"ATOM  1  CA ALA A   1\n",
        },
    )

    # The mock recorded all 3 step commands.
    assert len(mock.calls) == 3, f"expected 3 steps, got {len(mock.calls)}"
    step3_cmd = mock.calls[2]["cmd"]
    step3_blob = " ".join(step3_cmd)
    assert "amber_only_postprocess.py" in step3_blob, (
        f"real execution entry did not use amber_only_postprocess.py; step3={step3_cmd}"
    )
    assert _forbidden_in(step3_blob) == [], (
        f"forbidden tokens in real spawn step3: {_forbidden_in(step3_blob)}"
    )
    # And the run closed cleanly (proves the full execute path exercised).
    assert out.state == gate.CLOSED
    assert out.pid == 4242
    assert st.attempt_count("diffpepbuilder") == 1


def test_real_execution_entry_step3_not_run_postprocess(tmp_path, monkeypatch):
    """Explicit guard: the real spawn step 3 must not be run_postprocess.py."""
    in_dir, fake_src = _diffpepbuilder_input(tmp_path)
    monkeypatch.setitem(config.MODEL_BY_ID["diffpepbuilder"], "source", fake_src)
    c = get_contract_amber_only("diffpepbuilder")
    st = state.P33UState(state_path=str(tmp_path / "state.json"))
    mock = runner.MockProcessRunner(returncode=0)
    c.execute(
        run_id="r_guard", input_dir=in_dir, output_dir=str(tmp_path / "out"),
        manifest_sha=VALID_SHA, authorized_manifest_sha=VALID_SHA, state=st,
        process_transport=mock,
        mock_artifacts={
            "runs/inference/postprocess_results.csv": b"design\nACDEFGHIK\n",
            "runs/inference/case_sample/sample_0.pdb": b"ATOM  1  CA ALA A   1\n",
        },
    )
    step3_blob = " ".join(mock.calls[2]["cmd"])
    assert "run_postprocess.py" not in step3_blob
    assert "--rosetta_relax" not in step3_blob


# ===========================================================================
# amber_only_postprocess.py source — static forbidden-token guard
# ===========================================================================
def _amber_script_path() -> Path:
    src = config.MODEL_BY_ID["diffpepbuilder"]["source"]
    return Path(src) / "experiments" / "amber_only_postprocess.py"


def _is_postprocess_module(name: str) -> bool:
    """True only for analysis.postprocess (the module that imports pyrosetta).
    analysis.postprocess_utils is a DIFFERENT, pyrosetta-free module and is
    intentionally allowed."""
    return name == "analysis.postprocess" or name.startswith("analysis.postprocess.")


def test_amber_only_script_no_pyrosetta_imports():
    """The script must not IMPORT pyrosetta or analysis.postprocess (the latter
    pulls pyrosetta at module top). Checked via AST so docstring/comments that
    mention 'pyrosetta' to document what is NOT imported are fine.
    analysis.postprocess_utils is allowed (pyrosetta-free)."""
    import ast
    p = _amber_script_path()
    assert p.is_file(), f"amber_only_postprocess.py missing at {p}"
    tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                if n.name.startswith("pyrosetta") or _is_postprocess_module(n.name):
                    bad.append(f"import {n.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith("pyrosetta") or _is_postprocess_module(mod):
                bad.append(f"from {mod} import ...")
    assert not bad, f"amber_only_postprocess.py has forbidden imports: {bad}"


def test_amber_only_script_imports_amber_minimize():
    """The script must reuse the openmm-based AmberRelaxation (not pyrosetta)."""
    import ast
    p = _amber_script_path()
    src = p.read_text(encoding="utf-8", errors="replace")
    assert "from analysis.amber_minimize import AmberRelaxation" in src
    # Must NOT import analysis.postprocess (AST check, robust to comments).
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and _is_postprocess_module(node.module or ""):
            pytest.fail("amber_only_postprocess.py imports analysis.postprocess")
        if isinstance(node, ast.Import) and any(
            _is_postprocess_module(n.name) for n in node.names
        ):
            pytest.fail("amber_only_postprocess.py imports analysis.postprocess")


# ===========================================================================
# Rosetta ddG stays unavailable_with_reason
# ===========================================================================
def test_rosetta_ddg_unavailable_with_reason():
    assert "unavailable_with_reason" in ROSETTA_DDG_UNAVAILABLE_REASON
    assert "rosetta" in ROSETTA_DDG_UNAVAILABLE_REASON.lower()


def test_amber_only_registry_only_diffpepbuilder():
    """Only diffpepbuilder has an Amber-only variant; other models are not
    silently swapped."""
    assert set(all_amber_only_contracts()) == {"diffpepbuilder"}
    with pytest.raises(KeyError):
        get_contract_amber_only("pepflow")
