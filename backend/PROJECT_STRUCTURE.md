# STAMP Backend — Project Directory Structure

## Overview

This document defines the canonical directory layout for the STAMP Platform
FastAPI backend.  All paths are relative to the repository root (`backend/`).

```
backend/
│
├── app/                               # Main Python package
│   ├── __init__.py                    # Package marker (empty)
│   │
│   ├── main.py                        # FastAPI application factory
│   │                                    - Lifespan context (eager data load)
│   │                                    - CORS middleware configuration
│   │                                    - Global exception handler registration
│   │                                    - Router inclusion
│   │                                    - Root endpoint + 404 fallback
│   │
│   ├── core/                          # Core infrastructure
│   │   ├── __init__.py                # Package marker
│   │   ├── config.py                  # Pydantic-Settings configuration
│   │   │                                - Settings class (env + .env support)
│   │   │                                - PROJECT_ROOT / DATA_DIR constants
│   │   │                                - All JSON data file path properties
│   │   │                                - Global `settings` singleton
│   │   └── exceptions.py              # Domain exception hierarchy
│   │                                      - StampException (base)
│   │                                      - CandidateNotFoundError (404)
│   │                                      - AmpNotFoundError (404)
│   │                                      - AmpLibraryEmptyError (500)
│   │                                      - InvalidSequenceError (400)
│   │                                      - DataLoadError (500)
│   │                                      - BuildError (422)
│   │                                      - FastAPI exception handlers
│   │
│   ├── models/                        # Data models (Pydantic v2)
│   │   ├── __init__.py                # Package marker
│   │   └── schemas.py                 # All Pydantic schemas
│   │                                      - Enums: FilterStatus, LinkerType,
│   │                                        PriorityLevel, ValidationStatus,
│   │                                        AmpRole
│   │                                      - PepMLMCandidate
│   │                                      - AmpRecord
│   │                                      - TargetingDomain, LinkerDomain,
│   │                                        KillingDomain
│   │                                      - BiophysicalProperties
│   │                                      - MockScores (deprecated, null)
│   │                                      - ExperimentalData (all null)
│   │                                      - StructureStatus
│   │                                      - StampCandidate (top-level)
│   │                                      - StampBuildRequest (POST DTO)
│   │                                      - PaginatedResponse[T]
│   │                                      - ApiResponse[T] (unified envelope)
│   │                                      - List-item DTOs (trimmed views)
│   │
│   ├── routers/                       # FastAPI route handlers
│   │   ├── __init__.py                # Package marker
│   │   ├── health.py                  # GET /health
│   │   ├── pepmlm.py                  # GET /api/v1/pepmlm/candidates
│   │   │                                # GET /api/v1/pepmlm/candidates/{id}
│   │   ├── amp.py                     # GET /api/v1/amp/library
│   │   │                                # GET /api/v1/amp/library/{name}
│   │   │                                # GET /api/v1/amp/structures
│   │   └── stamp.py                   # POST /api/v1/stamp/build (CORE)
│   │                                      # GET /api/v1/stamp/templates
│   │                                      # GET /api/v1/stamp/hybrid-candidates
│   │                                      # GET /api/v1/stamp/candidates/{id}
│   │
│   ├── services/                      # Business logic layer
│   │   ├── __init__.py                # Package marker
│   │   ├── stamp_builder.py           # Core STAMP assembly orchestrator
│   │   │                                - _find_pepmlm_candidate()
│   │   │                                - build_stamp()
│   │   ├── amp_selector.py            # AMP selection strategies
│   │   │                                - select_amp() (P4 default + fallback)
│   │   │                                - get_amp_by_name()
│   │   │                                - list_amp_records()
│   │   ├── sequence_validator.py      # Sequence validation utilities
│   │   │                                - validate_sequence()
│   │   │                                - clean_sequence()
│   │   │                                - compute_net_charge()
│   │   │                                - compute_gravy()
│   │   │                                - assemble_stamp_sequence()
│   │   │                                - Constants: VALID_AA, LINKER_SEQUENCE
│   │   └── biocalc.py                 # Lightweight bio calculations
│   │                                      - calculate_length()
│   │                                      - calculate_net_charge_simple()
│   │                                      - calculate_gravy()
│   │                                      - calculate_hydrophobicity_fraction()
│   │                                      - calculate_pi_approximate()
│   │
│   ├── data/                          # Data access layer
│   │   ├── __init__.py                # Package marker
│   │   └── loader.py                  # JSON file loading with @lru_cache
│   │                                      - _load_json() helper
│   │                                      - get_pepmlm_candidates()
│   │                                      - get_priority_amp_library()
│   │                                      - get_stamp_hybrid_candidates()
│   │                                      - get_amp_structure_manifest()
│   │                                      - get_real_amp_candidates()
│   │                                      - get_stamp_template_library()
│   │                                      - get_pepmlm_oprf_top10()
│   │                                      - eager_load_all()
│   │
│   └── utils/                         # Utility helpers
│       ├── __init__.py                # Package marker
│       └── response.py                # Unified response factory functions
│                                          - ok()       -> code 200
│                                          - created()  -> code 201
│                                          - paginated() -> PaginatedResponse
│
├── data/                              # Static JSON data files (read-only)
│   ├── pepmlm_generated_targeting_peptides.json
│   ├── priority_amp_library.json
│   ├── stamp_hybrid_candidates.json
│   ├── amp_structure_manifest.json
│   ├── real_amp_candidates.json
│   ├── stamp_template_library.json
│   └── pepmlm_oprf_top10.json
│
├── tests/                             # Pytest test suite
│   (test files to be added by KimiCode)
│
├── requirements.txt                   # Python dependencies
└── README_BACKEND.md                  # Backend documentation
```

## Layer Architecture

```
┌─────────────────────────────────────────────┐
│  Client (React frontend / curl / browser)    │
└──────────────────┬──────────────────────────┘
                   │ HTTP
┌──────────────────▼──────────────────────────┐
│  routers/         │ FastAPI route handlers   │
│  (health/pepmlm/  │ - URL routing            │
│   amp/stamp)      │ - Query/path params      │
│                   │ - Request validation       │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  services/        │ Business logic           │
│  (stamp_builder/  │ - STAMP assembly rules   │
│   amp_selector/   │ - AMP selection strategy │
│   sequence_       │ - Sequence validation    │
│   validator/      │ - Bio calculations       │
│   biocalc)        │                          │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  data/            │ Data access              │
│  (loader.py)      │ - JSON file I/O          │
│                   │ - LRU caching            │
│                   │ - Eager startup loading  │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  models/          │ Type system              │
│  (schemas.py)     │ - Pydantic v2 models     │
│                   │ - Enums                  │
│                   │ - Request/Response DTOs  │
└─────────────────────────────────────────────┘

Cross-cutting:
  core/config.py       — Settings, paths
  core/exceptions.py   — Domain exceptions + handlers
  utils/response.py    — Response envelope helpers
```

## Design Principles

1. **Single Responsibility** — Each module has one clear purpose.
2. **Dependency Injection** — Services receive data via parameters, not globals.
3. **Fail Fast** — `eager_load_all()` in lifespan raises on missing data files.
4. **No Mock Data** — Experimental fields are always `null`; no pseudo-scores.
5. **Type Safety** — Complete type annotations; Pydantic v2 validation.
6. **DRY** — `ApiResponse[T]` envelope used by every endpoint via `utils/response.py`.
