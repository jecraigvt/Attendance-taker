---
phase: 05-auth-foundation-and-data-migration
plan: 03
subsystem: ui, auth
tags: [firebase, kiosk, login, firestore-paths, multi-tenant, python-sync]

requires:
  - phase: 05-02
    provides: "Cloud Function authenticateTeacher, Firestore security rules"
  - phase: 05-01
    provides: "Migrated data at per-teacher Firestore paths"
provides:
  - "Login screen with Aeries credential authentication"
  - "PIN-based kiosk exit to admin panel"
  - "All Firestore paths rewritten to per-teacher structure"
  - "Python sync script reads per-teacher paths with legacy fallback"
  - "public/index.html deployed to Firebase Hosting"
affects: [06-teacher-dashboard, 07-cloud-sync]

tech-stack:
  added: [firebase-functions-client-sdk]
  patterns:
    - "teacherPath() helper for all per-teacher Firestore path construction"
    - "Kiosk binding stored in sessionStorage (always) and localStorage (if remember-me)"
    - "PIN stored in Firestore at teachers/{uid}/config/main"

key-files:
  created: []
  modified:
    - "attendance v 2.5.html"
    - public/index.html
    - attendance-sync/attendance_to_aeries.py

key-decisions:
  - "Firestore even-segment paths: config/main, rosters/{id}, profile/main (propagated from 05-01 fix)"
  - "PIN stored in Firestore config doc, not just localStorage, so it persists across devices"
  - "Teacher name removed from kiosk screen per user request"
  - "Legacy fallback in Python sync for backward compatibility during transition"

patterns-established:
  - "teacherPath(subpath) helper constructs all per-teacher Firestore paths"
  - "Screen navigation: showLoginScreen / showPinSetup / showKioskMode / showPinEntry"
  - "Kiosk binding persistence: sessionStorage + optional localStorage"

duration: ~12min
completed: 2026-03-23
---

# Plan 05-03: Kiosk Integration Summary

**Login screen with Aeries auth, PIN-based kiosk exit, all Firestore paths rewritten to per-teacher structure, Python sync updated for multi-teacher reads**

## Performance

- **Duration:** ~12 min
- **Tasks:** 4 (3 auto + 1 human-verify checkpoint)
- **Files modified:** 3

## Accomplishments
- Login screen calls Cloud Function authenticateTeacher, signs in with custom token
- PIN setup after first login, stored in Firestore config doc
- Kiosk mode as default screen with PIN exit to admin panel
- All Firestore paths migrated from artifacts/{APP_ID}/public/... to teachers/{uid}/...
- Python sync script reads per-teacher paths with legacy fallback
- Deployed to Firebase Hosting and verified end-to-end in Playwright

## Task Commits

1. **Task 1: Add login screen and rewrite Firestore paths** - `b84d566` (feat)
2. **Task 2: Update Python sync script** - `e107480` (feat)
3. **Task 3: Copy HTML to public/index.html** - `acfb42f` (feat)
4. **Task 4: End-to-end verification** - Verified via Playwright
5. **Post-checkpoint: Remove teacher name from kiosk** - `7e81ade` (feat)

## Files Created/Modified
- `attendance v 2.5.html` - Login screen, PIN setup/entry, per-teacher Firestore paths, kiosk mode
- `public/index.html` - Deployed copy matching source HTML
- `attendance-sync/attendance_to_aeries.py` - Multi-teacher sync with legacy fallback

## Decisions Made
- Teacher name removed from kiosk screen per user request
- Used corrected even-segment Firestore paths from 05-01 fix
- PIN stored in Firestore (not just localStorage) for cross-device persistence

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Cloud Function deployment issues**
- **Found during:** Task 4 (E2E verification)
- **Issue:** Multiple deployment blockers: Node.js 18 decommissioned, CORS/auth on v2 functions, email format handling, FERNET_KEY secret declaration, signBlob IAM permission
- **Fix:** Updated to Node.js 20, granted allUsers invoker, fixed email detection, added secrets option, granted serviceAccountTokenCreator role
- **Files modified:** functions/index.js, functions/package.json
- **Verification:** Full auth flow verified in Playwright
- **Committed in:** 38d4a0c, f3bf461

---

**Total deviations:** 1 (deployment infrastructure — 5 sub-fixes)
**Impact on plan:** No scope creep. All fixes were necessary for the function to operate in production.

## Issues Encountered
- Firebase Hosting appeared to serve cached old HTML initially; resolved after fresh deploy
- School network blocks rollcall.it.com with SSL error; attendance-taker-56916.web.app works

## Next Phase Readiness
- Auth foundation complete: login, PIN, kiosk mode, per-teacher data isolation
- Ready for Phase 6: Teacher Dashboard and Roster Management
- Cloud Function deployed and operational
- Firestore security rules enforcing per-teacher isolation

---
*Phase: 05-auth-foundation-and-data-migration*
*Completed: 2026-03-23*
