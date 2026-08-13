"""P33U zero-model validation tests (V2 — executable runner closure).

These tests run with NO checkpoint loading, NO real job creation, NO GPU
access, and NO real call to the ESMFold 8189 service. P33U_BLOCK_ALL_EXECUTION
is set at import so the real subprocess path refuses. All execution tests
inject MockProcessRunner — no real process is ever spawned.

Covers:
- config registry, path contracts, independent state lineage
- runner command previews (PepHAR flag removal, PepFlow model2/full steps,
  DiffPepBuilder 3-step, no shell=True / no string-concat)
- gate lifecycle: open -> update_pid -> close (CLOSED/FAILED/TIMEOUT)
- execute_run: SHA mismatch refused, retry refused, input precheck refused,
  execution lock blocks real path, timeout -> FAILED/TIMEOUT, non-zero exit
  -> FAILED, empty artifacts -> FAILED, success -> CLOSED + provenance
- retry_count structurally 0 (second call refused)
- output parsers: fixed-fixture parse + empty-output guard
- P33L state cannot be loaded by P33U (lineage isolation)
- static: no torch/cuda/requests/subprocess-at-module-level imports
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.p33u import config, gate, output_parsers, paths, runner, runner_contracts, state  # noqa: E402

# Zero-model mode for the whole session: real subprocess path must refuse.
os.environ["P33U_BLOCK_ALL_EXECUTION"] = "1"

VALID_SHA = "a" * 64
OTHER_SHA = "b" * 64


@pytest.fixture(autouse=True)
def _isolate_gate_and_gpu(tmp_path, monkeypatch):
    """Redirect P33U gate root + GPU lock to tmp_path for EVERY test so no test
    ever writes a real gate.json or lock under /home/xh/kxc/stampup/run_gates/."""
    monkeypatch.setattr(gate, "GATE_ROOT", str(tmp_path / "gates"))
    monkeypatch.setattr(config, "GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))
    monkeypatch.setattr(runner, "GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))


# ===========================================================================
# Config registry
# ===========================================================================
def test_lane_d_min_scope_exactly_four_models_in_order():
    assert config.lane_d_min_model_ids() == ["pepmlm", "diffpepbuilder", "pepflow", "pephar"]


def test_excluded_models_documented():
    for m in ("evobind2", "ppflow", "mic", "iptm"):
        assert m in config.EXCLUDED_MODELS


def test_pephar_checkpoint_paths_corrected_not_logs():
    m = config.MODEL_BY_ID["pephar"]
    assert "/logs/" not in m["density_checkpoint"]
    assert "/logs/" not in m["prediction_checkpoint"]
    assert m["density_checkpoint"].endswith("1400.pt")
    assert m["prediction_checkpoint"].endswith("2400.pt")
    assert m["density_checkpoint_sha256"] == "06b9a2701a9594158de2650d10da756c51dda3cc410ea98c47cf9fd1dbc32d15"
    assert m["prediction_checkpoint_sha256"] == "94eb9933312a4c851e3a6dae44f2435dcfc417648d271ca75e8c22bebc1523f6"


def test_pepflow_uses_model2_not_model1():
    m = config.MODEL_BY_ID["pepflow"]
    assert m["checkpoint"].endswith("model2.pt")


# ===========================================================================
# Path contracts
# ===========================================================================
def test_run_id_prefix_is_p33u_not_p33l():
    assert paths.new_run_id("pephar").startswith("p33u_pephar_")
    assert not paths.new_run_id("pephar").startswith("p33l_")


def test_gate_path_under_p33u_lane_d_root():
    assert paths.gate_path("pepflow", "p33u_pepflow_abc").startswith(
        "/home/xh/kxc/stampup/run_gates/p33u_lane_d/pepflow/")


def test_artifact_dir_under_p33u_lane_d():
    assert "/artifacts/p33u_lane_d/pepmlm/p33u_pepmlm_xyz" in paths.artifact_dir("pepmlm", "p33u_pepmlm_xyz")


# ===========================================================================
# Independent state
# ===========================================================================
def test_state_lineage_marker_present(tmp_path):
    s = state.P33UState(state_path=str(tmp_path / "state.json"))
    assert s.lineage() == config.LINEAGE
    assert s.get_attempts("pepmlm") == []
    assert s.attempt_count("pepmlm") == 0


def test_state_refuses_foreign_lineage(tmp_path):
    sp = tmp_path / "state.json"
    sp.write_text(json.dumps({"lineage": "SOMETHING_ELSE", "models": {}}), encoding="utf-8")
    s = state.P33UState(state_path=str(sp))
    assert s.lineage() == config.LINEAGE
    assert s.get_attempts("pepmlm") == []


def test_p33l_state_directory_not_loadable_by_p33u(tmp_path):
    """P33U state loader must refuse a P33L-shaped state file (different lineage)."""
    p33l_like = tmp_path / "p33l_state.json"
    p33l_like.write_text(json.dumps({
        "models": {"evobind2": {"attempts": [{"job_id": "p33l_evobind2_x", "status": "failed"}]},
                   "pepmlm": {"attempts": [{"job_id": "p33l_pepmlm_x", "status": "succeeded"}]}}
    }), encoding="utf-8")
    s = state.P33UState(state_path=str(p33l_like))
    # P33L has no lineage marker -> P33U treats as empty, does NOT inherit.
    assert s.attempt_count("pepmlm") == 0
    assert s.attempt_count("evobind2") == 0


# ===========================================================================
# Gate lifecycle
# ===========================================================================
def test_gate_open_update_close(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "GATE_ROOT", str(tmp_path / "gates"))
    gs = gate.open_gate("pepmlm", "p33u_pepmlm_g1", manifest_sha=VALID_SHA, ttl_seconds=60)
    assert gs.state == gate.OPEN
    assert gs.manifest_sha == VALID_SHA
    gate.update_pid("pepmlm", "p33u_pepmlm_g1", 12345)
    gs2 = gate.read_gate("pepmlm", "p33u_pepmlm_g1")
    assert gs2.pid == 12345
    gate.close_gate("pepmlm", "p33u_pepmlm_g1", gate.CLOSED, exit_code=0, note="ok")
    gs3 = gate.read_gate("pepmlm", "p33u_pepmlm_g1")
    assert gs3.state == gate.CLOSED
    assert gs3.exit_code == 0


def test_gate_open_requires_manifest_sha(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "GATE_ROOT", str(tmp_path / "gates"))
    with pytest.raises(ValueError):
        gate.open_gate("pepmlm", "p33u_pepmlm_g2", manifest_sha="")


def test_gate_timeout_state_preserves_scene(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "GATE_ROOT", str(tmp_path / "gates"))
    gate.open_gate("pepflow", "p33u_pepflow_t1", manifest_sha=VALID_SHA)
    gate.update_pid("pepflow", "p33u_pepflow_t1", 555)
    gate.close_gate("pepflow", "p33u_pepflow_t1", gate.TIMEOUT, exit_code=None,
                    note="subprocess timeout")
    gs = gate.read_gate("pepflow", "p33u_pepflow_t1")
    assert gs.state == gate.TIMEOUT
    assert gs.pid == 555
    assert "timeout" in gs.note
    # gate file preserved (not deleted)
    assert gate.read_gate("pepflow", "p33u_pepflow_t1") is not None


# ===========================================================================
# Command preview correctness (no shell=True, list argv)
# ===========================================================================
def test_all_command_previews_are_list_of_list_of_str():
    for mid in config.lane_d_min_model_ids():
        c = runner_contracts.get_contract(mid)
        groups = c.command_preview("rid", "/in", "/out")
        assert isinstance(groups, list)
        for step in groups:
            assert isinstance(step, list)
            assert all(isinstance(t, str) for t in step)
            assert len(step) > 0


def test_pephar_command_preview_has_no_removed_flags():
    c = runner_contracts.get_contract("pephar")
    flat = " ".join(c.command_preview("r", "/in", "/out")[0])
    for bad in ("--rec-length", "--pep-length", "--qry-length"):
        assert bad not in flat
    assert "--density_param_path" in flat
    assert "--prediction_param_path" in flat


def test_pepflow_command_preview_uses_model2_and_full_steps():
    c = runner_contracts.get_contract("pepflow")
    cmd = c.command_preview("r", "/in", "/out")[0]
    assert "model2.pt" in " ".join(cmd)
    idx = cmd.index("--num_steps")
    assert cmd[idx + 1] == "200"


def test_diffpepbuilder_command_preview_three_steps_no_dummy():
    c = runner_contracts.get_contract("diffpepbuilder")
    steps = c.command_preview("r", "/in", "/out")
    assert len(steps) == 3
    assert "torchrun" in steps[1][0]
    assert "dummy" not in " ".join(sum(steps, [])).lower()


# ===========================================================================
# execute_run — refusals
# ===========================================================================
def _pepmlm_input(tmp_path):
    ind = tmp_path / "in"
    ind.mkdir(exist_ok=True)
    (ind / "target.fasta").write_text(">rec\nMKTAYIAKQR\n", encoding="utf-8")
    return str(ind)


def test_execute_refuses_on_empty_authorized_sha(tmp_path):
    c = runner_contracts.get_contract("pepmlm")
    st = state.P33UState(state_path=str(tmp_path / "state.json"))
    with pytest.raises(runner.ExecutionRefused):
        c.execute(run_id="r1", input_dir=_pepmlm_input(tmp_path),
                  output_dir=str(tmp_path / "out"), manifest_sha=VALID_SHA,
                  authorized_manifest_sha="", state=st,
                  process_transport=runner.MockProcessRunner())


def test_execute_refuses_on_sha_mismatch(tmp_path):
    c = runner_contracts.get_contract("pepmlm")
    st = state.P33UState(state_path=str(tmp_path / "state.json"))
    with pytest.raises(runner.ExecutionRefused, match="SHA mismatch"):
        c.execute(run_id="r1", input_dir=_pepmlm_input(tmp_path),
                  output_dir=str(tmp_path / "out"), manifest_sha=VALID_SHA,
                  authorized_manifest_sha=OTHER_SHA, state=st,
                  process_transport=runner.MockProcessRunner())


def test_execute_refuses_on_invalid_input(tmp_path):
    c = runner_contracts.get_contract("pepmlm")
    st = state.P33UState(state_path=str(tmp_path / "state.json"))
    # empty input dir -> validate_input fails
    empty_in = tmp_path / "empty_in"
    empty_in.mkdir()
    with pytest.raises(runner.ExecutionRefused, match="precheck"):
        c.execute(run_id="r1", input_dir=str(empty_in),
                  output_dir=str(tmp_path / "out"), manifest_sha=VALID_SHA,
                  authorized_manifest_sha=VALID_SHA, state=st,
                  process_transport=runner.MockProcessRunner())


def test_execute_refuses_retry_second_call(tmp_path):
    """retry_count = 0: after one recorded attempt, second execute is refused."""
    c = runner_contracts.get_contract("pepmlm")
    sp = tmp_path / "state.json"
    st = state.P33UState(state_path=str(sp))
    out = tmp_path / "out"
    mock = runner.MockProcessRunner(returncode=0)
    # success path with mock artifacts so it doesn't fail on empty output
    c.execute(run_id="r1", input_dir=_pepmlm_input(tmp_path), output_dir=str(out),
              manifest_sha=VALID_SHA, authorized_manifest_sha=VALID_SHA, state=st,
              process_transport=mock,
              mock_artifacts={"candidate_sequences.csv": b"sequence\nACDEFGHIK\n"})
    assert st.attempt_count("pepmlm") == 1
    with pytest.raises(runner.ExecutionRefused, match="retry"):
        c.execute(run_id="r2", input_dir=_pepmlm_input(tmp_path), output_dir=str(out),
                  manifest_sha=VALID_SHA, authorized_manifest_sha=VALID_SHA, state=st,
                  process_transport=mock)


# ===========================================================================
# execute_run — real subprocess path blocked by env
# ===========================================================================
def test_real_subprocess_transport_refuses_under_block_env():
    """P33U_BLOCK_ALL_EXECUTION is set at import; real transport must refuse."""
    transport = runner.RealSubprocessTransport()
    with pytest.raises(runner.ExecutionBlocked):
        transport.run(["echo", "hi"], cwd="/tmp", env={}, timeout=5,
                      log_path="/tmp/p33u_block_test.log")


def test_execute_real_path_blocked_preserves_gate_scene(tmp_path, monkeypatch):
    """When no transport is injected (real path) + block env set, execute_run
    must close the gate FAILED and preserve the scene — not silently drop it."""
    monkeypatch.setattr(gate, "GATE_ROOT", str(tmp_path / "gates"))
    monkeypatch.setattr(config, "GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))
    monkeypatch.setattr(runner, "GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))
    c = runner_contracts.get_contract("pepmlm")
    st = state.P33UState(state_path=str(tmp_path / "state.json"))
    with pytest.raises(runner.ExecutionBlocked):
        c.execute(run_id="r_block", input_dir=_pepmlm_input(tmp_path),
                  output_dir=str(tmp_path / "out"), manifest_sha=VALID_SHA,
                  authorized_manifest_sha=VALID_SHA, state=st)  # no transport -> real
    # gate preserved as FAILED
    gs = gate.read_gate("pepmlm", "r_block")
    assert gs is not None
    assert gs.state == gate.FAILED
    assert "blocked" in gs.note
    # attempt recorded as failed
    assert st.attempt_count("pepmlm") == 1


# ===========================================================================
# execute_run — outcomes
# ===========================================================================
def test_execute_timeout_closes_gate_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "GATE_ROOT", str(tmp_path / "gates"))
    monkeypatch.setattr(config, "GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))
    monkeypatch.setattr(runner, "GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))
    c = runner_contracts.get_contract("pepmlm")
    st = state.P33UState(state_path=str(tmp_path / "state.json"))
    mock = runner.MockProcessRunner(returncode=None, timed_out=True, pid=777)
    out = c.execute(run_id="r_to", input_dir=_pepmlm_input(tmp_path),
                    output_dir=str(tmp_path / "out"), manifest_sha=VALID_SHA,
                    authorized_manifest_sha=VALID_SHA, state=st,
                    process_transport=mock)
    assert out.state == gate.TIMEOUT
    assert out.pid == 777
    gs = gate.read_gate("pepmlm", "r_to")
    assert gs.state == gate.TIMEOUT
    assert st.attempt_count("pepmlm") == 1


def test_execute_nonzero_exit_closes_gate_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "GATE_ROOT", str(tmp_path / "gates"))
    monkeypatch.setattr(config, "GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))
    monkeypatch.setattr(runner, "GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))
    c = runner_contracts.get_contract("pepmlm")
    st = state.P33UState(state_path=str(tmp_path / "state.json"))
    mock = runner.MockProcessRunner(returncode=2)
    out = c.execute(run_id="r_nz", input_dir=_pepmlm_input(tmp_path),
                    output_dir=str(tmp_path / "out"), manifest_sha=VALID_SHA,
                    authorized_manifest_sha=VALID_SHA, state=st,
                    process_transport=mock)
    assert out.state == gate.FAILED
    assert out.exit_code == 2
    assert gate.read_gate("pepmlm", "r_nz").state == gate.FAILED


def test_execute_empty_artifacts_closes_gate_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "GATE_ROOT", str(tmp_path / "gates"))
    monkeypatch.setattr(config, "GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))
    monkeypatch.setattr(runner, "GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))
    c = runner_contracts.get_contract("pepmlm")
    st = state.P33UState(state_path=str(tmp_path / "state.json"))
    mock = runner.MockProcessRunner(returncode=0)
    # no mock_artifacts -> parser sees empty output_dir -> FAILED
    out = c.execute(run_id="r_empty", input_dir=_pepmlm_input(tmp_path),
                    output_dir=str(tmp_path / "out"), manifest_sha=VALID_SHA,
                    authorized_manifest_sha=VALID_SHA, state=st,
                    process_transport=mock)
    assert out.state == gate.FAILED
    assert "empty" in out.note
    assert gate.read_gate("pepmlm", "r_empty").state == gate.FAILED


def test_execute_success_closes_gate_closed_writes_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "GATE_ROOT", str(tmp_path / "gates"))
    monkeypatch.setattr(config, "GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))
    monkeypatch.setattr(runner, "GPU_LOCK_PATH", str(tmp_path / "gpu.lock"))
    c = runner_contracts.get_contract("pepmlm")
    st = state.P33UState(state_path=str(tmp_path / "state.json"))
    mock = runner.MockProcessRunner(returncode=0, pid=4242)
    out_dir = tmp_path / "out"
    out = c.execute(run_id="r_ok", input_dir=_pepmlm_input(tmp_path),
                    output_dir=str(out_dir), manifest_sha=VALID_SHA,
                    authorized_manifest_sha=VALID_SHA, state=st,
                    process_transport=mock,
                    mock_artifacts={"candidate_sequences.csv": b"sequence,score\nACDEFGHIK,0.9\n"})
    assert out.state == gate.CLOSED
    assert out.exit_code == 0
    assert out.pid == 4242
    assert gate.read_gate("pepmlm", "r_ok").state == gate.CLOSED
    # provenance written + tagged
    prov = json.loads((out_dir / "provenance.json").read_text(encoding="utf-8"))
    assert prov["manifest_sha"] == VALID_SHA
    assert prov["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert prov["pid"] == 4242
    assert st.attempt_count("pepmlm") == 1


# ===========================================================================
# Output parsers — fixed fixtures (no real model output)
# ===========================================================================
def test_parse_pepmlm_fixed_fixture(tmp_path):
    (tmp_path / "candidate_sequences.csv").write_text(
        "sequence,score\nACDEFGHIK,0.91\nGHIKLMNPQ,0.88\n", encoding="utf-8")
    p = output_parsers.parse_pepmlm(str(tmp_path))
    assert not p.empty
    assert p.candidates == ["ACDEFGHIK", "GHIKLMNPQ"]
    assert p.metrics.get("score") == 0.91


def test_parse_pepmlm_empty_dir(tmp_path):
    p = output_parsers.parse_pepmlm(str(tmp_path))
    assert p.empty
    assert p.candidates == []


def test_parse_pephar_fixed_fixture(tmp_path):
    case_dir = tmp_path / "caseA"
    case_dir.mkdir()
    (case_dir / "gen_0.pdb").write_text("ATOM", encoding="utf-8")
    (case_dir / "gt.pdb").write_text("ATOM", encoding="utf-8")
    (tmp_path / "test.csv").write_text("rmsd,recovery\n1.2,0.5\n", encoding="utf-8")
    p = output_parsers.parse_pephar(str(tmp_path))
    assert not p.empty
    assert any("gen_0.pdb" in x for x in p.pdbs)
    assert p.metrics.get("rmsd") == 1.2


def test_parse_pepflow_fixed_fixture(tmp_path):
    (tmp_path / "outputs.csv").write_text("tran,rot,aar,len\n0.1,0.2,0.3,12\n", encoding="utf-8")
    od = tmp_path / "outputs"
    od.mkdir()
    (od / "0.pt").write_bytes(b"\x00\x01")
    p = output_parsers.parse_pepflow(str(tmp_path))
    assert not p.empty
    assert p.metrics.get("aar") == 0.3


def test_parse_diffpepbuilder_fixed_fixture(tmp_path):
    inf = tmp_path / "runs" / "inference"
    inf.mkdir(parents=True)
    (inf / "postprocess_results.csv").write_text(
        "sequence,ddG\nACDEFGHIK,-5.2\n", encoding="utf-8")
    case = inf / "case1"
    case.mkdir()
    (case / "sample_0.pdb").write_text("ATOM", encoding="utf-8")
    p = output_parsers.parse_diffpepbuilder(str(tmp_path))
    assert not p.empty
    assert "ACDEFGHIK" in p.candidates
    assert p.pdbs


def test_parse_output_dispatch():
    for mid in config.lane_d_min_model_ids():
        # ensure dispatcher has a parser for each model
        d = output_parsers.parse_output(mid, "/nonexistent_dir")
        assert d["model_id"] == mid
        assert d["empty"] is True


# ===========================================================================
# Scorer contracts (mock-only ESMFold, PRODIGY, MM-GBSA, MIC/ipTM blocked)
# ===========================================================================
def test_esmfold_no_transport_returns_unavailable_no_call():
    r = runner_contracts  # noqa: F841 (placeholder; scorer tests below)
    from app.services.p33u import scorer_contracts as sc
    out = sc.ESMFoldHTTPScorer().score("ACDEFGHIK", "/tmp/p33u_unused")
    assert out.status == sc.STATUS_UNAVAILABLE
    assert "8189" in out.detail.get("endpoint", "")


def test_esmfold_mock_transport_returns_canned_plddt():
    from app.services.p33u import scorer_contracts as sc
    mock = sc.MockTransport(mean_plddt=82.5)
    out = sc.ESMFoldHTTPScorer().score("ACDEFGHIK", "/tmp/p33u_unused", transport=mock)
    assert out.status == sc.STATUS_OK and out.value == 82.5
    assert len(mock.calls) == 1


def test_prodigy_rejects_single_chain(tmp_path):
    from app.services.p33u import scorer_contracts as sc
    pdb = tmp_path / "single.pdb"
    pdb.write_text(
        "ATOM      1  CA  ALA A   1      1.0  2.0  3.0  1.00 20.00           C\n"
        "ATOM      2  CA  GLY A   2      1.0  2.0  3.0  1.00 20.00           C\n",
        encoding="utf-8")
    v = sc.validate_prodigy_complex_pdb(str(pdb))
    assert not v.valid


def test_mmgbsa_rejects_missing_assets(tmp_path):
    from app.services.p33u import scorer_contracts as sc
    v = sc.validate_mmgbsa_topology_trajectory(str(tmp_path / "x.prmtop"), str(tmp_path / "x.nc"))
    assert not v.valid


def test_mic_and_iptm_blocked_no_value():
    from app.services.p33u import scorer_contracts as sc
    assert sc.score_mic().status == sc.STATUS_UNAVAILABLE and sc.score_mic().value is None
    assert sc.score_iptm().status == sc.STATUS_UNAVAILABLE and sc.score_iptm().value is None


# ===========================================================================
# Static boundary checks
# ===========================================================================
def _module_level_imports(module) -> set[str]:
    """Return the set of module-level import names (ast-based, ignores
    docstrings and local imports inside functions)."""
    import ast
    tree = ast.parse(_src_of(module))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for n in node.names:
                names.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def _src_of(module) -> str:
    import inspect
    return inspect.getsource(module)


def _has_shell_true_call(module) -> bool:
    """True if any subprocess.Popen/call/run invocation uses shell=True."""
    import ast
    tree = ast.parse(_src_of(module))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) \
                        and kw.value.value is True:
                    return True
    return False


def test_no_subprocess_import_at_module_level_in_runner_contracts():
    # runner_contracts must not import subprocess at module level (it delegates
    # to runner, which imports subprocess only inside the real transport).
    assert "subprocess" not in _module_level_imports(runner_contracts)


def test_no_torch_cuda_requests_at_module_level_in_runner():
    mods = _module_level_imports(runner)
    for bad in ("torch", "cuda", "requests"):
        assert bad not in mods, f"runner imports {bad} at module level"
    # shell=True must never appear as an actual call keyword.
    assert not _has_shell_true_call(runner)


def test_no_torch_cuda_requests_at_module_level_in_parsers():
    mods = _module_level_imports(output_parsers)
    for bad in ("torch", "cuda", "requests", "subprocess"):
        assert bad not in mods, f"output_parsers imports {bad} at module level"


def test_execute_stub_no_longer_notimplemented():
    """D0 replaces the C2 NotImplementedError stub with a real implementation."""
    import inspect
    src = inspect.getsource(runner_contracts.RunnerContract.execute)
    assert "NotImplementedError" not in src
    assert "execute_run" in src
