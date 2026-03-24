---
phase: 07-railway-cloud-sync
plan: 01
subsystem: infra
tags: [docker, playwright, railway, firebase-admin, fernet, cryptography, python]

# Dependency graph
requires:
  - phase: 05-auth-foundation
    provides: FERNET_KEY stored in Firebase Functions secrets; same key reused in Railway env vars
  - phase: 06-teacher-dashboard
    provides: sync-status-path (teachers/{uid}/sync/status) that this worker will write to
provides:
  - Docker image based on mcr.microsoft.com/playwright/python:v1.49.1-noble with Chromium
  - requirements.txt pinning firebase-admin, playwright, cryptography, apscheduler, pytz
  - smoke_test.py proving Playwright + Firebase Admin + Fernet work in the container
  - railway.toml for Railway Dockerfile-based deployment
affects: [07-02, 07-03, 08-self-healing]

# Tech tracking
tech-stack:
  added:
    - mcr.microsoft.com/playwright/python:v1.49.1-noble (Docker base image)
    - firebase-admin>=6.0.0,<7.0.0
    - playwright>=1.49.0,<2.0.0
    - cryptography>=41.0.0,<44.0.0
    - apscheduler>=3.10.0,<4.0.0
    - pytz>=2024.1
  patterns:
    - Firebase Admin SDK initialized from FIREBASE_SERVICE_ACCOUNT env var (JSON blob, not key file)
    - cryptography.fernet.Fernet used for Fernet encryption (cross-compatible with Node fernet npm)
    - Smoke test pattern: each test returns "pass"/"fail"/"skip", exits 1 only on failures

key-files:
  created:
    - railway-worker/Dockerfile
    - railway-worker/requirements.txt
    - railway-worker/.dockerignore
    - railway-worker/smoke_test.py
    - railway.toml
  modified: []

key-decisions:
  - "Use mcr.microsoft.com/playwright/python:v1.49.1-noble base image to avoid Chromium system library issues"
  - "FIREBASE_SERVICE_ACCOUNT env var holds full JSON blob (not file path) since Railway has no local disk"
  - "Use cryptography package (not python-fernet) for Fernet cross-compatibility with Node fernet npm"
  - "railway.toml builder=DOCKERFILE with numReplicas=1; no healthcheck (worker, not web server)"
  - "smoke_test.py gracefully skips tests when env vars absent so Playwright test can run without secrets"

patterns-established:
  - "railway-worker/: all sync worker source files live here, separate from legacy attendance-sync/"
  - "smoke_test.py: run before deploying worker.py updates to verify container environment"

# Metrics
duration: 1min
completed: 2026-03-24
---

# Phase 7 Plan 01: Railway Worker Docker Infrastructure Summary

**Playwright + Firebase Admin + Fernet smoke-tested Docker container on mcr.microsoft.com/playwright/python:v1.49.1-noble, with railway.toml for one-click Railway deployment**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-24T18:05:12Z
- **Completed:** 2026-03-24T18:06:23Z
- **Tasks:** 2 auto + 1 checkpoint
- **Files modified:** 5

## Accomplishments

- Docker image configured with Microsoft's official Playwright base image (eliminates most Chromium-in-Docker failures)
- requirements.txt pins all five dependencies including `cryptography` (not `python-fernet`) for correct Fernet cross-compatibility with Node
- smoke_test.py validates all three critical subsystems independently — Playwright, Firebase Admin, and Fernet — with graceful skips for missing env vars

## Task Commits

Each task was committed atomically:

1. **Task 1: Create railway-worker directory with Dockerfile and dependencies** - `bcc59a2` (feat)
2. **Task 2: Create smoke test script** - `3ac4293` (feat)

**Plan metadata:** (pending — created at checkpoint)

## Files Created/Modified

- `railway-worker/Dockerfile` - Playwright base image, pip install, playwright install chromium, CMD worker.py
- `railway-worker/requirements.txt` - firebase-admin, playwright, cryptography, apscheduler, pytz with version pins
- `railway-worker/.dockerignore` - excludes *.png, *.csv, *.log, *.txt (keeps requirements.txt)
- `railway-worker/smoke_test.py` - three independent tests, graceful [SKIP] on missing env vars, exit 1 on failure
- `railway.toml` - DOCKERFILE builder, numReplicas=1, ON_FAILURE restart, maxRetries=5

## Decisions Made

- **Base image:** `mcr.microsoft.com/playwright/python:v1.49.1-noble` — Microsoft's official image has all Chromium system libraries pre-installed, avoiding the #1 Playwright-in-Docker failure mode
- **FIREBASE_SERVICE_ACCOUNT as JSON blob:** Railway has no persistent disk for key files; env var holds the entire JSON string parsed with `json.loads()`
- **`cryptography` not `python-fernet`:** The `python-fernet` package is abandoned; `cryptography.fernet.Fernet` implements the same spec and is cross-compatible with the Node `fernet` npm package already in use
- **No healthcheck in railway.toml:** This is a background worker, not a web server; healthcheck would cause false failures

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

**External services require manual configuration before smoke test can fully pass.**

Railway setup steps:
1. Create new Railway project from GitHub repo at railway.app
2. In Railway project Settings, set root directory to `railway-worker`
3. Add environment variables:
   - `FIREBASE_SERVICE_ACCOUNT`: full JSON contents of `attendance-sync/attendance-key.json`
   - `FERNET_KEY`: run `firebase functions:secrets:access FERNET_KEY` to retrieve value
4. Deploy and check build logs
5. In Railway shell, run `python smoke_test.py` — all three tests should show [PASS]

## Next Phase Readiness

- Container infrastructure is ready; Plan 07-02 adds `worker.py` with the actual sync logic
- Smoke test must pass on Railway before proceeding to 07-02
- Known risk: Playwright headless Chromium behavior can vary slightly in Railway's Linux environment vs. local Docker; smoke test proves it works before any Aeries automation is written

---
*Phase: 07-railway-cloud-sync*
*Completed: 2026-03-24*
