"""
STAMP Platform — AMP Selection Service

Encapsulates the business rules for selecting an AMP from the priority
library.  The default strategy prefers P4; if P4 is absent it falls
back to the first available AMP with ``priority == high``.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.exceptions import AmpLibraryEmptyError, AmpNotFoundError
from app.models.schemas import AmpRecord, AmpRole, PriorityLevel

logger = logging.getLogger(__name__)

DEFAULT_AMP_NAME: str = "P4"


def select_amp(
    amp_library: list[dict[str, Any]],
    preferred_name: str | None = None,
) -> AmpRecord:
    """Select an AMP record from the loaded library.

    Business rules (in order):
        1. If *preferred_name* is given and exists → use it.
        2. Else if P4 exists → use P4.
        3. Else pick the first AMP with ``priority == high``.
        4. Else pick the very first AMP in the library.
        5. Else raise ``AmpLibraryEmptyError``.

    Args:
        amp_library: Raw dicts loaded from ``priority_amp_library.json``.
        preferred_name: Optional override (e.g. user-selected AMP).

    Returns:
        Parsed ``AmpRecord`` with ``clean_sequence`` guaranteed valid.

    Raises:
        AmpLibraryEmptyError: If the library contains no records.
        AmpNotFoundError: If *preferred_name* is specified but missing.
    """
    if not amp_library:
        raise AmpLibraryEmptyError()

    # Build a lookup map (by amp_name, case-insensitive)
    by_name: dict[str, dict[str, Any]] = {}
    for record in amp_library:
        name = str(record.get("ampName", record.get("amp_name", ""))).strip()
        if name:
            by_name[name.upper()] = record

    target_name = (preferred_name or DEFAULT_AMP_NAME).strip()

    raw_record: dict[str, Any] | None = None

    if preferred_name:
        raw_record = by_name.get(preferred_name.upper())
        if raw_record is None:
            raise AmpNotFoundError(preferred_name)
    else:
        # Strategy: P4 first
        raw_record = by_name.get("P4")
        if raw_record is None:
            # Fallback: first high-priority
            for record in amp_library:
                if record.get("priority", "").lower() == "high":
                    raw_record = record
                    break
            if raw_record is None:
                raw_record = amp_library[0]

    amp = AmpRecord.model_validate(raw_record)
    logger.info(
        "Selected AMP '%s' (priority=%s, role=%s)",
        amp.amp_name,
        amp.priority,
        amp.role,
    )
    return amp


def get_amp_by_name(
    amp_library: list[dict[str, Any]],
    name: str,
) -> AmpRecord:
    """Fetch a single AMP by exact name match.

    Args:
        amp_library: Raw dicts from the AMP library.
        name: Canonical AMP name (case-insensitive).

    Returns:
        Parsed ``AmpRecord``.

    Raises:
        AmpNotFoundError: If no matching AMP exists.
    """
    target = name.strip().upper()
    for record in amp_library:
        record_name = str(record.get("ampName", record.get("amp_name", ""))).strip().upper()
        if record_name == target:
            return AmpRecord.model_validate(record)
    raise AmpNotFoundError(name)


def list_amp_records(
    amp_library: list[dict[str, Any]],
) -> list[AmpRecord]:
    """Parse the entire AMP library into typed records.

    Args:
        amp_library: Raw dicts from the JSON file.

    Returns:
        List of validated ``AmpRecord`` objects.
    """
    return [AmpRecord.model_validate(r) for r in amp_library]
