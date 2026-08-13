import fcntl
import json
import os
import time
from typing import Any, Dict, List, Optional

from .config import MODEL_CONFIGS


class P33LState:
    """Persistent attempt counting for the P33L model sequence."""

    def __init__(self, state_path: str = "/home/xh/kxc/stampup/run_gates/p33l/state.json"):
        self.state_path = state_path
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        dir_path = os.path.dirname(self.state_path)
        os.makedirs(dir_path, exist_ok=True)

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.state_path):
            return {"models": {}}
        with open(self.state_path, "r", encoding="utf-8") as fh:
            try:
                return json.load(fh)
            except json.JSONDecodeError:
                return {"models": {}}

    def _save(self, data: Dict[str, Any]) -> None:
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

    def get_attempts(self, model_id: str) -> List[Dict[str, Any]]:
        fh = self._acquire_lock()
        try:
            data = self._load()
            return list(data.get("models", {}).get(model_id, {}).get("attempts", []))
        finally:
            self._release_lock(fh)

    def record_attempt(self, model_id: str, job_id: str, status: str) -> None:
        fh = self._acquire_lock()
        try:
            data = self._load()
            data.setdefault("models", {}).setdefault(model_id, {"attempts": []})
            data["models"][model_id]["attempts"].append(
                {
                    "job_id": job_id,
                    "status": status,
                    "recorded_at": time.time(),
                }
            )
            self._save(data)
        finally:
            self._release_lock(fh)

    def reset(self) -> None:
        fh = self._acquire_lock()
        try:
            self._save({"models": {}})
        finally:
            self._release_lock(fh)

    def is_model_attempted(self, model_id: str) -> bool:
        return len(self.get_attempts(model_id)) > 0

    def next_model(self) -> Optional[str]:
        for cfg in sorted(MODEL_CONFIGS, key=lambda c: c.order):
            if not self.is_model_attempted(cfg.model_id):
                return cfg.model_id
        return None
