# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-23)

**Core value:** Every student who signs in must have their correct attendance status reflected in Aeries. The system must work reliably for multiple teachers without requiring technical support.
**Current focus:** Milestone v2.0 — Multi-Tenant SaaS

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-03-23 — Milestone v2.0 started

## Accumulated Context

### Decisions

Carried forward from v1.0:

| ID | Plan | Decision | Impact |
|----|------|----------|--------|
| retry-strategy | 01-01 | Exponential backoff with 3 retries (5s, 15s, 45s) | Login failures resolved in 70s max |
| selector-fallback-order | 01-02 | Fallback order: data-attr -> text-content -> xpath | Prioritizes most stable selectors |
| cross-cycle-retry | 01-02 | Failed students persist to JSON and retry next cycle | Handles systematic failures |
| interval-schedule | 03-01 | 20-minute intervals 08:00-15:40, plus 15:45 final | Frequent syncs catch failures fast |
| bell-schedule-based-logic | 04-01 | Bell-schedule-based tardy logic replaces 5th-student logic | Deterministic, reduces disputes |

### Pending Todos

None — defining requirements for v2.0.

### Blockers/Concerns

- Storing teacher Aeries credentials securely is a significant responsibility
- Playwright in cloud containers can be resource-intensive
- Gemini self-healing is cutting-edge; may need iteration

## Session Continuity

Last session: 2026-03-23
Stopped at: Milestone v2.0 initialization
Resume file: None
