# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-23)

**Core value:** Every student who signs in must have their correct attendance status reflected in Aeries. The system must work reliably for multiple teachers without requiring technical support.
**Current focus:** Phase 5 complete — ready to plan Phase 6

## Current Position

Phase: 5 of 8 (Auth Foundation and Data Migration) — COMPLETE
Plan: 3 of 3 in current phase
Status: Phase 5 complete, verified, deployed
Last activity: 2026-03-23 — Phase 5 executed and deployed to production

Progress: [██████░░░░░░░░░░░░░░] 55% (v1.0 complete; v2.0 phase 5 complete)

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
| 6-8. Remaining v2.0 | 0/8 | Not started |

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

### Blockers/Concerns

- [Phase 5] RESOLVED: All deployment issues (IAM, CORS, secrets, token signing) fixed
- [Phase 5] RESOLVED: Firestore path even-segment requirement — corrected paths propagated to all files
- [Phase 5] RESOLVED: Token expiry — Firebase Auth session persists via refresh token + onAuthStateChanged
- [Phase 7] Playwright in Docker has environment-specific failure modes; deploy smoke-test container before writing multi-teacher logic
- [Phase 8] LLM self-healing prompt is not production-validated for Aeries DOM; plan one prompt-tuning iteration

## Session Continuity

Last session: 2026-03-23
Stopped at: Phase 5 complete — all plans executed, verified, deployed to production
Resume file: None — ready to plan Phase 6
