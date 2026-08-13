"""STAMP Platform — CRUD package exports."""

from app.crud.projects import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)
from app.crud.target_proteins import (
    create_target_protein,
    get_target_protein,
    list_target_proteins_by_project,
    update_target_protein,
)
from app.crud.epitopes import (
    create_epitope_scan,
    create_epitope_candidate,
    create_epitope_candidates_bulk,
    get_epitope_candidate,
    get_epitope_scan,
    list_epitope_candidates_by_scan,
    update_epitope_scan,
    update_epitope_candidate,
)
from app.crud.stamp_candidates import (
    create_stamp_candidate,
    create_stamp_candidates_bulk,
    create_stamp_generation_run,
    get_stamp_candidate,
    get_stamp_generation_run,
    list_stamp_candidates_by_generation_run,
    list_stamp_candidates_by_project,
    mark_stamp_generation_run_completed,
    mark_stamp_generation_run_failed,
    mark_stamp_generation_run_running,
    update_stamp_candidate,
    update_stamp_candidates_bulk,
    update_stamp_generation_run,
    update_stamp_generation_run_status,
)
from app.crud.experimental_validation import (
    add_measurement,
    create_validation_run,
    get_measurement,
    get_validation_run,
    list_measurements_by_candidate,
    list_measurements_by_run,
    list_validation_runs_by_candidate,
    list_validation_runs_by_project,
    summarize_candidate_experimental_validation,
    update_validation_run,
)

__all__ = [
    # projects
    "create_project",
    "get_project",
    "list_projects",
    "update_project",
    "delete_project",
    # target_proteins
    "create_target_protein",
    "get_target_protein",
    "list_target_proteins_by_project",
    "update_target_protein",
    # epitopes
    "create_epitope_scan",
    "create_epitope_candidate",
    "create_epitope_candidates_bulk",
    "get_epitope_scan",
    "get_epitope_candidate",
    "list_epitope_candidates_by_scan",
    "update_epitope_scan",
    "update_epitope_candidate",
    # stamp
    "create_stamp_generation_run",
    "create_stamp_candidate",
    "create_stamp_candidates_bulk",
    "get_stamp_generation_run",
    "get_stamp_candidate",
    "list_stamp_candidates_by_project",
    "list_stamp_candidates_by_generation_run",
    "update_stamp_generation_run",
    "update_stamp_candidate",
    "update_stamp_candidates_bulk",
    # P5-lite P3 generation run status helpers
    "mark_stamp_generation_run_running",
    "mark_stamp_generation_run_completed",
    "mark_stamp_generation_run_failed",
    "update_stamp_generation_run_status",
    # Experimental Validation (v0.11-P1)
    "create_validation_run",
    "get_validation_run",
    "list_validation_runs_by_candidate",
    "list_validation_runs_by_project",
    "update_validation_run",
    "add_measurement",
    "get_measurement",
    "list_measurements_by_run",
    "list_measurements_by_candidate",
    "summarize_candidate_experimental_validation",
]
