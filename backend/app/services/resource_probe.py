"""Resource Probe Service (v1.5-md-computation-pilot).

Collects server resource status:
  - GPU info via nvidia-smi (name, memory, utilization)
  - CPU load
  - RAM usage
  - Disk usage
  - GPU lock status (from gpu_lock_service)

Returns BLOCKED when resources are insufficient for new compute jobs.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.services.gpu_lock_service import probe_gpu_lock_status

logger = logging.getLogger("stamp")

# Thresholds for BLOCKED status
GPU_MEM_THRESHOLD = 0.90
CPU_LOAD_THRESHOLD = 0.90
RAM_THRESHOLD = 0.90
DISK_THRESHOLD = 0.95


def _run_nvidia_smi() -> list[dict[str, Any]]:
    """Query nvidia-smi and return a list of GPU info dicts."""
    gpus: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            logger.debug("nvidia-smi returned non-zero: %s", result.stderr)
            return gpus
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                try:
                    mem_used = int(parts[2])
                    mem_total = int(parts[3])
                    util = int(parts[4])
                    gpus.append(
                        {
                            "index": int(parts[0]),
                            "name": parts[1],
                            "memory_used_mb": mem_used,
                            "memory_total_mb": mem_total,
                            "memory_free_mb": mem_total - mem_used,
                            "utilization_percent": util,
                        }
                    )
                except (ValueError, IndexError):
                    continue
    except FileNotFoundError:
        logger.debug("nvidia-smi not found — GPU probe skipped")
    except subprocess.TimeoutExpired:
        logger.warning("nvidia-smi timed out")
    except Exception as exc:
        logger.warning("GPU probe failed: %s", exc)
    return gpus


def _read_cpu_load() -> dict[str, Any]:
    """Read CPU load. Uses /proc/loadavg on Linux, falls back to placeholder."""
    load_info: dict[str, Any] = {"cores": None, "load_1min": None, "utilization_percent": None}
    try:
        import os

        load_info["cores"] = os.cpu_count()
    except Exception:
        pass

    # Try Linux /proc/loadavg
    proc_loadavg = Path("/proc/loadavg")
    if proc_loadavg.exists():
        try:
            text = proc_loadavg.read_text(encoding="utf-8").strip()
            parts = text.split()
            if parts:
                load_info["load_1min"] = float(parts[0])
                if load_info["cores"]:
                    load_info["utilization_percent"] = round(
                        (load_info["load_1min"] / load_info["cores"]) * 100, 1
                    )
        except (OSError, ValueError):
            pass

    return load_info


def _read_ram_usage() -> dict[str, Any]:
    """Read RAM usage. Uses /proc/meminfo on Linux, falls back to placeholder."""
    ram: dict[str, Any] = {"total_mb": None, "used_mb": None, "free_mb": None, "utilization_percent": None}
    proc_meminfo = Path("/proc/meminfo")
    if proc_meminfo.exists():
        try:
            text = proc_meminfo.read_text(encoding="utf-8")
            mem_total_kb = 0
            mem_available_kb = 0
            for line in text.splitlines():
                if line.startswith("MemTotal:"):
                    mem_total_kb = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    mem_available_kb = int(line.split()[1])
            if mem_total_kb:
                ram["total_mb"] = round(mem_total_kb / 1024, 1)
                ram["free_mb"] = round(mem_available_kb / 1024, 1)
                ram["used_mb"] = round((mem_total_kb - mem_available_kb) / 1024, 1)
                ram["utilization_percent"] = round(
                    ((mem_total_kb - mem_available_kb) / mem_total_kb) * 100, 1
                )
        except (OSError, ValueError):
            pass
    return ram


def _read_disk_usage() -> dict[str, Any]:
    """Read disk usage for the current working directory."""
    disk: dict[str, Any] = {"total_gb": None, "used_gb": None, "free_gb": None, "utilization_percent": None}
    try:
        usage = shutil.disk_usage(".")
        disk["total_gb"] = round(usage.total / (1024 ** 3), 2)
        disk["used_gb"] = round((usage.total - usage.free) / (1024 ** 3), 2)
        disk["free_gb"] = round(usage.free / (1024 ** 3), 2)
        disk["utilization_percent"] = round(
            ((usage.total - usage.free) / usage.total) * 100, 1
        )
    except Exception as exc:
        logger.debug("Disk probe failed: %s", exc)
    return disk


def probe_resources() -> dict[str, Any]:
    """Probe all server resources and return a unified status dict.

    Returns:
        {
            "status": "healthy" | "blocked",
            "gpus": [...],
            "cpu": {...},
            "ram": {...},
            "disk": {...},
            "gpu_lock": {...},
            "blocked_reasons": [...] | None,
        }
    """
    gpus = _run_nvidia_smi()
    cpu = _read_cpu_load()
    ram = _read_ram_usage()
    disk = _read_disk_usage()
    gpu_lock = probe_gpu_lock_status()

    blocked_reasons: list[str] = []

    # GPU memory check
    for gpu in gpus:
        if gpu.get("memory_total_mb", 0) > 0:
            mem_ratio = gpu["memory_used_mb"] / gpu["memory_total_mb"]
            if mem_ratio > GPU_MEM_THRESHOLD:
                blocked_reasons.append(
                    f"GPU {gpu['index']} memory usage {mem_ratio:.0%} exceeds threshold"
                )

    # CPU load check
    if cpu.get("utilization_percent") is not None:
        cpu_ratio = cpu["utilization_percent"] / 100
        if cpu_ratio > CPU_LOAD_THRESHOLD:
            blocked_reasons.append(
                f"CPU load {cpu['utilization_percent']}% exceeds threshold"
            )

    # RAM check
    if ram.get("utilization_percent") is not None:
        ram_ratio = ram["utilization_percent"] / 100
        if ram_ratio > RAM_THRESHOLD:
            blocked_reasons.append(
                f"RAM usage {ram['utilization_percent']}% exceeds threshold"
            )

    # Disk check
    if disk.get("utilization_percent") is not None:
        disk_ratio = disk["utilization_percent"] / 100
        if disk_ratio > DISK_THRESHOLD:
            blocked_reasons.append(
                f"Disk usage {disk['utilization_percent']}% exceeds threshold"
            )

    # GPU lock check — if locked, consider it a blocked reason for *new* MD/FlexPepDock jobs
    if gpu_lock.get("locked"):
        blocked_reasons.append(
            f"GPU lock held by {gpu_lock.get('holder')} — new GPU jobs blocked"
        )

    status = "blocked" if blocked_reasons else "healthy"

    return {
        "status": status,
        "gpus": gpus,
        "cpu": cpu,
        "ram": ram,
        "disk": disk,
        "gpu_lock": gpu_lock,
        "blocked_reasons": blocked_reasons if blocked_reasons else None,
    }
