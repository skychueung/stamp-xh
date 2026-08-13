"""EvoBind2 fail-closed real-run gate (Phase 8).

The gate is a temporary JSON file that must be explicitly created by an
authorized operator for each run.  Without a valid gate file, all real
execution paths remain CLOSED.

Gate rules (fail-closed):
  - Default state: CLOSED (no gate file or gate file invalid).
  - Content must be exactly {"enabled": true, ...}; any other value is closed.
  - Gate is bound to a single run_id.
  - Gate carries created_at / expires_at timestamps; outside this window is closed.
  - Symlinks, path traversal, wrong owner, or unsafe permissions are rejected.
  - On timeout or unhandled exception during a run, the gate is cleared.

This module performs NO subprocess calls, NO HHblits searches, NO AlphaFold2
forward passes, and NO artifact creation during import or gate validation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Safe run_id charset: alphanumeric, hyphen, underscore, dot.  No path chars.
RUN_ID_SAFE_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
MAX_RUN_ID_LEN = 128

# Gate filename template.  run_id is embedded in the filename for binding.
GATE_FILENAME_TEMPLATE = "evobind2_run_gate_{run_id}.json"

# Default gate root.  Fixed, auditable path on the STAMP server.
# Overridable ONLY via EVOBIND2_GATE_ROOT env var for explicit operator override;
# tests must inject gate_root via the function arguments instead of env vars.
DEFAULT_GATE_ROOT = Path("/home/xh/kxc/stampup/run_gates/evobind2")

# Production code must never fall back to these roots.
_FORBIDDEN_GATE_ROOT_PREFIXES = ("/tmp", "/root", "/home/xh")

# Maximum gate lifetime; operator may set shorter.
DEFAULT_GATE_TTL_SECONDS = 3600  # 1 hour
MAX_GATE_TTL_SECONDS = 24 * 3600  # 24 hours

# Required gate schema keys
REQUIRED_GATE_KEYS = {"enabled", "run_id", "created_at", "expires_at", "authorized_by"}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GateError(Exception):
    """Base exception for gate validation failures."""

    def __init__(self, reason: str, closed: bool = True) -> None:
        self.reason = reason
        self.closed = closed
        super().__init__(reason)


class GateClosedError(GateError):
    """Gate is closed or missing."""


class GateInvalidError(GateError):
    """Gate exists but is malformed, expired, or not bound to this run_id."""


class GatePathUnsafeError(GateError):
    """Gate path fails symlink / traversal / owner / permission checks."""


# ---------------------------------------------------------------------------
# run_id validation
# ---------------------------------------------------------------------------


def validate_run_id(run_id: str) -> tuple[bool, str | None]:
    """Validate run_id for safe filesystem and logging use.

    Rules:
      - non-empty string
      - length <= MAX_RUN_ID_LEN
      - only [A-Za-z0-9._-]
      - no path separators or traversal sequences
      - not a reserved name
    """
    if not isinstance(run_id, str) or not run_id:
        return False, "run_id must be a non-empty string"
    if len(run_id) > MAX_RUN_ID_LEN:
        return False, f"run_id exceeds max length {MAX_RUN_ID_LEN}"
    if not RUN_ID_SAFE_PATTERN.match(run_id):
        return False, (
            "run_id contains unsafe characters; allowed: "
            "alphanumeric, hyphen, underscore, dot"
        )
    lower = run_id.lower()
    reserved = {"", ".", "..", "con", "prn", "aux", "nul"}
    if lower in reserved:
        return False, f"run_id '{run_id}' is reserved"
    if any(lower.startswith(r + ".") for r in {"con", "prn", "aux", "nul"}):
        return False, f"run_id '{run_id}' uses a reserved Windows device name prefix"
    return True, None


def sanitize_run_id(run_id: str) -> str:
    """Return run_id if valid; otherwise raise GateInvalidError."""
    ok, error = validate_run_id(run_id)
    if not ok:
        raise GateInvalidError(error or "invalid run_id")
    return run_id


# ---------------------------------------------------------------------------
# Gate path resolution
# ---------------------------------------------------------------------------


def _is_forbidden_gate_root(path: Path) -> bool:
    """Return True if an env-var override points to a forbidden fallback root.

    The fixed DEFAULT_GATE_ROOT is always allowed.  Generic fallbacks such as
    /tmp, /root, or the user's home directory (/home/xh) are forbidden.
    Comparisons use POSIX-style paths so the check is deterministic across
    Windows and Unix.  A Windows drive letter (e.g. "D:") is ignored.
    """
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        return True
    allowed = DEFAULT_GATE_ROOT.resolve()
    try:
        if resolved == allowed or resolved.is_relative_to(allowed):
            return False
    except (OSError, RuntimeError, AttributeError):
        pass
    resolved_posix = resolved.as_posix()
    # Strip optional Windows drive letter so "D:/tmp" is treated as "/tmp".
    normalized = re.sub(r"^[A-Za-z]:", "", resolved_posix)
    for prefix in _FORBIDDEN_GATE_ROOT_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return True
    return False


def _get_gate_root() -> Path:
    """Return the configured gate root directory.

    Production code never falls back to /tmp, /root, or generic /home/xh.
    Only the fixed DEFAULT_GATE_ROOT or an explicit operator override that
    survives the forbidden-prefix check is returned.
    """
    env_root = os.environ.get("EVOBIND2_GATE_ROOT")
    if env_root:
        candidate = Path(env_root).resolve()
        if _is_forbidden_gate_root(candidate):
            raise GatePathUnsafeError(
                f"EVOBIND2_GATE_ROOT points to a forbidden root: {candidate}"
            )
        return candidate
    return DEFAULT_GATE_ROOT.resolve()


def _gate_path_for_run_id(run_id: str, gate_root: Path | None = None) -> Path:
    """Return the resolved gate file path for a run_id."""
    sanitized = sanitize_run_id(run_id)
    root = (gate_root or _get_gate_root()).resolve()
    return (root / GATE_FILENAME_TEMPLATE.format(run_id=sanitized)).resolve()


def _verify_safe_gate_path(
    gate_path: Path,
    gate_root: Path,
    expected_owner_uid: int | None = None,
    max_permissions: int = 0o644,
) -> None:
    """Verify gate path is safe: real file, under root, not symlink, safe perms.

    Raises GatePathUnsafeError on any failure.
    """
    try:
        resolved = gate_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise GatePathUnsafeError(f"gate path cannot be resolved: {exc}")

    root_resolved = gate_root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise GatePathUnsafeError(
            f"gate path {resolved} escapes gate root {root_resolved}"
        ) from exc

    # Symlink check: lstat must point to same place as stat, or be a regular file.
    try:
        lstat = os.lstat(resolved)
    except OSError as exc:
        raise GatePathUnsafeError(f"cannot lstat gate file: {exc}")

    if stat.S_ISLNK(lstat.st_mode):
        raise GatePathUnsafeError("gate file is a symlink")
    if not stat.S_ISREG(lstat.st_mode):
        raise GatePathUnsafeError("gate file is not a regular file")

    # Owner check (Unix only)
    if expected_owner_uid is not None and hasattr(os, "getuid"):
        if lstat.st_uid != expected_owner_uid:
            raise GatePathUnsafeError(
                f"gate file owner uid {lstat.st_uid} != expected {expected_owner_uid}"
            )

    # Permission check: reject overly permissive files (Unix only).
    mode = stat.S_IMODE(lstat.st_mode)
    if os.name != "nt" and mode & ~max_permissions:
        raise GatePathUnsafeError(
            f"gate file permissions {oct(mode)} exceed max {oct(max_permissions)}"
        )


# ---------------------------------------------------------------------------
# Gate content validation
# ---------------------------------------------------------------------------


def _parse_iso_timestamp(value: str) -> datetime:
    """Parse ISO 8601 timestamp with timezone."""
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise GateInvalidError(f"invalid ISO timestamp: {value}") from exc
    if dt.tzinfo is None:
        raise GateInvalidError(f"timestamp must be timezone-aware: {value}")
    return dt


def _validate_gate_content(
    data: Any,
    run_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate parsed gate JSON content.

    Requirements:
      - dict with required keys
      - enabled is exactly True (bool)
      - run_id matches
      - created_at <= now <= expires_at
    """
    if not isinstance(data, dict):
        raise GateInvalidError("gate content is not a JSON object")

    # enabled must be exactly boolean True before checking other keys.
    enabled = data.get("enabled")
    if enabled is not True:
        raise GateInvalidError(f"gate enabled must be boolean true, got {enabled!r}")

    missing = REQUIRED_GATE_KEYS - set(data.keys())
    if missing:
        raise GateInvalidError(f"gate missing required keys: {sorted(missing)}")

    gate_run_id = data.get("run_id")
    if gate_run_id != run_id:
        raise GateInvalidError(
            f"gate run_id mismatch: expected '{run_id}', got '{gate_run_id}'"
        )

    now = now or datetime.now(timezone.utc)
    try:
        created_at = _parse_iso_timestamp(data["created_at"])
        expires_at = _parse_iso_timestamp(data["expires_at"])
    except GateInvalidError:
        raise

    if now < created_at:
        raise GateInvalidError(f"gate not yet valid (created_at={created_at})")
    if now > expires_at:
        raise GateInvalidError(f"gate expired at {expires_at}")

    return {
        "enabled": True,
        "run_id": gate_run_id,
        "created_at": created_at,
        "expires_at": expires_at,
        "authorized_by": data.get("authorized_by"),
        "purpose": data.get("purpose"),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateStatus:
    """Result of a gate check."""

    open_: bool  # 'open' is a builtin; use open_
    reason: str
    run_id: str
    authorized_by: str | None = None
    expires_at: datetime | None = None

    @property
    def closed(self) -> bool:
        return not self.open_


def check_run_gate(
    run_id: str,
    gate_root: Path | None = None,
    expected_owner_uid: int | None = None,
    now: datetime | None = None,
) -> GateStatus:
    """Check whether a fail-closed gate exists and is valid for run_id.

    Returns GateStatus(open_=True) only when all checks pass.
    Any failure returns GateStatus(open_=False) with a reason.
    """
    try:
        gate_path = _gate_path_for_run_id(run_id, gate_root)
        root = (gate_root or _get_gate_root()).resolve()
        _verify_safe_gate_path(gate_path, root, expected_owner_uid)

        try:
            with open(gate_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise GateInvalidError(f"gate file is not valid JSON: {exc}")
        except OSError as exc:
            raise GateClosedError(f"cannot read gate file: {exc}")

        info = _validate_gate_content(data, run_id, now=now)
        return GateStatus(
            open_=True,
            reason="gate open",
            run_id=run_id,
            authorized_by=info.get("authorized_by"),
            expires_at=info.get("expires_at"),
        )
    except GateError as exc:
        logger.warning("EvoBind2 gate closed for run_id=%s: %s", run_id, exc.reason)
        return GateStatus(open_=False, reason=exc.reason, run_id=run_id)


def require_run_gate(
    run_id: str,
    gate_root: Path | None = None,
    expected_owner_uid: int | None = None,
    now: datetime | None = None,
) -> GateStatus:
    """Like check_run_gate but raises GateClosedError if the gate is closed."""
    status = check_run_gate(run_id, gate_root, expected_owner_uid, now)
    if status.closed:
        raise GateClosedError(status.reason)
    return status


def create_run_gate(
    run_id: str,
    authorized_by: str,
    purpose: str,
    ttl_seconds: int = DEFAULT_GATE_TTL_SECONDS,
    gate_root: Path | None = None,
    now: datetime | None = None,
) -> Path:
    """Create a new gate file for an authorized run.

    This is the ONLY supported way to open the gate.  The caller (operator)
    must explicitly supply run_id, authorized_by, and purpose.
    """
    sanitized = sanitize_run_id(run_id)
    if not isinstance(authorized_by, str) or not authorized_by.strip():
        raise GateInvalidError("authorized_by must be a non-empty string")
    if not isinstance(purpose, str) or not purpose.strip():
        raise GateInvalidError("purpose must be a non-empty string")

    if ttl_seconds <= 0 or ttl_seconds > MAX_GATE_TTL_SECONDS:
        raise GateInvalidError(
            f"ttl_seconds must be between 1 and {MAX_GATE_TTL_SECONDS}"
        )

    root = (gate_root or _get_gate_root()).resolve()
    # Create root with restricted permissions; if it already exists, enforce 0700.
    root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(root, 0o700)
    except (OSError, AttributeError):
        pass

    now = now or datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)

    gate_path = root / GATE_FILENAME_TEMPLATE.format(run_id=sanitized)
    content = {
        "enabled": True,
        "run_id": sanitized,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "authorized_by": authorized_by.strip(),
        "purpose": purpose.strip(),
    }

    # Write atomically to avoid readers seeing partial JSON.
    tmp_path = gate_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(content, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, gate_path)
    except OSError as exc:
        raise GateInvalidError(f"failed to write gate file: {exc}")
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass

    # Restrict permissions (Unix).  Ignore errors on Windows.
    try:
        os.chmod(gate_path, 0o600)
    except (OSError, AttributeError):
        pass

    logger.info("EvoBind2 gate created for run_id=%s at %s", sanitized, gate_path)
    return gate_path


def close_run_gate(
    run_id: str,
    gate_root: Path | None = None,
) -> bool:
    """Safely close (delete) a gate file for a run_id.

    Returns True if a gate file existed and was removed, False otherwise.
    Path-safety checks are applied before deletion.
    """
    try:
        gate_path = _gate_path_for_run_id(run_id, gate_root)
        root = (gate_root or _get_gate_root()).resolve()
        _verify_safe_gate_path(gate_path, root)
    except GateClosedError:
        # Already closed (missing file) — treat as success.
        return False
    except GateError as exc:
        logger.warning("Cannot safely close gate for run_id=%s: %s", run_id, exc.reason)
        return False

    try:
        gate_path.unlink()
        logger.info("EvoBind2 gate closed for run_id=%s", run_id)
        return True
    except OSError as exc:
        logger.warning("Failed to close gate for run_id=%s: %s", run_id, exc)
        return False


@contextmanager
def run_gate_context(
    run_id: str,
    gate_root: Path | None = None,
    expected_owner_uid: int | None = None,
    close_on_exit: bool = False,
):
    """Context manager that validates the gate before yielding.

    If close_on_exit is True, the gate is closed in the finally block.
    If an unhandled exception occurs and close_on_exit is True, the gate is
    also closed, ensuring timeout/exception finally semantics.
    """
    status = require_run_gate(run_id, gate_root, expected_owner_uid)
    try:
        yield status
    finally:
        if close_on_exit:
            close_run_gate(run_id, gate_root)


def build_authorized_gate_path(run_id: str, gate_root: Path | None = None) -> Path:
    """Return the expected gate path for an authorized run (for operator docs)."""
    return _gate_path_for_run_id(run_id, gate_root)
