---
phase: 01-core-reliability
plan: 02
subsystem: sync-reliability
tags: [playwright, selenium, ui-automation, error-recovery, retry-logic]

# Dependency graph
requires:
  - phase: 01-01
    provides: Retry logic with exponential backoff and failure logging
provides:
  - Selector fallback strategies for Aeries UI resilience
  - Failed student persistence across sync cycles
  - Partial failure handling preserving successful syncs
affects: [01-03, audit-verification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Selector fallback pattern with primary/fallback strategies"
    - "Cross-cycle retry queue for failed students"
    - "Alert logging for UI change detection"

key-files:
  created:
    - attendance-sync/failed_students.json (runtime)
    - selector_alerts_{YYYY-MM}.log (runtime)
  modified:
    - attendance-sync/sync_utils.py
    - attendance-sync/upload_to_aeries.py

key-decisions:
  - "Use fallback selector strategies (data-attr → text-content → xpath) for UI resilience"
  - "Persist failed students to JSON for cross-cycle retry (15-20 min later)"
  - "Alert logging when fallback selectors are used to detect UI changes"
  - "Preserve successful syncs even when some students fail"

patterns-established:
  - "SELECTOR_STRATEGIES dict with ordered fallback selectors"
  - "find_element_with_fallback tries each strategy until success"
  - "Failed student queue structure: {date, students: [{student_id, period, error, timestamp}]}"

# Metrics
duration: 3min
completed: 2026-02-05
---

# Phase 01 Plan 02: Selector Fallbacks & Partial Failure Handling Summary

**Selector fallback strategies with cross-cycle failed student retry queue for Aeries UI resilience**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-05T08:06:28Z
- **Completed:** 2026-02-05T08:09:20Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- Selector fallback strategies enable graceful degradation when Aeries UI changes
- Failed students persist to JSON and retry in next sync cycle (15-20 min later)
- Successful syncs preserved even when some students fail
- Alert logging when fallback selectors used to detect UI changes early

## Task Commits

Each task was committed atomically:

1. **Task 1: Add selector fallback utilities to sync_utils** - `18f889f` (feat)
2. **Task 2: Add failed student persistence to sync_utils** - `fe79bf4` (feat)
3. **Task 3: Integrate fallback selectors and partial failure handling into upload_to_aeries** - `668164b` (feat)

## Files Created/Modified
- `attendance-sync/sync_utils.py` - Added SELECTOR_STRATEGIES dict, find_element_with_fallback, load_failed_students, save_failed_students, clear_failed_students
- `attendance-sync/upload_to_aeries.py` - Replaced hardcoded selectors with find_element_with_fallback, integrated failed student tracking and retry logic
- `attendance-sync/failed_students.json` (runtime) - Persists failed students for cross-cycle retry
- `selector_alerts_{YYYY-MM}.log` (runtime) - Logs when fallback selectors are used

## Decisions Made

1. **Selector fallback order: data-attr → text-content → xpath** - Prioritizes most stable selector (data attributes) first, falls back to less stable options
2. **Cross-cycle retry (no immediate retry)** - Per-student failures are systematic (DOM/selector issues), not transient. Retry in next cycle (15-20 min) gives time for transient issues to resolve
3. **Alert file for fallback usage** - Separate `selector_alerts_{YYYY-MM}.log` makes it easy for admin to monitor UI changes without parsing main error logs
4. **Preserve successful syncs** - Track failures but don't rollback successful students. Critical for "every student's attendance must be correct" requirement

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tasks completed without issues.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Phase 01-03 (End-of-day sync and recovery testing).

**Capabilities delivered:**
- Selector resilience handles Aeries UI changes gracefully
- Failed student queue enables automatic retry without manual intervention
- Alert logging provides early warning of UI changes

**Potential concerns:**
- Fallback selectors are educated guesses - may need tuning after real UI changes
- Failed student retry assumes 15-20 min cycle - needs verification with actual schedule
- No limit on retry attempts - failed students persist all day until successful or end-of-day

---
*Phase: 01-core-reliability*
*Completed: 2026-02-05*
