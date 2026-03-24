# Phase 8: Self-Healing LLM Layer - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

When Aeries UI changes break selectors, the system automatically uses Gemini to find replacement selectors — reducing developer intervention to zero for common selector failures. Escalation chain: static fallbacks → Gemini Flash → Gemini Pro. Healed selectors stored in config file, healing events logged.

</domain>

<decisions>
## Implementation Decisions

### Healing trigger & flow
- Per-selector healing — each selector heals independently when its fallbacks fail (not full-page batch)
- Re-heal each time — if a healed selector breaks again later, try Gemini again with fresh page context (no permanent failure state)
- Use existing selector logic as the template/baseline — current selectors work well, Gemini builds from that foundation

### Claude's Discretion: Healing flow details
- Selector priority order after healing (healed-first vs originals-first)
- Behavior when both Flash and Pro fail (skip student vs abort teacher sync — may depend on which selector broke)
- Healing timing (inline during sync vs async for next cycle)

### Selector validation
- Claude's discretion on validation approach (live test, sanity check, or combination)
- Claude's discretion on DOM context preparation for Gemini (raw HTML vs simplified)
- Claude's discretion on healed selector expiry policy

### Dashboard visibility
- Successful heals are SILENT to teachers — no dashboard indication, just logged
- Failed heals show specific message to teacher: "Aeries page changed and auto-repair failed — developer notified"
- Healing events written to a GLOBAL Firestore collection (not per-teacher) for developer review
- No push notifications — Firestore log only, Jeremy checks when he wants

### Cost & guardrails
- Daily cap of 25 Gemini calls across all teachers
- After cap is hit, selectors just fail normally (no healing attempts)
- Claude's discretion on cap-reached behavior (log to Firestore, teacher notification, etc.)
- Claude's discretion on Gemini API key management (consistent with existing infrastructure patterns)

</decisions>

<specifics>
## Specific Ideas

- "The current selector works pretty well so definitely use that as a template and go from there" — existing selector fallback logic is the proven baseline, Gemini augments it rather than replacing it
- Error category `selector_broken` from Phase 7 is the natural trigger point for self-healing

</specifics>

<deferred>
## Deferred Ideas

- **Sync feature gate** — Aeries sync should be OFF by default for all teachers. Only Jeremy (or teachers he explicitly enables) should have sync running. Teachers without sync enabled shouldn't see sync-related UI on their dashboard. Jeremy wants to use it himself first, tell select teachers, and only open it up after admin approval. This is a sync-system-wide gate, not Phase 8 specific — could be a small addition before or alongside Phase 8.

</deferred>

---

*Phase: 08-self-healing*
*Context gathered: 2026-03-24*
