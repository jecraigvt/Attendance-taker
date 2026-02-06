---
phase: 04-tardy-logic-review
plan: 02
subsystem: attendance
tags: [tardy-logic, bell-schedule, status-calculation, javascript]

# Dependency graph
requires:
  - phase: 04-01
    provides: Analysis showing 5th-student logic causes 52% of tardy disputes
provides:
  - Bell-schedule-based tardy determination
  - Configurable grace period constant
  - getPeriodStartTime() helper function
affects: [attendance-status, student-signin, future-tardy-adjustments]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tardy threshold calculated from bell schedule + grace period"
    - "Period start time lookup via getPeriodStartTime(period, schedule)"

key-files:
  created: []
  modified:
    - "attendance v 2.2.html"

key-decisions:
  - "5-minute default grace period (TARDY_GRACE_MINUTES constant)"
  - "Tardy determined by comparing sign-in time to (period start + grace period)"
  - "Fall back to Default schedule if specified schedule not found"
  - "Keep pendingEntry parameter in statusForNow() for API compatibility"

patterns-established:
  - "Bell schedule lookup pattern: bellSchedules[schedule] || bellSchedules.Default"
  - "Time-based status: periodStart + grace period threshold"

# Metrics
duration: 2min
completed: 2026-02-06
---

# Phase 4 Plan 02: Implement Bell-Schedule-Based Tardy Logic Summary

**Replaced 5th-student-relative tardy logic with deterministic bell-schedule-based threshold using configurable 5-minute grace period**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-06T05:00:35Z
- **Completed:** 2026-02-06T05:02:30Z
- **Tasks:** 3
- **Files modified:** 1

## Accomplishments
- Added TARDY_GRACE_MINUTES constant (5 minutes) for configurable grace period
- Added getPeriodStartTime() helper to look up period start times from bellSchedules
- Replaced statusForNow() to use bell-schedule-based logic instead of 5th student counting
- Removed unused getTimestampMs() helper function

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Configuration Constant and Helper Function** - `fed4974` (feat)
2. **Task 2: Replace statusForNow() Logic** - `e57166a` (feat)
3. **Task 3: Remove Unused Helper Function** - `164a6d1` (refactor)

## Files Created/Modified
- `attendance v 2.2.html` - Updated with new tardy logic:
  - Line 565: TARDY_GRACE_MINUTES constant
  - Lines 628-637: getPeriodStartTime() helper function
  - Lines 1254-1276: New statusForNow() implementation
  - Line 1251: Comment documenting removal of getTimestampMs()

## Decisions Made
- **5-minute grace period**: Default TARDY_GRACE_MINUTES = 5, easily configurable
- **Fallback schedule handling**: If period not found in schedule, log warning and default to "On Time" (safe default)
- **API compatibility preserved**: pendingEntry parameter kept in statusForNow() signature but no longer used

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Bell-schedule-based tardy logic is now active
- Grace period can be adjusted by changing TARDY_GRACE_MINUTES constant
- Future enhancements could include:
  - Per-period grace periods
  - Admin UI to adjust grace period
  - Different grace periods for different schedules (Late Start, Assembly, etc.)

---
*Phase: 04-tardy-logic-review*
*Completed: 2026-02-06*
