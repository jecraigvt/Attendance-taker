---
phase: 04-tardy-logic-review
plan: 01
subsystem: attendance-logic
tags: [tardy, statusForNow, bell-schedule, edge-cases, analysis]

dependency-graph:
  requires: []
  provides: [tardy-logic-analysis, edge-case-documentation, bell-schedule-reference]
  affects: [04-02 (if implementation plan created)]

tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - .planning/phases/04-tardy-logic-review/TARDY-LOGIC-ANALYSIS.md
  modified: []

decisions:
  - id: bell-schedule-based-logic
    description: Recommend replacing 5th-student-relative logic with absolute bell-schedule-based tardy logic
    rationale: Current logic causes 52% of disputes; new logic is deterministic and transparent

metrics:
  duration: 2 minutes
  completed: 2026-02-06
---

# Phase 4 Plan 1: Tardy Logic Review Summary

**One-liner:** Complete analysis of statusForNow() revealing 7 edge cases causing 52% of disputes, with bell-schedule-based fix recommended.

## What Was Done

### Task 1: Document Current Tardy Logic

Created TARDY-LOGIC-ANALYSIS.md with comprehensive documentation:

1. **Current Logic** - Documented the `statusForNow()` function (lines 1252-1283):
   - Gets all sign-in logs sorted by timestamp
   - If < 5 students: everyone is "On Time"
   - 5th student's timestamp + 8 minutes = tardy threshold
   - Current time > threshold = "Late"

2. **Edge Cases** - Identified 7 edge cases:
   | # | Case | Issue |
   |---|------|-------|
   | 1 | < 5 students | No tardies possible |
   | 2 | First 5 arrive late | All marked "On Time" |
   | 3 | 5th student very early | On-time students marked late |
   | 4 | Passing period sign-in | Wrong period context |
   | 5 | No bell schedule reference | Relative-only threshold |
   | 6 | 5th arrives end of class | Wrong threshold |
   | 7 | High absenteeism | No tardies if < 5 show |

3. **Bell Schedule Configuration** - Documented `bellSchedules` object (lines 616-624):
   - 7 schedule types (Regular, Late Start, Assembly, etc.)
   - All periods have defined start times
   - **Not currently used for tardy logic** (key insight)

4. **Dispute Analysis** - Connected PROJECT.md data:
   - 15 of 29 corrections (52%) are tardy disputes
   - Students signing in 8:27-8:34 for 8:30 class get random results
   - Unpredictability is root cause

5. **Root Cause** - Five fundamental problems:
   - Relative to peers, not absolute to bell
   - Slow 5th student skews everyone late
   - Fast 5th student hides actual tardies
   - 8-minute buffer is arbitrary
   - Small classes are exempt

6. **Recommendation** - Proposed new bell-schedule-based logic:
   ```javascript
   const TARDY_GRACE_MINUTES = 5;
   function statusForNow() {
     const periodStart = getPeriodStartTime();
     const tardyThreshold = periodStart + (TARDY_GRACE_MINUTES * 60 * 1000);
     return (Date.now() <= tardyThreshold) ? 'On Time' : 'Late';
   }
   ```

### Task 2: Verify Analysis Against Codebase

Added Code Verification section with confirmed line numbers:

| Function | Lines | Verified |
|----------|-------|----------|
| statusForNow() | 1252-1283 | Confirmed |
| bellSchedules | 616-624 | Confirmed |
| handleSignIn() calls statusForNow | 1396 | Confirmed |
| manualCheckIn() calls statusForNow | 1628 | Confirmed |

## Key Files

| File | Purpose |
|------|---------|
| `.planning/phases/04-tardy-logic-review/TARDY-LOGIC-ANALYSIS.md` | Complete analysis document |

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Recommend bell-schedule-based logic | Current logic is unpredictable and causes 52% of disputes |
| Suggest 5-minute grace period | Balances leniency with accountability, configurable |
| Document all 7 edge cases | Comprehensive understanding prevents incomplete fix |

## Next Phase Readiness

The analysis document provides:
- Complete understanding of current logic and its flaws
- Clear specification for new logic
- Code locations for implementation
- Configuration points (bell times, grace period)

Ready for implementation planning if Phase 4 continues.

## Commit History

| Hash | Message |
|------|---------|
| 7a2e3c7 | docs(04-01): Document current tardy logic and edge cases |
