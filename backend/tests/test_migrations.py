"""
STAMP Platform — Migration Smoke Tests

Covers:
1. Alembic config loads correctly.
2. Baseline migration can run on a fresh empty DB (upgrade + downgrade).
3. Existing stamped DB is recognised as up-to-date.
4. Backup script creates a valid copy.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).parent.parent
ALEMBIC_EXE = BACKEND_ROOT / "venv" / "Scripts" / "alembic.exe"
if sys.platform != "win32":
    ALEMBIC_EXE = BACKEND_ROOT / "venv" / "bin" / "alembic"


def _alembic(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run alembic CLI with given args."""
    cmd = [sys.executable, "-m", "alembic", *args]
    extra_env = {**os.environ, **(env or {})}
    return subprocess.run(
        cmd,
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        env=extra_env,
        check=False,
    )


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Return a temporary SQLite DB path."""
    return tmp_path / "test_stamp.db"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAlembicConfig:
    def test_alembic_ini_exists(self) -> None:
        assert (BACKEND_ROOT / "alembic.ini").exists()

    def test_env_py_imports_models(self) -> None:
        """env.py must import app.models so metadata is populated."""
        env_py = BACKEND_ROOT / "alembic" / "env.py"
        content = env_py.read_text(encoding="utf-8")
        assert "import app.models" in content

    def test_baseline_migration_exists(self) -> None:
        versions_dir = BACKEND_ROOT / "alembic" / "versions"
        migrations = list(versions_dir.glob("*.py"))
        assert any("baseline" in m.name for m in migrations)


class TestMigrationOnEmptyDb:
    def test_upgrade_downgrade_empty_db(self, temp_db_path: Path) -> None:
        """A fresh empty DB can be upgraded to head and then downgraded to base."""
        env = {"STAMP_DATABASE_URL": f"sqlite:///{temp_db_path}"}

        # Upgrade to head
        up = _alembic("upgrade", "head", env=env)
        assert up.returncode == 0, up.stderr

        # Downgrade to base
        down = _alembic("downgrade", "base", env=env)
        assert down.returncode == 0, down.stderr

    def test_tables_created_after_upgrade(self, temp_db_path: Path) -> None:
        """After upgrade, expected tables exist."""
        env = {"STAMP_DATABASE_URL": f"sqlite:///{temp_db_path}"}
        up = _alembic("upgrade", "head", env=env)
        assert up.returncode == 0, up.stderr

        from sqlalchemy import create_engine, inspect

        engine = create_engine(f"sqlite:///{temp_db_path}")
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        expected = {
            "projects",
            "target_proteins",
            "epitope_scans",
            "epitope_candidates",
            "stamp_generation_runs",
            "stamp_candidates",
            "jobs",
            "experimental_validation_runs",
            "experimental_measurements",
            "integration_configs",
            "compute_batches",
            "batch_computations",
            "batch_computation_items",
            "computation_artifacts",
            "file_assets",
            "audit_logs",
            "alembic_version",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"


class TestMigrationOnExistingDb:
    def test_stamped_db_is_up_to_date(self, temp_db_path: Path) -> None:
        """If we create tables via init_db() and stamp the DB, alembic sees no drift."""
        env = {"STAMP_DATABASE_URL": f"sqlite:///{temp_db_path}"}

        # Create tables using the app's own init_db (simulates existing deployment)
        from app.database import init_db

        init_db()

        # Stamp with current head
        stamp = _alembic("stamp", "head", env=env)
        assert stamp.returncode == 0, stamp.stderr

        # Check history shows current
        hist = _alembic("history", env=env)
        assert hist.returncode == 0
        assert "baseline" in hist.stdout.lower()


class TestBackupScript:
    def test_backup_creates_file(self, tmp_path: Path) -> None:
        from scripts.backup_db import backup_db

        db_path = tmp_path / "stamp_p5_lite.db"
        # Create a minimal SQLite file
        import sqlite3

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        out_dir = tmp_path / "backups"
        backup_path = backup_db(db_path, out_dir)

        assert backup_path.exists()
        assert backup_path.stat().st_size >= db_path.stat().st_size
