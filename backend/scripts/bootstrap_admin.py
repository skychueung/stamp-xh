"""
STAMP Platform — Bootstrap the initial admin user (P33V-A1).

Usage (password via stdin, no shell history):
    echo 'INITIAL_PASSWORD' | python scripts/bootstrap_admin.py

Or via short-lived env var:
    STAMP_BOOTSTRAP_ADMIN_PASSWORD='INITIAL_PASSWORD' python scripts/bootstrap_admin.py

The password is never logged, written to source code, migrations, or reports.
"""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

# Ensure backend/ is on path when run from repo root or backend/.
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.user import User

ADMIN_USERNAME = "kxc"


def _read_password() -> str:
    """Read password from stdin, env, or interactive prompt; clear env immediately."""
    env_key = "STAMP_BOOTSTRAP_ADMIN_PASSWORD"
    password = os.environ.pop(env_key, None)
    if password:
        return password

    if not sys.stdin.isatty():
        password = sys.stdin.read().strip()
        if password:
            return password

    password = getpass.getpass(f"Enter initial password for '{ADMIN_USERNAME}': ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        sys.exit(1)
    return password


def main() -> int:
    password = _read_password()
    if len(password) < 8:
        print("Password must be at least 8 characters long.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == ADMIN_USERNAME).first()
        if existing:
            print(
                f"ERROR: Admin user '{ADMIN_USERNAME}' already exists (id={existing.id}). "
                "Refusing to overwrite password or role. Stopping.",
                file=sys.stderr,
            )
            return 2

        admin = User(
            username=ADMIN_USERNAME,
            email=None,
            password_hash=hash_password(password),
            role="admin",
            status="active",
            must_change_password=True,
        )
        db.add(admin)
        db.commit()
        print(f"Admin user '{ADMIN_USERNAME}' created successfully (id={admin.id}).")
        print("IMPORTANT: Initial login will require password change.")
        return 0
    finally:
        db.close()
        # Best-effort clear from memory references.
        password = ""


if __name__ == "__main__":
    sys.exit(main())
