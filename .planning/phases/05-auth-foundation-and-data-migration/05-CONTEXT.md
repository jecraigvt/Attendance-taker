# Phase 5: Auth Foundation and Data Migration - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform the single-user attendance system into a multi-tenant structure. Teachers authenticate with Aeries credentials, existing data migrates to per-teacher paths, and kiosk sign-ins write to the correct tenant. This phase establishes the structural foundation every subsequent phase builds on.

Out of scope: Teacher dashboard UI (Phase 6), cloud sync (Phase 7), self-healing (Phase 8).

</domain>

<decisions>
## Implementation Decisions

### Login Experience
- Brief welcome message explaining the app, then login fields below
- Teacher enters Aeries username and password; app validates credentials against Aeries in real-time and warns if login fails
- "Remember me" checkbox — teacher chooses whether to stay logged in across sessions
- No in-app password recovery — if teacher forgets password, they reset through Aeries directly
- No "forgot password" link needed (Aeries handles credential management)

### Migration Experience
- Brief downtime acceptable — run migration during off-hours (evening/weekend)
- Automated count check for verification: script compares record counts old vs new paths, reports pass/fail
- Old data paths kept as safety net after migration — remove later once confidence builds
- Migration script must be idempotent — safe to re-run without duplicating data (skips already-migrated records)

### Kiosk Mode Transition
- Kiosk mode is the DEFAULT state — app loads directly into student sign-in screen (preserves current behavior)
- Teacher enters a unique PIN to break out of kiosk into their dashboard/console
- "Forgot PIN?" option on kiosk screen — teacher enters Aeries credentials to reset their PIN
- Teacher name displayed on kiosk screen (e.g., "Mr. Smith's class")
- Different teacher can use same tablet: sign out from dashboard, new teacher logs in, kiosk rebinds to new teacher's UID

### Data Isolation Rules
- Completely isolated — no teacher sees another teacher's data, no awareness of other teachers
- No school-level grouping — each teacher is a standalone account
- No in-app admin role — developer (Jeremy) accesses all data via Firebase console
- Bell schedule configuration is per-teacher and optional
- Default tardy logic: 5th sign-in + configurable time increment (default 8 minutes) — the time increment after 5th sign-in is adjustable per teacher

### Claude's Discretion
- Login form styling and layout details
- Exact migration script implementation (copy strategy, batch size, error handling)
- PIN length and format for kiosk exit
- Firestore path structure for per-teacher data
- Security rules implementation details

</decisions>

<specifics>
## Specific Ideas

- Current kiosk behavior should be preserved — "I like how I have it" (app auto-displays kiosk mode)
- Tardy logic stays 5th-sign-in-based, not bell-schedule-based — bell schedule info is optional
- The configurable time increment (teacher console UI) is Phase 6; the data model supporting it belongs here

</specifics>

<deferred>
## Deferred Ideas

- Teacher console configuration UI for tardy time increment — Phase 6
- Bell schedule as optional alternative tardy method — future consideration
- School-level grouping for shared bell schedules — if multi-school demand arises

</deferred>

---

*Phase: 05-auth-foundation-and-data-migration*
*Context gathered: 2026-03-23*
