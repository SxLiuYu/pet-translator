# Pet Translator Reliability Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete and verify the event-driven audio/visual fusion release with robust time handling, API boundaries, compatible authentication, CI, and complete documentation.

**Architecture:** Retain the current FastAPI process and bounded in-memory fusion engine. Add injectable time and ingestion normalization at the fusion boundary, validate HTTP queries at FastAPI's boundary, and keep persistence responsibilities in the existing event repositories.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, pytest, SQLAlchemy, bcrypt, GitHub Actions, Docker

---

### Task 1: Harden fusion time semantics

**Files:**
- Modify: `tests/test_audio_visual_fusion.py`
- Modify: `server/audio_visual_fusion.py`

- [x] Add a failing test proving old observations expire when an injected clock advances.
- [x] Add a failing test proving malformed timestamps normalize without crashing.
- [x] Run `python -m pytest tests/test_audio_visual_fusion.py -q` and confirm the new tests fail for the expected reasons.
- [x] Add a constructor clock dependency, normalize timestamp input, and clean buffers against both current time and latest observation time.
- [x] Run `python -m pytest tests/test_audio_visual_fusion.py -q` and confirm all fusion tests pass.

### Task 2: Enforce API query contracts

**Files:**
- Modify: `tests/test_app_api.py`
- Modify: `server/app.py`

- [x] Add failing tests for `limit=0`, `limit=101`, and unfiltered event listing when `PET_ID` is set.
- [x] Run the focused API tests and confirm contract failures.
- [x] Use FastAPI `Query(ge=1, le=100)` constraints and separate ingestion defaults from event filtering.
- [x] Run `python -m pytest tests/test_app_api.py -q` and confirm all API tests pass.

### Task 3: Remove project-owned authentication deprecations

**Files:**
- Modify: `tests/test_auth.py`
- Modify: `server/auth/database.py`
- Modify: `server/auth/dependencies.py`
- Modify: `server/requirements-auth.txt`

- [x] Add a subprocess test that imports authentication with deprecation warnings treated as errors.
- [x] Run the focused test and confirm Passlib's `crypt` import causes failure.
- [x] Replace Passlib with direct bcrypt hashing/verification and replace deprecated UTC calls.
- [x] Run `python -m pytest tests/test_auth.py -q` and confirm authentication tests pass without warnings.

### Task 4: Add repeatable CI

**Files:**
- Create: `server/requirements-test.txt`
- Create: `.github/workflows/ci.yml`

- [x] Define only the dependencies required by the complete offline test suite.
- [x] Configure Python 3.11 CI to install them, run pytest, compile server modules, and run `git diff --check`.
- [x] Validate workflow YAML syntax locally when a parser is available and inspect the workflow commands.

### Task 5: Document and verify release

**Files:**
- Modify: `README.md`
- Replace: `SUMMARY.md`
- Modify: `session_summary.md`
- Create: `docs/acceptance-report.md`

- [x] Reconcile architecture, versions, endpoints, implementation status, and limitations across documents.
- [x] Run the full pytest suite with strict project-warning checks.
- [x] Run byte compilation, application import/route smoke checks, and `git diff --check`.
- [x] Build the Docker image and smoke-test `/health` when Docker is available; otherwise record the exact environmental blocker.
- [x] Review the complete diff for secrets, runtime artifacts, generated evidence, and unrelated files.
- [x] Record commands, outputs, test counts, limitations, and the implementation commit in the acceptance report.
- [x] Commit the scoped files, push `master`, and verify local HEAD equals `origin/master`.

### Task 6: Close the Docker acceptance gap

**Files:**
- Modify: `Dockerfile`
- Modify: `.dockerignore`
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/superpowers/specs/2026-07-19-reliability-optimization-design.md`
- Modify: `docs/acceptance-report.md`

- [x] Resolve production requirements as binary wheels for the Python 3.9 Linux x86_64 Docker target.
- [x] Reduce the Docker build context without excluding production source or model assets.
- [x] Add an independent CI job that builds the production image and starts the real container command.
- [x] Poll `/health`, validate its response contract, expose failure logs, and clean up the container.
- [ ] Push the workflow and confirm the Docker build and container smoke test pass on GitHub Actions.
- [ ] Record the final workflow run, commit SHAs, commands, and evidence in the acceptance report.
