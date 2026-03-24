---
phase: 06-teacher-dashboard-and-roster-management
plan: 03
subsystem: ui
tags: [roster, preferred-names, cloud-functions, aeries, firestore, csv, dashboard]

# Dependency graph
requires:
  - phase: 06-teacher-dashboard-and-roster-management/06-01
    provides: dashboard shell with dashboard-roster section placeholder ready to populate
  - phase: 05-auth-foundation-and-data-migration
    provides: Firebase Auth session, Fernet encryption, teachers/{uid}/credentials/aeries path

provides:
  - fetchRoster Cloud Function (us-central1) that scrapes Aeries via HTTP session cookies
  - fernetDecrypt() helper for decrypting stored Aeries passwords
  - Roster management UI in dashboard-roster section (accordion per period)
  - Preferred name editing per student (inline, saves to Firestore)
  - Manual student add/remove per period with source badges (Aeries/CSV/Manual)
  - CSV upload in Roster tab (replaces Attendance tab roster upload, backwards-compat stubs kept)
  - preferredName field on all student records (defaults to FirstName)
  - getDisplayName() helper used in kiosk sign-in, absent list, group display

affects:
  - 06-04-PLAN (settings/onboarding — fetchRoster usable in onboarding wizard)
  - 07-PLAN (cloud sync — uses preferredName-aware roster data from Firestore)
  - kiosk sign-in display (now shows preferredName instead of FirstName)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "fetchRoster returns { success: false, error: 'roster_requires_browser', fallback: 'csv_upload' } when HTTP scraping is insufficient"
    - "preferredName field on every roster student record; getDisplayName() helper for display"
    - "Roster management UI: accordion sections per period, inline editable preferred name cells"
    - "Roster mutation functions exposed as window.* for inline HTML onclick handlers"

key-files:
  created: []
  modified:
    - functions/index.js
    - public/index.html
    - attendance v 2.5.html

key-decisions:
  - "fetchRoster returns roster_requires_browser fallback rather than hard-failing — maintains CSV upload path for schools where HTTP scraping won't work"
  - "Preferred name editing uses onblur save (no Save button) — lower friction, saves immediately"
  - "Roster upload moved from Attendance tab to Roster tab; hidden stubs kept in Attendance tab so existing JS (rosterUpload, rosterStatus, etc.) continues to work without changes"
  - "parseRoster() adds preferredName and source:'csv' to newly parsed students"
  - "Manual roster additions flagged with source:'manual'; preserved across Aeries re-fetches if StudentID not in Aeries"

patterns-established:
  - "showRosterTabStatus(message, type): in-tab status display for async operations (info/success/error/warning)"
  - "renderRosterManagementUI(): called on loadRostersLocal, watchRostersFromCloud snapshot, and after CSV upload"
  - "window.savePreferredName / removeStudentFromRoster / addManualStudent: window-exposed for inline onclick"

# Metrics
duration: 14min
completed: 2026-03-24
---

# Phase 6 Plan 03: Roster Management and Preferred Names Summary

**fetchRoster Cloud Function with HTTP Aeries scraping + accordion roster editor with inline preferred-name editing, manual add/remove, and CSV fallback; preferred names now used throughout kiosk and dashboard displays**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-03-24T06:03:41Z
- **Completed:** 2026-03-24T06:18:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `fetchRoster` Cloud Function that logs into Aeries via HTTP, navigates to class list pages, parses student data, and writes to `teachers/{uid}/rosters/{period}` — with full fallback to CSV upload when HTTP scraping returns unusable content
- Added `fernetDecrypt()` to reverse Fernet encryption for stored Aeries credentials
- Replaced `#dashboard-roster` placeholder with full roster management UI: Fetch from Aeries button with spinner, CSV upload, CSV fallback notice, and period accordion
- Built period accordion with student table showing StudentID, official name, inline preferred name editor (onblur saves to Firestore), source badge (Aeries/CSV/Manual), and remove button
- Added "Add Student" row at bottom of each period for manual additions
- Updated `buildLogEntry()`, `showGroup()` (3 call sites), and absent list to use `getDisplayName(student)` which returns `preferredName` when set
- `parseRoster()` now adds `preferredName` and `source:'csv'` fields to parsed students
- Roster upload moved to Roster tab; Attendance tab shows redirect notice with hidden stub elements for JS compatibility

## Task Commits

1. **Task 1: Build fetchRoster Cloud Function** - `ad10145` (feat)
2. **Task 2: Build roster management UI with preferred names** - `b68248f` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `functions/index.js` - Added fernetDecrypt(), loginToAeries(), aeriesGet(), parseAeriesClassList(), parseAeriesRosterPage(), fetchRoster Cloud Function; updated AERIES_BASE_URL constant
- `public/index.html` - Roster section HTML, roster management JS functions, preferred name integration throughout
- `attendance v 2.5.html` - Synced to match public/index.html

## Decisions Made

- `fetchRoster` returns `{ error: "roster_requires_browser" }` when HTTP scraping fails rather than throwing — keeps the CSV upload path functional for Aeries setups that require a real browser session
- Preferred name editing uses onblur (no explicit Save button) — reduces friction; the cursor leaving the input triggers an immediate Firestore write
- Existing `#roster-upload` input and JS variable references in the Attendance tab are preserved as hidden stubs — this avoids any risk of breaking the existing CSV upload code path
- `parseRoster()` now stamps every incoming CSV student with `source:'csv'` and `preferredName: first` — gives teachers a clean starting point to customize

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Preserved preferred names across Aeries re-fetches**
- **Found during:** Task 1 (fetchRoster implementation)
- **Issue:** Plan said to write roster data to Firestore but didn't specify behavior on re-fetch when teacher has customized preferred names
- **Fix:** fetchRoster loads existing roster docs before writing, merges incoming Aeries data while preserving teacher-customized preferredName values; manual students not in Aeries are appended rather than deleted
- **Files modified:** functions/index.js
- **Committed in:** ad10145 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical — merge behavior)
**Impact on plan:** Necessary to meet "Refresh roster: preserve preferred names" from CONTEXT.md. No scope creep.

## Issues Encountered

- File edit tool reported "modified since read" on several attempts due to concurrent disk normalization (git line endings). Resolved by reading fresh state before each edit attempt.

## User Setup Required

None — fetchRoster is deployed and callable. No additional secrets or dashboard configuration required.

## Next Phase Readiness

- `fetchRoster` is deployed and callable by any authenticated teacher
- Roster management UI is functional in the Roster tab
- `preferredName` field is now on all student records and used in kiosk/dashboard displays
- Plan 06-04 (Settings/Onboarding) can use `fetchRoster` as part of the onboarding wizard
- No blockers for remaining 06-02, 06-04 plans

---
*Phase: 06-teacher-dashboard-and-roster-management*
*Completed: 2026-03-24*
