# Phase 7: Railway Cloud Sync - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Automated cloud-based attendance sync running on Railway for all teachers. The worker processes each teacher's attendance data and syncs it to Aeries on a schedule — replacing the dependency on Jeremy's local machine. Does not include self-healing (Phase 8) or new dashboard features beyond what Phase 6 already built.

</domain>

<decisions>
## Implementation Decisions

### Schedule & calendar
- 30-minute intervals, first run at 8:00 AM, last run at 4:00 PM
- Run on weekdays only (skip weekends)
- No school calendar needed — worker checks each teacher's Firestore for attendance data; if no data exists for that day, it skips that teacher. Summer, holidays, snow days all handled automatically.
- Only sync when there is NEW data that hasn't been synced already (timestamp comparison: last sync time vs latest attendance record)
- Per-teacher timezone stored in teacher profile (default to Pacific Time)

### Teacher-facing status
- Sync status card updates in real-time via existing Firestore onSnapshot (already wired in Phase 6)
- Show last sync time (e.g., "Last synced: 10:32 AM")
- Full day sync history: all runs from today, collapsed previous days that teachers can expand
- No student count or next-sync-time display needed

### Failure & recovery
- Error categorization: distinguish between credentials invalid, Aeries unreachable, selector broken, and unknown errors
- Each category gets different dashboard messaging (friendly + category, e.g., "Sync failed — couldn't reach Aeries. We'll retry next cycle.")
- Invalid credentials: immediately stop syncing for that teacher, mark status as "credentials invalid" so dashboard prompts credential update
- Retry behavior for non-credential failures: Claude's discretion (retry transient in-cycle, skip persistent)
- Unsyncable records (student not found in Aeries): flag for teacher on dashboard so they know which students need manual attention
- One teacher's failure never blocks other teachers

### Operational visibility
- System health monitoring: Claude's discretion (lightweight approach fitting the stack)
- Admin overview vs individual checking: Claude's discretion (5-10 teachers expected near-term)
- Logging verbosity: Claude's discretion (appropriate log levels)

### Claude's Discretion
- In-cycle retry strategy for transient failures vs waiting for next 30-min cycle
- System health monitoring approach (Railway built-in, Firestore admin doc, or email)
- Whether to build an admin overview page or rely on individual status checks
- Log verbosity levels
- Docker and deployment configuration details
- Worker process architecture (APScheduler, cron, etc.)

</decisions>

<specifics>
## Specific Ideas

- User's key insight: "Only sync when there is attendance data for that teacher on that day" — the simplest approach to handling non-school days
- The existing sync/status Firestore path and onSnapshot listener from Phase 6 should be the write target for the Railway worker
- Sequential teacher processing is fine for 5-10 teachers

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-railway-cloud-sync*
*Context gathered: 2026-03-24*
