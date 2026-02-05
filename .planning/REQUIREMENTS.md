# Requirements

## Sync Reliability

### REQ-SYNC-01: Retry Logic
**Priority:** High
**Status:** Active

Sync retries up to 3 times with exponential backoff (e.g., 5s, 15s, 45s) when Aeries sync fails.

**Acceptance Criteria:**
- [ ] Failed sync triggers automatic retry
- [ ] Backoff increases exponentially between attempts
- [ ] After 3 failures, error is logged with full context
- [ ] Retry count and outcomes are tracked

---

### REQ-SYNC-02: Frequent Sync Schedule
**Priority:** High
**Status:** Active

Sync runs every 15-20 minutes during school hours instead of once per period.

**Acceptance Criteria:**
- [ ] Sync schedule updated to 15-20 minute intervals
- [ ] Schedule covers 8:00 AM - 3:45 PM school hours
- [ ] Final "catch-all" sync at end of day retained

---

### REQ-SYNC-03: Sync Failure Logging
**Priority:** High
**Status:** Active

Failed syncs are logged with full context for debugging (student ID, period, timestamp, error details, retry count).

**Acceptance Criteria:**
- [ ] Each sync attempt is logged with timestamp
- [ ] Failed syncs include error message and stack trace
- [ ] Log includes which students were affected
- [ ] Logs are persisted to file for later review

---

## Audit & Logging

### REQ-AUDIT-01: Sync Action Logging
**Priority:** Medium
**Status:** Active

Each sync logs exactly what was sent to Aeries (student ID, status, period).

**Acceptance Criteria:**
- [ ] Pre-sync: log intended actions
- [ ] Post-sync: log actual actions taken
- [ ] Format allows easy comparison with Firebase data

---

### REQ-AUDIT-02: Post-Sync Verification Report
**Priority:** Medium
**Status:** Active

After each sync, generate a report comparing Firebase data to sync attempt.

**Acceptance Criteria:**
- [ ] Report shows: students synced, status sent, any discrepancies
- [ ] Discrepancies flagged for review
- [ ] Report saved to file or displayed in console

---

### REQ-AUDIT-03: Daily Summary Report
**Priority:** Low
**Status:** Active

Generate a daily summary of all sync activity.

**Acceptance Criteria:**
- [ ] Total students synced per period
- [ ] Total failures and retries
- [ ] List of any unresolved issues

---

## Tardy Logic

### REQ-TARDY-01: Review Threshold Logic
**Priority:** Medium
**Status:** Active

Review the 8-minute threshold logic (after 5th student) for correctness.

**Acceptance Criteria:**
- [ ] Current logic documented and analyzed
- [ ] Edge cases identified (e.g., what if <5 students in period?)
- [ ] Recommendation made: keep, modify, or replace

---

### REQ-TARDY-02: Bell Schedule Integration
**Priority:** Medium
**Status:** Active

Tardy calculation should use actual bell schedule times, not just relative timing.

**Acceptance Criteria:**
- [ ] Bell schedule times configurable
- [ ] Tardy determined by: sign-in time vs. period start time
- [ ] Current "5th student + 8 min" logic evaluated against this

---

## Robustness

### REQ-ROBUST-01: Selector Fallbacks
**Priority:** High
**Status:** Active

Aeries UI selectors have fallbacks for when UI changes.

**Acceptance Criteria:**
- [ ] Multiple selector strategies per element (ID, class, text, XPath)
- [ ] Graceful degradation when primary selector fails
- [ ] Alert when fallback is used (indicates UI changed)

---

### REQ-ROBUST-02: Partial Failure Handling
**Priority:** Medium
**Status:** Active

Sync gracefully handles partial failures (some students sync, others fail).

**Acceptance Criteria:**
- [ ] Failed students tracked separately
- [ ] Successful syncs not rolled back on partial failure
- [ ] Failed students queued for retry in next sync cycle

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| REQ-SYNC-01 | Phase 1 | Complete |
| REQ-SYNC-02 | Phase 3 | Complete |
| REQ-SYNC-03 | Phase 1 | Complete |
| REQ-AUDIT-01 | Phase 2 | Complete |
| REQ-AUDIT-02 | Phase 2 | Complete |
| REQ-AUDIT-03 | Phase 3 | Complete |
| REQ-TARDY-01 | Phase 4 | Pending |
| REQ-TARDY-02 | Phase 4 | Pending |
| REQ-ROBUST-01 | Phase 1 | Complete |
| REQ-ROBUST-02 | Phase 1 | Complete |

---
*Generated: 2026-02-05*
