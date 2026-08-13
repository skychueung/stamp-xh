# STAMP Platform Backend

FastAPI-based backend for the **STAMP** (Synergistic Targeting Antimicrobial Peptide) platform.

## Overview

STAMP is a three-part molecular architecture:

```
[Targeting Peptide (TP)] — [Linker: EAAAK] — [AMP (Killing Domain)] — NH2
```

This backend provides RESTful APIs to:
- Browse PepMLM-generated targeting peptide candidates
- Query the priority AMP library (102 peptides, default P4)
- **Build STAMP hybrid candidates** (`POST /api/v1/stamp/build`)
- Access structure manifests and template libraries

**Key principle**: No mock experimental data (ipTM, pDockQ, MIC, MBC, etc.) is ever fabricated. All experimental fields are `null` pending real laboratory assays.

## Technology Stack

| Component | Version |
|-----------|---------|
| Python | 3.10+ |
| FastAPI | 0.110+ |
| Pydantic | v2 |
| Uvicorn | 0.27+ |
| Pydantic-Settings | 2.1+ |

## Quick Start

### 1. Install Dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Prepare Data Files

Copy JSON data files from the frontend project into `backend/data/`:

```
backend/data/
  pepmlm_generated_targeting_peptides.json
  priority_amp_library.json
  stamp_hybrid_candidates.json
  amp_structure_manifest.json
  real_amp_candidates.json
  stamp_template_library.json
  pepmlm_oprf_top10.json
```

### 3. Run the Server

```bash
# Development (with auto-reload and docs)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. Verify

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "code": 200,
  "message": "STAMP backend is healthy",
  "data": {
    "status": "ok",
    "service": "stamp-backend"
  }
}
```

## API Endpoints

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |

### PepMLM Candidates
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/pepmlm/candidates` | List candidates (paginated, filter by `filter_status`) |
| GET | `/api/v1/pepmlm/candidates/{candidate_id}` | Get single candidate |

### AMP Library
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/amp/library` | List AMP library (paginated) |
| GET | `/api/v1/amp/library/{amp_name}` | Get single AMP |
| GET | `/api/v1/amp/structures` | AMP structure manifest |

### STAMP Candidates
| Method | Path | Description |
|--------|------|-------------|
| **POST** | **`/api/v1/stamp/build`** | **Build STAMP candidate (core endpoint)** |
| GET | `/api/v1/stamp/templates` | STAMP template library |
| GET | `/api/v1/stamp/hybrid-candidates` | Existing hybrid candidates |
| GET | `/api/v1/stamp/candidates/{candidate_id}` | Get STAMP candidate |

### Unified Response Format

Every endpoint returns:
```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

### Core Endpoint Example

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/stamp/build \
  -H "Content-Type: application/json" \
  -d '{"candidate_id": "OPRF_0001", "amp_name": "P4"}'
```

**Response:**
```json
{
  "code": 201,
  "message": "STAMP candidate built successfully",
  "data": {
    "candidate_id": "stamp_oprf_0001",
    "target_molecule": "Pseudomonas OprF",
    "targeting_domain": {
      "name": "OPRF_0001",
      "sequence": "DKTKKAFLIAAG",
      "length": 12,
      "net_charge": 2.0,
      "gravy": 0.017
    },
    "linker": {
      "name": "EAAAK",
      "sequence": "EAAAK",
      "length": 5,
      "type": "rigid"
    },
    "killing_domain": {
      "name": "P4",
      "sequence": "FSRFLRRVRRYRPKISFNLEPFFKF",
      "length": 25,
      "net_charge": 7,
      "gravy": -0.592
    },
    "orientation": "N-to-C",
    "terminal_modification": "-NH2",
    "raw_full_sequence": "DKTKKAFLIAAGEAAAKFSRFLRRVRRYRPKISFNLEPFFKF",
    "display_full_sequence": "DKTKKAFLIAAG-EAAAK-FSRFLRRVRRYRPKISFNLEPFFKF-NH2",
    "is_complete": true,
    "biophysical": {
      "length": 42,
      "net_charge": 9,
      "pI": null,
      "GRAVY": null,
      "hydrophobicity_fraction": null
    },
    "mock_scores": null,
    "experimental": {
      "MIC_ug_ml": null,
      "MBC_ug_ml": null,
      "hemolysis_percent": null,
      "LPS_binding_Kd_nM": null,
      "pLDDT": null,
      "ipTM": null,
      "pDockQ": null,
      "note": "Reserved for real experimental data"
    },
    "structure_status": {
      "monomer_predicted": false,
      "complex_predicted": false,
      "experimental_structure": false
    },
    "validation_status": "NOT_EXPERIMENTALLY_VALIDATED"
  }
}
```

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI entry point, lifespan, CORS
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Pydantic-settings, paths
│   │   └── exceptions.py        # Domain exceptions + handlers
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py           # All Pydantic v2 models
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py            # GET /health
│   │   ├── pepmlm.py            # PepMLM candidate endpoints
│   │   ├── amp.py               # AMP library endpoints
│   │   └── stamp.py             # STAMP build + query endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── stamp_builder.py     # Core STAMP assembly logic
│   │   ├── amp_selector.py      # AMP selection (default P4)
│   │   ├── sequence_validator.py # Sequence validation + helpers
│   │   └── biocalc.py           # Lightweight bio calculations
│   ├── data/
│   │   ├── __init__.py
│   │   └── loader.py            # JSON data loading (cached)
│   └── utils/
│       ├── __init__.py
│       └── response.py          # Unified response wrappers
├── data/                        # JSON data files (from frontend)
│   ├── pepmlm_generated_targeting_peptides.json
│   ├── priority_amp_library.json
│   ├── stamp_hybrid_candidates.json
│   ├── amp_structure_manifest.json
│   ├── real_amp_candidates.json
│   ├── stamp_template_library.json
│   └── pepmlm_oprf_top10.json
├── tests/                       # Pytest test suite
├── requirements.txt
└── README_BACKEND.md
```

## Business Rules

| Rule | Implementation |
|------|----------------|
| Linker is always `EAAAK` | `services/sequence_validator.py` — `LINKER_SEQUENCE` constant |
| Default AMP is P4 | `services/amp_selector.py` — `DEFAULT_AMP_NAME = "P4"` |
| AMP uses `cleanSequence` | `services/amp_selector.py` — validates via `AmpRecord` |
| `-NH2` only at C-terminus | `services/stamp_builder.py` — appended in `assemble_stamp_sequence` |
| No mock experimental data | All experimental fields default to `null` |
| `validation_status` always `NOT_EXPERIMENTALLY_VALIDATED` | Hard-coded in `StampCandidate` factory |
| `mock_scores` is `null` in v0.6d | Explicitly set to `None` in builder |
| `biophysical.pI/GRAVY/hydrophobicity_fraction` not computed | Left as `null` (deferred to future pipeline) |

## Configuration

Settings are loaded from environment variables (highest priority) or a `.env` file.

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | STAMP Platform API | Display name |
| `APP_VERSION` | 0.6.0 | API version |
| `DEBUG` | False | Enable debug mode |
| `HOST` | 0.0.0.0 | Bind address |
| `PORT` | 8000 | Bind port |
| `CORS_ORIGINS` | `["*"]` | Allowed origins |
| `PEPMLM_CANDIDATES_FILE` | `pepmlm_generated_targeting_peptides.json` | Data file path |
| `PRIORITY_AMP_LIBRARY_FILE` | `priority_amp_library.json` | Data file path |

## Development

### Run Tests
```bash
pytest tests/ -v
```

### Type Check
```bash
mypy app/
```

### Lint
```bash
ruff check app/
```

## License

Proprietary — part of the STAMP antimicrobial peptide research platform.
