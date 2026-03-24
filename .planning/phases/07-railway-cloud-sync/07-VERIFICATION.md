---
phase: 07-railway-cloud-sync
verified: 2026-03-24T18:31:41Z
status: gaps_found
score: 2.5/3 must-haves verified
gaps:
  - truth: When sync fails for any teacher, dashboard shows error; one teacher failure does not block others
    status: partial
    reason: Per-teacher isolation is implemented. Dashboard error display is wired. But credentials_invalid does not stop future syncs -- the worker retries indefinitely.
    artifacts:
      - path: railway-worker/sync_engine.py
        issue: No persistent flag prevents the next cycle from retrying a credentials_invalid teacher.
      - path: railway-worker/worker.py
        issue: run_all_teachers() calls sync_teacher(uid) unconditionally for every UID.
      - path: railway-worker/firestore_client.py
        issue: write_sync_status() does not persist an errorCategory field.
    missing:
      - write_sync_status() should persist errorCategory on credentials_invalid failures
      - run_all_teachers() should skip teachers with errorCategory == credentials_invalid
      - sync_teacher() could read last errorCategory at start and return skipped if credentials_invalid
human_verification:
  - test: Deploy to Railway and watch logs for one school-hours period
    expected: Logs show Sync cycle fired every 30 min; outside hours shows Skipping sync
    why_human: Cannot verify APScheduler timing from static analysis
  - test: End-to-end sync for a real teacher on a school day
    expected: Firestore shows status success, lastSyncTime set; dashboard shows green indicator
    why_human: Requires live Railway deployment with real data
  - test: Failure isolation between two teachers
    expected: Misconfigured teacher shows red error; other teachers sync successfully
    why_human: Requires two configured teachers and live deployment
---

# Phase 7: Railway Cloud Sync Verification Report

**Phase Goal:** Attendance sync runs automatically in the cloud on Railway every 30 minutes during school hours for every teacher with no dependency on the developer local machine
**Verified:** 2026-03-24T18:31:41Z
**Status:** gaps_found (1 partial gap)
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Aeries sync runs every 30 minutes during school hours without action from developer or teacher | VERIFIED | worker.py line 167: minutes=30; time guard lines 51-60 checks weekday and 08:00-16:00 PT; SIGTERM handler; immediate startup sync at line 156 |
| 2 | Each teacher attendance is processed in the cloud with no involvement of developer local machine | VERIFIED | Firebase Admin initialized from FIREBASE_SERVICE_ACCOUNT env var (JSON blob, no disk file); Playwright runs inside Docker; Fernet decrypt uses FERNET_KEY env var |
| 3 | When sync fails for any teacher, dashboard shows error; one teacher failure does not block others | PARTIAL | Per-teacher try/except isolation in worker.py lines 76-99 is complete. Dashboard onSnapshot reads data.error (index.html lines 3730-3731). Gap: credentials_invalid failures do not stop future sync attempts. |

**Score:** 2.5/3 truths verified (Truth 3 is partial)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| railway-worker/Dockerfile | Playwright base image, pip install, CMD worker.py | VERIFIED | Uses mcr.microsoft.com/playwright/python:v1.49.1-noble; runs playwright install chromium; CMD is python worker.py |
| railway-worker/requirements.txt | Pinned deps: playwright, firebase-admin, cryptography, apscheduler, pytz | VERIFIED | All 5 deps with correct version pins; uses cryptography not python-fernet |
| railway-worker/smoke_test.py | Three independent tests for Playwright, Firebase, Fernet | VERIFIED | All three test functions present; graceful SKIP on missing env vars; exits 1 on failures |
| railway.toml | Railway Dockerfile deployment config | VERIFIED | builder=DOCKERFILE, dockerfilePath=railway-worker/Dockerfile, numReplicas=1, restartPolicyType=ON_FAILURE |
| railway-worker/worker.py | APScheduler loop, teacher iteration, graceful shutdown | VERIFIED | BlockingScheduler 30-min interval; run_all_teachers() with per-teacher try/except; SIGTERM/SIGINT handlers; env-var fail-fast |
| railway-worker/sync_engine.py | Per-teacher sync with Playwright and status writes | VERIFIED | sync_teacher() 5-step flow; SELECTOR_STRATEGIES with fallbacks; retry_login 3 attempts; 4 error categories; writes sync/status on all exit paths |
| railway-worker/firestore_client.py | Firebase Admin init from env var, 7 Firestore helpers | VERIFIED | get_db() from env var JSON; all 7 functions with correct Firestore paths |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| worker.py | sync_engine.py | sync_teacher(uid) per teacher | WIRED | Line 77 calls sync_teacher(uid) in for loop with try/except |
| worker.py | firestore_client.py | get_all_teacher_uids(), get_db() | WIRED | Line 24 import; line 148 get_db() fail-fast; line 63 get_all_teacher_uids() |
| sync_engine.py | firestore_client.py | get_teacher_credentials(), write_sync_status() | WIRED | Lines 19-25 imports; called in all steps of sync_teacher() |
| sync_engine.py | teachers/{uid}/sync/status | write_sync_status() on all exit paths | WIRED | Lines 263, 282, 330, 553, 558, 570-574 -- every failure and success path writes status |
| sync_engine.py | Playwright headless Chromium | sync_playwright() context manager | WIRED | Line 312 with sync_playwright() as p launches headless Chromium |
| Dockerfile | requirements.txt | pip install -r requirements.txt | WIRED | Dockerfile line 9 |
| public/index.html watchSyncStatus() | teachers/{uid}/sync/status | onSnapshot(syncRef) | WIRED | index.html line 3682 reads correct path; lines 3714-3738 render all states |

### Requirements Coverage

| Requirement | Status | Notes |
|-------------|--------|-------|
| SYNC-01: Aeries sync runs on Railway not local PC | SATISFIED | Dockerfile, railway.toml, and env-var-only Firebase init confirm cloud-only operation |
| SYNC-02: Each teacher syncs every 20 minutes during school hours | PARTIALLY SATISFIED | Interval is 30 minutes per deliberate decision in 07-CONTEXT.md. REQUIREMENTS.md text is stale at 20 minutes. One comment in requirements.txt also says 20-minute -- cosmetic only. |
| SYNC-03: Teacher notified on dashboard when sync fails | SATISFIED | write_sync_status() writes error field; watchSyncStatus() reads it via onSnapshot; red indicator and Details button show error text |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| railway-worker/requirements.txt | 11 | Comment says 20-minute sync intervals but scheduler uses 30 minutes | Info | Misleading comment only; actual behavior is 30 minutes as intended per 07-CONTEXT.md |

### Human Verification Required

#### 1. Scheduled sync running on Railway

**Test:** After deployment, watch Railway log viewer for one full school-hours period
**Expected:** Logs show Sync cycle fired at... entries every 30 minutes; entries outside 08:00-16:00 PT show Skipping sync -- outside school hours
**Why human:** Cannot verify APScheduler timer behavior or Railway container state from static code analysis

#### 2. End-to-end sync for a real teacher

**Test:** On a school day, let the worker run. Check Firebase console at teachers/{uid}/sync/status and open the teacher dashboard
**Expected:** status success, lastSyncTime populated, periodsProcessed set; dashboard shows green Last sync indicator
**Why human:** Requires live Railway deployment, real Firestore data, and real Aeries credentials

#### 3. Failure isolation between teachers

**Test:** Temporarily misconfigure one teacher credentials in Firestore, let a sync cycle run
**Expected:** That teacher dashboard shows red error with friendly message. Other teachers sync successfully.
**Why human:** Requires two configured teachers and a live deployment

### Gaps Summary

One partial gap affects Truth 3. Per-teacher isolation at the run_all_teachers() loop level is correctly implemented -- exceptions from one teacher do not propagate to others. Dashboard error display is fully wired via onSnapshot.

The gap: the 07-CONTEXT.md decision that credentials_invalid immediately stops future syncs for that teacher is not implemented. When a teacher login returns credentials_invalid, sync_engine.py correctly writes status failed with the friendly error, but no persistent flag prevents the next 30-minute cycle from attempting that teacher again.

The fix is small: write an errorCategory field to teachers/{uid}/sync/status on credentials_invalid failures, and add a guard in run_all_teachers() or sync_teacher() that skips teachers in that state until a new credential is saved.

---

*Verified: 2026-03-24T18:31:41Z*
*Verifier: Claude (gsd-verifier)*
