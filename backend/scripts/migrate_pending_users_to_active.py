"""Safely activate legacy pending users when approval mode is disabled.

Dry-run is the default. Pass --apply after backing up the development database.
Explicitly disabled users and administrator accounts are never modified.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal
from app.models.user import User


TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def approval_mode_enabled() -> bool:
    return os.environ.get("STAMP_REQUIRE_ADMIN_APPROVAL", "false").strip().lower() in TRUE_VALUES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit pending-to-active updates.")
    args = parser.parse_args()

    if approval_mode_enabled():
        raise SystemExit("Refusing migration while STAMP_REQUIRE_ADMIN_APPROVAL is enabled.")

    with SessionLocal() as db:
        pending_users = (
            db.query(User)
            .filter(User.role == "user", User.status == "pending")
            .all()
        )
        print(f"PENDING_NORMAL_USERS={len(pending_users)}")
        print(f"DISABLED_USERS_UNCHANGED={db.query(User).filter(User.status == 'disabled').count()}")

        if not args.apply:
            print("MODE=DRY_RUN")
            return 0

        activated_at = datetime.now(timezone.utc)
        for user in pending_users:
            user.status = "active"
            user.approved_at = activated_at
            user.approved_by = None
            db.add(user)
        db.commit()
        print(f"ACTIVATED_USERS={len(pending_users)}")
        print("MODE=APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
