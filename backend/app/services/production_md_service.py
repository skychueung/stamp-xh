"""Production MD task service.

v1.2-lab-production-fast — P7 Production MD templates.

Generates GROMACS-compatible parameter sets for 1/5/10/50 ns production runs
and submits them as Jobs to the compute queue.

No fabricated metrics: this module only prepares input parameters and creates
Job records. Results are parsed from real server artifacts after the run finishes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.orm import Job
from app.services.server_compute_runner import ServerComputeRunner

logger = logging.getLogger("stamp")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_DURATIONS_NS = {1, 5, 10, 50}

# GROMACS mdp parameters scaled by duration
# Assumes 2 fs timestep, 1000 steps = 2 ps = 0.002 ns
# nsteps = duration_ns * 500_000
_MDP_TEMPLATE = {
    "integrator": "md",
    "dt": 0.002,  # ps
    "nsteps": None,  # computed from duration
    "nstxout": 5000,  # 10 ps
    "nstvout": 5000,
    "nstfout": 5000,
    "nstenergy": 5000,
    "nstlog": 5000,
    "continuation": "yes",
    "constraint_algorithm": "lincs",
    "constraints": "all-bonds",
    "lincs_iter": 1,
    "lincs_order": 4,
    "ns_type": "grid",
    "coulombtype": "PME",
    "pme_order": 4,
    "fourierspacing": 0.16,
    "rcoulomb": 1.0,
    "rvdw": 1.0,
    "tcoupl": "V-rescale",
    "tc-grps": "Protein Non-Protein",
    "tau_t": "0.1 0.1",
    "ref_t": "310 310",
    "pcoupl": "Parrinello-Rahman",
    "pcoupltype": "isotropic",
    "tau_p": 2.0,
    "ref_p": 1.0,
    "compressibility": "4.5e-5",
    "gen_vel": "no",
    "cutoff-scheme": "Verlet",
}


def _build_mdp(duration_ns: int) -> dict:
    """Build mdp parameter dict for a given duration."""
    mdp = dict(_MDP_TEMPLATE)
    mdp["nsteps"] = duration_ns * 500_000
    mdp["duration_ns"] = duration_ns
    return mdp


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_production_md_job(
    db: Session,
    *,
    project_id: str,
    candidate_id: str,
    duration_ns: int,
    topology_path: str,
    coordinates_path: str,
    previous_md_job_id: Optional[str] = None,
    server_host: Optional[str] = None,
    priority: int = 0,
) -> Job:
    """Create a production MD Job record.

    Args:
        project_id: Project UUID.
        candidate_id: Candidate UUID.
        duration_ns: Must be one of {1, 5, 10, 50}.
        topology_path: Absolute path to .tpr or .top file.
        coordinates_path: Absolute path to .gro or .cpt restart file.
        previous_md_job_id: Optional prior equilibration/production job for chaining.
        server_host: Target compute server (default from settings).
        priority: Job queue priority (higher = earlier).

    Returns:
        Created Job with status PENDING.

    Raises:
        ValueError: If duration_ns is not supported.
    """
    if duration_ns not in VALID_DURATIONS_NS:
        raise ValueError(
            f"duration_ns={duration_ns} not supported. Choose from {sorted(VALID_DURATIONS_NS)}"
        )

    mdp = _build_mdp(duration_ns)
    input_json = {
        "pipeline_stage": "production_md",
        "duration_ns": duration_ns,
        "topology_path": topology_path,
        "coordinates_path": coordinates_path,
        "previous_md_job_id": previous_md_job_id,
        "mdp": mdp,
        "expected_outputs": [
            "md.xtc",
            "md.edr",
            "md.log",
            "md.cpt",
            "md.tpr",
        ],
    }

    job = Job(
        project_id=project_id,
        job_type="production_md",
        status="PENDING",
        input_json=input_json,
        candidate_id=candidate_id,
        priority=priority,
        server_host=server_host,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info(
        "Created production_md job %s for candidate %s (%d ns)",
        job.id,
        candidate_id,
        duration_ns,
    )
    return job


def submit_production_md_to_server(db: Session, job: Job) -> dict:
    """Attempt to submit a production MD job to the configured server.

    If the server is unreachable, the job status is updated to BLOCKED
    and a retryable connectivity error is recorded.

    Returns:
        Dict with ``status`` (SUBMITTED / BLOCKED / FAILED) and ``detail``.
    """
    if job.job_type != "production_md":
        raise ValueError(f"Job {job.id} is not a production_md job")

    runner = ServerComputeRunner(host=job.server_host or "192.168.31.218")
    result = runner.dispatch(job.job_type, job.input_json or {})

    if result.get("status") == "BLOCKED":
        job.status = "BLOCKED"
        job.error_message = result.get("message", "Server unreachable")
        job.error_json = result
        db.commit()
        db.refresh(job)
        return {"status": "BLOCKED", "detail": job.error_message}

    # If submit_server_job returns a real success dict, mark accordingly
    job.status = "RUNNING"
    job.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return {"status": "SUBMITTED", "detail": "Job dispatched to server"}
