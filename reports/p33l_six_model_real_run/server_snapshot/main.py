"""
STAMP Platform — FastAPI Application Entry Point

Assembles all routers, configures CORS, mounts global exception handlers,
and eager-loads JSON data files on startup via an async lifespan context.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import (
    StampException,
    generic_exception_handler,
    stamp_exception_handler,
)
from app.data.loader import eager_load_all
from app.database import init_db
from app.models.schemas import ApiResponse
from app.routers import amp, epitope, epitope_scans, final_ranking, health, legacy_predict, pepmlm, projects, stamp, stamp_assembly, targeting_peptide, target_peptide_design
from app.routers.pipeline_runs import router as pipeline_runs_router
from app.routers.evobind2 import router as evobind2_router
from app.routers.evobind2_compute import router as evobind2_compute_router
from app.routers.target_design_workflow import router as target_design_workflow_router

from app.routers.model_registry import (
    model_registry_status_router,
    router as model_registry_router,
)
from app.routers.epitope_candidates import router as epitope_candidates_router
from app.routers.peptide_generations import router as peptide_generations_router
from app.routers.peptide_generations import stamp_runs_router as stamp_generation_runs_router
from app.routers.project_results import router as project_results_router
from app.routers.project_results import stamp_candidates_router as project_stamp_candidates_router
from app.routers.stamp_assembly_runs import router as stamp_assembly_runs_router
from app.routers.jobs import router as jobs_router
from app.routers.audit_logs import router as audit_logs_router
from app.routers.batches import router as batches_router
from app.routers.experimental_validation import router as experimental_validation_router
from app.routers.file_assets import router as file_assets_router
from app.routers.lims_integration import router as lims_integration_router
from app.routers.production_md import router as production_md_router
from app.routers.batch_computations import router as batch_computations_router
from app.routers.flexpepdock_pilot import router as flexpepdock_pilot_router
from app.routers.md_production_pilot import router as md_production_pilot_router
from app.routers.runner_logs import router as runner_logs_router
from app.routers.mmgbsa_pilot import router as mmgbsa_pilot_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("stamp")

# ---------------------------------------------------------------------------
# Lifespan — eager data loading on startup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager.

    On startup: eagerly load all JSON data files so that missing or
    malformed files raise immediately rather than at first request.

    On shutdown: nothing to clean up (data is in-memory and immutable).
    """
    logger.info("STAMP backend starting up — version %s", settings.app_version)
    try:
        init_db()
        logger.info("Database initialized (tables created if missing).")
    except Exception as exc:
        logger.critical("Startup failed during database init: %s", exc)
        raise
    try:
        eager_load_all()
    except Exception as exc:
        logger.critical("Startup failed during data loading: %s", exc)
        raise
    logger.info("STAMP backend startup complete.")
    yield
    logger.info("STAMP backend shutting down.")


# ---------------------------------------------------------------------------
# FastAPI app factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Fully configured ``FastAPI`` instance.
    """
    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )

    # --- CORS --------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # --- Global exception handlers ------------------------------------------
    app.add_exception_handler(StampException, stamp_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # --- Router registration ------------------------------------------------
    app.include_router(health.router)              # /health
    app.include_router(health.router, prefix="/api")  # /api/health (overrides legacy sidecar)
    app.include_router(projects.router)
    app.include_router(legacy_predict.router)
    app.include_router(pepmlm.router)
    app.include_router(amp.router)
    app.include_router(stamp.router)
    app.include_router(epitope.router)
    app.include_router(epitope_scans.router)
    app.include_router(epitope_candidates_router)
    app.include_router(targeting_peptide.router)
    app.include_router(target_peptide_design.router)
    app.include_router(stamp_assembly.router)
    app.include_router(final_ranking.router)
    app.include_router(peptide_generations_router)
    app.include_router(stamp_generation_runs_router)
    app.include_router(stamp_assembly_runs_router)
    app.include_router(project_results_router)
    app.include_router(project_stamp_candidates_router)
    app.include_router(jobs_router)
    app.include_router(batches_router)
    app.include_router(file_assets_router)
    app.include_router(audit_logs_router)
    app.include_router(lims_integration_router)
    app.include_router(production_md_router)
    app.include_router(batch_computations_router)
    app.include_router(md_production_pilot_router)
    app.include_router(flexpepdock_pilot_router)
    app.include_router(runner_logs_router)
    app.include_router(mmgbsa_pilot_router)
    app.include_router(experimental_validation_router)
    app.include_router(pipeline_runs_router)
    app.include_router(evobind2_router)          # /api/v1/evobind2/dry-run & probe
    app.include_router(evobind2_compute_router)  # /api/v1/evobind2/jobs (gated)
    app.include_router(model_registry_router)  # /api/v1/models (unified registry)
    app.include_router(model_registry_status_router)  # /api/v1/model-registry/status
    app.include_router(target_design_workflow_router)  # /api/v1/workflows (P7A)

    # --- API info ----------------------------------------------------------
    @app.get("/api/info", include_in_schema=False)
    async def api_info() -> dict:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs" if settings.debug else None,
            "health": "/health",
        }

    # --- SPA static files fallback (production) ------------------------------
    dist_dir = os.environ.get("STAMP_DIST_DIR")
    if dist_dir and os.path.isdir(dist_dir):
        from fastapi.responses import FileResponse

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi") or full_path.startswith("health"):
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content=ApiResponse[None].error(
                        code=status.HTTP_404_NOT_FOUND,
                        message=f"Endpoint '/{full_path}' not found.",
                    ).model_dump(),
                )
            file_path = os.path.join(dist_dir, full_path)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse(os.path.join(dist_dir, "index.html"))

    # --- 404 fallback -------------------------------------------------------
    @app.exception_handler(404)
    async def not_found_handler(request, exc) -> JSONResponse:
        body = ApiResponse[None].error(
            code=status.HTTP_404_NOT_FOUND,
            message=f"Endpoint '{request.url.path}' not found.",
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=body.model_dump(),
        )

    return app


# ---------------------------------------------------------------------------
# Global app instance (used by ASGI servers like uvicorn)
# ---------------------------------------------------------------------------

app = create_app()
