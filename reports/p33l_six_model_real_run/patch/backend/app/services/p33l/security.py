import os
from typing import Iterable


def safe_relative_path(base: str, rel: str) -> str:
    """Resolve rel inside base and reject path traversal."""
    base_real = os.path.realpath(base)
    target = os.path.realpath(os.path.join(base_real, rel))
    if not (target == base_real or target.startswith(base_real + os.sep)):
        raise ValueError(f"Path traversal rejected: {rel}")
    return target


def is_within_whitelist(path: str, whitelist_dirs: Iterable[str]) -> bool:
    """Return True if path is inside one of the whitelisted directories."""
    real_path = os.path.realpath(path)
    for allowed in whitelist_dirs:
        allowed_real = os.path.realpath(allowed)
        if real_path == allowed_real or real_path.startswith(allowed_real + os.sep):
            return True
    return False


def validate_run_dir(path: str) -> str:
    """Validate a run directory: reject symlinks and return real path."""
    if os.path.islink(path):
        raise ValueError(f"Symlink rejected: {path}")
    return os.path.realpath(path)


def compute_file_sha256(path: str) -> str:
    """Compute SHA-256 digest for a file on disk."""
    import hashlib

    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
