#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze peptide structures with DSSP/mkdssp.
Generate structure-metadata.json for frontend Structure Viewer.

Usage:
    python3 analyze_dssp.py --pdb-dir /path/to/pdbs --output /path/to/structure-metadata.json
"""

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

# DSSP secondary structure classification standard
HELIX_CODES: Final[set[str]] = {'H', 'G', 'I'}
SHEET_CODES: Final[set[str]] = {'E', 'B'}

AA_MAP: Final[dict[str, str]] = {
    'ALA': 'A', 'CYS': 'C', 'ASP': 'D', 'GLU': 'E',
    'PHE': 'F', 'GLY': 'G', 'HIS': 'H', 'ILE': 'I',
    'LYS': 'K', 'LEU': 'L', 'MET': 'M', 'ASN': 'N',
    'PRO': 'P', 'GLN': 'Q', 'ARG': 'R', 'SER': 'S',
    'THR': 'T', 'VAL': 'V', 'TRP': 'W', 'TYR': 'Y',
}


@dataclass(frozen=True)
class SecondaryStructure:
    helix: float
    sheet: float
    coil: float


@dataclass(frozen=True)
class StructureMetadata:
    id: str
    name: str
    sequence: str
    length: int
    netCharge: float
    meanPlddt: float
    pdbUrl: str
    secondaryStructure: SecondaryStructure


def run_mkdssp(pdb_path: Path, dssp_path: Path) -> subprocess.CompletedProcess[str]:
    """Execute mkdssp with fallback parameter styles."""
    commands = [
        ['mkdssp', str(pdb_path), str(dssp_path)],
        ['mkdssp', '-i', str(pdb_path), '-o', str(dssp_path)],
    ]
    last_error: subprocess.CompletedProcess[str] | None = None

    for cmd in commands:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
        )
        if result.returncode == 0:
            return result
        last_error = result

    raise RuntimeError(
        f"mkdssp failed for {pdb_path}: {last_error.stderr if last_error else 'unknown error'}"
    )


def parse_dssp(dssp_path: Path) -> SecondaryStructure:
    """Parse DSSP output and calculate secondary structure proportions."""
    total = 0
    counts = {'helix': 0, 'sheet': 0, 'coil': 0}

    with open(dssp_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.rstrip('\n')
            # Skip header and comment lines
            if not stripped or stripped.startswith('====') or stripped.startswith('  #'):
                continue
            # Skip histogram and summary lines (usually start with spaces + numbers or text)
            if 'TOTAL NUMBER OF' in stripped or 'ACCESSIBLE SURFACE' in stripped:
                continue
            if 'RESIDUES PER ALPHA HELIX' in stripped:
                continue
            if 'PARALLEL BRIDGES' in stripped or 'ANTIPARALLEL BRIDGES' in stripped:
                continue
            if 'LADDERS PER SHEET' in stripped:
                continue
            # Data lines must be long enough and start with a residue number
            if len(stripped) < 17:
                continue
            # The secondary structure code is at column 17 (0-indexed 16)
            # DSSP format: col 1-5 resnum, 6 chain, 7-10 seq, 11-12 icode, 13 aa, 14 ss
            try:
                # Check if first non-space character is a digit (residue number)
                first_char = stripped.lstrip()[0]
                if not first_char.isdigit():
                    continue
            except IndexError:
                continue

            ss_code = stripped[16] if len(stripped) > 16 else ' '
            total += 1
            if ss_code in HELIX_CODES:
                counts['helix'] += 1
            elif ss_code in SHEET_CODES:
                counts['sheet'] += 1
            else:
                counts['coil'] += 1

    if total == 0:
        raise ValueError(f"No valid residues found in {dssp_path}")

    return SecondaryStructure(
        helix=round(counts['helix'] / total, 4),
        sheet=round(counts['sheet'] / total, 4),
        coil=round(counts['coil'] / total, 4),
    )


def extract_sequence_from_pdb(pdb_path: Path) -> str:
    """Extract amino acid sequence from PDB ATOM records."""
    sequence: list[str] = []
    seen_residues: set[str] = set()

    with open(pdb_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.startswith('ATOM'):
                continue
            res_name = line[17:20].strip()
            res_num = line[22:27].strip()
            if res_num not in seen_residues:
                seen_residues.add(res_num)
                sequence.append(AA_MAP.get(res_name, 'X'))

    return ''.join(sequence)


def calculate_net_charge(sequence: str) -> float:
    """Calculate approximate net charge at pH 7.4."""
    positive = sequence.count('K') + sequence.count('R') + sequence.count('H') * 0.1
    negative = sequence.count('D') + sequence.count('E')
    return round(positive - negative, 2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Analyze peptide structures with DSSP and generate metadata JSON'
    )
    parser.add_argument(
        '--pdb-dir',
        required=True,
        help='Directory containing PDB files (e.g., /mnt/d/.../public/structures)',
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output JSON file path',
    )
    parser.add_argument(
        '--mock-plddt',
        type=float,
        default=85.0,
        help='Mock mean pLDDT value for placeholder PDBs (default: 85.0)',
    )
    parser.add_argument(
        '--keep-dssp',
        action='store_true',
        help='Keep generated .dssp files as audit trail',
    )
    args = parser.parse_args()

    pdb_dir = Path(args.pdb_dir)
    if not pdb_dir.exists():
        print(f"Error: PDB directory does not exist: {pdb_dir}", file=sys.stderr)
        return 1

    structures: list[StructureMetadata] = []

    for pdb_file in sorted(pdb_dir.glob('candidate_*.pdb')):
        candidate_id = pdb_file.stem
        dssp_file = pdb_file.with_suffix('.dssp')

        print(f"Processing {pdb_file.name} ...", file=sys.stderr)

        try:
            run_mkdssp(pdb_file, dssp_file)
            ss = parse_dssp(dssp_file)
            seq = extract_sequence_from_pdb(pdb_file)
            net_charge = calculate_net_charge(seq)

            structures.append(StructureMetadata(
                id=candidate_id,
                name=f"Candidate {candidate_id.split('_')[-1]}",
                sequence=seq,
                length=len(seq),
                netCharge=net_charge,
                meanPlddt=args.mock_plddt,
                pdbUrl=f"/structures/{pdb_file.name}",
                secondaryStructure=ss,
            ))

            print(f"  → helix={ss.helix}, sheet={ss.sheet}, coil={ss.coil}, seq={seq}", file=sys.stderr)
        except Exception as exc:
            print(f"  → FAILED: {exc}", file=sys.stderr)
            # Continue with other files
            continue
        finally:
            if not args.keep_dssp and dssp_file.exists():
                dssp_file.unlink()

    output_obj = {
        'generatedBy': 'analyze_dssp.py',
        'version': '1.0.0',
        'count': len(structures),
        'structures': [asdict(s) for s in structures],
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_obj, f, indent=2, ensure_ascii=False)

    print(f"\nGenerated {output_path} with {len(structures)} structures", file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
