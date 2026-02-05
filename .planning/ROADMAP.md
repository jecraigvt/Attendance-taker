# Roadmap: Attendance Sync Reliability

## Overview

This project transforms the attendance sync system from ~97% reliable to near-100% by addressing the root causes of sync failures (17% of errors) and tardy disputes (52% of errors). We progress from core reliability fixes, through audit/verification capabilities, to schedule improvements, and finally tackle the tardy logic that causes the majority of disputes.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (e.g., 2.1): Urgent insertions if needed (marked with INSERTED)

- [x] **Phase 1: Core Reliability** - Retry logic, failure logging, and selector fallbacks to address sync failures
- [x] **Phase 2: Audit & Verification** - Track exactly what was synced and verify it succeeded
- [ ] **Phase 3: Schedule Improvements** - More frequent syncs and daily summary reporting
- [ ] **Phase 4: Tardy Logic Review** - Analyze and fix the threshold logic causing tardy disputes

## Phase Details

### Phase 1: Core Reliability
**Goal**: Sync failures are automatically retried, gracefully handled, and fully logged so no student is incorrectly marked absent due to transient errors
**Depends on**: Nothing (first phase)
**Requirements**: REQ-SYNC-01, REQ-SYNC-03, REQ-ROBUST-01, REQ-ROBUST-02
**Success Criteria** (what must be TRUE):
  1. When Aeries sync fails, the system automatically retries up to 3 times with increasing delays before giving up
  2. Every sync failure is logged with full context (student ID, period, timestamp, error details) to a persistent file
  3. When Aeries UI changes break primary selectors, fallback selectors attempt to continue and alert is raised
  4. When some students sync and others fail, successful syncs are preserved and failed students are queued for next cycle
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md - Retry logic with exponential backoff and comprehensive failure logging
- [x] 01-02-PLAN.md - Selector fallbacks for UI resilience and partial failure handling

### Phase 2: Audit & Verification
**Goal**: Every sync action is logged and verified so discrepancies can be identified and investigated
**Depends on**: Phase 1
**Requirements**: REQ-AUDIT-01, REQ-AUDIT-02
**Success Criteria** (what must be TRUE):
  1. Each sync logs the exact data sent to Aeries (student ID, attendance status, period) before and after the attempt
  2. After each sync, a verification report shows what was sent and flags any discrepancies between Firebase and sync attempt
  3. Discrepancy reports are saved to file for later review
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md - Sync action audit logging (pre/post intent and action logging)
- [x] 02-02-PLAN.md - Verification report generator (compare Firebase to sync actions)

### Phase 3: Schedule Improvements
**Goal**: Syncs run frequently enough that errors are caught quickly, with daily summaries for oversight
**Depends on**: Phase 2
**Requirements**: REQ-SYNC-02, REQ-AUDIT-03
**Success Criteria** (what must be TRUE):
  1. Sync runs every 15-20 minutes during school hours (8:00 AM - 3:45 PM) instead of once per period
  2. Final catch-all sync at end of day processes any remaining records
  3. Daily summary report shows total students synced, failures, retries, and any unresolved issues
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

### Phase 4: Tardy Logic Review
**Goal**: Tardy determination is based on actual bell schedule times, eliminating the 52% of disputes caused by the current threshold logic
**Depends on**: Phase 3
**Requirements**: REQ-TARDY-01, REQ-TARDY-02
**Success Criteria** (what must be TRUE):
  1. Current "5th student + 8 minutes" logic is documented with all edge cases identified
  2. Bell schedule times are configurable in the system
  3. Tardy status is determined by comparing sign-in time to actual period start time
  4. Analysis shows whether new logic reduces dispute rate
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Reliability | 2/2 | Complete | 2026-02-05 |
| 2. Audit & Verification | 2/2 | Complete | 2026-02-05 |
| 3. Schedule Improvements | 0/TBD | Not started | - |
| 4. Tardy Logic Review | 0/TBD | Not started | - |
