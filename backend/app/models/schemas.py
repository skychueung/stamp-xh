"""
STAMP Platform — Pydantic v2 Schemas

All data models for the STAMP (Synergistic Targeting Antimicrobial Peptide)
platform. Models cover:
    - PepMLM generated targeting peptide candidates
    - AMP (Antimicrobial Peptide) library records
    - STAMP hybrid candidates (three-part molecular structure)
    - Domain-level components (Targeting, Linker, Killing)
    - Biophysical property placeholders
    - Experimental data placeholders (reserved for real lab data)

Version: v0.6d (Pydantic v2 compatible)
"""

from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FilterStatus(str, Enum):
    """Validation filter status for PepMLM candidates."""

    PASS = "Pass"
    FAIL = "Fail"
    WARNING = "Warning"


class LinkerType(str, Enum):
    """Type classification for the linker domain."""

    RIGID = "rigid"
    FLEXIBLE = "flexible"
    CLEAVABLE = "cleavable"


class PriorityLevel(str, Enum):
    """Priority level for AMP selection."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValidationStatus(str, Enum):
    """Experimental validation status of a STAMP candidate.

    All v0.6d candidates start at NOT_EXPERIMENTALLY_VALIDATED.
    No mock scores are computed.
    """

    NOT_EXPERIMENTALLY_VALIDATED = "NOT_EXPERIMENTALLY_VALIDATED"
    IN_VITRO_TESTED = "IN_VITRO_TESTED"
    IN_VIVO_TESTED = "IN_VIVO_TESTED"
    CLINICAL_TRIAL = "CLINICAL_TRIAL"


class AmpRole(str, Enum):
    """Functional role of an AMP within the STAMP architecture."""

    KILLING_DOMAIN = "killing_domain"
    TARGETING_DOMAIN = "targeting_domain"
    LINKER = "linker"
    FULL_AMP = "full_amp"


# ---------------------------------------------------------------------------
# Generic type variable for ApiResponse
# ---------------------------------------------------------------------------

T = TypeVar("T")


# ===========================================================================
# 1. PepMLM Candidate Models
# ===========================================================================


class PepMLMCandidate(BaseModel):
    """A single PepMLM-generated targeting peptide candidate.

    Attributes:
        candidate_id: Unique identifier, e.g. ``OPRF_0001``.
        target_name: Target molecule name, e.g. ``Pseudomonas_OprF``.
        peptide_length: Length in amino acids (typically 12-18).
        generated_peptide: The amino acid sequence.
        ppl_score: Perplexity score from PepMLM (lower is better).
        net_charge: Net charge at physiological pH.
        pI: Isoelectric point.
        GRAVY: Grand average of hydropathicity.
        cysteine_count: Number of cysteine residues.
        filter_status: Pass / Fail / Warning.
        validation_warning: Human-readable validation note.
    """

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    candidate_id: str = Field(..., examples=["OPRF_0001"])
    target_name: str = Field(..., examples=["Pseudomonas_OprF"])
    peptide_length: int = Field(..., ge=1, le=100, examples=[12])
    generated_peptide: str = Field(..., min_length=1, examples=["DKTKKAFLIAAG"])
    ppl_score: float = Field(..., ge=0.0, examples=[9.1933])
    net_charge: float = Field(..., examples=[2.0])
    pI: float | None = Field(default=None, examples=[7.8])
    GRAVY: float | None = Field(default=None, examples=[0.017])
    cysteine_count: int = Field(default=0, ge=0, examples=[0])
    filter_status: FilterStatus = Field(default=FilterStatus.PASS)
    validation_warning: str | None = Field(
        default=None,
        examples=["OFFICIAL PepMLM target-conditioned generation"],
    )

    @field_validator("generated_peptide")
    @classmethod
    def _uppercase_sequence(cls, v: str) -> str:
        """Normalize peptide sequences to uppercase."""
        return v.upper()


# ===========================================================================
# 2. AMP Library Models
# ===========================================================================


class AmpRecord(BaseModel):
    """An AMP (Antimicrobial Peptide) record from the priority library.

    Attributes:
        amp_name: Canonical name, e.g. ``P4``.
        raw_sequence: Raw sequence as stored (may contain illegal chars).
        clean_sequence: Sequence with illegal characters removed.
        source: Origin or screening campaign.
        priority: Selection priority (high > medium > low).
        role: Functional role in STAMP architecture.
        illegal_char_found: The illegal character(s) removed, if any.
        illegal_char_position: 1-based position of illegal char, if known.
    """

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    amp_name: str = Field(..., alias="ampName", examples=["P4"])
    raw_sequence: str = Field(..., alias="rawSequence", examples=["FSRFLRRVRRYRPKISFNLEPFFKF5"])
    clean_sequence: str = Field(
        ...,
        alias="cleanSequence",
        examples=["FSRFLRRVRRYRPKISFNLEPFFKF"],
    )
    source: str = Field(default="unknown", examples=["cosmetic_preservative_screening"])
    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM)
    role: AmpRole = Field(default=AmpRole.KILLING_DOMAIN)
    illegal_char_found: str | None = Field(
        default=None,
        alias="illegalCharFound",
        examples=["5"],
    )
    illegal_char_position: str | None = Field(
        default=None,
        alias="illegalCharPosition",
        examples=["25"],
    )

    @field_validator("clean_sequence")
    @classmethod
    def _uppercase_clean(cls, v: str) -> str:
        """Ensure clean sequence is uppercase and stripped."""
        return v.upper().strip()


# ===========================================================================
# 3. Domain Component Models (used inside STAMP)
# ===========================================================================


class TargetingDomain(BaseModel):
    """The targeting peptide (TP) domain of a STAMP molecule.

    Derived from a PepMLM candidate; responsible for binding to the
    bacterial outer-membrane target (e.g. P. aeruginosa OprF).
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., examples=["OPRF_0001"])
    sequence: str = Field(..., min_length=1, examples=["DKTKKAFLIAAG"])
    length: int = Field(..., ge=1)
    net_charge: float = Field(..., examples=[2.0])
    gravy: float | None = Field(default=None, examples=[0.017])


class LinkerDomain(BaseModel):
    """The rigid linker domain connecting TP and AMP.

    In the current architecture the linker is fixed to ``EAAAK``
    (5-residue alpha-helical rigid linker).
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(default="EAAAK")
    sequence: str = Field(default="EAAAK", min_length=1)
    length: int = Field(default=5)
    type: LinkerType = Field(default=LinkerType.RIGID)


class KillingDomain(BaseModel):
    """The AMP killing domain of a STAMP molecule.

    Selected from the priority AMP library; responsible for membrane
    disruption and bacterial killing.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., examples=["P4"])
    sequence: str = Field(..., min_length=1, examples=["FSRFLRRVRRYRPKISFNLEPFFKF"])
    length: int = Field(..., ge=1)
    net_charge: int | float | None = Field(default=None, examples=[7])
    gravy: float | None = Field(default=None, examples=[-0.592])


# ===========================================================================
# 4. Property / Score / Experimental Placeholder Models
# ===========================================================================


class BiophysicalProperties(BaseModel):
    """Computed biophysical properties of the full STAMP sequence.

    In v0.6d the *pI*, *GRAVY* and *hydrophobicity_fraction* fields
    are intentionally left as ``None`` — they will be populated by a
    dedicated bio-calculation pipeline in a future release.
    """

    model_config = ConfigDict(populate_by_name=True)

    length: int = Field(..., ge=1, description="Total amino acid count")
    net_charge: int | float | None = Field(
        default=None,
        description="Net charge at pH 7.4",
    )
    pI: float | None = Field(
        default=None,
        description="Isoelectric point (not yet computed)",
    )
    GRAVY: float | None = Field(
        default=None,
        description="Grand average of hydropathicity (not yet computed)",
    )
    hydrophobicity_fraction: float | None = Field(
        default=None,
        description="Fraction of hydrophobic residues (not yet computed)",
    )


class MockScores(BaseModel):
    """Mock scoring placeholder — **DEPRECATED in v0.6d**.

    Previously used for formula-based pseudo-scores.  All fields are
    now ``None`` to prevent fabricated data from leaking into the
    scientific pipeline.
    """

    model_config = ConfigDict(populate_by_name=True)

    docking_score: float | None = None
    binding_affinity_delta_g: float | None = None
    composite_score: float | None = None
    version: str | None = Field(
        default=None,
        description="Version tag of the scoring model, if any",
    )


class ExperimentalData(BaseModel):
    """Real wet-lab experimental measurements.

    **All fields are ``None`` by design in v0.6d.**
    This model acts as a schema contract with the experimental team.
    No mock values are injected — data will be populated only after
    actual laboratory assays are performed.
    """

    model_config = ConfigDict(populate_by_name=True)

    MIC_ug_ml: float | None = Field(
        default=None,
        description="Minimum inhibitory concentration (µg/mL)",
    )
    MBC_ug_ml: float | None = Field(
        default=None,
        description="Minimum bactericidal concentration (µg/mL)",
    )
    hemolysis_percent: float | None = Field(
        default=None,
        description="Hemolysis percentage at reference concentration",
    )
    LPS_binding_Kd_nM: float | None = Field(
        default=None,
        description="LPS binding dissociation constant (nM)",
    )
    pLDDT: float | None = Field(
        default=None,
        description="AF2 predicted LDDT (0-100)",
    )
    ipTM: float | None = Field(
        default=None,
        description="AF2 interface predicted TM-score (not fabricated)",
    )
    pDockQ: float | None = Field(
        default=None,
        description="Predicted DockQ score (not fabricated)",
    )
    note: str | None = Field(
        default="Reserved for real experimental data",
        description="Human-readable provenance note",
    )


class StructureStatus(BaseModel):
    """Availability flags for structural data."""

    model_config = ConfigDict(populate_by_name=True)

    monomer_predicted: bool = Field(default=False)
    complex_predicted: bool = Field(default=False)
    experimental_structure: bool = Field(default=False)


# ===========================================================================
# 5. STAMP Candidate Model (top-level output)
# ===========================================================================


class StampCandidate(BaseModel):
    """A fully assembled STAMP hybrid peptide candidate.

    Architecture::

        N-term [Targeting Domain] — [Linker] — [Killing Domain] C-term
                 TP (12-18 aa)       EAAAK       AMP (from library)

    The ``display_full_sequence`` inserts visual separators and the
    ``-NH2`` C-terminal modification for human readability.

    Attributes:
        candidate_id: Unique STAMP identifier, e.g. ``stamp_auto_001``.
        target_molecule: Human-readable target, e.g. ``P. aeruginosa OprF``.
        targeting_domain: PepMLM-derived targeting peptide.
        linker: Fixed ``EAAAK`` rigid linker.
        killing_domain: Selected AMP (default P4).
        orientation: Always ``N-to-C`` for this release.
        terminal_modification: Always ``-NH2`` (C-terminal amidation).
        raw_full_sequence: Concatenated sequence without separators.
        display_full_sequence: Human-readable formatted sequence.
        is_complete: Whether all three domains are present.
        biophysical: Biophysical properties (partially deferred).
        mock_scores: Always ``None`` in v0.6d.
        experimental: Wet-lab data placeholders (all ``None``).
        structure_status: Structure availability flags.
        validation_status: Always ``NOT_EXPERIMENTALLY_VALIDATED``.
    """

    model_config = ConfigDict(populate_by_name=True)

    candidate_id: str = Field(..., examples=["stamp_auto_001"])
    target_molecule: str = Field(
        ...,
        examples=["Pseudomonas aeruginosa OprF"],
    )
    targeting_domain: TargetingDomain
    linker: LinkerDomain
    killing_domain: KillingDomain
    orientation: str = Field(default="N-to-C")
    terminal_modification: str = Field(default="-NH2")
    raw_full_sequence: str = Field(
        ...,
        description="Concatenated sequence without separators or mods",
    )
    display_full_sequence: str = Field(
        ...,
        description="Human-readable: TP-EAAAK-AMP-NH2",
    )
    is_complete: bool = Field(default=True)
    biophysical: BiophysicalProperties
    mock_scores: MockScores | None = Field(
        default=None,
        description="v0.6d: intentionally null (no pseudo-scores)",
    )
    experimental: ExperimentalData = Field(default_factory=ExperimentalData)
    structure_status: StructureStatus = Field(default_factory=StructureStatus)
    validation_status: ValidationStatus = Field(
        default=ValidationStatus.NOT_EXPERIMENTALLY_VALIDATED,
    )


# ===========================================================================
# 6. Request / Response DTOs
# ===========================================================================


class StampBuildRequest(BaseModel):
    """Request body for POST /api/v1/stamp/build.

    Builds a single STAMP candidate from a PepMLM targeting peptide
    and an optional AMP name.  If ``amp_name`` is omitted, P4 is used
    as the default killing domain.
    """

    model_config = ConfigDict(populate_by_name=True)

    candidate_id: str = Field(
        ...,
        description="PepMLM candidate ID to use as targeting domain",
        examples=["OPRF_0001"],
    )
    amp_name: str | None = Field(
        default=None,
        description="AMP name from library (default: P4)",
        examples=["P4"],
    )

    @field_validator("candidate_id")
    @classmethod
    def _non_empty_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("candidate_id must not be empty")
        return v


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated list wrapper.

    Used for endpoints that return collections (e.g. candidate lists).
    """

    model_config = ConfigDict(populate_by_name=True)

    items: list[T]
    total: int
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)


# ===========================================================================
# 7. Unified API Response Wrapper
# ===========================================================================


class ApiResponse(BaseModel, Generic[T]):
    """STAMP platform unified API response envelope.

    Every successful endpoint returns this structure so that front-end
    clients can rely on a consistent ``{code, message, data}`` shape.
    Errors are handled by global exception handlers and also normalised
    into this envelope.
    """

    model_config = ConfigDict(populate_by_name=True)

    code: int = Field(default=200, ge=100, le=599)
    message: str = Field(default="success")
    data: T | None = Field(default=None)

    @classmethod
    def success(cls, data: T | None = None, message: str = "success") -> "ApiResponse[T]":
        """Factory method for a successful response.

        Args:
            data: Payload to return.
            message: Human-readable status message.

        Returns:
            Populated ``ApiResponse`` with *code* = 200.
        """
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(
        cls,
        code: int,
        message: str,
        data: T | None = None,
    ) -> "ApiResponse[T]":
        """Factory method for an error response.

        Args:
            code: HTTP status code (4xx or 5xx).
            message: Human-readable error description.
            data: Optional error detail payload.

        Returns:
            Populated ``ApiResponse`` with the given error code.
        """
        return cls(code=code, message=message, data=data)


# ===========================================================================
# 8. Lightweight list-item schemas (for collection endpoints)
# ===========================================================================


class PepMLMCandidateListItem(BaseModel):
    """Trimmed view of a PepMLM candidate for list endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    candidate_id: str
    target_name: str
    peptide_length: int
    generated_peptide: str
    ppl_score: float
    filter_status: FilterStatus


class AmpListItem(BaseModel):
    """Trimmed view of an AMP record for list endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    amp_name: str = Field(..., alias="ampName")
    clean_sequence: str = Field(..., alias="cleanSequence")
    priority: PriorityLevel
    role: AmpRole


class StampListItem(BaseModel):
    """Trimmed view of a STAMP candidate for list endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    candidate_id: str
    target_molecule: str
    raw_full_sequence: str
    display_full_sequence: str
    is_complete: bool
    validation_status: ValidationStatus
