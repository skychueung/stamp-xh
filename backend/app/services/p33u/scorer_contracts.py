"""P33U scientific scorer interface preparation for Lane D-min.

This module is ADDITIVE: it does NOT modify p33s/scorers.py. It provides
P33U-specific scorer contracts with stricter input validation and a
configurable, mock-only ESMFold HTTP interface.

Boundary rules (per P33U-C2):
- ESMFold: configurable HTTP scorer pointing at the existing 8189 service.
  Tests MUST mock; real HTTP calls are forbidden in zero-model validation.
  Default behavior returns unavailable_with_reason unless an explicit real
  transport is injected (Lane D only).
- PRODIGY: require a receptor-candidate-peptide COMPLEX PDB as input. If
  absent, return unavailable_with_reason. Never fabricate Kd.
- MM-GBSA: require topology (prmtop) AND trajectory files. If either is
  missing, return unavailable_with_reason. Never fabricate ΔG.
- MIC, ipTM: stay BLOCKED. No substitute algorithm, no fake value.

No checkpoint is loaded. No GPU is touched. No real HTTP call is made.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from .config import PREDICTION_TAG, VALIDATION_STATUS

# Default endpoint of the existing ESMFold folding service (port 8189).
# This is configuration ONLY — no call is made to it by this module.
DEFAULT_ESMFOLD_ENDPOINT = "http://127.0.0.1:8189"

# Statuses (mirror p33s conventions; P33U does not import p33s to stay additive).
STATUS_OK = "ok"
STATUS_UNAVAILABLE = "unavailable_with_reason"
STATUS_FAILED = "failed_with_evidence"
STATUS_NOT_APPLICABLE = "not_applicable"


@dataclass
class P33UScorerResult:
    metric: str  # plddt | iptm | kd | mic | mmgbsa
    status: str
    value: float | None = None
    unit: str = ""
    model_or_algorithm: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    log_path: str = ""
    validation_status: str = VALIDATION_STATUS
    prediction_tag: str = PREDICTION_TAG

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__}


# ---------------------------------------------------------------------------
# ESMFold HTTP transport abstraction
# ---------------------------------------------------------------------------
class HTTPTransport(Protocol):
    """Minimal transport protocol so tests can inject a mock.

    A real transport (Lane D only) would wrap requests.Session.post. This
    module never imports requests and never opens a socket.
    """

    def post(self, url: str, json_body: dict[str, Any], timeout: float) -> "HTTPResponse":
        ...


@dataclass
class HTTPResponse:
    status_code: int
    text: str
    json_data: dict[str, Any] | None = None


class MockTransport:
    """Test-only transport. Returns a canned pLDDT without any network."""

    def __init__(self, mean_plddt: float = 75.0, status_code: int = 200) -> None:
        self.mean_plddt = mean_plddt
        self.status_code = status_code
        self.calls: list[tuple[str, dict[str, Any], float]] = []

    def post(self, url: str, json_body: dict[str, Any], timeout: float) -> HTTPResponse:
        self.calls.append((url, json_body, timeout))
        payload = {"mean_plddt": self.mean_plddt, "structure_pdb": "FAKE"}
        return HTTPResponse(status_code=self.status_code, text=json.dumps(payload),
                            json_data=payload)


class ESMFoldHTTPScorer:
    """Configurable HTTP scorer for pLDDT via the existing 8189 ESMFold service.

    Zero-model safe: score() returns unavailable_with_reason UNLESS a real
    transport is explicitly injected. Tests inject MockTransport. No real
    HTTP call ever originates from this module's defaults.
    """

    def __init__(self, endpoint: str = DEFAULT_ESMFOLD_ENDPOINT,
                 timeout_seconds: float = 300.0) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def score(self, peptide_sequence: str, out_dir: str,
              transport: HTTPTransport | None = None) -> P33UScorerResult:
        """Return pLDDT via HTTP. Real call only if transport is non-None."""
        if transport is None:
            # Zero-model / pre-Lane-D default: never call 8189.
            return P33UScorerResult(
                metric="plddt", status=STATUS_UNAVAILABLE,
                model_or_algorithm="ESMFold_HTTP",
                detail={"reason": "no transport injected; real HTTP disabled "
                                  "in zero-model mode (set transport=MockTransport "
                                  "for tests, or a real transport at Lane D)",
                        "endpoint": self.endpoint},
            )
        if not peptide_sequence:
            return P33UScorerResult(
                metric="plddt", status=STATUS_FAILED,
                model_or_algorithm="ESMFold_HTTP",
                detail={"reason": "empty peptide_sequence"},
            )
        os.makedirs(out_dir, exist_ok=True)
        body = {"sequence": peptide_sequence}
        try:
            resp = transport.post(self.endpoint, body, self.timeout_seconds)
        except Exception as exc:  # pragma: no cover - transport-defined
            return P33UScorerResult(
                metric="plddt", status=STATUS_FAILED,
                model_or_algorithm="ESMFold_HTTP",
                detail={"reason": "transport error", "error": str(exc),
                        "endpoint": self.endpoint},
            )
        if resp.status_code != 200 or resp.json_data is None:
            return P33UScorerResult(
                metric="plddt", status=STATUS_FAILED,
                model_or_algorithm="ESMFold_HTTP",
                detail={"reason": "non-200 or empty body",
                        "status_code": resp.status_code, "endpoint": self.endpoint},
            )
        mean_plddt = resp.json_data.get("mean_plddt")
        if mean_plddt is None:
            return P33UScorerResult(
                metric="plddt", status=STATUS_FAILED,
                model_or_algorithm="ESMFold_HTTP",
                detail={"reason": "response missing mean_plddt",
                        "endpoint": self.endpoint},
            )
        return P33UScorerResult(
            metric="plddt", status=STATUS_OK, value=float(mean_plddt),
            unit="", model_or_algorithm="ESMFold_HTTP",
            detail={"endpoint": self.endpoint, "validation": VALIDATION_STATUS},
        )


# ---------------------------------------------------------------------------
# PRODIGY complex-PDB input validation
# ---------------------------------------------------------------------------
@dataclass
class ProdigyInputValidation:
    valid: bool
    complex_pdb: str
    errors: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)


def validate_prodigy_complex_pdb(complex_pdb: str) -> ProdigyInputValidation:
    """PRODIGY needs a receptor-candidate-peptide COMPLEX PDB. A bare peptide
    sequence or receptor-only PDB is insufficient. This validator enforces
    that the file exists, is non-empty, and contains ATOM records from more
    than one chain (receptor + peptide). Never fabricates Kd."""
    errors: list[str] = []
    checks: list[str] = []
    if not complex_pdb or not os.path.isfile(complex_pdb):
        errors.append(f"complex PDB missing: {complex_pdb!r}")
        return ProdigyInputValidation(False, complex_pdb, errors, checks)
    checks.append(f"exists:{complex_pdb}")
    if os.path.getsize(complex_pdb) == 0:
        errors.append("complex PDB is empty")
        return ProdigyInputValidation(False, complex_pdb, errors, checks)
    chains: set[str] = set()
    atom_lines = 0
    try:
        with open(complex_pdb, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith(("ATOM", "HETATM")):
                    atom_lines += 1
                    if len(line) > 21:
                        chains.add(line[21].strip())
    except OSError as exc:
        errors.append(f"read error: {exc}")
        return ProdigyInputValidation(False, complex_pdb, errors, checks)
    checks.append(f"atom_lines={atom_lines}")
    checks.append(f"chains={sorted(chains)}")
    if atom_lines == 0:
        errors.append("complex PDB has no ATOM/HETATM records")
    # A receptor-peptide complex must have >=2 chains (receptor + peptide).
    if len(chains) < 2:
        errors.append(
            f"complex PDB has {len(chains)} chain(s); PRODIGY requires a "
            f"receptor-peptide COMPLEX (>=2 chains). A receptor-only or "
            f"peptide-only PDB is not a valid PRODIGY input."
        )
    return ProdigyInputValidation(valid=not errors, complex_pdb=complex_pdb,
                                  errors=errors, checks=checks)


def score_kd_prodigy(complex_pdb: str) -> P33UScorerResult:
    """PRODIGY Kd scorer with mandatory complex-PDB precheck."""
    v = validate_prodigy_complex_pdb(complex_pdb)
    if not v.valid:
        return P33UScorerResult(
            metric="kd", status=STATUS_UNAVAILABLE,
            model_or_algorithm="PRODIGY",
            detail={"reason": "complex PDB validation failed",
                    "errors": v.errors, "checks": v.checks},
        )
    # Real PRODIGY invocation happens at Lane D via p33s_scorers env.
    # This interface only validates; it never fabricates a Kd value.
    return P33UScorerResult(
        metric="kd", status=STATUS_UNAVAILABLE,
        model_or_algorithm="PRODIGY",
        detail={"reason": "input valid; PRODIGY execution deferred to Lane D",
                "complex_pdb": complex_pdb, "checks": v.checks},
    )


# ---------------------------------------------------------------------------
# MM-GBSA topology / trajectory precheck
# ---------------------------------------------------------------------------
@dataclass
class MMGBSAAssetCheck:
    valid: bool
    prmtop: str
    trajectory: str
    errors: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)


def validate_mmgbsa_topology_trajectory(prmtop: str, trajectory: str) -> MMGBSAAssetCheck:
    """MM-GBSA via AmberTools MMPBSA.py requires a topology (prmtop) AND a
    trajectory. If either is missing, return unavailable_with_reason.
    Never fabricates a ΔG."""
    errors: list[str] = []
    checks: list[str] = []
    for label, path in (("prmtop", prmtop), ("trajectory", trajectory)):
        if not path or not os.path.isfile(path):
            errors.append(f"{label} missing: {path!r}")
        else:
            checks.append(f"{label}:exists")
            if os.path.getsize(path) == 0:
                errors.append(f"{label} is empty: {path}")
    return MMGBSAAssetCheck(valid=not errors, prmtop=prmtop, trajectory=trajectory,
                            errors=errors, checks=checks)


def score_mmgbsa(prmtop: str, trajectory: str) -> P33UScorerResult:
    """MM-GBSA scorer with mandatory topology+trajectory precheck."""
    v = validate_mmgbsa_topology_trajectory(prmtop, trajectory)
    if not v.valid:
        return P33UScorerResult(
            metric="mmgbsa", status=STATUS_UNAVAILABLE,
            model_or_algorithm="AmberTools MMPBSA.py",
            detail={"reason": "topology/trajectory precheck failed",
                    "errors": v.errors, "checks": v.checks},
        )
    return P33UScorerResult(
        metric="mmgbsa", status=STATUS_UNAVAILABLE,
        model_or_algorithm="AmberTools MMPBSA.py",
        detail={"reason": "assets present; MM-GBSA execution deferred to Lane D",
                "prmtop": prmtop, "trajectory": trajectory, "checks": v.checks},
    )


# ---------------------------------------------------------------------------
# MIC, ipTM — stay BLOCKED (no substitute, no fake value)
# ---------------------------------------------------------------------------
def score_mic() -> P33UScorerResult:
    """MIC predictor: BLOCKED. No validated MIC model exists on disk
    (scorer-models/p6f_mic_saureus_regressor/ is empty). No substitute
    algorithm, no heuristic, no fabricated value."""
    return P33UScorerResult(
        metric="mic", status=STATUS_UNAVAILABLE,
        model_or_algorithm="none",
        detail={"reason": "no validated MIC model on disk; "
                          "scorer-models/p6f_mic_saureus_regressor/ is empty. "
                          "Stays blocked until a licensed, validated MIC model "
                          "is provided by the user."},
    )


def score_iptm() -> P33UScorerResult:
    """ipTM (AF2-Multimer): BLOCKED. Requires AF2-Multimer params repair
    (params_model_1.npz monomer suspect broken; multimer_v3 present) plus a
    GPU window. No substitute, no fabricated ipTM value."""
    return P33UScorerResult(
        metric="iptm", status=STATUS_UNAVAILABLE,
        model_or_algorithm="AlphaFold2-Multimer",
        detail={"reason": "AF2-Multimer params require repair + GPU window. "
                          "Stays blocked. No substitute algorithm."},
    )
