# Project Research Summary

**Project:** Attendance Taker — Multi-Tenant SaaS (v2.0 milestone)
**Domain:** Cloud-sync attendance platform with multi-teacher auth, encrypted credential storage, and LLM self-healing browser automation
**Researched:** 2026-03-23
**Confidence:** MEDIUM-HIGH

## Executive Summary

This milestone transforms a single-teacher desktop tool into a multi-tenant cloud SaaS. The existing foundation (single HTML kiosk, Firebase Firestore, Playwright Python sync) is solid and well-validated — the work is purely additive. The recommended approach centers on four changes in strict dependency order: Google Sign-In and per-teacher Firestore path isolation (everything else depends on this), then a teacher credential management dashboard with server-side encrypted Aeries password storage, then migration of the Playwright sync service to a Railway Docker container with APScheduler, and finally an LLM self-healing layer via Gemini Flash that activates only on selector failure. No new frontend framework, no new database — just Firebase Auth, one Dockerfile, and a new Python orchestrator.

The stack additions are minimal and all use well-documented patterns: Firebase JS SDK 12.11.0 for Google login, the `cryptography` Python package (Fernet) for credential encryption, `mcr.microsoft.com/playwright/python:v1.58.0-noble` as the Docker base image, and `google-genai==1.68.0` for LLM selector repair. Version pinning is critical — particularly the Playwright package version must match the Docker image version exactly or the container will silently fail to find browser executables.

The single biggest risk is a student attendance data gap during the auth migration. The existing Firestore path must be migrated to the per-teacher path structure before any auth code ships. The second most critical risk is a Firestore security rules misconfiguration that allows cross-tenant reads — a silent FERPA violation. Both risks have well-defined prevention strategies and must be addressed in Phase 1 before any other teacher is onboarded.

## Key Findings

### Recommended Stack

The project already has the right core stack. The v2.0 additions are surgical: Firebase JS SDK v12 (Google Sign-In, no new service), `firebase-admin==7.3.0` for server-side token verification on Railway, `cryptography==46.0.5` for Fernet encryption of Aeries credentials, `google-genai==1.68.0` for Gemini Flash/Pro LLM calls, and `playwright==1.58.0` pinned to match the official Docker base image. Railway Hobby plan ($5/month) is the minimum viable infrastructure — the free tier's 0.5 GB RAM is insufficient for Chromium.

**Core technologies:**
- Firebase JS SDK 12.11.0: Google Sign-In + Firestore — already integrated, trivial to extend with `firebase/auth`
- firebase-admin 7.3.0: Server-side UID verification in Railway container — already a dependency, just version-pin it
- cryptography 46.0.5 (Fernet): Aeries credential encryption at rest — AES-128-CBC + HMAC-SHA256, four-line implementation
- google-genai 1.68.0: Gemini Flash/Pro for self-healing selector repair — official SDK (replaces deprecated `google-generativeai`)
- `mcr.microsoft.com/playwright/python:v1.58.0-noble`: Docker base image — Ubuntu 24.04, Chromium pre-installed, Python included
- Railway Hobby plan: Cloud sync host — $5/month, 48 GB RAM limit, native cron scheduling at 5-minute minimum intervals

### Expected Features

Auth and data isolation are non-negotiable table stakes; self-healing is a genuine differentiator. The kiosk sign-in experience must remain unchanged for students.

**Must have (table stakes — P1 for launch):**
- Google Sign-In — school Google accounts already exist; any auth friction kills adoption
- Per-teacher Firestore isolation with security rules — privacy non-negotiable; silent FERPA risk if omitted
- Teacher onboarding flow (login → credentials → roster → done) — without this, second teacher cannot self-serve
- Aeries credentials stored encrypted per teacher — required for cloud sync to function
- Cloud sync on Railway (Docker + Playwright) — moves sync off Jeremy's PC; core value proposition
- Teacher dashboard: roster view + last sync status — minimal proof the system is working
- Kiosk re-pathing to per-teacher Firestore path — existing sign-in must write to correct tenant

**Should have (differentiators — P2 after validation):**
- Self-healing LLM via Gemini Flash — Aeries UI changes no longer require developer intervention; ~75% success rate on selector failures
- Sync run history (last 5 attempts) — teacher confidence without polling Railway logs
- In-app failure notification — visible failures without email infrastructure

**Defer (v2+):**
- Email/push notifications — dashboard-first is sufficient; adds infrastructure complexity
- Admin cross-teacher view — valid but not blocking multi-tenancy
- Roster auto-import from Aeries — high complexity for infrequent task
- Multi-school/district tenancy — not needed for current user base

### Architecture Approach

The architecture extends the existing system at four clean boundaries without touching the student kiosk UI or Aeries upload logic. A per-teacher Firestore path (`teachers/{uid}/...`) with UID-based security rules is the multi-tenancy foundation. The Railway container runs APScheduler to fire every 20 minutes on school days, loops over teachers sequentially (one browser at a time to stay within Railway's memory limits), decrypts credentials at runtime, and writes sync status back to Firestore for display in the teacher dashboard. Self-healing is a layer wrapped around `find_element_with_fallback()` — it only invokes Gemini when all static fallback selectors are exhausted, caches repaired selectors in Firestore, and validates any LLM-returned selector finds exactly one element before applying it.

**Major components:**
1. Firebase Auth (Google provider) — teacher identity; UID becomes the tenant key for all subsequent data isolation
2. Firestore per-teacher paths (`teachers/{uid}/...`) + security rules — data isolation enforced at database layer
3. Teacher dashboard (new sections in existing HTML file) — roster management, credential entry, sync status display
4. Railway Docker container (`cloud_sync.py` + APScheduler) — replaces Windows Task Scheduler; sequential per-teacher sync loop
5. `selector_healer.py` — LLM self-healing layer wrapping existing `find_element_with_fallback()`; Gemini Flash first, Pro fallback

### Critical Pitfalls

1. **Existing data orphaned during path restructure** — write and verify a migration script before changing any app code; compare record counts old-path vs new-path before decommissioning old paths. Silent failure: app loads empty, no errors.

2. **Firestore security rules don't actually isolate tenants** — rules must check `request.auth.uid == teacherUid` at every `teachers/{uid}/` path, not just `request.auth != null`. Test cross-tenant reads explicitly; this is a FERPA violation if missed.

3. **Playwright crashes silently in Docker due to 64 MB `/dev/shm` limit** — add `--disable-dev-shm-usage`, `--no-sandbox`, `--disable-setuid-sandbox`, `--disable-gpu` to Chromium launch args. Use official Playwright Docker image to avoid missing system dependencies.

4. **Auth migration breaks kiosk sign-in** — anonymous auth must remain enabled; security rules must handle both auth types. Kiosk sign-in must be in the acceptance criteria for the auth phase, not treated as an afterthought.

5. **Aeries credentials weakly stored** — encryption key must live only in Railway environment variables, never in Firestore, client JS, or the repository. Add a Firestore security rule blocking client-side reads of the credentials document entirely.

6. **One teacher's Playwright crash kills all other teachers' syncs** — wrap each teacher's sync block in a full try/except with per-teacher error logging; never let one unhandled exception propagate to the scheduler loop.

## Implications for Roadmap

Based on the research, the architecture's own dependency graph dictates the phase order. Every subsequent phase is blocked on the one before it.

### Phase 1: Auth Foundation and Data Migration

**Rationale:** Auth must come first — it establishes the UID that every other feature depends on. The data migration must happen before auth code ships to avoid silently orphaning Jeremy's existing data. This phase is load-bearing and irreversible; getting the path structure wrong requires a painful re-migration.

**Delivers:** Google Sign-In working in the HTML app; all Firestore reads/writes scoped to `teachers/{uid}/...`; security rules deployed and verified; Jeremy's existing data migrated to the new path; kiosk still writes attendance correctly.

**Addresses (from FEATURES.md):** Google Sign-In, per-teacher Firestore isolation, kiosk re-pathing.

**Avoids (from PITFALLS.md):** Pitfall 1 (orphaned data), Pitfall 2 (tenant isolation failure), Pitfall 6 (kiosk broken by auth migration).

**Research flag:** Standard patterns — Firebase Auth + Firestore security rules are extensively documented. No additional research needed.

### Phase 2: Teacher Dashboard and Credential Storage

**Rationale:** Once auth exists and the Firestore path structure is correct, the teacher can log in and configure their account. Credentials must be stored before the cloud sync can work — this phase is the prerequisite for Phase 3.

**Delivers:** Teacher onboarding flow (login → credentials → roster → done); Aeries username/password stored encrypted in Firestore; teacher dashboard showing roster and credential status; encryption key stored in Railway environment variables only.

**Addresses (from FEATURES.md):** Teacher onboarding flow, Aeries credential entry, roster management, teacher dashboard.

**Avoids (from PITFALLS.md):** Pitfall 5 (weak credential storage).

**Research flag:** Credential encryption boundary needs a clear decision: encrypt in Cloud Function (server-side, better key hygiene) vs. browser-side Web Crypto (simpler). ARCHITECTURE.md recommends server-side; this decision should be confirmed before implementation begins.

### Phase 3: Railway Cloud Sync

**Rationale:** Credentials now exist. The cloud sync is the core value proposition — it moves the sync off Jeremy's PC. This is the highest-complexity phase: Dockerfile, APScheduler, per-teacher loop, credential decryption at runtime, sync status writes.

**Delivers:** Docker container deployed on Railway running every 20 minutes on school days; per-teacher sync loop; sync results written back to Firestore for dashboard display; sequential processing (one browser at a time) to stay within Railway Hobby RAM limits.

**Addresses (from FEATURES.md):** Cloud sync on Railway, sync status visibility.

**Avoids (from PITFALLS.md):** Pitfall 3 (Playwright Docker `/dev/shm` crash), Pitfall 4 (one crash kills all syncs).

**Research flag:** Needs validation with a live Railway deployment early — Playwright in Docker has environment-specific failure modes that only surface in production (not local dev). Deploy a smoke-test container before writing multi-teacher logic.

### Phase 4: Self-Healing LLM Layer

**Rationale:** Cloud sync works without self-healing; this phase adds resilience after the core system is proven stable. Building it last means the healing layer wraps a working, validated sync — reducing the surface area of unknowns.

**Delivers:** `selector_healer.py` wrapping `find_element_with_fallback()`; Gemini Flash called only on static-selector exhaustion; healed selectors cached in Firestore; Gemini Pro fallback; self-healing events logged to teacher dashboard.

**Addresses (from FEATURES.md):** Self-healing LLM, sync run history, failure notification.

**Avoids (from PITFALLS.md):** LLM returning wrong selector (validate selector finds exactly one element before applying; dry-run mode on first heal); LLM API call rate limiting (per-teacher per-day cap).

**Research flag:** LLM self-healing is a newer pattern (MEDIUM confidence sources). A dry-run validation step is essential before any LLM-repaired selector touches a live Aeries session. Budget for one iteration of the prompt engineering.

### Phase Ordering Rationale

- Auth before everything: UID is the tenant key; without it, there is no multi-tenancy.
- Data migration inside Phase 1 (not a separate phase): Must be done before any auth code ships to avoid the "empty app" failure mode.
- Credentials before cloud sync: The Railway worker fetches credentials at runtime; if they don't exist, the container does nothing useful.
- Cloud sync before self-healing: Self-healing wraps a working sync. Building healing on top of a broken sync creates two debugging layers at once.
- Self-healing is enhancement, not MVP: Cloud sync works at 100% if Aeries UI never changes. Self-healing is insurance — add it after the product is proven.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Railway Cloud Sync):** Deploy a minimal Playwright Docker container to Railway as a smoke test before writing multi-teacher logic. Playwright in Docker has memory and browser-executable failure modes that don't surface locally.
- **Phase 4 (Self-Healing LLM):** Prototype the Gemini Flash prompt and validation loop against a real Aeries selector failure before designing the full caching/retry architecture. Self-healing source confidence is MEDIUM; real-world prompt engineering may differ from documented patterns.

Phases with standard patterns (skip additional research):
- **Phase 1 (Auth + Data Migration):** Firebase Auth + Firestore security rules are extensively documented. Migration script is a one-time data copy — no novel patterns.
- **Phase 2 (Dashboard + Credentials):** Fernet encryption is a four-line implementation. The only open decision (Cloud Function vs. browser-side encryption) should be resolved in planning, not researched further.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified via PyPI and official release notes as of 2026-03-23. Playwright/Docker version pinning requirement is well-documented. |
| Features | MEDIUM | Table stakes and architecture decisions are HIGH confidence (official Firebase docs). Self-healing success rate (~75%) is MEDIUM (BrowserStack citing Microsoft benchmark; not independently verified). |
| Architecture | HIGH for existing components; MEDIUM for new | Existing codebase inspected directly. New components (Railway container, self-healing layer) verified via official docs and multiple community sources. |
| Pitfalls | MEDIUM-HIGH | Critical pitfalls (data orphaning, tenant isolation, Docker shm, kiosk breakage, credential exposure) all verified against official Firebase/Playwright docs. LLM self-healing pitfalls are MEDIUM (newer pattern). |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Credential encryption boundary:** ARCHITECTURE.md recommends server-side encryption via Cloud Function for key hygiene. STACK.md recommends direct Firestore write + Fernet decryption on Railway. These are compatible but the encryption path (who holds the key, when it's applied) needs a single clear decision before Phase 2 implementation begins.
- **Kiosk-to-teacher UID linkage:** Three options identified (teacher logs in then switches to kiosk mode; URL parameter with UID; short room code mapping to UID). ARCHITECTURE.md recommends Option 1 (teacher login → kiosk mode). This should be confirmed in requirements before Phase 1 ships to avoid a re-implementation during Phase 2.
- **LLM selector repair prompt:** No production-validated prompt exists for this specific Aeries automation context. The ARCHITECTURE.md code snippet is a starting pattern but will require iteration against real Aeries DOM failures. Plan for a prompt-tuning iteration before Phase 4 is marked complete.
- **Data migration script:** Needs to be written and tested against Jeremy's actual Firestore path before any auth code ships. This is Phase 1's first deliverable, not a footnote.

## Sources

### Primary (HIGH confidence)
- Firebase JS SDK release notes (firebase.google.com) — v12.11.0 confirmed current stable
- firebase-admin PyPI — v7.3.0 confirmed current stable
- google-genai PyPI — v1.68.0 confirmed current stable; replaces deprecated `google-generativeai`
- cryptography PyPI — v46.0.5, released Feb 2026
- playwright PyPI — v1.58.0, released Jan 2026
- Microsoft Playwright Docker Hub — v1.58.0-noble, Ubuntu 24.04
- Firebase Security Rules docs (firebase.google.com) — `request.auth.uid == uid` pattern
- Firebase Auth Web docs (firebase.google.com) — `signInWithPopup`, `GoogleAuthProvider`
- Railway cron docs and pricing docs — 5-min minimum interval, Hobby tier RAM limits
- Existing codebase (`attendance-sync/*.py`, `attendance v 2.5.html`) — direct inspection

### Secondary (MEDIUM confidence)
- Playwright Docker docs (playwright.dev/docs/docker) — container-specific launch args
- Railway help station — Playwright worker timeout patterns
- Google Codelabs — Agentic UI testing with Gemini CLI and Playwright
- SanjayPG/playwright-autoheal-locators-demo (GitHub) — DOM snapshot → Gemini → healed selector pattern
- BrowserStack — Modern Test Automation with AI and Playwright — ~75% self-healing success rate
- Firebase Anonymous Auth linking docs — `linkWithCredential` upgrade path

### Tertiary (LOW confidence)
- TestDino — Playwright AI Ecosystem 2026 — consistent with BrowserStack findings; page inaccessible during research
- KTree — Implementing Multi-Tenancy with Firebase — community blog; consistent with official Firebase docs
- SaaS Onboarding Best Practices 2025 (flowjam.com) — general principles applied to onboarding flow design

---
*Research completed: 2026-03-23*
*Ready for roadmap: yes*
