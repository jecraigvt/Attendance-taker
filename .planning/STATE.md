# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-23)

**Core value:** Every student who signs in must have their correct attendance status reflected in Aeries. The system must work reliably for multiple teachers without requiring technical support.
**Current focus:** Phase 7 — Cloud Sync Worker (Railway)

## Current Position

Phase: 6 of 8 (Teacher Dashboard and Roster Management) — COMPLETE
Plan: 4 of 4 in current phase — COMPLETE
Status: Phase 6 complete, ready for Phase 7
Last activity: 2026-03-24 — Completed 06-04-PLAN.md (Onboarding wizard, sync status card, Settings section)

Progress: [█████████░░░░░░░░░░░] 70% (v1.0 complete; v2.0 phases 1-6 complete)

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
| 6. Teacher Dashboard | 4/4 | Complete |
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
- seating-config-path: seatingConfig stored in teachers/{uid}/config/main (merge with kioskPin/avoidPairs/frontRow)
- pickGroup-return-type: pickGroup() returns { group, overflow } — callers must destructure
- seat-field-in-logs: attendance log entries now include Seat field (number or absent)
- seating-front-groups: first 15% of numGroups are "front" groups for front-row preference logic
- fetchRoster-fallback: fetchRoster returns { error: "roster_requires_browser", fallback: "csv_upload" } when HTTP scraping fails — CSV upload always available
- preferredName-field: every student record has preferredName field; getDisplayName() helper returns it (or FirstName); used in kiosk, absent list, group display
- roster-upload-location: CSV upload moved to Roster tab; Attendance tab has hidden stubs for JS compat (rosterUpload, rosterStatus, rosterWarning, rosterSummary, rosterDebug, clearRostersBtn)
- roster-source-field: student records have source field ('aeries'|'csv'|'manual'); manual students preserved across Aeries re-fetches
- onboarding-wizard: showOnboardingWizard() triggered from handleLogin(); checkNeedsOnboarding() detects new teachers by absence of kioskPin/seatingConfig/frontRow/avoidPairs; onboardingComplete flag set to true on wizard completion
- sync-status-path: sync status read from teachers/{uid}/sync/status (onSnapshot); doc written by Phase 7 Railway sync worker
- settings-section: credential update calls authenticateTeacher CF; PIN change saves to config/main and updates kiosk binding; initSettingsUI() called on every showDashboard()

### Blockers/Concerns

- [Phase 5] RESOLVED: All deployment issues (IAM, CORS, secrets, token signing) fixed
- [Phase 5] RESOLVED: Firestore path even-segment requirement — corrected paths propagated to all files
- [Phase 5] RESOLVED: Token expiry — Firebase Auth session persists via refresh token + onAuthStateChanged
- [Phase 7] Playwright in Docker has environment-specific failure modes; deploy smoke-test container before writing multi-teacher logic
- [Phase 8] LLM self-healing prompt is not production-validated for Aeries DOM; plan one prompt-tuning iteration

## Session Continuity

Last session: 2026-03-24T06:29Z
Stopped at: Phase 6 complete — verified and deployed
Resume file: None — ready to plan Phase 7
