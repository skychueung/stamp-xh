import json
import os
import time
import uuid
from typing import Any, Dict, Optional


class P33LGate:
    """A per-job authorization gate stored on disk."""

    def __init__(
        self,
        model_id: str,
        job_id: str,
        base_dir: str = "/home/xh/kxc/stampup/run_gates/p33l",
        manifest_sha: str = "",
        ttl_seconds: int = 86400,
    ):
        self.model_id = model_id
        self.job_id = job_id
        self.base_dir = base_dir
        self.manifest_sha = manifest_sha
        self.ttl_seconds = ttl_seconds
        self.gate_dir = os.path.join(base_dir, model_id, job_id)
        self.gate_path = os.path.join(self.gate_dir, "gate.json")

    def _reject_unsafe_path(self, path: str) -> None:
        """Reject symlinks and paths that escape the base directory."""
        if os.path.islink(path):
            raise ValueError(f"Symlink rejected: {path}")
        real_path = os.path.realpath(path)
        base_real = os.path.realpath(self.base_dir)
        if not (real_path == base_real or real_path.startswith(base_real + os.sep)):
            raise ValueError(f"Path traversal rejected: {path}")

    def create(self) -> Dict[str, Any]:
        """Create the gate directory and write the gate file atomically."""
        self._reject_unsafe_path(self.gate_dir)
        old_umask = os.umask(0o077)
        try:
            os.makedirs(self.gate_dir, mode=0o700, exist_ok=True)
        finally:
            os.umask(old_umask)

        now = time.time()
        gate_doc = {
            "gate_id": str(uuid.uuid4()),
            "model_id": self.model_id,
            "job_id": self.job_id,
            "manifest_sha": self.manifest_sha,
            "created_at": now,
            "expires_at": now + self.ttl_seconds,
            "status": "created",
        }
        tmp_path = self.gate_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(gate_doc, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, self.gate_path)
        os.chmod(self.gate_path, 0o600)
        return gate_doc

    def validate(self) -> Optional[Dict[str, Any]]:
        """Return the gate document if it is open, unexpired, and bound to this manifest."""
        if not os.path.exists(self.gate_path):
            return None
        with open(self.gate_path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        if doc.get("status") != "created":
            return None
        if doc.get("manifest_sha") != self.manifest_sha:
            return None
        if time.time() > doc.get("expires_at", 0):
            return None
        return doc

    def close(self) -> None:
        """Mark the gate as closed."""
        if not os.path.exists(self.gate_path):
            return
        with open(self.gate_path, "r+", encoding="utf-8") as fh:
            doc = json.load(fh)
            doc["status"] = "closed"
            doc["closed_at"] = time.time()
            fh.seek(0)
            json.dump(doc, fh, indent=2)
            fh.truncate()
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(self.gate_path, 0o600)
