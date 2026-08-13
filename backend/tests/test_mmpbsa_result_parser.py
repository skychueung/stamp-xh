"""
test_mmpbsa_result_parser.py
----------------------------
Tests for MMPBSA result parser.

Scientific boundary checks:
- Pilot results must never set official_mm_gbsa_delta_g.
- Missing values must be None, not invented.
- Non-existent files must return BLOCKED status.
- Output files must be based ONLY on real parsed data.
"""

import csv
import json
import tempfile
from pathlib import Path

import pytest

from app.services.mmpbsa_result_parser import (
    parse_mmpbsa_result,
    parse_mmpbsa_dat,
    to_dict,
    get_mmgbsa_components,
    write_mmgbsa_summary_json,
    write_mmgbsa_components_csv,
)

# Fixture: actual Server P2b MMPBSA output (abbreviated but structurally complete)
SAMPLE_PILOT_RESULT = """| Run on Mon May 11 22:50:05 2026
|
|Input file:
|--------------------------------------------------------------
|MMPBSA Pilot Input
|&general
|  startframe=1,
|  endframe=100,
|  interval=1,
|  verbose=1,
|  keep_files=2,
|/
|&gb
|  igb=5,
|  saltcon=0.150,
|/
|--------------------------------------------------------------
|MMPBSA.py Version=14.0
|Solvated complex topology file:  /home/xh/kxc/v013_p2b_server_100ps_pilot/run/solvated_complex.prmtop
|Complex topology file:           /home/xh/kxc/v013_p2b_server_100ps_pilot/topo/complex.prmtop
|Receptor topology file:          /home/xh/kxc/v013_p2b_server_100ps_pilot/topo/receptor.prmtop
|Ligand topology file:            /home/xh/kxc/v013_p2b_server_100ps_pilot/topo/peptide.prmtop
|Initial mdcrd(s):                /home/xh/kxc/v013_p2b_server_100ps_pilot/run/production_stripped.mdcrd
|
|Receptor mask:                  ":1-100"
|Ligand mask:                    ":101-115"
|
|Calculations performed using 7.0 complex frames.
|
|Generalized Born ESURF calculated using 'LCPO' surface areas
|
|All units are reported in kcal/mole.
-------------------------------------------------------------------------------
-------------------------------------------------------------------------------

GENERALIZED BORN:

Complex:
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
EGB                     -24045.5663                0.0000              0.0000
ESURF                      352.8881                0.0000              0.0000

G gas                        0.0000                0.0000              0.0000
G solv                  -23692.6782                0.0000              0.0000

TOTAL                   -23692.6782                0.0000              0.0000


Receptor:
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
EGB                     -20802.9270                0.0003              0.0001
ESURF                      305.4760                0.0000              0.0000

G gas                        0.0000                0.0000              0.0000
G solv                  -20497.4510                0.0002              0.0001

TOTAL                   -20497.4510                0.0002              0.0001


Ligand:
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
EGB                      -3242.6392                0.0000              0.0000
ESURF                       47.4120                0.0000              0.0000

G gas                        0.0000                0.0000              0.0000
G solv                   -3195.2272                0.0000              0.0000

TOTAL                    -3195.2272                0.0000              0.0000


Differences (Complex - Receptor - Ligand):
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
VDWAALS                      0.0000                0.0000              0.0000
EEL                          0.0000                0.0000              0.0000
EGB                         -0.0001                0.0000              0.0000
ESURF                       -0.0000                0.0000              0.0000

DELTA G gas                  0.0000                0.0000              0.0000
DELTA G solv                -0.0001                0.0000              0.0000

DELTA TOTAL                 -0.0001                0.0000              0.0000


-------------------------------------------------------------------------------
-------------------------------------------------------------------------------
"""

SAMPLE_PRODUCTION_RESULT = """| Run on Mon May 12 10:00:00 2026
|
|MMPBSA.py Version=14.0
|Calculations performed using 500.0 complex frames.
|
|Generalized Born ESURF calculated using 'LCPO' surface areas
|
|All units are reported in kcal/mole.
-------------------------------------------------------------------------------
-------------------------------------------------------------------------------

GENERALIZED BORN:

Complex:
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
VDWAALS                   -123.4567               10.1234              1.2345
EEL                       -456.7890               20.5678              2.5678
EGB                     -24045.5663                0.0000              0.0000
ESURF                      352.8881                0.0000              0.0000

G gas                     -580.2457               15.3456              1.8765
G solv                  -23692.6782                0.0000              0.0000

TOTAL                   -23692.6782                0.0000              0.0000


Receptor:
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
VDWAALS                   -100.0000                8.0000              1.0000
EEL                       -400.0000               18.0000              2.0000
EGB                     -20802.9270                0.0003              0.0001
ESURF                      305.4760                0.0000              0.0000

G gas                     -500.0000               12.0000              1.5000
G solv                  -20497.4510                0.0002              0.0001

TOTAL                   -20497.4510                0.0002              0.0001


Ligand:
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
VDWAALS                    -15.0000                2.0000              0.3000
EEL                        -50.0000                5.0000              0.7000
EGB                      -3242.6392                0.0000              0.0000
ESURF                       47.4120                0.0000              0.0000

G gas                      -65.0000                4.0000              0.5000
G solv                   -3195.2272                0.0000              0.0000

TOTAL                    -3195.2272                0.0000              0.0000


Differences (Complex - Receptor - Ligand):
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
VDWAALS                     -8.4567                3.1234              0.4567
EEL                         -6.7890                4.5678              0.5678
EGB                         -0.0001                0.0000              0.0000
ESURF                       -0.0000                0.0000              0.0000

DELTA G gas                -15.2457                5.3456              0.8765
DELTA G solv                -0.0001                0.0000              0.0000

DELTA TOTAL                -15.2458                5.3456              0.8765


-------------------------------------------------------------------------------
-------------------------------------------------------------------------------
"""

SAMPLE_WITH_DECOMP = """| Run on Mon May 12 10:00:00 2026
|MMPBSA.py Version=14.0
|Calculations performed using 500.0 complex frames.
|All units are reported in kcal/mole.

GENERALIZED BORN:

Complex:
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
EGB                     -24045.5663                0.0000              0.0000
ESURF                      352.8881                0.0000              0.0000
G gas                        0.0000                0.0000              0.0000
G solv                  -23692.6782                0.0000              0.0000
TOTAL                   -23692.6782                0.0000              0.0000

Receptor:
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
EGB                     -20802.9270                0.0003              0.0001
ESURF                      305.4760                0.0000              0.0000
G gas                        0.0000                0.0000              0.0000
G solv                  -20497.4510                0.0002              0.0001
TOTAL                   -20497.4510                0.0002              0.0001

Ligand:
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
EGB                      -3242.6392                0.0000              0.0000
ESURF                       47.4120                0.0000              0.0000
G gas                        0.0000                0.0000              0.0000
G solv                   -3195.2272                0.0000              0.0000
TOTAL                    -3195.2272                0.0000              0.0000

Differences (Complex - Receptor - Ligand):
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
VDWAALS                      0.0000                0.0000              0.0000
EEL                          0.0000                0.0000              0.0000
EGB                         -0.0001                0.0000              0.0000
ESURF                       -0.0000                0.0000              0.0000
DELTA G gas                  0.0000                0.0000              0.0000
DELTA G solv                -0.0001                0.0000              0.0000
DELTA TOTAL                 -0.0001                0.0000              0.0000

-------------------------------------------------------------------------------
-------------------------------------------------------------------------------

DECOMP MM-GBSA:

Residue 1:
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
Internal                       1.2345                0.1000              0.0100
VDWAALS                       -2.3456                0.2000              0.0200
EEL                           -3.4567                0.3000              0.0300
EGB                           -4.5678                0.4000              0.0400
ESURF                          0.5678                0.0500              0.0050
G gas                         -4.5678                0.3000              0.0300
G solv                        -4.0000                0.3500              0.0350
TOTAL                         -8.5678                0.4000              0.0400

Residue 2:
Energy Component            Average              Std. Dev.   Std. Err. of Mean
-------------------------------------------------------------------------------
Internal                       0.5000                0.0500              0.0050
VDWAALS                       -1.0000                0.1000              0.0100
EEL                           -1.5000                0.1500              0.0150
EGB                           -2.0000                0.2000              0.0200
ESURF                          0.2000                0.0200              0.0020
G gas                         -2.0000                0.1500              0.0150
G solv                        -1.8000                0.1800              0.0180
TOTAL                         -3.8000                0.2000              0.0200
"""


def test_parse_existing_pilot_file():
    """Parse the sample pilot result and verify all fields."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False) as f:
        f.write(SAMPLE_PILOT_RESULT)
        tmp_path = f.name

    result = parse_mmpbsa_result(tmp_path, run_type_hint="PILOT")

    assert result.status == "SUCCESS"
    assert result.source_file == tmp_path
    assert result.parser_version == "0.2.0"
    assert result.run_type == "PILOT"
    assert result.convergence_status == "PILOT_ONLY"
    assert result.frames_used == 7
    assert result.pilot_delta_total_kcal_mol == pytest.approx(-0.0001)
    assert result.pilot_delta_gb_kcal_mol is None  # Not extracted separately in this version
    assert result.official_mm_gbsa_delta_g is None

    # Energy terms
    assert "complex" in result.energy_terms
    assert "receptor" in result.energy_terms
    assert "ligand" in result.energy_terms
    assert "delta" in result.energy_terms
    assert result.energy_terms["complex"]["TOTAL"] == pytest.approx(-23692.6782)
    assert result.energy_terms["receptor"]["TOTAL"] == pytest.approx(-20497.4510)
    assert result.energy_terms["ligand"]["TOTAL"] == pytest.approx(-3195.2272)
    assert result.energy_terms["delta"]["DELTA_TOTAL"] == pytest.approx(-0.0001)

    # Warnings
    assert any("G gas = 0" in w for w in result.warnings)
    assert any("7 frames" in w for w in result.warnings)
    assert any("official_mm_gbsa_delta_g remains null" in w for w in result.warnings)

    Path(tmp_path).unlink()


def test_official_delta_g_is_null_for_pilot():
    """Hard boundary: pilot results must never set official_mm_gbsa_delta_g."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False) as f:
        f.write(SAMPLE_PILOT_RESULT)
        tmp_path = f.name

    result = parse_mmpbsa_result(tmp_path, run_type_hint="PILOT")
    assert result.official_mm_gbsa_delta_g is None
    assert result.convergence_status == "PILOT_ONLY"
    Path(tmp_path).unlink()


def test_official_delta_g_is_null_for_smoke():
    """Hard boundary: smoke results must never set official_mm_gbsa_delta_g."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False) as f:
        f.write(SAMPLE_PILOT_RESULT)
        tmp_path = f.name

    result = parse_mmpbsa_result(tmp_path, run_type_hint="SMOKE")
    assert result.official_mm_gbsa_delta_g is None
    assert result.convergence_status == "SMOKE_ONLY"
    Path(tmp_path).unlink()


def test_missing_file_returns_blocked():
    """If source file is missing, return BLOCKED rather than fabricating data."""
    result = parse_mmpbsa_result("/nonexistent/path/FINAL_RESULTS_MMPBSA_PILOT.dat")
    assert result.status == "BLOCKED"
    assert result.warnings
    assert "not found" in result.warnings[0].lower()
    assert result.official_mm_gbsa_delta_g is None


def test_to_dict_serializes_correctly():
    """Verify dict serialization is JSON-safe."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False) as f:
        f.write(SAMPLE_PILOT_RESULT)
        tmp_path = f.name

    result = parse_mmpbsa_result(tmp_path, run_type_hint="PILOT")
    d = to_dict(result)

    # Must be JSON serializable
    json_str = json.dumps(d, indent=2)
    assert json_str
    assert d["official_mm_gbsa_delta_g"] is None
    assert d["convergence_status"] == "PILOT_ONLY"
    assert "decomposition" in d

    Path(tmp_path).unlink()


def test_auto_detect_run_type_from_path():
    """Run type should be auto-detected from file path if no hint given."""
    with tempfile.NamedTemporaryFile(mode="w", suffix="_pilot.dat", delete=False) as f:
        f.write(SAMPLE_PILOT_RESULT)
        tmp_path = f.name

    result = parse_mmpbsa_result(tmp_path)
    assert result.run_type == "PILOT"
    Path(tmp_path).unlink()


def test_parse_mmpbsa_dat_alias():
    """parse_mmpbsa_dat must be an alias for parse_mmpbsa_result."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False) as f:
        f.write(SAMPLE_PILOT_RESULT)
        tmp_path = f.name

    result = parse_mmpbsa_dat(tmp_path, run_type_hint="PILOT")
    assert result.status == "SUCCESS"
    assert result.run_type == "PILOT"
    Path(tmp_path).unlink()


def test_get_mmgbsa_components_maps_terms():
    """User-friendly component mapping must reflect real parsed values."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False) as f:
        f.write(SAMPLE_PRODUCTION_RESULT)
        tmp_path = f.name

    result = parse_mmpbsa_result(tmp_path, run_type_hint="PRODUCTION")
    components = get_mmgbsa_components(result)

    assert components["delta_g_total"] == pytest.approx(-15.2458)
    assert components["vdw"] == pytest.approx(-8.4567)
    assert components["electrostatic"] == pytest.approx(-6.7890)
    assert components["polar_solvation"] == pytest.approx(-0.0001)
    assert components["nonpolar_solvation"] == pytest.approx(-0.0000)
    Path(tmp_path).unlink()


def test_write_mmgbsa_summary_json():
    """Summary JSON must be written and contain real parsed data only."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False) as f:
        f.write(SAMPLE_PRODUCTION_RESULT)
        tmp_path = f.name

    result = parse_mmpbsa_result(tmp_path, run_type_hint="PRODUCTION")
    out_dir = tempfile.mkdtemp()
    path = write_mmgbsa_summary_json(result, out_dir)

    assert path.exists()
    assert path.name == "mmgbsa_summary.json"

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "SUCCESS"
    assert data["run_type"] == "PRODUCTION"
    assert data["delta_g_total"] == pytest.approx(-15.2458)
    assert data["components"]["vdW"] == pytest.approx(-8.4567)
    assert data["components"]["electrostatic"] == pytest.approx(-6.7890)
    assert data["components"]["polar_solvation"] == pytest.approx(-0.0001)
    assert data["components"]["nonpolar_solvation"] == pytest.approx(-0.0000)
    assert data["decomposition_available"] is False

    Path(tmp_path).unlink()
    import shutil
    shutil.rmtree(out_dir)


def test_write_mmgbsa_components_csv():
    """Components CSV must be written and contain real parsed data only."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False) as f:
        f.write(SAMPLE_PRODUCTION_RESULT)
        tmp_path = f.name

    result = parse_mmpbsa_result(tmp_path, run_type_hint="PRODUCTION")
    out_dir = tempfile.mkdtemp()
    path = write_mmgbsa_components_csv(result, out_dir)

    assert path.exists()
    assert path.name == "mmgbsa_components.csv"

    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    {r["section"]: r for r in rows}
    assert "delta" in {r["section"] for r in rows}
    delta_total_row = [r for r in rows if r["section"] == "delta" and r["term"] == "DELTA_TOTAL"][0]
    assert float(delta_total_row["value_kcal_mol"]) == pytest.approx(-15.2458)

    Path(tmp_path).unlink()
    import shutil
    shutil.rmtree(out_dir)


def test_decomposition_parsing():
    """Decomposition results must be parsed when present."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False) as f:
        f.write(SAMPLE_WITH_DECOMP)
        tmp_path = f.name

    result = parse_mmpbsa_result(tmp_path, run_type_hint="PRODUCTION")
    assert len(result.decomposition) == 2
    assert result.decomposition[0]["residue"] == "1"
    assert result.decomposition[0]["TOTAL"] == pytest.approx(-8.5678)
    assert result.decomposition[1]["residue"] == "2"
    assert result.decomposition[1]["TOTAL"] == pytest.approx(-3.8000)

    Path(tmp_path).unlink()


def test_decomposition_written_to_csv():
    """Decomposition rows must appear in components CSV."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False) as f:
        f.write(SAMPLE_WITH_DECOMP)
        tmp_path = f.name

    result = parse_mmpbsa_result(tmp_path, run_type_hint="PRODUCTION")
    out_dir = tempfile.mkdtemp()
    path = write_mmgbsa_components_csv(result, out_dir)

    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    decomp_rows = [r for r in rows if r["section"].startswith("decomp_")]
    assert len(decomp_rows) > 0
    assert any(r["section"] == "decomp_1" and r["term"] == "TOTAL" for r in decomp_rows)

    Path(tmp_path).unlink()
    import shutil
    shutil.rmtree(out_dir)


def test_no_fabricated_values_when_file_missing():
    """When file is missing, all numeric outputs must be None or absent."""
    result = parse_mmpbsa_result("/does/not/exist.dat")
    components = get_mmgbsa_components(result)
    assert components["delta_g_total"] is None
    assert components["vdw"] is None
    assert components["electrostatic"] is None
    assert components["polar_solvation"] is None
    assert components["nonpolar_solvation"] is None
