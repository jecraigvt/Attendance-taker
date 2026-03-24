# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-23)

**Core value:** Every student who signs in must have their correct attendance status reflected in Aeries. The system must work reliably for multiple teachers without requiring technical support.
**Current focus:** Phase 8 — Self-Healing LLM Layer

## Current Position

Phase: 8 of 8 (Self-Healing) — COMPLETE
Plan: 2 of 2 in current phase — COMPLETE
Status: Phase 8 complete — full self-healing pipeline integrated into live sync
Last activity: 2026-03-24 — Completed 08-02-PLAN.md (healer wired into sync_engine, deps added)

Progress: [████████████████████] 100% (all phases complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 15 (8 v1.0 + 7 v2.0)
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
| 7. Railway Cloud Sync | 2/2 | Complete |
| 8. Self-Healing | 2/2 | Complete |

## Accumulated Context

### Decisions

Carried forward from v1.0:

- retry-strategy: Exponential backoff with 3 retries (5s, 15s, 45s)
- selector-fallback-order: data-attr -> text-content -> xpath
- interval-schedule: 20-minute intervals 08:00-15:40, plus 15:45 final (local); 30-minute intervals in cloud worker
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

Phase 7 confirmed:

- railway-base-image: mcr.microsoft.com/playwright/python:v1.49.1-noble (avoids Chromium system library issues)
- firebase-admin-init-pattern: FIREBASE_SERVICE_ACCOUNT env var holds full JSON blob parsed with json.loads() (no key file on disk)
- fernet-python-package: use `cryptography` (not `python-fernet`) for Fernet cross-compatibility with Node fernet npm
- railway-toml-worker: builder=DOCKERFILE, numReplicas=1, ON_FAILURE restart, no healthcheck (worker not web server)
- smoke-test-pattern: three independent tests return pass/skip/fail; exits 1 only on actual failures
- railway-worker-dir: all sync worker source files in railway-worker/ (separate from legacy attendance-sync/)
- time-of-day-guard-location: in run_all_teachers() body (not scheduler config) — scheduler fires unconditionally, guard is cheap early return
- skipped-sync-no-write: skipped syncs (no_data, already_synced) do NOT write sync/status — preserves last real sync timestamp on dashboard
- sync-engine-never-raises: sync_teacher() catches all exceptions internally, returns result dict, writes Firestore status
- error-categories-4: credentials_invalid, aeries_unreachable, selector_broken, unknown — mapped to friendly dashboard messages
- credentials-invalid-blocks-sync: errorCategory=credentials_invalid persisted to sync/status; is_sync_blocked() skips teacher until credentials re-entered
- unsyncable-list-pattern: per-student failures accumulate in unsyncable list, whole sync continues; list written to unsyncableStudents in sync/status
- startup-immediate-sync: worker runs one sync cycle immediately on startup before scheduler begins
- cloud-sync-interval: 30-minute intervals (refined from original 20-min during Phase 7 planning — 5-10 teachers × ~2min/sync fits in 30-min window)

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
- roster-upload-location: CSV upload moved to Roster tab; Attendance tab has hidden stubs for JS compat
- roster-source-field: student records have source field ('aeries'|'csv'|'manual'); manual students preserved across Aeries re-fetches
- onboarding-wizard: showOnboardingWizard() triggered from handleLogin(); checkNeedsOnboarding() detects new teachers
- sync-status-path: sync status read from teachers/{uid}/sync/status (onSnapshot); doc written by Phase 7 Railway sync worker
- settings-section: credential update calls authenticateTeacher CF; PIN change saves to config/main and updates kiosk binding

Phase 8 plan 2 confirmed:

- healing-lazy-import: attempt_heal imported inside find_element_with_fallback() body to avoid circular imports at module load
- healing-index-sentinel: strategy_index == len(strategies) returned when element found via healing (one past last static index)
- gemini-key-non-fatal: GEMINI_API_KEY missing is a WARNING not an exit — self-healing degrades gracefully, sync continues
- selector-broken-message: "Aeries page changed and auto-repair failed — developer notified"
- dockerfile-explicit-json: non-glob data files like selectors.json must be explicitly COPY'd in Dockerfile alongside *.py

Phase 8 plan 1 confirmed:

- selectors-config-file: SELECTOR_STRATEGIES loaded from railway-worker/selectors.json at module import; _DEFAULT_SELECTORS hardcoded fallback if file missing
- healing-daily-cap: DAILY_HEALING_CAP=25 per UTC day, global across all teachers (not per-teacher)
- healing-event-collection: healing_events is a top-level Firestore collection (not per-teacher subcollection)
- gemini-escalation-order: Flash first (gemini-2.0-flash), Pro escalation (gemini-2.0-pro) on Flash validation failure
- healing-fail-open: attempt_heal() returns None on cap hit, API error, or missing GEMINI_API_KEY — never crashes sync
- healing-dom-prep: strip script/style tags, truncate to 30KB before sending to Gemini
- healing-validation: Gemini candidate tested with page.locator(formatted).count() > 0 before acceptance
- google-generativeai-package: required for self-healing (add to requirements.txt before Phase 8 plan 2)

### Blockers/Concerns

- [Phase 5] RESOLVED: All deployment issues (IAM, CORS, secrets, token signing) fixed
- [Phase 5] RESOLVED: Firestore path even-segment requirement — corrected paths propagated to all files
- [Phase 5] RESOLVED: Token expiry — Firebase Auth session persists via refresh token + onAuthStateChanged
- [Phase 7] RESOLVED: Docker/Playwright smoke test passed; environment validated
- [Phase 7] RESOLVED: credentials_invalid blocking — gap closed, errorCategory persists and is_sync_blocked() skips teacher
- [Phase 7] PENDING: Push to GitHub and deploy to Railway for live verification
- [Phase 8] LLM self-healing prompt is not production-validated for Aeries DOM; plan one prompt-tuning iteration

## Session Continuity

Last session: 2026-03-24T19:52Z
Stopped at: Phase 8 plan 2 complete — healer integrated into sync_engine.py, deps added
Resume file: None — all phases complete. Next: push to GitHub and deploy to Railway.
