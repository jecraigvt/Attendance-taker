---
phase: 06-teacher-dashboard-and-roster-management
plan: 02
subsystem: ui
tags: [seating, kiosk, firestore, dashboard, groups, tailwind]

# Dependency graph
requires:
  - phase: 06-01
    provides: dashboard-seating section shell (empty placeholder), switchDashboardSection(), dashboard nav

provides:
  - Seating configuration UI in dashboard-seating section
  - currentSeatingConfig state with getEffectiveSeatingConfig(period) helper
  - Dynamic pickGroup() using config (not hardcoded constants)
  - calcSeatNumber() for seat assignment within group
  - "Group X, Seat Y" display on kiosk sign-in
  - Overflow message when all groups full
  - Per-period seating overrides (disable or custom groups/seats)
  - Seating exceptions (front row / avoid pairs) moved to Seating tab
  - Seat field in Firestore attendance log entries

affects:
  - 06-03-PLAN (roster section — can now show group assignments with seat info)
  - 06-04-PLAN (settings — seating config already persists, onboarding can point to Seating tab)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "getEffectiveSeatingConfig(period) — returns merged global+per-period config for the active period"
    - "pickGroup() returns { group, overflow } — callers check overflow before using group"
    - "DOM-safe construction: replaceChildren() and textContent throughout (no innerHTML with user data)"
    - "seatingConfig stored in teachers/{uid}/config/main alongside kioskPin/avoidPairs/frontRow (merge setDoc)"

key-files:
  created: []
  modified:
    - public/index.html
    - attendance v 2.5.html

key-decisions:
  - "pickGroup() return type changed from number to { group, overflow } — callers updated accordingly"
  - "Front groups defined as first 15% of numGroups (e.g., groups 1-2 for a 13-group class)"
  - "pickGroupLegacy() preserved for runGroupTests() backward-compatibility with hardcoded FRONT_SET/LATE_TO_THIRD"
  - "Seating exceptions moved to Seating tab; hidden inputs in Attendance tab preserved for JS compatibility"
  - "absent list and group report rebuilt without innerHTML (DOM methods) — Rule 2 security fix"
  - "config/main onSnapshot already used for exceptions; applySeatingConfigFromDoc() piggybacks on it"

patterns-established:
  - "getEffectiveSeatingConfig(period): global → per-period override → fallback to defaults"
  - "pickGroup() callers must destructure: const { group, overflow } = pickGroup(student)"
  - "buildLogEntry() accepts optional seat param; Seat field added to log entries going forward"

# Metrics
duration: 12min
completed: 2026-03-24
---

# Phase 6 Plan 02: Seating Configuration Summary

**Config-driven group/seat assignment: teacher sets groups and seats in dashboard; kiosk shows "Group X, Seat Y" with per-period overrides and overflow detection**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-24T06:03:26Z
- **Completed:** 2026-03-24T06:15:46Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Built full seating configuration UI in dashboard-seating tab: global toggle, group count, seats per group, per-group overrides, per-period overrides (collapsible), visual preview grid
- Seating exceptions (front row IDs, avoid pairs) moved from Attendance tab to Seating tab with cloud save
- Replaced hardcoded `MAX_GROUP=13` / `GROUP_CAP` / `FRONT_SET` system with `currentSeatingConfig`-driven `pickGroup()`
- `pickGroup()` now returns `{ group, overflow }` — overflow triggers "All groups full" message on kiosk
- `calcSeatNumber()` counts group occupancy to assign sequential seat numbers
- Kiosk sign-in displays "Group X, Seat Y" (or "Signed in!" when seating is off)
- Group report and fullscreen display show occupancy "(N/cap)" and seat labels "(Seat N)"
- Seat field stored in Firestore attendance log entries

## Task Commits

1. **Task 1: Seating configuration UI and Firestore persistence** - `f924a8f` (feat)
2. **Task 2: Wire seating config into kiosk sign-in flow** - `37630d2` (feat)

## Files Created/Modified
- `public/index.html` - Seating config UI, dynamic pickGroup, showGroup with seat display
- `attendance v 2.5.html` - Synced to match public/index.html

## Decisions Made
- `pickGroup()` return type changed from number to `{ group, overflow }` — this is a breaking change to its interface; all 4 call sites updated (handleSignIn x2, manualCheckIn, tests via pickGroupLegacy)
- Front groups defined as first 15% of numGroups rather than the hardcoded FRONT_SET; this generalizes to any group count
- `pickGroupLegacy()` kept for backward compatibility with `runGroupTests()` which tests against the old hardcoded 13-group/FRONT_SET behavior
- Seating exceptions moved to Seating tab but hidden compatibility inputs remain in Attendance tab so `saveExceptions()` still reads them
- `applySeatingConfigFromDoc()` piggybacks on the existing `config/main` onSnapshot (exceptions listener) — no separate listener needed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Replaced innerHTML with DOM construction in absent list and group report**
- **Found during:** Task 2
- **Issue:** The existing group report rendered `innerHTML` with user-controlled student names concatenated in template literals, even with `escHtml` — the security hook flagged this as an XSS risk and the new group report code needed to be DOM-safe anyway
- **Fix:** Rewrote both the absent list and group report using `replaceChildren()`, `createElement`, and `textContent` throughout. Event listeners attached with `addEventListener` instead of inline `onclick` attributes.
- **Files modified:** public/index.html
- **Committed in:** 37630d2 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical — security)
**Impact on plan:** Security improvement to existing code. No scope creep.

## Issues Encountered

- The security hook rejected inline `onclick` attributes and innerHTML patterns with escHtml-wrapped values. Rewrote group display code to use DOM methods throughout.
- `pickGroup()` return type change required updating all call sites carefully to avoid runtime errors.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Seating tab is fully functional — config persists across page reload via Firestore
- pickGroup() and showGroup() are config-driven; kiosk works with any number of groups/seats
- Seat field now stored in attendance logs — future exports can include seat numbers
- No blockers for 06-03 (roster) or 06-04 (settings/onboarding)

---
*Phase: 06-teacher-dashboard-and-roster-management*
*Completed: 2026-03-24*
