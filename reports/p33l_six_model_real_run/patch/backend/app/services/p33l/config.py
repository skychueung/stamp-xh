import os
import re
import shutil
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class ModelConfig:
    """Static configuration for one P33L model.

    All paths are frozen to /home/xh/kxc/stampup or /mnt/sdb/kxc/stamp_models.
    SHA256 values were computed from the server on 2026-06-29.
    """

    model_id: str
    display_name: str
    order: int
    source_path: str
    source_sha256: str
    checkpoint_path: str
    checkpoint_sha256: str
    fixture_path: str
    fixture_sha256: str
    env_python: str
    runner_script_path: str
    runner_script_sha256: str
    command_args: Callable[[Dict[str, Any]], List[str]]
    timeout_seconds: int
    disk_quota_bytes: int
    max_output_files: int
    output_files: List[str]


def _pepmlm_command(ctx: Dict[str, Any]) -> List[str]:
    run_dir = ctx["run_dir"]
    fixture_path = ctx["fixture_path"]
    target_sequence = ""
    with open(fixture_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith(">"):
                continue
            target_sequence += line
    output_dir = os.path.join(run_dir, "output")
    cfg = ctx["config"]
    return [
        cfg.env_python,
        cfg.source_path,
        "--model_path",
        cfg.checkpoint_path,
        "--target_sequence",
        target_sequence,
        "--peptide_length",
        "9",
        "--num_candidates",
        "3",
        "--device",
        "cuda",
        "--output_dir",
        output_dir,
    ]


def _evobind2_command(ctx: Dict[str, Any]) -> List[str]:
    run_dir = ctx["run_dir"]
    output_dir = os.path.join(run_dir, "output")
    cfg = ctx["config"]
    return [
        cfg.env_python,
        cfg.source_path,
        "--receptor_fasta_path",
        os.path.join(run_dir, "input", "receptor.fasta"),
        "--peptide_length",
        "9",
        "--output_dir",
        output_dir,
        "--model_names",
        "model_1",
        "--data_dir",
        "/home/xh/kxc/stampup/models_dev/evobind2/cache/af2_data_dir",
        "--max_recycles",
        "1",
        "--num_iterations",
        "1",
        "--predict_only=True",
    ]


def _diffpepbuilder_command(ctx: Dict[str, Any]) -> List[str]:
    run_dir = ctx["run_dir"]
    gate_path = ctx["gate_path"]
    output_dir = os.path.join(run_dir, "output")
    cfg = ctx["config"]
    return [
        cfg.env_python,
        cfg.runner_script_path,
        "--target_pdb",
        os.path.join(run_dir, "input", "target.pdb"),
        "--output_dir",
        output_dir,
        "--num_candidates",
        "3",
        "--gate-file",
        gate_path,
    ]


def _pepflow_command(ctx: Dict[str, Any]) -> List[str]:
    run_dir = ctx["run_dir"]
    cfg = ctx["config"]
    source_dir = os.path.dirname(cfg.source_path)
    output_dir = os.path.join(run_dir, "output")
    return [
        cfg.env_python,
        cfg.source_path,
        "--config",
        os.path.join(source_dir, "configs", "learn_angle.yaml"),
        "--ckpt",
        cfg.checkpoint_path,
        "--receptor",
        os.path.join(run_dir, "input", "receptor.pdb"),
        "--output",
        output_dir,
        "--num_samples",
        "3",
        "--num_steps",
        "5",
        "--device",
        "cuda",
    ]


def _pephar_command(ctx: Dict[str, Any]) -> List[str]:
    run_dir = ctx["run_dir"]
    gate_path = ctx["gate_path"]
    cfg = ctx["config"]
    output_dir = os.path.join(run_dir, "output")
    variant = ctx.get("model_variant", "prediction")
    if variant == "density":
        checkpoint = os.path.join(
            cfg.source_path,
            "logs",
            "density_v4_x5o2_2024_09_08__11_25_36",
            "checkpoints",
            "1400.pt",
        )
        config = os.path.join(cfg.source_path, "configs", "density_v4_x5o2.yml")
    else:
        checkpoint = os.path.join(
            cfg.source_path,
            "logs",
            "prediction_d2_x2o1_2024_09_08__11_21_33",
            "checkpoints",
            "2400.pt",
        )
        config = os.path.join(cfg.source_path, "configs", "prediction_d2_x2o1.yml")
    return [
        cfg.env_python,
        cfg.runner_script_path,
        "--model-variant",
        variant,
        "--checkpoint",
        checkpoint,
        "--config",
        config,
        "--gate-file",
        gate_path,
        "--output-dir",
        output_dir,
        "--rec-length",
        "30",
        "--pep-length",
        "10",
        "--qry-length",
        "5",
        "--seed",
        "2024",
    ]


def _ppflow_command(ctx: Dict[str, Any]) -> List[str]:
    run_dir = ctx["run_dir"]
    cfg = ctx["config"]
    source_dir = os.path.dirname(cfg.source_path)
    output_dir = os.path.join(run_dir, "output")
    return [
        cfg.env_python,
        cfg.source_path,
        "--index",
        "0",
        "-c",
        os.path.join(source_dir, "configs", "test", "codesign_ppflow.yml"),
        "-o",
        output_dir,
        "-t",
        "p33l",
        "-d",
        "cuda",
        "-b",
        "1",
        "-ckpt",
        cfg.checkpoint_path,
    ]


MODEL_CONFIGS: List[ModelConfig] = [
    ModelConfig(
        model_id="pepmlm",
        display_name="PepMLM",
        order=1,
        source_path="/home/xh/kxc/stampup/models_dev/pepmlm/scripts/pepmlm_infer.py",
        source_sha256="3805fd68bbce940f6318ec460633157b73670195915a490b205ed8e8591d988b",
        checkpoint_path="/home/xh/kxc/stampup/models_dev/pepmlm/ChatterjeeLab_PepMLM-650M",
        checkpoint_sha256="e80587d2ac4a3fb84f2be2cd4f4d02d5f2127cafc75144108ba349d4796c3668",
        fixture_path="/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/artifacts/pepmlm/ac90e622-492d-4697-a8fa-ce35b2d2bfc5/input/target.fasta",
        fixture_sha256="7cd0f2cd0a30f231b286c49f64f4deff6428b258f59e2cc027ea41cae0fccc42",
        env_python="/home/xh/kxc/stampup/tools/envs/pepmlm/bin/python",
        runner_script_path="",
        runner_script_sha256="",
        command_args=_pepmlm_command,
        timeout_seconds=3600,
        disk_quota_bytes=10 * 1024 * 1024 * 1024,
        max_output_files=1000,
        output_files=["candidate_sequences.csv", "candidate_sequences.json"],
    ),
    ModelConfig(
        model_id="evobind2",
        display_name="EvoBind2",
        order=2,
        source_path="/home/xh/kxc/stampup/models_dev/evobind2/source/EvoBind/src/mc_design.py",
        source_sha256="9833d00263f652755b073628d06b9f9d0370703a44b1d2f1f75c1e08bc74d121",
        checkpoint_path="/home/xh/kxc/stampup/stamp-small-change-model/models/evobind2/cache/af2_params/params_model_1.npz",
        checkpoint_sha256="f95e453e6a290ddf317ba1c9698d53fa110cf007ea979b0eae43e6ad38b4e364",
        fixture_path="/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/artifacts/evobind2/b8ab6d11-5762-4bdf-a9db-6d30602637fd/input/receptor.fasta",
        fixture_sha256="faba901952b6ddca4d9a09c5ba5fa60de315ba0ea8889e0198531a96d3b76473",
        env_python="/home/xh/kxc/stampup/stamp-small-change-model/models/evobind2/envs/evobind/bin/python",
        runner_script_path="",
        runner_script_sha256="",
        command_args=_evobind2_command,
        timeout_seconds=7200,
        disk_quota_bytes=10 * 1024 * 1024 * 1024,
        max_output_files=1000,
        output_files=["designed_peptides.json", "scores.csv"],
    ),
    ModelConfig(
        model_id="diffpepbuilder",
        display_name="DiffPepBuilder",
        order=3,
        source_path="/mnt/sdb/kxc/stamp_models/source/diffpepbuilder/extracted_p24_install_probe/DiffPepBuilder-main",
        source_sha256="",
        checkpoint_path="/mnt/sdb/kxc/stamp_models/weights/diffpepbuilder/diffpepbuilder_v1.pth",
        checkpoint_sha256="dbc4283257d27e38a1ce90c9344063b046ab7161745ebed1fd98a4b0439b992a",
        fixture_path="/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33f_ppflow_smoke_20260628_195952/ppflow_p33_temp_config_p33/0000_2qbx_2026_06_28__20_00_08/reference.pdb",
        fixture_sha256="db60daf68e547f6f3727cdb7bccda77ae22520e586aa566c1e5f543dc6fc09dc",
        env_python="/mnt/sdb/kxc/stamp_models/envs/diffpepbuilder_py39/bin/python",
        runner_script_path="/mnt/sdb/kxc/stamp_models/scripts/stamp_diffpepbuilder_p31b_smoke_runner_hardened_v2.py",
        runner_script_sha256="ec3adaa8ad072b8abd3bbf5ae189ce410713ad5a7365dd76a825844d16f9811a",
        command_args=_diffpepbuilder_command,
        timeout_seconds=3600,
        disk_quota_bytes=10 * 1024 * 1024 * 1024,
        max_output_files=1000,
        output_files=["candidates.pdb", "scores.json"],
    ),
    ModelConfig(
        model_id="pepflow",
        display_name="PepFlow",
        order=4,
        source_path="/mnt/sdb/kxc/stamp_models/source/pepflow/extracted_p25_install_probe/PepFlowww-main/models_con/inference.py",
        source_sha256="c59b5096da6582adecca967d0506efbd69ece188ef9d0903c927a67490125605",
        checkpoint_path="/mnt/sdb/kxc/stamp_models/checkpoints/pepflow/p25_install_probe/PepFlow2024_share/model1.pt",
        checkpoint_sha256="ee3f0458cc47b63f2c5c8bc27f0e9897fab395592a2beb5e627a42f74754fb0a",
        fixture_path="/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33f_ppflow_smoke_20260628_195952/ppflow_p33_temp_config_p33/0000_2qbx_2026_06_28__20_00_08/reference.pdb",
        fixture_sha256="db60daf68e547f6f3727cdb7bccda77ae22520e586aa566c1e5f543dc6fc09dc",
        env_python="/mnt/sdb/kxc/stamp_models/envs/pepflow_py310_pypi_candidate/bin/python",
        runner_script_path="",
        runner_script_sha256="",
        command_args=_pepflow_command,
        timeout_seconds=3600,
        disk_quota_bytes=10 * 1024 * 1024 * 1024,
        max_output_files=1000,
        output_files=["generated.pdb", "samples/"],
    ),
    ModelConfig(
        model_id="pephar",
        display_name="PepHAR",
        order=5,
        source_path="/mnt/sdb/kxc/stamp_models/source/pephar/extracted_p25_install_probe/PepHAR-main",
        source_sha256="",
        checkpoint_path="",
        checkpoint_sha256="",
        fixture_path="/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33f_ppflow_smoke_20260628_195952/ppflow_p33_temp_config_p33/0000_2qbx_2026_06_28__20_00_08/reference.pdb",
        fixture_sha256="db60daf68e547f6f3727cdb7bccda77ae22520e586aa566c1e5f543dc6fc09dc",
        env_python="/mnt/sdb/kxc/stamp_models/envs/pephar_py310/bin/python",
        runner_script_path="/mnt/sdb/kxc/stamp_models/scripts/stamp_pephar_p31c_smoke_runner.py",
        runner_script_sha256="eb28dbad4718903f38fa7b40bc7102f67fe02a424021a016b0d8fde4cb9925b2",
        command_args=_pephar_command,
        timeout_seconds=3600,
        disk_quota_bytes=10 * 1024 * 1024 * 1024,
        max_output_files=1000,
        output_files=["manifest.json"],
    ),
    ModelConfig(
        model_id="ppflow",
        display_name="PPFlow",
        order=6,
        source_path="/mnt/sdb/kxc/stamp_models/source/ppflow/extracted_p25_install_probe/ppflow-main/codesign_ppf.py",
        source_sha256="1bf50964b4f4e34b594b894a274d6c119361e1eba00f2c58e70c41200fc92d08",
        checkpoint_path="/mnt/sdb/kxc/stamp_models/checkpoints/ppflow/p25_install_probe/ppflow/pretrained.pt",
        checkpoint_sha256="be1b53ae09dee78c45faa84c4c90f6c65c285c64e70d3b6e8c931b93abaa6d5d",
        fixture_path="/mnt/sdb/kxc/stamp_models/datasets/ppflow/p29g_c_smoke/p29g_c_fixture/receptor_repaired.pdb",
        fixture_sha256="1091c39a332ff29e917f8124afc472b2d717b9a73ff2e40088fc408a264b999b",
        env_python="/mnt/sdb/kxc/stamp_models/envs/ppflow_real_runner_py39/bin/python",
        runner_script_path="",
        runner_script_sha256="",
        command_args=_ppflow_command,
        timeout_seconds=3600,
        disk_quota_bytes=10 * 1024 * 1024 * 1024,
        max_output_files=1000,
        output_files=["designed.pdb", "output.json"],
    ),
]


def get_model_config(model_id: str) -> ModelConfig:
    normalized = model_id.lower().strip()
    for cfg in MODEL_CONFIGS:
        if cfg.model_id == normalized:
            return cfg
    raise ValueError(f"Unknown model_id: {model_id}")


def ordered_model_ids() -> List[str]:
    return [cfg.model_id for cfg in sorted(MODEL_CONFIGS, key=lambda c: c.order)]


def validate_job_id(job_id: str) -> str:
    if not job_id or ".." in job_id or not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$", job_id):
        raise ValueError(f"Invalid job_id: {job_id}")
    return job_id


def copy_fixture_to_run_dir(fixture_path: str, run_dir: str, model_id: str) -> str:
    """Copy the frozen acceptance fixture into the run input directory.

    Returns the path of the copied input file.
    """
    input_dir = os.path.join(run_dir, "input")
    os.makedirs(input_dir, exist_ok=True)

    ext = os.path.splitext(fixture_path)[1].lower()
    if model_id == "pepmlm":
        dest_name = "target.fasta"
    elif model_id == "evobind2":
        dest_name = "receptor.fasta"
    elif model_id in ("diffpepbuilder", "ppflow"):
        dest_name = "target.pdb"
    elif model_id in ("pepflow", "pephar"):
        dest_name = "receptor.pdb"
    else:
        dest_name = f"input{ext}"

    dest_path = os.path.join(input_dir, dest_name)
    shutil.copy2(fixture_path, dest_path)
    return dest_path
