"""Centralized storage paths for model adapters.

EvoBind2 prefers /mnt/sdb storage, honors explicit environment overrides, and
falls back to known legacy resources only when the preferred path is absent.
The conda environment is intentionally not placed on /mnt/sdb by default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Mapping


DEFAULT_MODEL_STORAGE_ROOT = "/mnt/sdb/kxc/stamp_models"
DEFAULT_EVOBIND2_ENV_PYTHON = (
    "/home/xh/kxc/stampup/stamp-small-change-model/models/evobind2/"
    "envs/evobind/bin/python"
)

LEGACY_EVOBIND2_SOURCE_DIR = "/home/xh/kxc/stampup/models_dev/evobind2/source/EvoBind"
LEGACY_EVOBIND2_AF2_PARAMS_DIR = (
    "/home/xh/kxc/stampup/stamp-small-change-model/models/evobind2/cache/af2_params"
)
LEGACY_EVOBIND2_AF2_DATA_DIR = "/home/xh/kxc/stampup/models_dev/evobind2/cache/af2_data_dir"
LEGACY_EVOBIND2_HHBLITS_BIN = (
    "/home/xh/kxc/stampup/stamp-small-change-model/models/evobind2/tools/bin/hhblits"
)


@dataclass(frozen=True)
class EvoBind2Paths:
    storage_root: str
    source_dir: str
    af2_params_dir: str
    af2_data_dir: str
    hhblits_bin: str
    env_python: str
    uniref30_dir: str
    uniref30_prefix: str
    cache_dir: str
    artifact_dir: str
    sources: dict[str, str]
    legacy_fallback_warnings: tuple[str, ...]


def _select_path(
    env_name: str,
    preferred: str,
    legacy: str | None,
    environ: Mapping[str, str],
    exists: Callable[[str], bool],
) -> tuple[str, str, str | None]:
    override = environ.get(env_name)
    if override:
        return override, "environment_override", None
    if exists(preferred) or legacy is None:
        return preferred, "storage_root", None
    if exists(legacy):
        warning = f"legacy_fallback_warning:{env_name}:{legacy}"
        return legacy, "legacy_fallback", warning
    return preferred, "storage_root_missing", None


def resolve_evobind2_paths(
    environ: Mapping[str, str] | None = None,
    exists: Callable[[str], bool] = os.path.exists,
) -> EvoBind2Paths:
    env = os.environ if environ is None else environ
    root = env.get("STAMP_MODEL_STORAGE_ROOT", DEFAULT_MODEL_STORAGE_ROOT).rstrip("/")

    preferred_source = f"{root}/source/evobind2"
    preferred_params = f"{root}/checkpoints/evobind2/af2_params"
    preferred_data = f"{root}/cache/evobind2/af2_data_dir"
    preferred_hhblits = f"{root}/source/evobind2/tools/bin/hhblits"

    selected: dict[str, str] = {}
    sources: dict[str, str] = {}
    warnings: list[str] = []
    for key, env_name, preferred, legacy, preferred_probe, legacy_probe in (
        ("source_dir", "EVOBIND2_SOURCE_DIR", preferred_source, LEGACY_EVOBIND2_SOURCE_DIR,
         f"{preferred_source}/src/mc_design.py", f"{LEGACY_EVOBIND2_SOURCE_DIR}/src/mc_design.py"),
        ("af2_params_dir", "EVOBIND2_AF2_PARAMS_DIR", preferred_params, LEGACY_EVOBIND2_AF2_PARAMS_DIR,
         f"{preferred_params}/params_model_1.npz", f"{LEGACY_EVOBIND2_AF2_PARAMS_DIR}/params_model_1.npz"),
        ("af2_data_dir", "EVOBIND2_AF2_DATA_DIR", preferred_data, LEGACY_EVOBIND2_AF2_DATA_DIR,
         preferred_data, LEGACY_EVOBIND2_AF2_DATA_DIR),
        ("hhblits_bin", "EVOBIND2_HHBLITS_BIN", preferred_hhblits, LEGACY_EVOBIND2_HHBLITS_BIN,
         preferred_hhblits, LEGACY_EVOBIND2_HHBLITS_BIN),
    ):
        readiness = {preferred: exists(preferred_probe), legacy: exists(legacy_probe)}
        value, source, warning = _select_path(
            env_name, preferred, legacy, env, lambda candidate: readiness.get(candidate, exists(candidate))
        )
        selected[key] = value
        sources[key] = source
        if warning:
            warnings.append(warning)

    env_python = env.get("EVOBIND2_ENV_PYTHON", DEFAULT_EVOBIND2_ENV_PYTHON)
    sources["env_python"] = "environment_override" if env.get("EVOBIND2_ENV_PYTHON") else "explicit_legacy_env_default"
    uniref30_dir = env.get("EVOBIND2_UNIREF30_DIR", "/mnt/sda/Bio_database/UniRef30").rstrip("/")
    sources["uniref30_dir"] = "environment_override" if env.get("EVOBIND2_UNIREF30_DIR") else "external_database_default"

    return EvoBind2Paths(
        storage_root=root,
        source_dir=selected["source_dir"],
        af2_params_dir=selected["af2_params_dir"],
        af2_data_dir=selected["af2_data_dir"],
        hhblits_bin=selected["hhblits_bin"],
        env_python=env_python,
        uniref30_dir=uniref30_dir,
        uniref30_prefix=f"{uniref30_dir}/UniRef30_2023_02",
        cache_dir=f"{root}/cache/evobind2",
        artifact_dir=f"{root}/artifacts/evobind2",
        sources=sources,
        legacy_fallback_warnings=tuple(warnings),
    )


EVOBIND2_PATHS = resolve_evobind2_paths()
