"""
STAMP Platform — Configuration Management

Uses Pydantic-settings for environment-aware configuration.
All paths are resolved relative to the project root so that the app
works both in local development and inside a Docker container.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
"""Absolute path to ``backend/`` (two levels above ``core/config.py``)."""


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Application settings loaded from environment variables and ``.env``.

    Priority order (highest → lowest):
        1. Environment variables
        2. ``.env`` file (if present)
        3. Default values defined below
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application identity ----------------------------------------------

    app_name: str = "STAMP Platform API"
    """Display name used in OpenAPI documentation."""

    app_version: str = "0.6.0"
    """API version (semantic versioning)."""

    app_description: str = (
        "STAMP (Synergistic Targeting Antimicrobial Peptide) "
        "platform backend. Assembles targeting peptides (PepMLM), "
        "rigid linkers (EAAAK), and AMP killing domains into hybrid "
        "candidates. No mock experimental data is ever fabricated."
    )
    """Long description shown in the automatic API docs."""

    debug: bool = False
    """Enable debug mode (stack traces in error responses)."""

    environment: str = "development"
    """Runtime profile: development, test, or production."""

    # --- HTTP / CORS -------------------------------------------------------

    host: str = "0.0.0.0"
    port: int = 8000

    # --- Filesystem layout -------------------------------------------------

    stamp_data_dir: str = str(PROJECT_ROOT / "data")
    stamp_database_url: str = f"sqlite:///{(PROJECT_ROOT / 'stamp_p5_lite.db').as_posix()}"
    stamp_batch_jobs_dir: str = str(PROJECT_ROOT / "data" / "batch_jobs")
    stamp_dist_dir: str = str(PROJECT_ROOT / "dist")
    stamp_logs_dir: str = str(PROJECT_ROOT / "logs")
    stamp_models_dir: str = str(PROJECT_ROOT / "models")
    stamp_pipeline_artifact_root: str = str(PROJECT_ROOT / "data" / "pipeline_runs")
    target_peptide_models_dir: str = str(PROJECT_ROOT.parent / "models_dev")

    pepmlm_model_path: str | None = None
    pepmlm_hf_model_id: str | None = None
    pepmlm_device: str = "auto"
    pepmlm_allow_download: bool = False
    pepmlm_offline_only: bool = True

    cors_origins: list[str] = ["*"]
    """Allowed origins for CORS.  Override in production."""

    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    secret_key: str = "change-me-in-production"
    """Secret key for signing session cookies. Override via STAMP_SECRET_KEY env var."""

    # --- Data file paths ---------------------------------------------------

    # Relative paths under DATA_DIR; override via env vars if mounted elsewhere.
    pepmlm_candidates_file: str = "pepmlm_generated_targeting_peptides.json"
    priority_amp_library_file: str = "priority_amp_library.json"
    stamp_hybrid_candidates_file: str = "stamp_hybrid_candidates.json"
    amp_structure_manifest_file: str = "amp_structure_manifest.json"
    real_amp_candidates_file: str = "real_amp_candidates.json"
    stamp_template_library_file: str = "stamp_template_library.json"
    pepmlm_oprf_top10_file: str = "pepmlm_oprf_top10.json"

    @property
    def pepmlm_candidates_path(self) -> Path:
        """Resolved absolute path to PepMLM candidates JSON."""
        return DATA_DIR / self.pepmlm_candidates_file

    @property
    def priority_amp_library_path(self) -> Path:
        """Resolved absolute path to priority AMP library JSON."""
        return DATA_DIR / self.priority_amp_library_file

    @property
    def stamp_hybrid_candidates_path(self) -> Path:
        """Resolved absolute path to STAMP hybrid candidates JSON."""
        return DATA_DIR / self.stamp_hybrid_candidates_file

    @property
    def amp_structure_manifest_path(self) -> Path:
        """Resolved absolute path to AMP structure manifest JSON."""
        return DATA_DIR / self.amp_structure_manifest_file

    @property
    def real_amp_candidates_path(self) -> Path:
        """Resolved absolute path to real AMP candidates JSON."""
        return DATA_DIR / self.real_amp_candidates_file

    @property
    def stamp_template_library_path(self) -> Path:
        """Resolved absolute path to STAMP template library JSON."""
        return DATA_DIR / self.stamp_template_library_file

    @property
    def pepmlm_oprf_top10_path(self) -> Path:
        """Resolved absolute path to simplified Top-10 JSON."""
        return DATA_DIR / self.pepmlm_oprf_top10_file


    # --- Public release safety guards --------------------------------------

    public_demo_mode: bool = True
    """When True, disable write/compute/file-asset endpoints by default."""

    enable_write_endpoints: bool = False
    """Enable write endpoints outside public-demo mode."""

    enable_compute_endpoints: bool = False
    """Enable compute endpoints outside public-demo mode."""

    enable_file_asset_registration: bool = False
    """Enable file asset registration outside public-demo mode."""

    def validate_runtime_security(self) -> None:
        """Reject deployment defaults when the production profile is selected."""
        if self.environment.lower() != "production":
            return
        if not self.secret_key or self.secret_key in {
            "change-me-in-production",
            "dev-insecure-fallback-secret-do-not-use-in-production",
        } or len(self.secret_key) < 32:
            raise RuntimeError("STAMP_SECRET_KEY must be a strong value in production")
        if self.cors_allow_credentials and "*" in self.cors_origins:
            raise RuntimeError("Explicit CORS origins are required with credentials in production")


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

settings = Settings()
"""Singleton settings instance imported by routers and services."""

DATA_DIR: Final[Path] = Path(settings.stamp_data_dir).expanduser().resolve()
"""Directory containing JSON data files (shared with / mounted from frontend)."""
