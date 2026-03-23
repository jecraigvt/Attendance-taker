---
phase: 05-auth-foundation-and-data-migration
plan: 01
subsystem: database
tags: [firestore, migration, firebase-admin, multi-tenant]

requires:
  - phase: 04-tardy-logic-review
    provides: stable single-tenant attendance system
provides:
  - Idempotent data migration script (migrate-to-tenants.js)
  - Jeremy's data at per-teacher Firestore paths (teachers/{uid}/...)
  - Firebase Auth user for Jeremy (IUaKeeP9YnY5qd4OLTWyACbtOrT2)
  - Teacher profile with tardy config at teachers/{uid}/profile/main
affects: [05-auth-foundation-and-data-migration, 06-teacher-dashboard]

tech-stack:
  added: [firebase-admin]
  patterns: [per-teacher Firestore paths]

key-files:
  created: [migrate-to-tenants.js, package.json]
  modified: []

key-decisions:
  - "Firestore even-segment fix: config stored at teachers/{uid}/config/main, rosters at teachers/{uid}/rosters/{id} (dropped intermediate 'periods' level)"
  - "Teacher profile stored at teachers/{uid}/profile/main"
  - "Jeremy's UID: IUaKeeP9YnY5qd4OLTWyACbtOrT2 (Firebase Auth user with email jeremy@rollcall.local)"
  - "Service account needed roles/serviceusage.serviceUsageConsumer for Identity Toolkit API access"

patterns-established:
  - "Per-teacher Firestore path pattern: teachers/{uid}/config/main, teachers/{uid}/rosters/{id}, teachers/{uid}/attendance/{date}/..."

duration: ~8min
completed: 2026-03-23
---

# Plan 05-01: Data Migration Summary

**Idempotent migration script copies Jeremy's attendance data to per-teacher Firestore paths with verified count parity**

## Performance

- **Duration:** ~8 min
- **Tasks:** 2 (1 auto + 1 human-verify checkpoint)
- **Files created:** 2

## Accomplishments
- Created migrate-to-tenants.js (391 lines) — copies all data from flat paths to per-teacher structure
- Migrated 5 roster docs, 1 config doc, teacher profile with tardy config
- Verified idempotency — re-run skips all docs, counts still match
- Old paths remain untouched as safety net

## Task Commits

1. **Task 1: Create migration script and dependencies** - `560dd86` (feat)
2. **Fix: Firestore path corrections** - `180cf82` (fix — even-segment requirement)
3. **Task 2: Verify migration against live Firestore** - Human verified via Firebase Console

**Plan metadata:** this commit (docs)

## Files Created/Modified
- `migrate-to-tenants.js` - Idempotent data migration script
- `package.json` - firebase-admin dependency

## Decisions Made
- Firestore requires even-numbered path segments for db.doc(). Original plan paths had odd segments. Fixed: config → config/main, rosters/periods/{id} → rosters/{id}, profile → profile/main
- Service account needed `roles/serviceusage.serviceUsageConsumer` IAM role for Firebase Auth API access

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Firestore path segment parity**
- **Found during:** Task 1 execution (runtime error)
- **Issue:** `teachers/{uid}/config` (3 segments) invalid for `db.doc()` — Firestore requires even segments
- **Fix:** Added intermediate doc IDs: config/main, profile/main; flattened rosters/periods/{id} → rosters/{id}
- **Files modified:** migrate-to-tenants.js
- **Verification:** Migration ran successfully after fix
- **Committed in:** 180cf82

**2. [Rule 3 - Blocking] Service account IAM permissions**
- **Found during:** Task 2 execution (runtime error)
- **Issue:** Service account lacked `serviceusage.serviceUsageConsumer` role for Identity Toolkit API
- **Fix:** User granted role in Google Cloud Console IAM
- **Verification:** Migration succeeded on retry

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Path structure change propagates to plans 05-02 and 05-03 — they must use the corrected paths.

## Issues Encountered
- 0 attendance records existed at old path (no student sign-in data to migrate yet) — this is expected and not an error

## Next Phase Readiness
- Data migration complete, auth infrastructure ready (05-02 done)
- Path corrections must be reflected in 05-03 (HTML Firestore path rewrites)
- Jeremy's UID (IUaKeeP9YnY5qd4OLTWyACbtOrT2) available for kiosk binding

---
*Phase: 05-auth-foundation-and-data-migration*
*Completed: 2026-03-23*
