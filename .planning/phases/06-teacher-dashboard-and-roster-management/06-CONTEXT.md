# Phase 6: Teacher Dashboard and Roster Management - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Teachers can self-serve their full account setup — entering credentials, configuring seating, and triggering roster fetches — through an in-app experience with no developer involvement. Includes a dashboard for day-to-day attendance overview and sync status visibility.

</domain>

<decisions>
## Implementation Decisions

### Onboarding flow
- Step-by-step wizard: Credentials → Roster fetch → Seating configuration
- Progress indicator showing current step (1 of 3, etc.)
- After onboarding, teacher lands on their dashboard (not kiosk)
- First time teacher launches kiosk, prompt them to set their PIN
- PIN can always be reset by logging in with Aeries credentials

### Seating configuration
- Seating is dynamic: students get randomly assigned a group and seat at sign-in time
- Teacher configures: number of groups + default seats per group (applied to all), then individually adjustable per group
- Groups of size 1 = individual desk seating (note this in the UI)
- Option to turn off seat assignment entirely
- Default config applies to all periods; option to customize per-period (including turning off per-period)
- When all seats in all groups are full, student sees overflow message ("All groups full — check with teacher")
- After sign-in, student sees prominent display: "You are in Group X, Seat Y"

### Dashboard layout
- Keep the existing attendance view largely as-is — don't redesign what works
- Primary view: today's attendance organized by period (Period 1 — 28/32 ✅, etc.)
- Expandable per-period details
- Sync status visible on main dashboard (small card/bar — last sync time, success/failure) but not dominant
- Preserve the existing full-screen timer feature
- Navigation between sections (attendance, roster, seating, settings): Claude's discretion

### Roster management
- Initial fetch: auto-fetch all periods from Aeries after credential verification
- Roster refresh: manual only — teacher clicks "Refresh Roster" when needed
- When refresh finds changes: auto-apply immediately, show summary ("2 added, 1 removed" with names)
- Teachers can manually add or remove students outside of Aeries sync
- Preferred names: editable during onboarding (review step after roster fetch) AND anytime from roster page
- Preferred names used everywhere in student-facing and teacher-facing UI (kiosk sign-in, group display, future features)
- Preferred names NOT used in Playwright/Aeries sync — official names from roster used there

### Claude's Discretion
- Navigation pattern (sidebar vs tabs vs other)
- Wizard skip logic (credentials required; whether roster/seating can be deferred)
- Loading states and error handling throughout
- Exact layout and spacing of dashboard components
- How manual roster edits are flagged vs Aeries-sourced students

</decisions>

<specifics>
## Specific Ideas

- "I really like the timer and its full-screen UI" — preserve this as-is
- Seating UI should have a note: "For individual desk assignment, set group size to 1"
- The existing attendance view works well — wrap it in the new dashboard context rather than rebuilding

</specifics>

<deferred>
## Deferred Ideas

- **Random name picker** — Full-screen UI (similar to timer) that randomly picks a present student from the current period. Knows the period and who's present. Great for calling on students. Small feature, could be a quick addition.

</deferred>

---

*Phase: 06-teacher-dashboard-and-roster-management*
*Context gathered: 2026-03-23*
