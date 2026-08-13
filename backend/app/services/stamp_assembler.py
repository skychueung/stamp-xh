"""
STAMP Platform — STAMP Three-Part Assembler (v0.7-P1c)

Assembles a STAMP candidate from:
  - Targeting peptide (selected by user)
  - Linker (default EAAAK)
  - AMP killing domain (default P4)

Computes biophysical properties for the full sequence.
No ML, no database, no experimental validation.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from app.models.stamp_assembly import (
    AmpComponent,
    LinkerComponent,
    StampAssembleRequest,
    StampAssembleResponse,
    TargetingDomainComponent,
)
from app.services.biophys import (
    calculate_gravy,
    calculate_net_charge,
    calculate_pi,
    count_cys,
)


def assemble_stamp(request: StampAssembleRequest) -> dict:
    """Assemble a STAMP candidate and compute its properties.

    Returns a plain dict matching StampAssembleResponse shape.
    """
    tp_seq = request.targeting_peptide.sequence.upper().strip()
    linker_seq = request.linker.upper().strip()
    amp_seq = request.amp_sequence.upper().strip()
    terminal = request.terminal_modification.strip()

    raw_full = tp_seq + linker_seq + amp_seq
    display_full = raw_full + terminal

    length = len(raw_full)
    net_charge = calculate_net_charge(raw_full)
    pi = calculate_pi(raw_full)
    gravy = calculate_gravy(raw_full)
    cys = count_cys(raw_full)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    seq_hash = hashlib.md5(raw_full.encode()).hexdigest()[:6].upper()
    candidate_id = f"STAMP_V07_{ts}_{seq_hash}"
    created_at = datetime.now(timezone.utc).isoformat()

    response = StampAssembleResponse(
        code=200,
        message="success",
        mode="REAL_STAMP_ASSEMBLY_V0_7",
        validation_status="NOT_EXPERIMENTALLY_VALIDATED",
        candidate_id=candidate_id,
        created_at=created_at,
        targeting_domain=TargetingDomainComponent(
            name=request.targeting_peptide.candidate_id,
            sequence=tp_seq,
            length=len(tp_seq),
        ),
        linker=LinkerComponent(
            sequence=linker_seq,
            length=len(linker_seq),
        ),
        amp=AmpComponent(
            name=request.amp_name,
            sequence=amp_seq,
            length=len(amp_seq),
        ),
        raw_full_sequence=raw_full,
        display_full_sequence=display_full,
        length=length,
        net_charge=net_charge,
        pI=pi,
        GRAVY=gravy,
        cys_count=cys,
    )
    return response.model_dump()
