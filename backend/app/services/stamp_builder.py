"""
STAMP Platform — STAMP Builder Service

Orchestrates the assembly of a STAMP candidate from three molecular
components: targeting peptide (TP), rigid linker (EAAAK), and AMP
killing domain.  No mock experimental data is ever fabricated.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.exceptions import (
    CandidateNotFoundError,
)
from app.models.schemas import (
    AmpRecord,
    BiophysicalProperties,
    ExperimentalData,
    KillingDomain,
    LinkerDomain,
    PepMLMCandidate,
    StampCandidate,
    StructureStatus,
    TargetingDomain,
    ValidationStatus,
)
from app.services.amp_selector import select_amp
from app.services.sequence_validator import (
    LINKER_LENGTH,
    LINKER_SEQUENCE,
    TERMINAL_MOD,
    assemble_stamp_sequence,
    compute_gravy,
    compute_net_charge,
    validate_sequence,
)

logger = logging.getLogger(__name__)


def _find_pepmlm_candidate(
    candidate_id: str,
    candidates: list[dict[str, Any]],
) -> PepMLMCandidate:
    """Locate a PepMLM candidate by ID.

    Args:
        candidate_id: The candidate identifier (e.g. ``OPRF_0001``).
        candidates: Raw dicts from the PepMLM JSON file.

    Returns:
        Parsed ``PepMLMCandidate``.

    Raises:
        CandidateNotFoundError: If the ID is not found.
    """
    target = candidate_id.strip()
    for raw in candidates:
        if str(raw.get("candidate_id", "")).strip() == target:
            return PepMLMCandidate.model_validate(raw)
    raise CandidateNotFoundError(candidate_id)


def build_stamp(
    candidate_id: str,
    amp_library: list[dict[str, Any]],
    pepmlm_candidates: list[dict[str, Any]],
    preferred_amp_name: str | None = None,
) -> StampCandidate:
    """Assemble a complete STAMP candidate.

    Steps:
        1. Resolve the PepMLM candidate by *candidate_id*.
        2. Select the AMP (default P4, fallback rules in ``amp_selector``).
        3. Validate both sequences.
        4. Concatenate TP + EAAAK + AMP.
        5. Compute lightweight biophysical properties.
        6. Populate placeholder fields (experimental, structure, mock_scores)
           **all as null / defaults** — no fabrication.

    Args:
        candidate_id: PepMLM candidate ID for the targeting domain.
        amp_library: Raw AMP library records.
        pepmlm_candidates: Raw PepMLM candidate records.
        preferred_amp_name: Optional AMP override (e.g. ``"P15"``).

    Returns:
        Fully populated ``StampCandidate``.

    Raises:
        CandidateNotFoundError: If the PepMLM ID is absent.
        AmpLibraryEmptyError: If no AMPs are available.
        BuildError: If assembly fails for any other reason.
    """
    # ---- 1. Resolve targeting peptide ------------------------------------
    pepmlm: PepMLMCandidate = _find_pepmlm_candidate(
        candidate_id, pepmlm_candidates
    )
    tp_seq = validate_sequence(pepmlm.generated_peptide, context="targeting peptide")

    # ---- 2. Select AMP killing domain ------------------------------------
    amp: AmpRecord = select_amp(amp_library, preferred_name=preferred_amp_name)
    amp_seq = validate_sequence(amp.clean_sequence, context="AMP killing domain")

    # ---- 3. Assemble sequences -------------------------------------------
    raw_full, display_full = assemble_stamp_sequence(
        tp_sequence=tp_seq,
        amp_sequence=amp_seq,
        linker=LINKER_SEQUENCE,
        terminal_mod=TERMINAL_MOD,
    )

    total_length = len(tp_seq) + LINKER_LENGTH + len(amp_seq)

    # ---- 4. Build domain objects -----------------------------------------
    targeting = TargetingDomain(
        name=pepmlm.candidate_id,
        sequence=tp_seq,
        length=len(tp_seq),
        net_charge=pepmlm.net_charge,
        gravy=pepmlm.GRAVY,
    )

    linker = LinkerDomain(
        name=LINKER_SEQUENCE,
        sequence=LINKER_SEQUENCE,
        length=LINKER_LENGTH,
    )

    killing = KillingDomain(
        name=amp.amp_name,
        sequence=amp_seq,
        length=len(amp_seq),
        net_charge=compute_net_charge(amp_seq),
        gravy=compute_gravy(amp_seq),
    )

    # ---- 5. Biophysical properties (partial) -----------------------------
    # v0.6d: pI, GRAVY-full, hydrophobicity_fraction are intentionally None.
    total_charge = pepmlm.net_charge + compute_net_charge(amp_seq)

    biophysical = BiophysicalProperties(
        length=total_length,
        net_charge=total_charge,
        pI=None,
        GRAVY=None,
        hydrophobicity_fraction=None,
    )

    # ---- 6. Placeholders (no fabrication) --------------------------------
    experimental = ExperimentalData()
    structure_status = StructureStatus()

    # Generate a deterministic STAMP candidate ID
    stamp_id = f"stamp_{pepmlm.candidate_id.lower()}"

    stamp = StampCandidate(
        candidate_id=stamp_id,
        target_molecule=pepmlm.target_name.replace("_", " "),
        targeting_domain=targeting,
        linker=linker,
        killing_domain=killing,
        orientation="N-to-C",
        terminal_modification=TERMINAL_MOD,
        raw_full_sequence=raw_full,
        display_full_sequence=display_full,
        is_complete=True,
        biophysical=biophysical,
        mock_scores=None,  # v0.6d: explicitly null
        experimental=experimental,
        structure_status=structure_status,
        validation_status=ValidationStatus.NOT_EXPERIMENTALLY_VALIDATED,
    )

    logger.info(
        "Built STAMP candidate %s (TP=%s, AMP=%s, len=%d)",
        stamp.candidate_id,
        targeting.name,
        killing.name,
        total_length,
    )
    return stamp
