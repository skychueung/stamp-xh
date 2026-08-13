"""Import v1.0 demo dataset into STAMP database.

Usage:
    cd backend
    python ..\scripts\import-demo-dataset.py

Requires: STAMP backend dependencies installed, database initialized.
"""

import json
import sys
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal, init_db
from app.models.orm import Project, TargetProtein, EpitopeCandidate, StampCandidate


def load_demo_dataset():
    fixture_path = BACKEND_DIR / "tests" / "fixtures" / "v1.0_demo_dataset.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


def import_projects(db, data):
    for p in data.get("projects", []):
        existing = db.query(Project).filter(Project.id == p["id"]).first()
        if existing:
            print(f"  Project {p['id']} already exists, skipping")
            continue
        proj = Project(
            id=p["id"],
            name=p["name"],
            description=p.get("description"),
            species=p.get("species"),
            project_type=p.get("project_type"),
        )
        db.add(proj)
        print(f"  Created project: {p['name']}")


def import_target_proteins(db, data):
    for t in data.get("target_proteins", []):
        existing = db.query(TargetProtein).filter(TargetProtein.id == t["id"]).first()
        if existing:
            print(f"  Target protein {t['id']} already exists, skipping")
            continue
        tp = TargetProtein(
            id=t["id"],
            project_id=t["project_id"],
            name=t["name"],
            sequence=t["sequence"],
            sequence_hash=t["sequence_hash"],
            length=t["length"],
            organism=t.get("organism"),
            source_type=t["source_type"],
            uniprot_id=t.get("uniprot_id"),
            pdb_id=t.get("pdb_id"),
        )
        db.add(tp)
        print(f"  Created target protein: {t['name']}")


def import_epitope_candidates(db, data):
    for e in data.get("epitope_candidates", []):
        existing = db.query(EpitopeCandidate).filter(EpitopeCandidate.id == e["id"]).first()
        if existing:
            print(f"  Epitope candidate {e['id']} already exists, skipping")
            continue
        ec = EpitopeCandidate(
            id=e["id"],
            scan_id=e["scan_id"],
            start=e["start"],
            end=e["end"],
            sequence=e["sequence"],
            net_charge=e.get("net_charge"),
            hydrophobicity=e.get("hydrophobicity"),
            pi=e.get("pi"),
            cys_count=e.get("cys_count"),
            surface_exposure_score=e.get("surface_exposure_score"),
            metrics=e.get("metrics"),
            ranking_score=e.get("ranking_score"),
            filter_status=e.get("filter_status"),
        )
        db.add(ec)
        print(f"  Created epitope candidate: {e['sequence']} ({e['start']}-{e['end']})")


def import_stamp_candidates(db, data):
    for c in data.get("stamp_candidates", []):
        existing = db.query(StampCandidate).filter(StampCandidate.id == c["id"]).first()
        if existing:
            print(f"  STAMP candidate {c['id']} already exists, skipping")
            continue
        sc = StampCandidate(
            id=c["id"],
            project_id=c["project_id"],
            epitope_id=c["epitope_id"],
            generation_run_id=c["generation_run_id"],
            targeting_peptide_seq=c["targeting_peptide_seq"],
            linker_seq=c["linker_seq"],
            full_sequence=c["full_sequence"],
            composite_score=c.get("composite_score"),
            validation_status=c.get("validation_status", "NOT_EXPERIMENTALLY_VALIDATED"),
            metrics=c.get("metrics"),
        )
        db.add(sc)
        print(f"  Created STAMP candidate: {c['id']}")


def main():
    print("[STAMP] Importing v1.0 demo dataset...")
    data = load_demo_dataset()

    # Ensure DB exists
    init_db()

    db = SessionLocal()
    try:
        import_projects(db, data)
        import_target_proteins(db, data)
        import_epitope_candidates(db, data)
        import_stamp_candidates(db, data)
        db.commit()
        print("[STAMP] Demo dataset imported successfully.")
    except Exception as e:
        db.rollback()
        print(f"[STAMP] Import failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
