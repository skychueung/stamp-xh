"""
STAMP Platform — Database Backup Script

Usage:
    python scripts/backup_db.py [--db-path PATH] [--output-dir DIR]

Creates a timestamped copy of the SQLite database.
Safe to run while the app is running (SQLite copy is atomic for WAL mode,
but we use shutil.copy2 for simplicity since the app uses default journal mode).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH = Path(__file__).parent.parent / "app" / "stamp_p5_lite.db"
DEFAULT_BACKUP_DIR = Path(__file__).parent.parent / "data" / "db_backups"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def backup_db(db_path: Path, output_dir: Path) -> Path:
    """Copy db_path to output_dir with a timestamped filename."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    stem = db_path.stem
    suffix = db_path.suffix
    backup_name = f"{stem}_backup_{_timestamp()}{suffix}"
    backup_path = output_dir / backup_name

    shutil.copy2(db_path, backup_path)

    # Also copy WAL / SHM if they exist (not used by current config, but future-proof)
    for extra in [".wal", ".shm"]:
        extra_src = db_path.with_suffix(suffix + extra)
        if extra_src.exists():
            shutil.copy2(extra_src, backup_path.with_suffix(suffix + extra))

    return backup_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backup STAMP SQLite database")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(os.environ.get("STAMP_DATABASE_URL", DEFAULT_DB_PATH).replace("sqlite:///", "")),
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_BACKUP_DIR,
        help="Directory to store backup files",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=10,
        help="Number of backups to retain (oldest auto-deleted)",
    )
    args = parser.parse_args(argv)

    try:
        backup_path = backup_db(args.db_path, args.output_dir)
        print(f"OK: backup created at {backup_path}")

        # Prune old backups
        backups = sorted(
            args.output_dir.glob(f"{args.db_path.stem}_backup_*{args.db_path.suffix}"),
            key=lambda p: p.stat().st_mtime,
        )
        for old in backups[:-args.keep]:
            old.unlink()
            print(f"Pruned old backup: {old.name}")

        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
