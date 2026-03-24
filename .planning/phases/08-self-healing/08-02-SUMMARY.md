---
phase: 08-self-healing
plan: 02
subsystem: infra
tags: [playwright, gemini, self-healing, sync-engine, requirements, docker]

# Dependency graph
requires:
  - phase: 08-01
    provides: healer.py with attempt_heal() function and selectors.json config
  - phase: 07-railway-cloud-sync
    provides: sync_engine.py with find_element_with_fallback() and Playwright sync loop
provides:
  - find_element_with_fallback() with healing integration — calls attempt_heal() after all static selectors fail
  - google-generativeai dependency in requirements.txt
  - GEMINI_API_KEY startup warning in worker.py (non-fatal)
  - selectors.json COPY in Dockerfile
affects: []

# Tech tracking
tech-stack:
  added: [google-generativeai>=0.8.0,<1.0.0]
  patterns:
    - "Lazy import pattern: from healer import attempt_heal inside function body to avoid circular imports"
    - "Fail-open healing: healing failure falls through to SyncEngineError, never crashes sync"
    - "Sentinel index: strategy_index == len(strategies) signals element was found via healing"

key-files:
  created: []
  modified:
    - railway-worker/sync_engine.py
    - railway-worker/worker.py
    - railway-worker/requirements.txt
    - railway-worker/Dockerfile

key-decisions:
  - "healing-lazy-import: attempt_heal imported inside find_element_with_fallback() body to avoid circular imports at module load"
  - "healing-index-sentinel: strategy_index == len(strategies) returned when element found via healing (distinguishes healed vs static)"
  - "gemini-key-non-fatal: GEMINI_API_KEY missing is a WARNING not an exit — self-healing degrades gracefully, sync continues"
  - "selector-broken-message: updated to 'Aeries page changed and auto-repair failed — developer notified'"

patterns-established:
  - "Lazy import for optional dependencies: import inside function body rather than at top of module"
  - "Dockerfile explicit copy: non-glob data files (JSON, etc.) must be explicitly COPY'd alongside *.py"

# Metrics
duration: 2min
completed: 2026-03-24
---

# Phase 8 Plan 2: Healer Integration Summary

**Gemini self-healing wired into Playwright sync loop — find_element_with_fallback() now calls attempt_heal() after all static selectors fail, with google-generativeai added as a dependency**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-24T19:50:20Z
- **Completed:** 2026-03-24T19:52:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `find_element_with_fallback()` now invokes Gemini self-healing as a last resort before raising `SyncEngineError`
- All three call sites in `sync_engine.py` pass `teacher_uid` through to `attempt_heal()`
- `selector_broken` dashboard message updated to "Aeries page changed and auto-repair failed — developer notified"
- `google-generativeai>=0.8.0,<1.0.0` added to `requirements.txt`
- `worker.py` warns on missing `GEMINI_API_KEY` at startup without exiting (healing is optional)
- `Dockerfile` explicitly copies `selectors.json` (not matched by `*.py` glob)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire attempt_heal into find_element_with_fallback** - `ab4963c` (feat)
2. **Task 2: Add google-generativeai dep, GEMINI_API_KEY warning, selectors.json copy** - `6a17a1e` (chore)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `railway-worker/sync_engine.py` - `find_element_with_fallback()` extended with healing integration; all call sites updated; error message updated
- `railway-worker/worker.py` - GEMINI_API_KEY checked at startup with WARNING (non-fatal)
- `railway-worker/requirements.txt` - `google-generativeai>=0.8.0,<1.0.0` added
- `railway-worker/Dockerfile` - `COPY selectors.json .` added after `COPY *.py .`

## Decisions Made
- **Lazy import:** `from healer import attempt_heal` placed inside `find_element_with_fallback()` body rather than at module top. Avoids circular import issues since `healer.py` imports from `firestore_client.py` which is also imported by `sync_engine.py`.
- **Sentinel index:** When healing succeeds, `strategy_index = len(strategies)` is returned. This is a valid signal value (one past the last static index) that callers can inspect if needed without breaking existing logic.
- **GEMINI_API_KEY non-fatal:** Missing API key is a warning, not an exit condition. The `healer.py` `attempt_heal()` already returns `None` gracefully; the worker-level warning just makes the missing key visible at startup rather than only when a heal is first attempted.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
Set `GEMINI_API_KEY` in Railway Variables panel to enable LLM self-healing. Without it, the worker starts normally and logs a warning — selector failures will not be auto-repaired but syncs will otherwise continue.

## Next Phase Readiness
- Phase 8 (Self-Healing) is now complete. All building blocks built (08-01) and integrated (08-02).
- The full healing pipeline: static fallback → Gemini Flash → Gemini Pro → SyncEngineError with updated user message.
- Remaining action before production use: push to GitHub and deploy to Railway (pending from Phase 7).
- One known concern: LLM self-healing prompt is not production-validated for Aeries DOM; plan one prompt-tuning iteration after first real heal attempt.

---
*Phase: 08-self-healing*
*Completed: 2026-03-24*
