"""
Tests for biophysics calculation service (biophys.py).

Covers:
  - GRAVY calculation
  - net_charge calculation
  - pI range reasonableness
  - Cys count / disulfide risk
  - Illegal character detection
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.biophys import (  # noqa: E402
    calculate_gravy,
    calculate_net_charge,
    calculate_pi,
    count_cys,
    disulfide_risk,
    hydrophobicity_class,
    validate_sequence,
)


class TestValidateSequence:
    def test_valid_sequence_uppercase(self):
        result = validate_sequence("ACDEFGHIKLMNPQRSTVWY")
        assert result == "ACDEFGHIKLMNPQRSTVWY"

    def test_valid_sequence_lowercase(self):
        result = validate_sequence("acdefghiklmnpqrstvwy")
        assert result == "ACDEFGHIKLMNPQRSTVWY"

    def test_illegal_character_raises(self):
        with pytest.raises(ValueError, match="illegal character"):
            validate_sequence("ACDXEF")

    def test_illegal_number_raises(self):
        with pytest.raises(ValueError, match="illegal character"):
            validate_sequence("ACD5EF")

    def test_empty_sequence_raises(self):
        with pytest.raises(ValueError, match="not be empty"):
            validate_sequence("")


class TestGRAVY:
    def test_known_hydrophobic(self):
        # Poly-isoleucine should be very hydrophobic (I=4.5)
        gravy = calculate_gravy("IIIIIIIIII")
        assert gravy == 4.5

    def test_known_hydrophilic(self):
        # Poly-arginine should be very hydrophilic (R=-4.5)
        gravy = calculate_gravy("RRRRRRRRRR")
        assert gravy == -4.5

    def test_mixed_sequence(self):
        # "DKTKKAFLIAAG" from test fixtures
        gravy = calculate_gravy("DKTKKAFLIAAG")
        # D=-3.5, K=-3.9, T=-0.7, K=-3.9, K=-3.9, A=1.8, F=2.8, L=3.8, I=4.5, A=1.8, A=1.8, G=-0.4
        # Sum = -3.5-3.9-0.7-3.9-3.9+1.8+2.8+3.8+4.5+1.8+1.8-0.4 = 0.2
        # /12 = 0.017
        assert pytest.approx(gravy, abs=0.05) == 0.017

    def test_empty_sequence_returns_zero(self):
        assert calculate_gravy("") == 0.0


class TestNetCharge:
    def test_poly_lysine_positive(self):
        # Poly-K at pH 7.0 should be strongly positive
        nc = calculate_net_charge("KKKKKKKKKK", ph=7.0)
        assert nc > 5.0

    def test_poly_aspartate_negative(self):
        # Poly-D at pH 7.0 should be strongly negative
        nc = calculate_net_charge("DDDDDDDDDD", ph=7.0)
        assert nc < -5.0

    def test_neutral_sequence(self):
        # Balanced sequence
        nc = calculate_net_charge("AGAGAGAGAG", ph=7.0)
        # Only N/C term contributions for neutral AAs
        assert -1.0 < nc < 1.0

    def test_oprf_window_charge(self):
        nc = calculate_net_charge("MKKTAIAIAIVAAGV", ph=7.0)
        # Expected: 2 Lys, 1 N-term → positive
        assert nc > 1.0

    def test_empty_sequence(self):
        assert calculate_net_charge("", ph=7.0) == 0.0


class TestPI:
    def test_pi_in_range(self):
        pi_val = calculate_pi("DKTKKAFLIAAG")
        assert 3.0 < pi_val < 12.0

    def test_poly_lysine_high_pi(self):
        pi_val = calculate_pi("KKKKKKKKKK")
        assert pi_val > 9.0

    def test_poly_aspartate_low_pi(self):
        pi_val = calculate_pi("DDDDDDDDDD")
        assert pi_val < 5.0

    def test_empty_sequence_defaults_to_7(self):
        assert calculate_pi("") == 7.0


class TestCysteine:
    def test_no_cys(self):
        assert count_cys("AGAGAGAGAG") == 0

    def test_one_cys(self):
        assert count_cys("AGCAGAGAG") == 1

    def test_two_cys(self):
        assert count_cys("AGCCAGAGAG") == 2

    def test_case_insensitive(self):
        assert count_cys("agcagc") == 2


class TestDisulfideRisk:
    def test_none_risk(self):
        assert disulfide_risk(0) == "none"

    def test_single_cys_risk(self):
        assert disulfide_risk(1) == "single_cys"

    def test_potential_disulfide_risk(self):
        assert disulfide_risk(2) == "potential_disulfide"
        assert disulfide_risk(5) == "potential_disulfide"


class TestHydrophobicityClass:
    def test_hydrophobic(self):
        assert hydrophobicity_class(0.8) == "hydrophobic"

    def test_hydrophilic(self):
        assert hydrophobicity_class(-0.8) == "hydrophilic"

    def test_neutral(self):
        assert hydrophobicity_class(0.0) == "neutral"
        assert hydrophobicity_class(0.3) == "neutral"
        assert hydrophobicity_class(-0.3) == "neutral"
