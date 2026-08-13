"""STAMP Platform — Pydantic Schemas (P5-lite).

Schemas are split into domain modules for maintainability.
This module re-exports all P5-lite ORM schemas for backward compatibility.
"""

from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    SchemaBase,
)
from app.schemas.target_protein import (
    TargetProteinCreate,
    TargetProteinResponse,
    TargetProteinUpdate,
)
from app.schemas.epitope import (
    EpitopeCandidateCreate,
    EpitopeCandidateResponse,
    EpitopeCandidateUpdate,
    EpitopeScanCandidateItem,
    EpitopeScanCreate,
    EpitopeScanResponse,
    EpitopeScanRunRequest,
    EpitopeScanRunResponse,
    EpitopeScanUpdate,
)
from app.schemas.project_results import (
    EpitopeCandidateLite,
    EpitopeScanLite,
    GenerationRunLite,
    GenerationRunListResponse,
    ProjectPipelineResultsResponse,
    ProjectStampResultsResponse,
    ProjectSummaryResponse,
    StampCandidateDetail,
    StampCandidateLite,
    TargetProteinLite,
)
from app.schemas.bepipred3 import (
    BepiPred3JobInput,
    BepiPred3JobOutput,
    BepiPred3SidecarRequest,
    BepiPred3SidecarResponse,
)
from app.schemas.pepmlm import (
    PepMLMJobInput,
    PepMLMPersistResponse,
)
from app.schemas.target_peptide_design import (
    TargetPeptideDesignCandidateItem,
    TargetPeptideDesignCandidatesResponse,
    TargetPeptideDesignJobCreate,
    TargetPeptideDesignJobResponse,
    TargetPeptideDesignModelInfo,
    TargetPeptideDesignModelProbeResult,
    TargetPeptideDesignModelProbesResponse,
    TargetPeptideDesignModelsResponse,
)
from app.schemas.experimental_validation import (
    CandidateExperimentalPriorityResponse,
    ExperimentalMeasurementCreate,
    ExperimentalMeasurementResponse,
    ExperimentalValidationRunCreate,
    ExperimentalValidationRunResponse,
    ExperimentalValidationRunUpdate,
    ExperimentalValidationSummaryResponse,
    ProjectExperimentalValidationSummaryResponse,
)
from app.schemas.job import (
    JobCreate,
    JobFailureDiagnosis,
    JobListResponse,
    JobResponse,
    JobRunMockRequest,
    JobRunMockResponse,
    BepiPred3PersistResponse,
    StructurePredictionPersistResponse,
    InterfaceQualityPersistResponse,
    EnergyQualityPersistResponse,
    JobCancelResponse,
    JobStartResponse,
    JobRetryResponse,
    JobUpdate,
)
from app.schemas.stamp import (
    PeptideGenerationRunRequest,
    PeptideGenerationRunResponse,
    StampAssemblyFailedCandidate,
    StampAssemblyRankedCandidate,
    StampAssemblyRunRequest,
    StampAssemblyRunResponse,
    StampCandidateCreate,
    StampCandidateResponse,
    StampCandidateUpdate,
    StampGenerationRunCreate,
    StampGenerationRunResponse,
    StampGenerationRunUpdate,
)

__all__ = [
    # Base
    "SchemaBase",
    # BepiPred3 Sidecar (v0.10-P1a)
    "BepiPred3JobInput",
    "BepiPred3JobOutput",
    "BepiPred3SidecarRequest",
    "BepiPred3SidecarResponse",
    # Project
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    # Target Protein
    "TargetProteinCreate",
    "TargetProteinUpdate",
    "TargetProteinResponse",
    # Epitope Scan
    "EpitopeScanCreate",
    "EpitopeScanUpdate",
    "EpitopeScanResponse",
    # Epitope Candidate
    "EpitopeCandidateCreate",
    "EpitopeCandidateUpdate",
    "EpitopeCandidateResponse",
    # P5-lite P2 Epitope Scan Run
    "EpitopeScanRunRequest",
    "EpitopeScanCandidateItem",
    "EpitopeScanRunResponse",
    # STAMP Generation Run
    "StampGenerationRunCreate",
    "StampGenerationRunUpdate",
    "StampGenerationRunResponse",
    # STAMP Candidate
    "StampCandidateCreate",
    "StampCandidateUpdate",
    "StampCandidateResponse",
    # P5-lite P3 Peptide Generation Run
    "PeptideGenerationRunRequest",
    "PeptideGenerationRunResponse",
    # P5-lite P4 STAMP Assembly Run
    "StampAssemblyRunRequest",
    "StampAssemblyRunResponse",
    "StampAssemblyFailedCandidate",
    "StampAssemblyRankedCandidate",
    # P5-lite P5 Project Results
    "ProjectSummaryResponse",
    "ProjectPipelineResultsResponse",
    "ProjectStampResultsResponse",
    "GenerationRunListResponse",
    "TargetProteinLite",
    "EpitopeScanLite",
    "EpitopeCandidateLite",
    "GenerationRunLite",
    "StampCandidateLite",
    "StampCandidateDetail",
    # Job System (v0.9-P6)
    "JobCreate",
    "JobUpdate",
    "JobResponse",
    "JobListResponse",
    "JobRunMockRequest",
    "JobRunMockResponse",
    "BepiPred3PersistResponse",
    "StructurePredictionPersistResponse",
    "InterfaceQualityPersistResponse",
    "EnergyQualityPersistResponse",
    "JobCancelResponse",
    "JobStartResponse",
    "JobRetryResponse",
    "JobFailureDiagnosis",
    # PepMLM (v0.10-P3a)
    "PepMLMJobInput",
    "PepMLMPersistResponse",
    # Targeted Peptide Design Center (P2 skeleton)
    "TargetPeptideDesignModelInfo",
    "TargetPeptideDesignModelsResponse",
    "TargetPeptideDesignModelProbeResult",
    "TargetPeptideDesignModelProbesResponse",
    "TargetPeptideDesignJobCreate",
    "TargetPeptideDesignJobResponse",
    "TargetPeptideDesignCandidateItem",
    "TargetPeptideDesignCandidatesResponse",
    # Experimental Validation (v0.11-P1)
    "ExperimentalValidationRunCreate",
    "ExperimentalValidationRunUpdate",
    "ExperimentalValidationRunResponse",
    "ExperimentalMeasurementCreate",
    "ExperimentalMeasurementResponse",
    "ExperimentalValidationSummaryResponse",
    "CandidateExperimentalPriorityResponse",
    "ProjectExperimentalValidationSummaryResponse",
]
