"""P33U attempt-state — independent namespace, does NOT inherit P33L history.

P33L history (`run_gates/p33l/state.json`) stays frozen and read-only.
P33U reads/writes only `run_gates/p33u_lane_d/state.json`.

The state file carries an explicit `lineage` marker so that P33U's empty
attempt list can never be misread as "P33L failures cleared".
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from typing import Any

from .config import LINEAGE, STATE_PATH


class P33UState:
    """Persistent attempt counting for the P33U Lane D-min sequence."""

    def __init__(self, state_path: str = STATE_PATH) -> None:
        self.state_path = state_path
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)

    def _empty_state(self) -> dict[str, Any]:
        # Explicit lineage marker: P33U starts at zero attempts and does NOT
        # inherit P33L's PepMLM-success / EvoBind2-failure history.
        return {"lineage": LINEAGE, "models": {}}

    def _load(self) -> dict[str, Any]:
        if not os.path.exists(self.state_path):
            return self._empty_state()
        try:
            with open(self.state_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return self._empty_state()
        # Refuse to adopt a state file missing the lineage marker — guards
        # against accidental cross-contamination with P33L state.
        if data.get("lineage") != LINEAGE:
            return self._empty_state()
        return data

    def _save(self, data: dict[str, Any]) -> None:
        tmp_path = self.state_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, self.state_path)

    def _acquire_lock(self):
        lock_path = self.state_path + ".lock"
        fh = open(lock_path, "w", encoding="utf-8")
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        return fh

    def _release_lock(self, fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()

    def lineage(self) -> str:
        return self._load().get("lineage", LINEAGE)

    def get_attempts(self, model_id: str) -> list[dict[str, Any]]:
        fh = self._acquire_lock()
        try:
            data = self._load()
            return list(data.get("models", {}).get(model_id, {}).get("attempts", []))
        finally:
            self._release_lock(fh)

    def is_model_attempted(self, model_id: str) -> bool:
        return len(self.get_attempts(model_id)) > 0

    def record_attempt(self, model_id: str, run_id: str, status: str) -> None:
        """Record an attempt. NOTE: only called at Lane D real-run time."""
        fh = self._acquire_lock()
        try:
            data = self._load()
            data.setdefault("models", {}).setdefault(model_id, {"attempts": []})
            data["models"][model_id]["attempts"].append(
                {"run_id": run_id, "status": status, "recorded_at": time.time()}
            )
            self._save(data)
        finally:
            self._release_lock(fh)

    def attempt_count(self, model_id: str) -> int:
        return len(self.get_attempts(model_id))

    def reset(self) -> None:
        """Reset P33U state to empty. Does NOT touch P33L state."""
        fh = self._acquire_lock()
        try:
            self._save(self._empty_state())
        finally:
            self._release_lock(fh)
