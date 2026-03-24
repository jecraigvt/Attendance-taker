---
phase: 08-self-healing
plan: 01
subsystem: infra
tags: [gemini, llm, self-healing, playwright, firestore, selectors, json-config]

# Dependency graph
requires:
  - phase: 07-railway-cloud-sync
    provides: sync_engine.py with hardcoded SELECTOR_STRATEGIES; firestore_client.py with Firestore helpers
provides:
  - selectors.json config file with all 4 element selector strategies
  - healer.py module with attempt_heal() — Gemini Flash with Pro escalation
  - write_healing_event() and get_healing_call_count_today() in firestore_client.py
  - _DEFAULT_SELECTORS fallback in sync_engine.py if selectors.json is missing
affects:
  - 08-02 (wires attempt_heal into live sync flow at selector failure points)

# Tech tracking
tech-stack:
  added: [google-generativeai (Gemini Flash + Pro)]
  patterns:
    - Selector config externalized to JSON for runtime-patchable updates
    - LLM healing with Flash-first, Pro-escalation on failure
    - Global Firestore collection (healing_events) for cross-teacher audit trail
    - Fail-open healing: cap check and API errors both return None, never crash sync

key-files:
  created:
    - railway-worker/selectors.json
    - railway-worker/healer.py
  modified:
    - railway-worker/sync_engine.py
    - railway-worker/firestore_client.py

key-decisions:
  - "DAILY_HEALING_CAP=25 across all teachers (not per-teacher) to bound Gemini costs"
  - "Healing events logged to global healing_events collection, not per-teacher subcollection"
  - "Fail-open on cap check and API errors — healing never crashes sync, returns None"
  - "DOM truncated to 30KB and stripped of script/style before sending to Gemini"
  - "_DEFAULT_SELECTORS fallback in sync_engine.py if selectors.json missing or corrupt"

patterns-established:
  - "Selector-config-as-JSON: SELECTOR_STRATEGIES loaded via json.load() at module import"
  - "Healer-module-pattern: attempt_heal() is called by sync_engine when all static fallbacks fail"
  - "Flash-then-Pro escalation: Gemini Flash tried first (cheaper); Pro only if Flash fails validation"
  - "Validation-before-acceptance: Gemini candidate selector tested via page.locator().count() > 0"

# Metrics
duration: 2min
completed: 2026-03-24
---

# Phase 8 Plan 1: Self-Healing Building Blocks Summary

**Selector strategies externalized to selectors.json, plus healer.py with Gemini Flash/Pro escalation and Firestore healing event logging**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-24T19:45:08Z
- **Completed:** 2026-03-24T19:47:34Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `selectors.json` with all 4 Aeries element selector strategies (student_cell, absent_checkbox, tardy_checkbox, period_dropdown) — now patchable at runtime without redeployment
- Updated `sync_engine.py` to load `SELECTOR_STRATEGIES` from `selectors.json` at module import with `_DEFAULT_SELECTORS` hardcoded fallback
- Created `healer.py` with `attempt_heal()` — daily cap check, DOM extraction, Gemini Flash call, selector validation, Pro escalation on Flash failure, Firestore event logging
- Added `write_healing_event()` and `get_healing_call_count_today()` to `firestore_client.py` targeting global `healing_events` collection

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract selectors to JSON config and update sync_engine.py** - `6cf1aee` (feat)
2. **Task 2: Create healer module and Firestore healing helpers** - `a5b3f03` (feat)

**Plan metadata:** (see below)

## Files Created/Modified

- `railway-worker/selectors.json` - All selector strategies; `student_cell`, `absent_checkbox`, `tardy_checkbox`, `period_dropdown`
- `railway-worker/healer.py` - Self-healing module with `attempt_heal()`, Flash/Pro escalation, 25-call daily cap, DOM extraction
- `railway-worker/sync_engine.py` - Now loads `SELECTOR_STRATEGIES` from `selectors.json` via `json.load()`; retains `_DEFAULT_SELECTORS` fallback
- `railway-worker/firestore_client.py` - Added `write_healing_event()` and `get_healing_call_count_today()` for global healing audit

## Decisions Made

- **DAILY_HEALING_CAP = 25**: Chosen to bound Gemini API costs while allowing reasonable healing across 5-10 teachers. The cap is global (not per-teacher) to prevent any one teacher's broken selectors from exhausting the daily budget.
- **Global `healing_events` collection**: Developer-facing audit log at top-level Firestore, not per-teacher. Makes it easy to query all healing events for the day without knowing teacher UIDs.
- **Fail-open healing**: If `GEMINI_API_KEY` is missing, library not installed, cap hit, or API error — `attempt_heal()` returns `None` silently. Sync engine continues with the existing failure path; healing never crashes a sync.
- **30KB DOM truncation + script/style removal**: Reduces Gemini token cost and focuses the model on structural HTML, not JS logic.
- **Flash-first, Pro escalation**: Gemini Flash is faster and cheaper for most selector discovery tasks. Pro is reserved for complex DOM structures where Flash fails.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

**GEMINI_API_KEY required for self-healing to activate.** Add to Railway environment variables:
- `GEMINI_API_KEY` — Google AI Studio API key with access to Gemini Flash and Pro models

Without this key, `attempt_heal()` returns `None` silently and sync continues unchanged. Self-healing is gracefully disabled.

Also ensure `google-generativeai` is in `requirements.txt` before Phase 8 plan 2 wires healing into the live sync flow.

## Next Phase Readiness

- `selectors.json` and `healer.py` are the two building blocks required before HEAL-01/02/03 can be wired in
- Phase 8 plan 2 will call `attempt_heal()` from `find_element_with_fallback()` when all static selectors fail
- `GEMINI_API_KEY` env var must be added to Railway before live healing activates
- Prompt quality is unvalidated against real Aeries DOM — plan one prompt-tuning iteration after first live healing event

---
*Phase: 08-self-healing*
*Completed: 2026-03-24*
