/**
 * Generate a minimal valid PDB for UI demonstration.
 * Chain A = Target Protein (alpha-helix, residues 450-470, epitope 455-465 highlighted by B-factor=50)
 * Chain B = Targeting Peptide (7 residues, placed near epitope)
 */

function padLeft(str: string | number, width: number): string {
  const s = String(str);
  return ' '.repeat(Math.max(0, width - s.length)) + s;
}

function padRight(str: string | number, width: number): string {
  const s = String(str);
  return s + ' '.repeat(Math.max(0, width - s.length));
}

function formatAtomLine(
  serial: number,
  name: string,
  resName: string,
  chainId: string,
  resSeq: number,
  x: number,
  y: number,
  z: number,
  occupancy: number,
  tempFactor: number,
  element: string
): string {
  const line =
    padRight('ATOM', 6) +
    padLeft(serial, 5) +
    ' ' +
    padRight(name, 4) +
    ' ' +
    padRight(resName, 3) +
    ' ' +
    chainId +
    padLeft(resSeq, 4) +
    '    ' +
    padLeft(x.toFixed(3), 8) +
    padLeft(y.toFixed(3), 8) +
    padLeft(z.toFixed(3), 8) +
    padLeft(occupancy.toFixed(2), 6) +
    padLeft(tempFactor.toFixed(2), 6) +
    '          ' +
    padRight(element, 2);
  return line.slice(0, 80);
}

function generateHelixCoords(
  _startRes: number,
  count: number,
  radius: number,
  rise: number,
  twistDeg: number,
  offsetX: number,
  offsetY: number,
  offsetZ: number
): Array<{ x: number; y: number; z: number }> {
  const coords: Array<{ x: number; y: number; z: number }> = [];
  for (let i = 0; i < count; i++) {
    const theta = (i * twistDeg * Math.PI) / 180;
    coords.push({
      x: offsetX + radius * Math.cos(theta),
      y: offsetY + radius * Math.sin(theta),
      z: offsetZ + i * rise,
    });
  }
  return coords;
}

function generateExtendedCoords(
  count: number,
  startX: number,
  startY: number,
  startZ: number,
  stepX: number,
  stepY: number,
  stepZ: number
): Array<{ x: number; y: number; z: number }> {
  const coords: Array<{ x: number; y: number; z: number }> = [];
  for (let i = 0; i < count; i++) {
    coords.push({
      x: startX + i * stepX,
      y: startY + i * stepY,
      z: startZ + i * stepZ,
    });
  }
  return coords;
}

const RESIDUES = [
  'ALA', 'CYS', 'ASP', 'GLU', 'PHE',
  'GLY', 'HIS', 'ILE', 'LYS', 'LEU',
  'MET', 'ASN', 'PRO', 'GLN', 'ARG',
  'SER', 'THR', 'VAL', 'TRP', 'TYR',
];

function getResidueName(index: number): string {
  return RESIDUES[index % RESIDUES.length];
}

export function generateMockComplexPdb(): string {
  const lines: string[] = [];
  lines.push('HEADER    MOCK COMPLEX FOR STAMP PLATFORM                01-JAN-26   1ABC');
  lines.push('TITLE     MOCK TARGET PROTEIN - TARGETING PEPTIDE COMPLEX');
  lines.push('REMARK   1 MOCK PDB GENERATED FOR DEMONSTRATION PURPOSES');
  lines.push('REMARK   1 CHAIN A = TARGET PROTEIN (EPITOPE 455-465 HIGHLIGHTED)');
  lines.push('REMARK   1 CHAIN B = TARGETING PEPTIDE (7 RESIDUES)');

  let serial = 1;

  // Chain A: Target Protein - alpha helix, 21 residues (450-470)
  const chainACount = 21;
  const chainACoords = generateHelixCoords(450, chainACount, 2.3, 1.5, 100, 0, 0, 0);

  for (let i = 0; i < chainACount; i++) {
    const resSeq = 450 + i;
    const resName = getResidueName(i);
    const base = chainACoords[i];
    const isEpitope = resSeq >= 455 && resSeq <= 465;
    const tempFactor = isEpitope ? 50.0 : 10.0;

    // N atom - slightly offset in -z direction
    lines.push(
      formatAtomLine(
        serial++, 'N', resName, 'A', resSeq,
        base.x, base.y, base.z - 0.6, 1.0, tempFactor, 'N'
      )
    );
    // CA atom - backbone center
    lines.push(
      formatAtomLine(
        serial++, 'CA', resName, 'A', resSeq,
        base.x + 0.8, base.y, base.z, 1.0, tempFactor, 'C'
      )
    );
    // C atom - slightly offset in +z direction
    lines.push(
      formatAtomLine(
        serial++, 'C', resName, 'A', resSeq,
        base.x, base.y, base.z + 0.6, 1.0, tempFactor, 'C'
      )
    );
    // O atom - carbonyl oxygen
    lines.push(
      formatAtomLine(
        serial++, 'O', resName, 'A', resSeq,
        base.x, base.y + 0.8, base.z + 0.9, 1.0, tempFactor, 'O'
      )
    );
  }
  lines.push('TER   ' + padLeft(serial, 5) + '      ' + padRight(getResidueName(chainACount - 1), 3) + ' A' + padLeft(470, 4));

  // Chain B: Targeting Peptide - 7 residues, placed near epitope (455-465)
  // Position it along the outer surface of the helix
  const chainBCount = 7;
  const epitopeCenterIdx = 5; // residue 455 in chain A is index 5
  const epitopeCenter = chainACoords[epitopeCenterIdx];
  const chainBCoords = generateExtendedCoords(
    chainBCount,
    epitopeCenter.x + 4.0,
    epitopeCenter.y - 1.0,
    epitopeCenter.z - 3.0,
    0.5,
    1.2,
    1.0
  );

  for (let i = 0; i < chainBCount; i++) {
    const resSeq = i + 1;
    const resName = getResidueName(i + 10);
    const base = chainBCoords[i];
    const tempFactor = 90.0;

    lines.push(
      formatAtomLine(
        serial++, 'N', resName, 'B', resSeq,
        base.x, base.y, base.z - 0.6, 1.0, tempFactor, 'N'
      )
    );
    lines.push(
      formatAtomLine(
        serial++, 'CA', resName, 'B', resSeq,
        base.x + 0.5, base.y - 0.3, base.z, 1.0, tempFactor, 'C'
      )
    );
    lines.push(
      formatAtomLine(
        serial++, 'C', resName, 'B', resSeq,
        base.x, base.y, base.z + 0.6, 1.0, tempFactor, 'C'
      )
    );
    lines.push(
      formatAtomLine(
        serial++, 'O', resName, 'B', resSeq,
        base.x, base.y + 0.8, base.z + 0.9, 1.0, tempFactor, 'O'
      )
    );
  }
  lines.push('TER   ' + padLeft(serial, 5) + '      ' + padRight(getResidueName(chainBCount - 1 + 10), 3) + ' B' + padLeft(chainBCount, 4));

  lines.push('END');
  return lines.join('\n');
}
