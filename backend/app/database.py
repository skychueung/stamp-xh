"""
STAMP Platform — Database Configuration (P5-lite)

SQLite + SQLAlchemy 2.0 (SYNC) persistence layer.
Provides engine, session maker, declarative base, and init helpers.
"""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# ---------------------------------------------------------------------------
# SQLite URL (sync driver)
# ---------------------------------------------------------------------------

DATABASE_URL: str = settings.stamp_database_url

# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Shared declarative base for all ORM tables."""

    pass


# ---------------------------------------------------------------------------
# Engine & Session Maker
# ---------------------------------------------------------------------------

engine = create_engine(
    DATABASE_URL,
    echo=False,          # Set True for SQL debug output
    future=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ---------------------------------------------------------------------------
# Init helper
# ---------------------------------------------------------------------------

def _migrate_sqlite_columns() -> None:
    """Add missing columns to existing SQLite tables (v1.2 fast migration)."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "jobs" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("jobs")}
        migrations = [
            ("candidate_id", "VARCHAR(36)"),
            ("batch_id", "VARCHAR(36)"),
            ("retry_count", "INTEGER DEFAULT 0"),
            ("max_retries", "INTEGER DEFAULT 3"),
            ("server_host", "VARCHAR(256)"),
            ("priority", "INTEGER DEFAULT 5"),
            ("error_json", "TEXT DEFAULT '{}'"),
            ("artifacts_json", "TEXT DEFAULT '{}'"),
        ]
        with engine.connect() as conn:
            for col_name, col_type in migrations:
                if col_name not in existing_cols:
                    conn.execute(text(f'ALTER TABLE jobs ADD COLUMN {col_name} {col_type}'))
            conn.commit()


def init_db() -> None:
    """Create all tables (idempotent) and migrate existing ones. Call once at startup."""
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_columns()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_db() -> Generator:
    """Yield a DB session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
