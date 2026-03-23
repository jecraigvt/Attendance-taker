# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-23)

**Core value:** Every student who signs in must have their correct attendance status reflected in Aeries. The system must work reliably for multiple teachers without requiring technical support.
**Current focus:** Phase 5 — Auth Foundation and Data Migration

## Current Position

Phase: 5 of 8 (Auth Foundation and Data Migration)
Plan: 1 of 3 in current phase (05-01 at checkpoint — awaiting human-verify)
Status: In progress — paused at checkpoint:human-verify
Last activity: 2026-03-23 — Completed Task 1 of 05-01 (migration script created)

Progress: [████░░░░░░░░░░░░░░░░] 50% (v1.0 complete; v2.0 phase 5 in progress)

## Performance Metrics

**Velocity:**
- Total plans completed: 8 (all v1.0)
- Average duration: unknown
- Total execution time: unknown

**By Phase:**

| Phase | Plans | Status |
|-------|-------|--------|
| 1. Core Reliability | 2/2 | Complete |
| 2. Audit & Verification | 2/2 | Complete |
| 3. Schedule Improvements | 1/1 | Complete |
| 4. Tardy Logic Review | 3/3 | Complete |
| 5-8. v2.0 phases | 0/11 | Not started |

## Accumulated Context

### Decisions

Carried forward from v1.0:

- retry-strategy: Exponential backoff with 3 retries (5s, 15s, 45s)
- selector-fallback-order: data-attr -> text-content -> xpath
- interval-schedule: 20-minute intervals 08:00-15:40, plus 15:45 final
- bell-schedule-based-logic: Bell-schedule tardy logic replaces 5th-student threshold

New for v2.0 (pending confirmation):

- auth-method: Aeries username/password (NOT Google Sign-In) — research reversed PROJECT.md assumption
- credential-encryption: Fernet encryption; key lives in Railway env vars only, never in Firestore or client JS
- cloud-sync-host: Railway Hobby plan ($5/month) — free tier RAM insufficient for Chromium
- kiosk-linkage: Teacher logs in once, switches to kiosk mode; UID bound to that tablet
- self-healing-order: Build AFTER cloud sync is proven stable (Phase 8, not earlier)
- migration-timing: Data migration script written and verified BEFORE any auth code ships

### Blockers/Concerns

- [Phase 5] Credential encryption boundary: who performs the encryption (Cloud Function vs. browser-side) — resolve in Phase 5 planning before implementation
- [Phase 5] Data migration must be verified against live Firestore counts before old paths are decommissioned
- [Phase 7] Playwright in Docker has environment-specific failure modes; deploy smoke-test container before writing multi-teacher logic
- [Phase 8] LLM self-healing prompt is not production-validated for Aeries DOM; plan one prompt-tuning iteration

## Session Continuity

Last session: 2026-03-23
Stopped at: 05-01 checkpoint:human-verify (Task 2) — migration script ready, awaiting live Firestore run
Resume file: .planning/phases/05-auth-foundation-and-data-migration/05-01-PLAN.md (Task 2)
