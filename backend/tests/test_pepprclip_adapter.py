"""Tests for the PepPrCLIP unified Model Registry adapter.

All tests are read-only and do not run PepPrCLIP inference. They verify that
probe, dry-run and submit behave according to the P6A safety gates.
"""
from __future__ import annotations


from app.schemas.model_registry import ModelDryRunPayload
from app.services.model_adapters.pepprclip_adapter import (
    PepPrCLIPAdapter,
    _parse_candidate_peptides,
    _parse_target_sequence,
)


def test_pepprclip_adapter_probe_is_read_only():
    """PepPrCLIP probe must not execute the model or generate rankings."""
    adapter = PepPrCLIPAdapter()
    result = adapter.probe()
    assert result.model_id == "pepprclip"
    assert result.status in ("PROBED", "INSTALLED", "DEGRADED", "UNAVAILABLE")
    assert result.safety_flags.executed_model is False
    assert result.safety_flags.is_scientific_result is False
    assert result.safety_flags.computational_prediction_only is True
    assert result.detail["real_run_enabled"] is False
    # P6A: MiniCLIP checkpoint should not be present, so weights_available is False
    assert result.detail.get("weights_available") is False


def test_pepprclip_adapter_dry_run_returns_command_preview():
    """PepPrCLIP dry-run must plan without execution and return a command preview."""
    adapter = PepPrCLIPAdapter()
    payload = ModelDryRunPayload(
        target_sequence=">target\nMKTAYIAKQRQIK",
        candidate_peptides="KRTAALLALIAT\nKKTKKLLFAIAL",
        top_k=2,
    )
    result = adapter.dry_run(payload)
    assert result.model_id == "pepprclip"
    assert result.status == "READY"
    assert result.safety_flags.executed_model is False
    assert result.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"
    assert result.command_preview
    cmd = " ".join(result.command_preview)
    assert "pepprclip_rank.py" in cmd
    assert "--checkpoint" in cmd
    assert "--candidates_csv" in cmd
    assert "output/ranking.csv" in result.artifacts
    assert "output/scores.json" in result.artifacts


def test_pepprclip_adapter_submit_blocked_by_default():
    """PepPrCLIP real submission must be blocked unless the gate is open."""
    adapter = PepPrCLIPAdapter()
    payload = ModelDryRunPayload(
        target_sequence=">target\nMKTAYIAKQRQIK",
        candidate_peptides="KRTAALLALIAT",
        top_k=1,
    )
    result = adapter.submit(payload)
    assert result.status == "BLOCKED"
    assert result.safety_flags.executed_model is False
    assert result.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"


def test_parse_target_sequence_from_fasta():
    """Target sequence parser should strip FASTA headers."""
    assert _parse_target_sequence(">target\nMKTAYIAKQRQIK") == "MKTAYIAKQRQIK"


def test_parse_candidate_peptides_from_list():
    """Candidate peptide parser should accept a list of sequences (API form)."""
    peptides = _parse_candidate_peptides(["KRTAALLALIAT", "KKTKKLLFAIAL"])
    assert peptides == ["KRTAALLALIAT", "KKTKKLLFAIAL"]


def test_parse_candidate_peptides_strips_non_letters():
    """Candidate peptide parser should remove separators and keep letters only per entry."""
    peptides = _parse_candidate_peptides("KRT-AA, LL|ALIAT")
    assert peptides == ["KRTAA", "LLALIAT"]


def test_pepprclip_adapter_dry_run_includes_checkpoint_status():
    """Dry-run message should mention checkpoint status when weights are missing."""
    adapter = PepPrCLIPAdapter()
    payload = ModelDryRunPayload(
        target_sequence=">target\nMKTAYIAKQRQIK",
        candidate_peptides=["AAAAAA", "GGGGGG"],
        top_k=2,
    )
    result = adapter.dry_run(payload)
    assert result.status == "READY"
    assert "checkpoint" in result.message.lower()
    assert result.env_preview.get("PEPPRCLIP_CHECKPOINT_EXISTS") in ("True", "False")


def test_pepprclip_adapter_dry_run_accepts_candidate_list():
    """Dry-run payload can pass candidate peptides as a list."""
    adapter = PepPrCLIPAdapter()
    payload = ModelDryRunPayload(
        target_sequence=">target\nMKTAYIAKQRQIK",
        candidate_peptides=["AAAAAA", "GGGGGG", "KKKKKK"],
        top_k=3,
    )
    result = adapter.dry_run(payload)
    assert result.status == "READY"
    assert result.safety_flags.executed_model is False
    assert "--top_k" in result.command_preview
    assert "3" in result.command_preview


def test_parse_candidate_peptides_from_multiline():
    """Candidate peptide parser should accept newline separated sequences."""
    peptides = _parse_candidate_peptides("KRTAALLALIAT\nKKTKKLLFAIAL")
    assert peptides == ["KRTAALLALIAT", "KKTKKLLFAIAL"]


def test_parse_candidate_peptides_from_comma_separated():
    """Candidate peptide parser should accept comma separated sequences."""
    peptides = _parse_candidate_peptides("KRTAALLALIAT, KKTKKLLFAIAL")
    assert peptides == ["KRTAALLALIAT", "KKTKKLLFAIAL"]


def test_pepprclip_registry_entry_is_not_real_run_enabled():
    """The registry entry must never advertise real_run_enabled in P6A."""
    from app.services.target_peptide_model_registry import get_model

    entry = get_model("pepprclip")
    assert entry is not None
    assert entry["real_run_enabled"] is False
    assert entry["supports_probe"] is True
    assert entry["supports_dry_run"] is True
    assert entry["supports_ranking"] is True
