#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from pathlib import Path

def fix_pdb(input_path: str, output_path: str) -> None:
    with open(input_path, 'r') as f:
        lines = f.readlines()

    out_lines = []
    atom_num = 0

    for line in lines:
        if not line.startswith('ATOM'):
            out_lines.append(line)
            continue

        atom_name = line[12:16].strip()
        res_name = line[17:20].strip()
        chain = line[21]
        res_seq = line[22:26].strip()
        x = float(line[30:38].strip())
        y = float(line[38:46].strip())
        z = float(line[46:54].strip())

        out_lines.append(line)
        atom_num = int(line[6:11].strip())

        if atom_name == 'C':
            atom_num += 1
            ox = x + 0.6
            oy = y + 0.8
            oz = z + 0.2
            o_line = f"ATOM  {atom_num:5d}  O   {res_name} {chain}{int(res_seq):4d}    {ox:8.3f}{oy:8.3f}{oz:8.3f}  1.00 80.00           O\n"
            out_lines.append(o_line)

    with open(output_path, 'w') as f:
        f.writelines(out_lines)

if __name__ == '__main__':
    base = "/mnt/d/Desktop/靶向肽/github/前端/public/structures"
    for i in [1, 2, 3]:
        inp = f"{base}/candidate_{i}.pdb"
        out = f"{base}/candidate_{i}.pdb"
        fix_pdb(inp, out)
        print(f"Fixed {out}")
