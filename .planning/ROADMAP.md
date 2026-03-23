# Roadmap: Attendance Taker

## Milestones

- ✅ **v1.0 Attendance Sync Reliability** - Phases 1-4 (shipped 2026-02-05)
- 🚧 **v2.0 Multi-Tenant SaaS** - Phases 5-8 (in progress)

## Phases

<details>
<summary>✅ v1.0 Attendance Sync Reliability (Phases 1-4) - SHIPPED 2026-02-05</summary>

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
**Plans**: 1 plan

Plans:
- [x] 03-01-PLAN.md - Update schedule to 20-min intervals and add daily summary report

### Phase 4: Tardy Logic Review
**Goal**: Tardy determination is based on actual bell schedule times, eliminating the 52% of disputes caused by the current threshold logic
**Depends on**: Phase 3
**Requirements**: REQ-TARDY-01, REQ-TARDY-02
**Success Criteria** (what must be TRUE):
  1. Current "5th student + 8 minutes" logic is documented with all edge cases identified
  2. Bell schedule times are configurable in the system
  3. Tardy status is determined by comparing sign-in time to actual period start time
  4. Analysis shows whether new logic reduces dispute rate
**Plans**: 3 plans

Plans:
- [x] 04-01-PLAN.md - Document current tardy logic and analyze edge cases
- [x] 04-02-PLAN.md - Implement bell-schedule-based tardy calculation
- [x] 04-03-PLAN.md - Validate new logic and analyze projected dispute reduction

</details>

---

### 🚧 v2.0 Multi-Tenant SaaS (In Progress)

**Milestone Goal:** Transform from single-teacher tool to multi-tenant platform where any teacher can sign up, manage rosters, and have attendance automatically synced to Aeries via cloud automation — without requiring developer support.

---

### Phase 5: Auth Foundation and Data Migration
**Goal**: Teachers have isolated accounts with their own data, the existing data is safely migrated, and kiosk sign-ins write to the correct tenant — making multi-tenancy the structural reality every subsequent phase builds on
**Depends on**: Phase 4
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, KIOSK-01, KIOSK-02
**Success Criteria** (what must be TRUE):
  1. Teacher can sign in with their Aeries username and password and land on a teacher-specific view
  2. Jeremy's existing attendance data is accessible after migration — no records missing, kiosk still accepts student sign-ins
  3. A second teacher's data is invisible to the first teacher (Firestore security rules block cross-tenant reads)
  4. Kiosk tablet links to a specific teacher's UID after teacher logs in once; subsequent student sign-ins go to that teacher's data path
  5. Aeries credentials are stored encrypted at rest — plaintext password never written to Firestore
**Plans**: 3 plans

Plans:
- [ ] 05-01-PLAN.md — Data migration script: copy existing records to per-teacher paths, verify counts, confirm kiosk still works
- [ ] 05-02-PLAN.md — Auth infrastructure: Cloud Function for Aeries credential validation/encryption, Firestore security rules
- [ ] 05-03-PLAN.md — Kiosk integration: login screen, PIN-based kiosk exit, per-teacher Firestore paths in HTML and sync script

### Phase 6: Teacher Dashboard and Roster Management
**Goal**: Teachers can self-serve their full account setup — entering credentials, configuring seating, and triggering roster fetches — without any developer involvement
**Depends on**: Phase 5
**Requirements**: DASH-01, DASH-02, DASH-03, SEAT-01, SEAT-02, SEAT-03, SEAT-04, ROST-01, ROST-02
**Success Criteria** (what must be TRUE):
  1. A new teacher completes first-time setup (enter Aeries creds, configure seating, fetch roster) through an in-app onboarding flow with no external help
  2. Teacher can see current sync status — last sync time, success or failure, error details — on their dashboard
  3. Teacher can update their Aeries credentials through the UI at any time without contacting the developer
  4. Teacher can choose group-based seating, individual desk-based seating, or no seat assignment — and configure it through the dashboard
  5. Class rosters are fetched automatically from Aeries using the teacher's credentials and refresh on a schedule or on demand
**Plans**: TBD

Plans:
- [ ] 06-01: Teacher onboarding flow — credential entry, seating mode selection, first roster fetch
- [ ] 06-02: Seating configuration UI — group mode, individual desk mode, and off mode
- [ ] 06-03: Roster auto-fetch from Aeries — Playwright-based roster pull, scheduled refresh, on-demand trigger
- [ ] 06-04: Sync status dashboard — last sync time, success/failure display, credential update UI

### Phase 7: Railway Cloud Sync
**Goal**: Attendance sync runs automatically in the cloud on Railway every 20 minutes during school hours for every teacher — with no dependency on the developer's local machine
**Depends on**: Phase 6
**Requirements**: SYNC-01, SYNC-02, SYNC-03
**Success Criteria** (what must be TRUE):
  1. Aeries sync runs every 20 minutes during school hours without any action from the developer or teacher
  2. Each teacher's attendance is processed in the cloud — Jeremy's PC is not involved
  3. When sync fails for any teacher, that teacher's dashboard shows an error with details; one teacher's failure does not block others
**Plans**: TBD

Plans:
- [ ] 07-01: Docker container and Railway deployment — Dockerfile, Playwright smoke test in Railway environment
- [ ] 07-02: Multi-teacher sync orchestrator — APScheduler, sequential per-teacher loop, credential decryption, sync status writes to Firestore

### Phase 8: Self-Healing LLM Layer
**Goal**: When Aeries UI changes break selectors, the system repairs itself using Gemini — reducing developer intervention to zero for common selector failures
**Depends on**: Phase 7
**Requirements**: HEAL-01, HEAL-02, HEAL-03
**Success Criteria** (what must be TRUE):
  1. When all static selector fallbacks are exhausted, Gemini Flash is automatically invoked to identify a replacement selector
  2. If Flash fails, Gemini Pro is tried as a fallback before the sync is marked failed
  3. Healed selectors are stored in a config file (not hardcoded) and the healing event appears in the teacher dashboard
**Plans**: TBD

Plans:
- [ ] 08-01: Selector config file and healer scaffold — extract selectors to config, wrap find_element_with_fallback(), dry-run validation
- [ ] 08-02: Gemini Flash/Pro integration — prompt, selector validation, Firestore caching, Flash-to-Pro escalation logic

---

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Core Reliability | v1.0 | 2/2 | Complete | 2026-02-05 |
| 2. Audit & Verification | v1.0 | 2/2 | Complete | 2026-02-05 |
| 3. Schedule Improvements | v1.0 | 1/1 | Complete | 2026-02-05 |
| 4. Tardy Logic Review | v1.0 | 3/3 | Complete | 2026-02-05 |
| 5. Auth Foundation and Data Migration | v2.0 | 0/3 | Planning complete | - |
| 6. Teacher Dashboard and Roster Management | v2.0 | 0/4 | Not started | - |
| 7. Railway Cloud Sync | v2.0 | 0/2 | Not started | - |
| 8. Self-Healing LLM Layer | v2.0 | 0/2 | Not started | - |
