"""
Seed script for E2E integration test.
Creates one project with full pipeline data for ProjectResultsPage validation.
"""
from __future__ import annotations

import sys
sys.path.insert(0, "D:/Desktop/靶向肽/github/前端/backend")

from app.database import SessionLocal, init_db
from app.crud import (
    create_project,
    create_target_protein,
    create_epitope_scan,
    create_epitope_candidate,
    create_stamp_generation_run,
    create_stamp_candidate,
)
from app.schemas import (
    ProjectCreate,
    TargetProteinCreate,
    EpitopeScanCreate,
    EpitopeCandidateCreate,
    StampGenerationRunCreate,
    StampCandidateCreate,
)


def seed() -> str:
    init_db()
    db = SessionLocal()
    try:
        # 1. Project
        proj = create_project(
            db,
            ProjectCreate(
                name="E2E Integration Project",
                description="End-to-end test project for v0.8 P5-lite",
                species="Pseudomonas aeruginosa",
                project_type="stamp_hybrid",
            ),
        )
        print(f"Created project: {proj.id}")

        # 2. Target Protein
        tp = create_target_protein(
            db,
            TargetProteinCreate(
                project_id=proj.id,
                name="OprF",
                sequence="MKKTAIAATAVLATASAQVAAGTSTWEYAQTTDPNQLTQQLTEAVQKLLENKDVQKIAGTGKGADAATYYTYILTAAKLIAGA",
                sequence_hash="oprftest123",
                length=68,
                source_type="manual",
            ),
        )
        print(f"Created target protein: {tp.id}")

        # 3. Epitope Scan
        scan = create_epitope_scan(
            db,
            EpitopeScanCreate(
                project_id=proj.id,
                target_protein_id=tp.id,
                algorithm="heuristic_v1",
            ),
        )
        print(f"Created epitope scan: {scan.id}")

        # 4. Epitope Candidates
        for i, (seq, score) in enumerate([
            ("TSTWEYAQTTDPNQL", 0.92),
            ("AQTTDPNQLTQQLTE", 0.88),
            ("TQQLTEAVQKLLENK", 0.85),
        ]):
            cand = create_epitope_candidate(
                db,
                EpitopeCandidateCreate(
                    scan_id=scan.id,
                    start=10 + i * 5,
                    end=24 + i * 5,
                    sequence=seq,
                    net_charge=2.0 + i * 0.5,
                    hydrophobicity=0.3 + i * 0.1,
                    pi=7.0 + i * 0.5,
                    cys_count=0,
                    ranking_score=score,
                    filter_status="PASS",
                ),
            )
            print(f"Created epitope candidate: {cand.id}")

        # 5. STAMP Generation Run
        run = create_stamp_generation_run(
            db,
            StampGenerationRunCreate(
                project_id=proj.id,
                generator_name="rule_based_v1",
            ),
        )
        print(f"Created generation run: {run.id}")

        # 6. STAMP Candidates
        for i, (tp_seq, amp_seq, score) in enumerate([
            ("EEDDAEEDAEDDAEE", "FSRFLRRVRRYRPKISFNLEPFFKF", 0.81),
            ("EEDDAEEDAEDDAEE", "FLGLLFHGVHHVGKIHGIGHLVHGH", 0.79),
            ("EEDDAEEDAEDDAEE", "KWKLFKKIEKVGQNIVGKGKVGKAGQ", 0.76),
        ]):
            stamp = create_stamp_candidate(
                db,
                StampCandidateCreate(
                    project_id=proj.id,
                    generation_run_id=run.id,
                    targeting_peptide_seq=tp_seq,
                    linker_seq="EAAAK",
                    full_sequence=f"{tp_seq}EAAAK{amp_seq}",
                    composite_score=score,
                ),
            )
            print(f"Created STAMP candidate: {stamp.id} — validation_status={stamp.validation_status}")

        db.commit()
        print(f"\n>>> PROJECT_ID for E2E test: {proj.id}")
        return proj.id
    except Exception as exc:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    project_id = seed()
    print(project_id)
