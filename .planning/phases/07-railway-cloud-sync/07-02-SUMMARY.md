---
phase: 07-railway-cloud-sync
plan: 02
subsystem: infra
tags: [railway, apscheduler, playwright, firebase-admin, fernet, python, firestore]

# Dependency graph
requires:
  - phase: 07-01
    provides: Dockerfile with Playwright + Python base image, requirements.txt with all deps
  - phase: 05-auth-foundation
    provides: teachers/{uid}/credentials/aeries Firestore path and Fernet encryption pattern
  - phase: 06-teacher-dashboard
    provides: teachers/{uid}/sync/status onSnapshot listener in dashboard (watchSyncStatus)
provides:
  - railway-worker/firestore_client.py — Firebase Admin init from env var, 7 Firestore helpers
  - railway-worker/sync_engine.py — per-teacher Playwright sync with error categorization
  - railway-worker/worker.py — APScheduler orchestrator, 30-min intervals, graceful shutdown
affects:
  - 07-03 (if exists) — self-healing or verification phases
  - 08-self-healing — sync logs and error categories are inputs to LLM self-healing

# Tech tracking
tech-stack:
  added: []
  patterns:
    - APScheduler BlockingScheduler for long-running Railway worker
    - Time-of-day guard (08:00–16:00 PT weekdays) checked on every job fire
    - Per-teacher isolation: each uid wrapped in try/except, failures don't block others
    - Freshness check before sync: compare lastSyncTime vs latest sign-in Timestamp
    - Fernet decrypt in Python from encryptedPassword stored by Node Cloud Functions

key-files:
  created:
    - railway-worker/firestore_client.py
    - railway-worker/sync_engine.py
    - railway-worker/worker.py
  modified: []

key-decisions:
  - "Time-of-day guard in run_all_teachers() (not scheduler config) — scheduler fires every 30 min always, guard is a cheap early return outside school hours"
  - "sync_teacher() never raises — all errors caught, written to Firestore, reflected in result dict"
  - "Skipped syncs (no_data, already_synced) do NOT write sync/status — avoids overwriting last real sync time"
  - "Immediate startup sync on deploy — no 30-min wait for first run"
  - "SIGTERM → scheduler.shutdown(wait=False) for Railway graceful deploy handoff"

patterns-established:
  - "worker.py pattern: validate env → init Firebase → immediate run → schedule → block"
  - "sync_engine.py pattern: check freshness → decrypt creds → fetch data → Playwright → write status"
  - "Error categorization: 4 categories (credentials_invalid, aeries_unreachable, selector_broken, unknown)"
  - "Unsyncable students list: individual student failures accumulate, whole sync continues"

# Metrics
duration: 4min
completed: 2026-03-24
---

# Phase 7 Plan 02: Railway Sync Worker — Core Files Summary

**APScheduler worker with per-teacher Playwright sync: reads Firestore attendance, uploads to Aeries, writes sync/status every 30 minutes on weekdays 8AM–4PM PT**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-24T18:23:34Z
- **Completed:** 2026-03-24T18:27:13Z
- **Tasks:** 3 auto tasks + 1 checkpoint
- **Files created:** 3

## Accomplishments

- Three-file Railway worker: `firestore_client.py` (data layer), `sync_engine.py` (sync logic), `worker.py` (orchestrator)
- Adapted existing `upload_to_aeries.py` Playwright logic and selector strategies into cloud context
- Full error categorization (credentials_invalid, aeries_unreachable, selector_broken, unknown) → friendly dashboard messages
- Freshness check prevents redundant syncs when no new data since last run
- Individual student failures accumulate in unsyncable list without stopping the overall sync

## Task Commits

1. **Task 1: Create firestore_client.py** - `a2b1250` (feat)
2. **Task 2: Create sync_engine.py** - `9d3d473` (feat)
3. **Task 3: Create worker.py** - `a429200` (feat)

## Files Created/Modified

- `railway-worker/firestore_client.py` — Firebase Admin init from FIREBASE_SERVICE_ACCOUNT env var; get_db(), get_all_teacher_uids(), get_teacher_credentials(), get_teacher_attendance(), get_last_sync_time(), get_latest_attendance_timestamp(), write_sync_status(), get_teacher_profile()
- `railway-worker/sync_engine.py` — sync_teacher() 5-step flow; SELECTOR_STRATEGIES + find_element_with_fallback(); Fernet decryption; retry_login decorator (3 attempts, 5/15/45s); categorize_error() with 4 categories
- `railway-worker/worker.py` — BlockingScheduler 30-min interval; run_all_teachers() with per-teacher try/except; SIGTERM/SIGINT handlers; env-var validation + fail-fast; immediate startup sync

## Decisions Made

- **Skipped syncs don't write sync/status**: If a teacher has no data today (weekend/holiday) or data hasn't changed, sync_teacher() returns `skipped` without touching Firestore. This preserves the last real sync timestamp on the dashboard.
- **Time-of-day guard in job body, not scheduler**: Scheduler fires every 30 min unconditionally; `run_all_teachers()` does the time check. This avoids APScheduler timezone edge cases and makes the guard easy to test.
- **SIGTERM → shutdown(wait=False)**: Railway sends SIGTERM when redeploying. `wait=False` lets the current sync finish within the kill timeout without blocking indefinitely.

## Deviations from Plan

None — plan executed exactly as written. All selector strategies, checkbox logic, and settle-time thresholds copied verbatim from the source files.

## Issues Encountered

None.

## User Setup Required

Before Railway worker can run:
1. Set `FIREBASE_SERVICE_ACCOUNT` in Railway Variables — full service-account JSON string
2. Set `FERNET_KEY` in Railway Variables — same key used by Cloud Functions
3. Push these files to GitHub → Railway auto-builds from Dockerfile

## Next Phase Readiness

- Worker is ready to deploy to Railway (all three files in `railway-worker/`)
- Checkpoint task 4 requires Railway deployment + sync verification
- Dashboard's `watchSyncStatus()` already wired (Phase 6) — will show live status once worker writes to `teachers/{uid}/sync/status`

---
*Phase: 07-railway-cloud-sync*
*Completed: 2026-03-24*
