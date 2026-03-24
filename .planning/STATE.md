# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-23)

**Core value:** Every student who signs in must have their correct attendance status reflected in Aeries. The system must work reliably for multiple teachers without requiring technical support.
**Current focus:** Phase 6 in progress — dashboard shell complete, plans 02-04 remaining

## Current Position

Phase: 6 of 8 (Teacher Dashboard and Roster Management) — In progress
Plan: 1 of 4 in current phase — COMPLETE
Status: Plan 06-01 complete, ready for 06-02
Last activity: 2026-03-24 — Completed 06-01-PLAN.md (dashboard shell and navigation)

Progress: [███████░░░░░░░░░░░░░] 59% (v1.0 complete; v2.0 phases 1-5 + 6-01 complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 11 (8 v1.0 + 3 v2.0)
- Average duration: unknown
- Total execution time: unknown

**By Phase:**

| Phase | Plans | Status |
|-------|-------|--------|
| 1. Core Reliability | 2/2 | Complete |
| 2. Audit & Verification | 2/2 | Complete |
| 3. Schedule Improvements | 1/1 | Complete |
| 4. Tardy Logic Review | 3/3 | Complete |
| 5. Auth Foundation | 3/3 | Complete |
| 6. Teacher Dashboard | 1/4 | In progress |
| 7-8. Remaining v2.0 | 0/4 | Not started |

## Accumulated Context

### Decisions

Carried forward from v1.0:

- retry-strategy: Exponential backoff with 3 retries (5s, 15s, 45s)
- selector-fallback-order: data-attr -> text-content -> xpath
- interval-schedule: 20-minute intervals 08:00-15:40, plus 15:45 final
- bell-schedule-based-logic: Bell-schedule tardy logic replaces 5th-student threshold

v2.0 confirmed:

- auth-method: Aeries username/password (NOT Google Sign-In)
- credential-encryption: Fernet encryption; key in Firebase Functions secrets (Phase 5) and Railway env vars (Phase 7)
- fernet-npm-package: fernet npm for Node/Python cross-compatibility
- synthetic-email-pattern: {aeriesUsername}@aeries.attendance.local (or email-format usernames used as-is)
- credentials-storage-path: teachers/{uid}/credentials/aeries
- aeries-graceful-degradation: If Aeries unreachable on login, proceed with validated: false
- cloud-sync-host: Railway Hobby plan ($5/month)
- kiosk-linkage: Teacher logs in once, PIN to exit kiosk, Firebase Auth session persists indefinitely via refresh token
- self-healing-order: Build AFTER cloud sync is proven stable (Phase 8, not earlier)
- firestore-even-segment-paths: config/main, rosters/{id}, profile/main (not config, rosters/periods/{id}, profile)
- jeremy-uid: IUaKeeP9YnY5qd4OLTWyACbtOrT2
- teacher-name-hidden-on-kiosk: Per user request, kiosk screen does not show teacher name
- kiosk-binding-storage: sessionStorage always; localStorage only if "remember me" checked
- pin-storage: kioskPin stored in teachers/{uid}/config/main

Phase 6 confirmed:

- dashboard-layout: Fixed fullscreen panel (fixed inset-0) with tab navigation; Attendance tab default on open
- dashboard-section-pattern: class=dashboard-section + id=dashboard-{name}; switchDashboardSection() shows/hides
- dashboard-nav-pattern: class=dashboard-nav-btn; active state = border-red-700 + text-red-700
- showAdminPanel-alias: showAdminPanel() is alias for showDashboard(); safe to call from anywhere

### Blockers/Concerns

- [Phase 5] RESOLVED: All deployment issues (IAM, CORS, secrets, token signing) fixed
- [Phase 5] RESOLVED: Firestore path even-segment requirement — corrected paths propagated to all files
- [Phase 5] RESOLVED: Token expiry — Firebase Auth session persists via refresh token + onAuthStateChanged
- [Phase 7] Playwright in Docker has environment-specific failure modes; deploy smoke-test container before writing multi-teacher logic
- [Phase 8] LLM self-healing prompt is not production-validated for Aeries DOM; plan one prompt-tuning iteration

## Session Continuity

Last session: 2026-03-24
Stopped at: Completed 06-01-PLAN.md — dashboard shell with navigation
Resume file: None — ready for 06-02
