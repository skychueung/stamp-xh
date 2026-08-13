# KimiCode Task List — STAMP Platform Backend v0.6d

## Project Overview

Build a FastAPI backend that implements the single-candidate STAMP full-process
minimum closed loop:

```
PepMLM targeting peptide + EAAAK linker + 1 AMP = complete three-part STAMP candidate
```

**Key**: Each task builds on the previous one and can be independently verified
by running `pytest`.

---

## Task Dependency Graph

```
Task 1 (Project Skeleton)
  |
  v
Task 2 (Pydantic Models)
  |
  v
Task 3 (Data Loader)
  |
  +------> Task 4 (Sequence Validator) ----+
  |                                         |
  +------> Task 5 (AMP Selector) --------+  |
  |                                      |  |
  +------> Task 6 (STAMP Builder) <------+  |
  |                                         |
  v                                         v
Task 7 (Health + PepMLM Routers)      Task 11 (Service Unit Tests)
  |                                         ^
  v                                         |
Task 8 (AMP Router)                        |
  |                                         |
  v                                         |
Task 9 (STAMP Router - Core) --------------+
  |
  v
Task 10 (Main Entry + Exception Handlers)
  |
  +------> Task 11 (Router Unit Tests)
  |
  v
Task 12 (Integration Tests + README)
```

---

## Task 1: Project Skeleton

- **Objective**: Create directory structure, `requirements.txt`, `.env.example`, and `backend/data/` sample JSON files.
- **Dependencies**: None
- **Input**: Project specification
- **Output**: Runnable project skeleton with all directories and dependencies
- **File List**:
  ```
  backend/
    app/
      __init__.py
      core/
        __init__.py
      models/
        __init__.py
      data/
        __init__.py
      services/
        __init__.py
      routers/
        __init__.py
      utils/
        __init__.py
    data/
      pepmlm_generated_targeting_peptides.json
      priority_amp_library.json
      stamp_hybrid_candidates.json
      amp_structure_manifest.json
      stamp_template_library.json
      pepmlm_oprf_top10.json
  requirements.txt
  .env.example
  ```
- **Acceptance Criteria**:
  1. `mkdir -p backend/app/{core,models,data,services,routers,utils} backend/data` creates the full tree
  2. All `__init__.py` files exist
  3. `pip install -r requirements.txt` succeeds in a clean venv
  4. `python -c "from fastapi import FastAPI; from pydantic import BaseModel; print('ok')"` succeeds
  5. All 6 JSON data files exist in `backend/data/` and are valid JSON (parseable by `json.load`)
  6. `pepmlm_generated_targeting_peptides.json` contains at least 150 candidate entries
  7. `priority_amp_library.json` contains at least P4 and P15 records
- **Verification Command**:
  ```bash
  python -c "
  import json, sys, os
  from pathlib import Path
  errors = 0
  for f in ['pepmlm_generated_targeting_peptides.json',
            'priority_amp_library.json',
            'stamp_hybrid_candidates.json',
            'amp_structure_manifest.json',
            'stamp_template_library.json',
            'pepmlm_oprf_top10.json']:
      path = Path('backend/data') / f
      if not path.exists():
          print(f'MISSING: {f}'); errors += 1
          continue
      try:
          data = json.loads(path.read_text())
          print(f'OK: {f} ({len(str(data))} chars)')
      except Exception as e:
          print(f'BAD JSON: {f}: {e}'); errors += 1
  sys.exit(errors)
  "
  ```

---

## Task 2: Pydantic Model Layer

- **Objective**: Implement all Pydantic v2 schemas in `app/models/schemas.py`.
- **Dependencies**: Task 1
- **Input**: Business rules, JSON data file schemas
- **Output**: Complete model layer with validation
- **File List**:
  ```
  backend/app/models/schemas.py
  ```
- **Model List**:
  - `ApiResponse[T]` — unified response envelope (Generic)
  - `FilterStatus` (Enum) — Pass / Fail / Warning
  - `ValidationStatus` (Enum) — NOT_EXPERIMENTALLY_VALIDATED / IN_VITRO_TESTED / etc.
  - `PriorityLevel` (Enum) — high / medium / low
  - `AmpRole` (Enum) — killing_domain / targeting_domain / linker / full_amp
  - `LinkerType` (Enum) — rigid / flexible / cleavable
  - `PepMLMCandidate` — targeting peptide candidate
  - `AmpRecord` — AMP library record (with clean_sequence validation)
  - `TargetingDomain` — TP domain inside StampCandidate
  - `LinkerDomain` — EAAAK linker domain
  - `KillingDomain` — AMP killing domain
  - `BiophysicalProperties` — computed properties (partially deferred to None)
  - `MockScores` — all fields None in v0.6d
  - `ExperimentalData` — all fields None (lab data placeholders)
  - `StructureStatus` — monomer/complex/experimental booleans
  - `StampCandidate` — top-level assembled candidate
  - `StampBuildRequest` — POST /api/v1/stamp/build request body
  - `PaginatedResponse[T]` — generic paginated wrapper
  - `PepMLMCandidateListItem` / `AmpListItem` / `StampListItem` — lightweight list views
- **Acceptance Criteria**:
  1. `python -c "from app.models.schemas import *; print('All models importable')"` succeeds
  2. `StampCandidate` instantiation with all three domains succeeds
  3. `ApiResponse[StampCandidate].success(data=...)` produces valid JSON
  4. `AmpRecord.model_validate({"amp_name": "P4", "clean_sequence": "FSRFLRRVRRYRPKISFNLEPFFKF", ...})` succeeds
  5. `StampBuildRequest.model_validate({"candidate_id": "OPRF_0001"})` succeeds
  6. `StampBuildRequest.model_validate({"candidate_id": ""})` raises ValidationError
  7. All enum values match the business rules (e.g., `ValidationStatus.NOT_EXPERIMENTALLY_VALIDATED.value == "NOT_EXPERIMENTALLY_VALIDATED"`)
- **Verification Command**:
  ```bash
  cd backend && python -c "
  from app.models.schemas import *
  # Test basic model instantiation
  candidate = PepMLMCandidate(
      candidate_id='OPRF_0001',
      target_name='Pseudomonas_OprF',
      peptide_length=12,
      generated_peptide='DKTKKAFLIAAG',
      ppl_score=9.1933,
      net_charge=2.0
  )
  assert candidate.candidate_id == 'OPRF_0001'
  # Test ApiResponse
  resp = ApiResponse[PepMLMCandidate].success(data=candidate)
  assert resp.code == 200
  print('Model layer OK')
  "
  ```

---

## Task 3: Data Loader Layer

- **Objective**: Implement JSON file loading with `@lru_cache` and eager-load support.
- **Dependencies**: Task 2
- **Input**: 6 JSON data files in `backend/data/`
- **Output**: `app/data/loader.py` with cached accessor functions
- **File List**:
  ```
  backend/app/data/loader.py
  ```
- **Function List**:
  - `_load_json(path)` — low-level JSON loader with error handling
  - `get_pepmlm_candidates()` → `list[dict]` — cached
  - `get_priority_amp_library()` → `list[dict]` — cached
  - `get_stamp_hybrid_candidates()` → `list[dict]` — cached
  - `get_amp_structure_manifest()` → `list[dict]` — cached
  - `get_stamp_template_library()` → `list[dict]` — cached
  - `get_pepmlm_oprf_top10()` → `list[dict]` — cached
  - `eager_load_all()` — touches all caches at startup
- **Acceptance Criteria**:
  1. `python -c "from app.data.loader import eager_load_all; eager_load_all()"` succeeds
  2. `get_pepmlm_candidates()` returns a list with >= 150 entries
  3. `get_priority_amp_library()` returns a list with >= 2 entries (P4, P15)
  4. Each loader is `@lru_cache` decorated (called once, subsequent calls return cached value)
  5. Missing file raises `DataLoadError` (from `app.core.exceptions`)
  6. Malformed JSON raises `DataLoadError` with descriptive message
  7. `eager_load_all()` completes in < 2 seconds for the full dataset
- **Verification Command**:
  ```bash
  cd backend && python -c "
  from app.data.loader import *
  eager_load_all()
  pepmlm = get_pepmlm_candidates()
  amps = get_priority_amp_library()
  print(f'PepMLM candidates: {len(pepmlm)}')
  print(f'AMP records: {len(amps)}')
  assert len(pepmlm) >= 150, f'Expected >= 150, got {len(pepmlm)}'
  assert len(amps) >= 2, f'Expected >= 2, got {len(amps)}'
  # Verify P4 is present
  p4 = next((a for a in amps if a.get('amp_name') == 'P4'), None)
  assert p4 is not None, 'P4 not found in AMP library'
  assert p4['clean_sequence'] == 'FSRFLRRVRRYRPKISFNLEPFFKF'
  print('Data loader OK')
  "
  ```

---

## Task 4: Sequence Validation Service

- **Objective**: Implement amino-acid sequence validation utilities.
- **Dependencies**: Task 1, Task 2 (exceptions)
- **Input**: Sequence validation rules (20 standard AA only)
- **Output**: `app/services/sequence_validator.py`
- **File List**:
  ```
  backend/app/services/sequence_validator.py
  ```
- **Function List**:
  - `validate_sequence(sequence, context="sequence")` → cleaned str or raises `InvalidSequenceError`
  - `clean_sequence(raw)` → `(clean, illegal_char_found, illegal_char_position)`
  - `compute_net_charge(sequence)` → float
  - `compute_gravy(sequence)` → float
  - `assemble_stamp_sequence(tp_sequence, amp_sequence, linker="EAAAK", terminal_mod="-NH2")` → `(raw, display)`
- **Constants**:
  - `VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")`
  - `LINKER_SEQUENCE = "EAAAK"`
  - `LINKER_LENGTH = 5`
  - `TERMINAL_MOD = "-NH2"`
- **Acceptance Criteria**:
  1. `validate_sequence("DKTKKAFLIAAG")` returns `"DKTKKAFLIAAG"`
  2. `validate_sequence("dktkkafliaag")` returns `"DKTKKAFLIAAG"` (auto-uppercase)
  3. `validate_sequence("DKTKKAFL1AAG")` raises `InvalidSequenceError` containing position info
  4. `validate_sequence("")` raises `InvalidSequenceError`
  5. `validate_sequence(None)` raises `InvalidSequenceError`
  6. `assemble_stamp_sequence("ABC", "DEF")` returns `("ABCEAAAKDEF", "ABC-EAAAK-DEF-NH2")`
  7. `compute_net_charge("KKR")` returns `3.0` (K=+1, R=+1 each)
  8. `compute_gravy` returns a float between -5 and +5 for any valid sequence
- **Verification Command**:
  ```bash
  cd backend && python -c "
  from app.services.sequence_validator import *
  # Valid sequence
  assert validate_sequence('DKTKKAFLIAAG') == 'DKTKKAFLIAAG'
  # Auto uppercase
  assert validate_sequence('dktkkafliaag') == 'DKTKKAFLIAAG'
  # Assemble
  raw, display = assemble_stamp_sequence('DKTKKAFLIAAG', 'FSRFLRRVRRYRPKISFNLEPFFKF')
  assert 'EAAAK' in raw
  assert display.endswith('-NH2')
  assert '-' not in raw
  print('Sequence validator OK')
  "
  ```

---

## Task 5: AMP Selection Service

- **Objective**: Implement AMP selection with P4-priority + fallback logic.
- **Dependencies**: Task 2, Task 3
- **Input**: AMP library from `get_priority_amp_library()`
- **Output**: `app/services/amp_selector.py`
- **File List**:
  ```
  backend/app/services/amp_selector.py
  ```
- **Function List**:
  - `select_amp(amp_library, preferred_name=None)` → `AmpRecord`
  - `get_amp_by_name(amp_library, name)` → `AmpRecord`
  - `list_amp_records(amp_library)` → `list[AmpRecord]`
- **Selection Algorithm**:
  1. If `preferred_name` is given and exists → use it
  2. Else if P4 exists → use P4
  3. Else pick first AMP with `priority == "high"`
  4. Else pick the very first AMP in the library
  5. Else raise `AmpLibraryEmptyError`
- **Acceptance Criteria**:
  1. `select_amp(library_with_p4)` returns P4
  2. `select_amp(library_without_p4)` returns the first high-priority AMP
  3. `select_amp(library_with_p4, preferred_name="P15")` returns P15
  4. `select_amp([], preferred_name="P4")` raises `AmpLibraryEmptyError`
  5. `select_amp(library_with_p4, preferred_name="NON_EXISTENT")` raises `AmpNotFoundError`
  6. `get_amp_by_name(library, "P4").amp_name == "P4"`
  7. `get_amp_by_name(library, "non_existent")` raises `AmpNotFoundError`
- **Verification Command**:
  ```bash
  cd backend && python -c "
  from app.services.amp_selector import select_amp, get_amp_by_name
  from app.data.loader import get_priority_amp_library
  
  library = get_priority_amp_library()
  
  # Default selection (should be P4)
  result = select_amp(library)
  assert result.amp_name == 'P4', f'Expected P4, got {result.amp_name}'
  assert result.clean_sequence == 'FSRFLRRVRRYRPKISFNLEPFFKF'
  
  # Explicit selection
  p15 = select_amp(library, preferred_name='P15')
  assert p15.amp_name == 'P15'
  
  # Lookup by name
  p4 = get_amp_by_name(library, 'P4')
  assert p4.amp_name == 'P4'
  
  print('AMP selector OK')
  "
  ```

---

## Task 6: STAMP Build Engine

- **Objective**: Implement the core STAMP assembly pipeline.
- **Dependencies**: Task 2, Task 3, Task 4, Task 5
- **Input**: PepMLM candidate ID, AMP library, targeting peptide list
- **Output**: `app/services/stamp_builder.py`
- **File List**:
  ```
  backend/app/services/stamp_builder.py
  ```
- **Function List**:
  - `_find_pepmlm_candidate(candidate_id, candidates)` → `PepMLMCandidate`
  - `build_stamp(candidate_id, amp_library, pepmlm_candidates, preferred_amp_name=None)` → `StampCandidate`
- **Build Pipeline**:
  1. Resolve PepMLM candidate by ID → `CandidateNotFoundError` if missing
  2. Select AMP → `AmpLibraryEmptyError` if empty
  3. Validate both sequences → `InvalidSequenceError` if illegal chars
  4. Concatenate: `raw = TP + EAAAK + AMP`
  5. Format: `display = TP-EAAAK-AMP-NH2`
  6. Compute lightweight biophysical properties (net charge from residues)
  7. Populate all experimental fields as `None`
  8. Set `mock_scores = None`
  9. Set `validation_status = "NOT_EXPERIMENTALLY_VALIDATED"`
  10. Set `is_complete = True`
- **Acceptance Criteria**:
  1. `build_stamp("OPRF_0001", amp_lib, pepmlm_list)` returns `StampCandidate`
  2. Result has `candidate_id == "stamp_oprf_0001"`
  3. Result `killing_domain.name == "P4"`
  4. Result `linker.sequence == "EAAAK"`
  5. Result `raw_full_sequence == TP + "EAAAK" + AMP`
  6. Result `display_full_sequence.endswith("-NH2")`
  7. Result `mock_scores is None`
  8. Result `validation_status == "NOT_EXPERIMENTALLY_VALIDATED"`
  9. Result `experimental.MIC_ug_ml is None`
  10. Result `experimental.ipTM is None`
  11. Result `experimental.pDockQ is None`
  12. Non-existent peptide raises `CandidateNotFoundError`
  13. Empty AMP library raises `AmpLibraryEmptyError`
- **Verification Command**:
  ```bash
  cd backend && python -c "
  from app.data.loader import get_pepmlm_candidates, get_priority_amp_library
  from app.services.stamp_builder import build_stamp
  
  pepmlm = get_pepmlm_candidates()
  amps = get_priority_amp_library()
  
  stamp = build_stamp('OPRF_0001', amps, pepmlm)
  
  assert stamp.candidate_id == 'stamp_oprf_0001'
  assert stamp.killing_domain.name == 'P4'
  assert stamp.linker.sequence == 'EAAAK'
  assert stamp.mock_scores is None
  assert stamp.validation_status == 'NOT_EXPERIMENTALLY_VALIDATED'
  assert stamp.experimental.MIC_ug_ml is None
  assert stamp.experimental.ipTM is None
  assert stamp.experimental.pDockQ is None
  assert stamp.display_full_sequence.endswith('-NH2')
  assert 'EAAAK' in stamp.raw_full_sequence
  assert '-' not in stamp.raw_full_sequence
  
  print(f'STAMP build OK: {stamp.candidate_id}')
  print(f'  TP: {stamp.targeting_domain.sequence}')
  print(f'  Linker: {stamp.linker.sequence}')
  print(f'  AMP: {stamp.killing_domain.sequence}')
  print(f'  Full: {stamp.display_full_sequence}')
  "
  ```

---

## Task 7: Health + PepMLM Routers

- **Objective**: Implement health check and PepMLM candidate endpoints.
- **Dependencies**: Task 2, Task 3
- **Input**: Data loader functions, Pydantic models
- **Output**:
  ```
  backend/app/routers/health.py
  backend/app/routers/pepmlm.py
  ```
- **Endpoint List**:
  - `GET /health` → `ApiResponse[{status, version}]`
  - `GET /api/v1/pepmlm/candidates?page=N&page_size=M&filter_status=X` → paginated list
  - `GET /api/v1/pepmlm/candidates/{candidate_id}` → single candidate
- **Acceptance Criteria**:
  1. `GET /health` returns `{"code": 200, "message": "ok", "data": {"status": "healthy", "version": "v0.6d"}}`
  2. `GET /api/v1/pepmlm/candidates` returns paginated list with `code: 200`
  3. `GET /api/v1/pepmlm/candidates?page=1&page_size=5` returns exactly 5 items (or all if < 5)
  4. `GET /api/v1/pepmlm/candidates?filter_status=Pass` returns only `Pass` candidates
  5. `GET /api/v1/pepmlm/candidates/OPRF_0001` returns the specific candidate
  6. `GET /api/v1/pepmlm/candidates/NON_EXISTENT` returns 404 with `ApiResponse` envelope
  7. `GET /api/v1/pepmlm/candidates?page=999` returns empty `items` list (not an error)
- **Verification Command**:
  ```bash
  cd backend && pytest tests/test_health.py tests/test_pepmlm.py -v
  ```

---

## Task 8: AMP Router

- **Objective**: Implement AMP library and structure endpoints.
- **Dependencies**: Task 2, Task 3
- **Input**: Data loader functions, Pydantic models
- **Output**:
  ```
  backend/app/routers/amp.py
  ```
- **Endpoint List**:
  - `GET /api/v1/amp/library` → full AMP library
  - `GET /api/v1/amp/library/{amp_name}` → single AMP (e.g., P4)
  - `GET /api/v1/amp/structures` → structure manifest
- **Acceptance Criteria**:
  1. `GET /api/v1/amp/library` returns list with at least P4 and P15
  2. `GET /api/v1/amp/library/P4` returns P4 record with `clean_sequence == "FSRFLRRVRRYRPKISFNLEPFFKF"`
  3. `GET /api/v1/amp/library/NON_EXISTENT` returns 404 with `ApiResponse` envelope
  4. `GET /api/v1/amp/structures` returns structure manifest
  5. P4 `clean_sequence` does NOT contain trailing `"5"`
  6. P4 `raw_sequence` DOES contain trailing `"5"`
- **Verification Command**:
  ```bash
  cd backend && pytest tests/test_amp.py -v
  ```

---

## Task 9: STAMP Router (Core)

- **Objective**: Implement the STAMP build endpoint and retrieval endpoints.
- **Dependencies**: Task 2, 3, 4, 5, 6
- **Input**: `StampBuilder`, data loaders, request/response models
- **Output**:
  ```
  backend/app/routers/stamp.py
  ```
- **Endpoint List**:
  - `POST /api/v1/stamp/build` → build new STAMP (core)
  - `GET /api/v1/stamp/templates` → template library
  - `GET /api/v1/stamp/hybrid-candidates` → pre-built candidates
  - `GET /api/v1/stamp/candidates/{candidate_id}` → retrieve built candidate
- **Request/Response Format**:
  ```json
  // POST /api/v1/stamp/build
  {
    "candidate_id": "OPRF_0001",
    "amp_name": "P4"  // optional, defaults to P4
  }
  ```
- **Build Flow**:
  1. Parse `StampBuildRequest` from JSON body
  2. Resolve targeting peptide by `candidate_id`
  3. Resolve AMP (P4 default, or explicit `amp_name`)
  4. Call `build_stamp()` from service layer
  5. Cache result in `_stamp_build_cache: dict[str, dict]`
  6. Return `ApiResponse[StampCandidate]`
- **Acceptance Criteria**:
  1. `POST /api/v1/stamp/build {"candidate_id": "OPRF_0001"}` returns 200 with complete StampCandidate
  2. Default AMP selection yields P4
  3. Explicit `amp_name: "P15"` yields P15
  4. Non-existent `candidate_id` returns 404
  5. Invalid peptide sequence returns 400 (or 422)
  6. `raw_full_sequence == TP + "EAAAK" + AMP`
  7. `display_full_sequence == TP-EAAAK-AMP-NH2`
  8. `mock_scores is None`
  9. `validation_status == "NOT_EXPERIMENTALLY_VALIDATED"`
  10. All experimental fields are null
  11. `-NH2` only at C-terminus
  12. Built candidate can be retrieved via `GET /api/v1/stamp/candidates/{candidate_id}`
- **Verification Command**:
  ```bash
  cd backend && pytest tests/test_stamp.py -v
  ```

---

## Task 10: Main Entry + Exception Handlers

- **Objective**: Wire everything together in `main.py` with lifespan management.
- **Dependencies**: Task 7, 8, 9
- **Input**: All routers, exception handlers, data loader
- **Output**:
  ```
  backend/app/main.py
  ```
- **Responsibilities**:
  - Create `FastAPI()` app instance
  - Register `StampException` handler → `JSONResponse` with `ApiResponse` envelope
  - Register generic `Exception` handler → 500 with safe message
  - Include all routers: health, pepmlm, amp, stamp
  - Lifespan context manager: call `eager_load_all()` on startup
  - Expose `get_data_store()` or equivalent for router dependency injection
- **Acceptance Criteria**:
  1. `python -c "from app.main import app; print(type(app).__name__)"` outputs `FastAPI`
  2. `uvicorn app.main:app --reload` starts without errors
  3. `GET /health` returns 200 via Uvicorn
  4. `GET /docs` shows all endpoints in Swagger UI
  5. `POST /api/v1/stamp/build` with valid body returns 200
  6. Any `StampException` raised in any router returns proper `ApiResponse` JSON
  7. Any unhandled exception returns 500 with safe message (no stack trace in production)
- **Verification Command**:
  ```bash
  cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000 &
  sleep 2
  curl -s http://127.0.0.1:8000/health | python -m json.tool
  curl -s http://127.0.0.1:8000/api/v1/pepmlm/candidates | python -c "import sys,json; d=json.load(sys.stdin); print(f'Candidates: {d[\"data\"][\"total\"]}')"
  kill %1
  ```

---

## Task 11: Unit Tests (Service Layer)

- **Objective**: Comprehensive unit tests for all service-layer functions.
- **Dependencies**: Task 4, 5, 6
- **Input**: Service implementations, test fixtures
- **Output**:
  ```
  tests/conftest.py       (shared fixtures)
  tests/test_services.py  (service unit tests)
  ```
- **Test Coverage**:

  **AMP Selector** (`TestAMPSelector`):
  - `test_amp_selector_p4_priority` — P4 present → P4 selected
  - `test_amp_selector_fallback` — P4 absent → first high-priority fallback
  - `test_amp_selector_explicit_preferred` — explicit name overrides P4
  - `test_amp_selector_preferred_not_found` — missing preferred → `AmpNotFoundError`
  - `test_amp_selector_empty_library` — empty library → `AmpLibraryEmptyError`

  **Sequence Validator** (`TestSequenceValidator`):
  - `test_sequence_validator_valid` — standard AA passes
  - `test_sequence_validator_valid_long` — long sequence passes
  - `test_sequence_validator_invalid_char` — illegal char → `InvalidSequenceError`
  - `test_sequence_validator_invalid_char_x` — 'X' rejected
  - `test_sequence_validator_empty` — empty → error
  - `test_sequence_validator_whitespace_only` — whitespace → error
  - `test_sequence_validator_lowercase` — auto-uppercase
  - `test_sequence_validator_trailing_whitespace` — strip whitespace
  - `test_sequence_validator_all_20_aa` — all 20 standard AA accepted

  **STAMP Builder** (`TestStampBuilder`):
  - `test_build_stamp_full_pipeline` — complete build validates all fields
  - `test_build_stamp_with_explicit_amp` — explicit AMP selection
  - `test_build_stamp_peptide_not_found` — missing peptide → `CandidateNotFoundError`
  - `test_build_stamp_empty_amp_library` — empty AMP → `AmpLibraryEmptyError`

  **Sequence Assembly** (`TestSequenceAssembly`):
  - `test_assemble_stamp_sequence_basic` — correct raw + display
  - `test_assemble_stamp_sequence_no_dash_in_raw` — no dashes in raw
  - `test_assemble_stamp_sequence_display_ends_with_nh2` — C-terminal NH2
- **Acceptance Criteria**:
  1. All service tests pass: `pytest tests/test_services.py -v` → 100% pass
  2. No test takes > 1 second
  3. Every business rule has at least one test
  4. Edge cases (empty input, missing data, illegal chars) are covered
- **Verification Command**:
  ```bash
  cd backend && pytest tests/test_services.py -v --tb=short
  ```

---

## Task 12: Integration Tests + README

- **Objective**: End-to-end integration tests and project documentation.
- **Dependencies**: Task 7, 8, 9, 10, 11
- **Input**: Complete application with all routes
- **Output**:
  ```
  tests/test_health.py       (integration)
  tests/test_pepmlm.py       (integration)
  tests/test_amp.py          (integration)
  tests/test_stamp.py        (integration — core)
  backend/README.md
  ```
- **Integration Test Coverage**:

  **Health** (`tests/test_health.py`):
  - `test_health_check` — 200, correct response shape

  **PepMLM** (`tests/test_pepmlm.py`):
  - `test_list_candidates` — paginated list
  - `test_list_candidates_filter_status_pass` — Pass filter
  - `test_list_candidates_filter_status_warning` — Warning filter
  - `test_list_candidates_filter_status_fail` — Fail filter
  - `test_list_candidates_pagination` — page/page_size respected
  - `test_list_candidates_out_of_range_page` — empty items, not error
  - `test_get_candidate` — single lookup
  - `test_get_candidate_not_found` — 404

  **AMP** (`tests/test_amp.py`):
  - `test_list_amps` — library list
  - `test_get_amp` — P4 lookup
  - `test_get_amp_not_found` — 404
  - `test_p4_clean_sequence` — no trailing "5"
  - `test_get_amp_structures` — structure manifest

  **STAMP** (`tests/test_stamp.py`) — Core:
  - `test_build_stamp_default` — auto-select P4
  - `test_build_stamp_with_p4` — explicit P4
  - `test_build_stamp_p4_not_in_library` — P4 absent, fallback
  - `test_build_stamp_peptide_not_found` — 404
  - `test_build_stamp_invalid_peptide_sequence` — 400
  - `test_stamp_full_sequence_format` — TP + EAAAK + AMP
  - `test_stamp_display_format` — TP-EAAAK-AMP-NH2
  - `test_stamp_no_mock_scores` — mock_scores is null
  - `test_stamp_not_experimentally_validated` — correct status
  - `test_stamp_experimental_all_null` — all lab fields null
  - `test_stamp_c_terminal_nh2_only` — NH2 only at C-term
  - `test_stamp_is_complete` — is_complete == True
  - `test_stamp_orientation` — N-to-C
  - `test_stamp_linker_is_eaaak` — linker == EAAAK
  - `test_get_stamp_templates` — template list
  - `test_get_hybrid_candidates` — hybrid list
  - `test_get_stamp_candidate_by_id` — build + retrieve round-trip
  - `test_get_stamp_candidate_not_found` — 404

- **README Requirements**:
  1. Project description (1 paragraph)
  2. Tech stack list
  3. Quick start (install → run → test)
  4. API endpoint table
  5. Data file description
  6. Test command
- **Acceptance Criteria**:
  1. `pytest tests/ -v` → all tests pass (expected: ~30+ tests)
  2. Test suite completes in < 30 seconds
  3. README includes quick start that works on a fresh clone
  4. All endpoints documented in README table
  5. No test failures, no warnings from deprecated APIs
- **Verification Command**:
  ```bash
  cd backend && pytest tests/ -v --tb=short
  ```

---

## Appendix: Quick Reference

### Running Tests

```bash
# All tests
cd backend && pytest tests/ -v

# Single module
cd backend && pytest tests/test_stamp.py -v

# Single test
cd backend && pytest tests/test_stamp.py::test_build_stamp_default -v

# With coverage
cd backend && pytest tests/ --cov=app --cov-report=term-missing
```

### Running the Server

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

### API Endpoints Summary

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/pepmlm/candidates` | List targeting peptides (paginated) |
| GET | `/api/v1/pepmlm/candidates/{id}` | Single targeting peptide |
| GET | `/api/v1/amp/library` | AMP library |
| GET | `/api/v1/amp/library/{name}` | Single AMP |
| GET | `/api/v1/amp/structures` | Structure manifest |
| POST | `/api/v1/stamp/build` | **Build STAMP (core)** |
| GET | `/api/v1/stamp/templates` | Template library |
| GET | `/api/v1/stamp/hybrid-candidates` | Pre-built hybrids |
| GET | `/api/v1/stamp/candidates/{id}` | Retrieve built STAMP |
