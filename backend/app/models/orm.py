"""
STAMP Platform — SQLAlchemy 2.0 ORM Models (P5-lite, SYNC)

6 core tables with ForeignKey relationships, UUID strings, and
scientific-integrity constraints.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 1. projects
# ---------------------------------------------------------------------------

class Project(Base):
    """A STAMP project container."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    species: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    project_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utc_now,
        server_default=func.now(),
        onupdate=_utc_now,
    )

    target_proteins: Mapped[List["TargetProtein"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    epitope_scans: Mapped[List["EpitopeScan"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    stamp_generation_runs: Mapped[List["StampGenerationRun"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    stamp_candidates: Mapped[List["StampCandidate"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    jobs: Mapped[List["Job"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    pipeline_runs: Mapped[List["PipelineRun"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# 2. target_proteins
# ---------------------------------------------------------------------------

class TargetProtein(Base):
    """A target protein sequence submitted for epitope scanning."""

    __tablename__ = "target_proteins"
    __table_args__ = (
        UniqueConstraint("project_id", "sequence_hash", name="uq_project_seqhash"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    length: Mapped[int] = mapped_column(Integer, nullable=False)
    organism: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual"
    )  # manual / uniprot / pdb / uploaded_fasta
    uniprot_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pdb_id: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    chain_id: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )

    project: Mapped["Project"] = relationship(back_populates="target_proteins")
    epitope_scans: Mapped[List["EpitopeScan"]] = relationship(
        back_populates="target_protein", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# 3. epitope_scans
# ---------------------------------------------------------------------------

class EpitopeScan(Base):
    """An epitope scan job against a target protein."""

    __tablename__ = "epitope_scans"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    target_protein_id: Mapped[str] = mapped_column(
        ForeignKey("target_proteins.id"), nullable=False, index=True
    )
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    algorithm: Mapped[str] = mapped_column(
        String(100), nullable=False, default="heuristic_v1"
    )
    algorithm_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )  # PENDING / RUNNING / COMPLETED / FAILED
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )

    project: Mapped["Project"] = relationship(back_populates="epitope_scans")
    target_protein: Mapped["TargetProtein"] = relationship(
        back_populates="epitope_scans"
    )
    epitope_candidates: Mapped[List["EpitopeCandidate"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# 4. epitope_candidates
# ---------------------------------------------------------------------------

class EpitopeCandidate(Base):
    """A candidate epitope fragment extracted by a scan."""

    __tablename__ = "epitope_candidates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scan_id: Mapped[str] = mapped_column(
        ForeignKey("epitope_scans.id"), nullable=False, index=True
    )
    start: Mapped[int] = mapped_column(Integer, nullable=False)
    end: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence: Mapped[str] = mapped_column(String(500), nullable=False)
    net_charge: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hydrophobicity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cys_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    surface_exposure_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    ranking_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    filter_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PASS"
    )  # PASS / WARNING / FAIL
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )

    scan: Mapped["EpitopeScan"] = relationship(back_populates="epitope_candidates")


# ---------------------------------------------------------------------------
# 5. stamp_generation_runs
# ---------------------------------------------------------------------------

class StampGenerationRun(Base):
    """A STAMP generation run (targeting peptide + linker + AMP)."""

    __tablename__ = "stamp_generation_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    epitope_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("epitope_candidates.id"), nullable=True, index=True
    )
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    generator_name: Mapped[str] = mapped_column(
        String(100), nullable=False, default="manual"
    )  # manual / mock / ampgen / pepmlm
    generator_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )  # PENDING / RUNNING / COMPLETED / FAILED
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )

    project: Mapped["Project"] = relationship(
        back_populates="stamp_generation_runs"
    )
    stamp_candidates: Mapped[List["StampCandidate"]] = relationship(
        back_populates="generation_run", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# 6. stamp_candidates
# ---------------------------------------------------------------------------

class StampCandidate(Base):
    """A fully assembled STAMP candidate peptide."""

    __tablename__ = "stamp_candidates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    epitope_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("epitope_candidates.id"), nullable=True, index=True
    )
    generation_run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("stamp_generation_runs.id"), nullable=True, index=True
    )
    targeting_peptide_seq: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    linker_seq: Mapped[str] = mapped_column(String(100), nullable=False)
    full_sequence: Mapped[str] = mapped_column(Text, nullable=False)
    composite_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    validation_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="NOT_EXPERIMENTALLY_VALIDATED",
    )
    metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )

    project: Mapped["Project"] = relationship(back_populates="stamp_candidates")
    generation_run: Mapped[Optional["StampGenerationRun"]] = relationship(
        back_populates="stamp_candidates"
    )


# ---------------------------------------------------------------------------
# 7. jobs (v0.9-P6 Job System)
# ---------------------------------------------------------------------------

class Job(Base):
    """A background computation job (e.g. PepMLM, CreoPep, ColabFold, FoldX)."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    job_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # e.g. epitope_scan / peptide_generation / stamp_assembly / pepmlm / creopep / colabfold / foldx
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending / running / succeeded / failed / cancelled
    progress: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0
    )  # 0-100
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    output_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    # v1.2-lab-production-fast: extended fields
    candidate_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    server_host: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    error_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    artifacts_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )

    project: Mapped["Project"] = relationship(back_populates="jobs")


# ---------------------------------------------------------------------------
# 8. experimental_validation_runs (v0.11-P1)
# ---------------------------------------------------------------------------

class ExperimentalValidationRun(Base):
    """A wet-lab experimental validation run for a stamp candidate."""

    __tablename__ = "experimental_validation_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("stamp_candidates.id"), nullable=False, index=True
    )
    experiment_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # MIC / MBC / HEMOLYSIS / CYTOTOXICITY / SERUM_STABILITY / PROTEASE_STABILITY / SALT_STABILITY / BIOFILM / RESISTANCE_INDUCTION / OTHER
    organism: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    strain: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    protocol_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    protocol_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    operator: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    experiment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PLANNED"
    )  # PLANNED / RUNNING / COMPLETED / FAILED / INVALIDATED
    validation_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="NOT_EXPERIMENTALLY_VALIDATED"
    )  # NOT_EXPERIMENTALLY_VALIDATED / EXPERIMENT_PLANNED / PARTIALLY_VALIDATED / EXPERIMENTALLY_VALIDATED / VALIDATION_FAILED
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )

    measurements: Mapped[List["ExperimentalMeasurement"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# 9. experimental_measurements (v0.11-P1)
# ---------------------------------------------------------------------------

class ExperimentalMeasurement(Base):
    """An individual measurement from an experimental validation run."""

    __tablename__ = "experimental_measurements"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    validation_run_id: Mapped[str] = mapped_column(
        ForeignKey("experimental_validation_runs.id"), nullable=False, index=True
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("stamp_candidates.id"), nullable=False, index=True
    )
    metric_name: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # MIC_ug_ml / MBC_ug_ml / hemolysis_percent / HC50_ug_ml / IC50_ug_ml / cell_viability_percent / serum_half_life_min / protease_remaining_percent / biofilm_inhibition_percent
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    condition_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    replicate_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    raw_data_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    quality_flag: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PASS"
    )  # PASS / WARNING / FAILED / NEEDS_REVIEW
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )

    run: Mapped["ExperimentalValidationRun"] = relationship(back_populates="measurements")


# ---------------------------------------------------------------------------
# 10. integration_configs (v1.2-lab-production-fast P6)
# ---------------------------------------------------------------------------

class IntegrationConfig(Base):
    """LIMS/ELN integration configuration."""

    __tablename__ = "integration_configs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    integration_type: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # LIMS / ELN
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    auth_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="token"
    )  # token / oauth2 / basic
    token_secret_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    field_mapping_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="CONFIG_REQUIRED"
    )  # CONFIG_REQUIRED / REAL_API_READY / TEST_FAILED / SYNC_SUCCEEDED / SYNC_FAILED
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    test_mode: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )


# ---------------------------------------------------------------------------
# 11. compute_batches (v1.2-lab-production-fast)
# ---------------------------------------------------------------------------

class ComputeBatch(Base):
    """A batch of compute jobs for multiple candidates."""

    __tablename__ = "compute_batches"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    batch_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # structure_pipeline / docking_pipeline / full_validation
    candidate_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=list)
    pipeline_stages: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=list)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )  # PENDING / RUNNING / PARTIAL_SUCCESS / SUCCEEDED / FAILED
    summary_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )


# ---------------------------------------------------------------------------
# 12. batch_computations (v1.4-batch-computation)
# ---------------------------------------------------------------------------

class BatchComputation(Base):
    """A batch computation job for multiple candidates (ColabFold/FoldX/MMGBSA)."""

    __tablename__ = "batch_computations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # COLABFOLD / FOLDX / MMGBSA / FLEXPEPDOCK / MIXED
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )  # PENDING / RUNNING / SUCCEEDED / FAILED / BLOCKED / CANCELLED
    input_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    summary_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    artifact_dir: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )


class BatchComputationItem(Base):
    """A single item within a batch computation."""

    __tablename__ = "batch_computation_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    batch_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    candidate_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # COLABFOLD / FOLDX / MMGBSA
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )  # PENDING / RUNNING / SUCCEEDED / FAILED / BLOCKED / CANCELLED
    input_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    output_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    artifact_dir: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )


class ComputationArtifact(Base):
    """An artifact produced by a computation job."""

    __tablename__ = "computation_artifacts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    batch_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    item_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    candidate_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


# ---------------------------------------------------------------------------
# 13. file_assets (v1.2-lab-production-fast)
# ---------------------------------------------------------------------------

class FileAsset(Base):
    """A large file artifact produced by a compute job."""

    __tablename__ = "file_assets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    candidate_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    file_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # pdb / cif / pdbqt / mdcrd / nc / prmtop / inpcrd / log / report / bundle
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    storage_backend: Mapped[str] = mapped_column(
        String(32), nullable=False, default="local_fs"
    )  # local_fs / server_nfs / s3
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


# ---------------------------------------------------------------------------
# 12. audit_logs (v1.2-lab-production-fast)
# ---------------------------------------------------------------------------

class AuditLogEntry(Base):
    """Immutable audit log entry for significant system events."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # CREATE / UPDATE / DELETE / SUBMIT / CANCEL / RETRY / EXPORT / SYNC / LOGIN / LOGOUT / DENIED
    entity_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # project / candidate / job / batch / asset / report / user / integration
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    before_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    after_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


# ---------------------------------------------------------------------------
# 14. pipeline_runs (v1.6-p0)
# ---------------------------------------------------------------------------

class PipelineRun(Base):
    """A complete STAMP pipeline execution from target protein to batch draft."""

    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=True, index=True
    )
    target_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_sequence: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )  # PENDING / RUNNING / SUCCEEDED / FAILED / BLOCKED
    current_step: Mapped[str] = mapped_column(
        String(64), nullable=False, default="TARGET_INPUT"
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    steps: Mapped[List["PipelineStep"]] = relationship(
        back_populates="pipeline_run", cascade="all, delete-orphan", order_by="PipelineStep.step_order"
    )
    project: Mapped[Optional["Project"]] = relationship(back_populates="pipeline_runs")


class PipelineStep(Base):
    """A single step within a PipelineRun."""

    __tablename__ = "pipeline_steps"
    __table_args__ = (
        UniqueConstraint("pipeline_run_id", "step_name", name="uq_pipeline_run_step"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    pipeline_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pipeline_runs.id"), nullable=False, index=True
    )
    step_name: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # TARGET_INPUT / EPITOPE_SCREENING / PEPTIDE_GENERATION / PEPTIDE_OPTIMIZATION / STAMP_ASSEMBLY / BATCH_DRAFT / STRUCTURE_VALIDATION_READY
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )  # PENDING / RUNNING / SUCCEEDED / FAILED / BLOCKED
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    input_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    output_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    artifact_dir: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    method: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    scientific_boundary_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now
    )

    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="steps")
