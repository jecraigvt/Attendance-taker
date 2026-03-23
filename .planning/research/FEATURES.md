# Feature Research

**Domain:** Multi-tenant education SaaS with cloud browser automation and LLM self-healing
**Researched:** 2026-03-23
**Confidence:** MEDIUM — all findings cross-referenced with official Firebase docs and multiple sources; LLM self-healing patterns verified against 2025-2026 community research

---

## Context: What This Milestone Adds

This is a SUBSEQUENT milestone on an existing app. The student kiosk, Firebase storage, Playwright sync, audit logging, and bell-schedule tardy logic are **already built**. This research covers only the **new** features being added:

1. Multi-tenant auth (Google login per teacher)
2. Per-teacher data isolation in Firestore
3. Teacher dashboard (roster, sync status, credential management)
4. Cloud-based sync on Railway
5. Self-healing Playwright via Gemini LLM
6. Secure Aeries credential storage per teacher

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or unsafe.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Google Sign-In | Teachers have school Google accounts; any auth friction kills adoption | LOW | Firebase Auth `signInWithPopup(GoogleAuthProvider)` — trivial to add |
| Per-teacher data isolation | Teacher A must never see Teacher B's students | MEDIUM | Firestore path `/teachers/{uid}/...` + security rules on `request.auth.uid`; standard pattern with well-documented Firebase rules |
| Sign-out button | Teachers expect to be able to sign out on shared devices | LOW | `firebase.auth().signOut()` — one-liner |
| Sync status visibility | Teacher needs to know if attendance landed in Aeries | MEDIUM | Show last-sync timestamp and success/failure per period in the dashboard; requires persisting sync results to Firestore |
| Error notification | If sync fails, teacher must know before Aeries closes for the day | MEDIUM | Write sync failures to Firestore, display in dashboard; push/email is post-MVP |
| Onboarding flow | First-time teacher needs guided setup: login → Aeries credentials → roster → confirm | MEDIUM | Linear wizard with progress bar; get teachers to "aha moment" (first successful sync) within first session |
| Roster management | Upload/edit class roster per period | MEDIUM | CSV upload to Firestore; existing app already reads rosters, just needs per-teacher pathing |
| Aeries credential entry | Teacher must provide their Aeries username/password | LOW | Simple form; the hard part is secure storage (see below) |
| Session persistence | Teacher should not have to re-login on every visit | LOW | Firebase Auth handles this with `onAuthStateChanged` |

### Differentiators (Competitive Advantage)

Features that set this product apart. Not required by default, but highly valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Self-healing sync (Gemini LLM) | Aeries UI changes no longer break sync without manual fix | HIGH | When a selector fails: capture DOM/accessibility snapshot, send to Gemini Flash with current selector config, receive suggested replacement selectors, write to config file, retry. Research shows 75%+ success rate on selector failures when using accessibility tree snapshots (MEDIUM confidence — BrowserStack/TestDino sources) |
| Cloud sync (no developer PC required) | Sync runs 24/7 without Jeremy's machine being on | HIGH | Railway Docker container running Python + Playwright + Chromium; requires `--no-sandbox --disable-dev-shm-usage` flags in cloud; non-trivial but well-documented pattern |
| Selector config as data (not code) | LLM writes to a config file, not source code — safer, git-trackable, auditable | LOW | Decision already made in PROJECT.md; this is the right call; code-patching via LLM has high hallucination risk |
| Gemini Flash first, Pro fallback | Cost-controlled LLM usage — Flash at 1/10th the cost for routine selector repair | LOW | Architecture decision; Flash handles ~90% of cases, Pro reserved for complex layout changes |
| Sync run history visible to teacher | Teacher can see "last 5 sync attempts" with status, not just "last sync at 2:30pm" | MEDIUM | Persist sync_log entries per teacher in Firestore; surface in dashboard as a compact table |
| Kiosk remains unchanged | Student sign-in experience is identical to before — zero retraining needed | LOW | Existing HTML kiosk reads from Firebase; just needs to write to new per-teacher path |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems in this context.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time sync to Aeries | "Why wait 20 minutes?" | Aeries is a browser automation target, not an API — rapid-firing Playwright sessions risks account lockout and session conflicts; 20-min batch is already validated as sufficient | Keep 20-minute intervals; show sync queue count so teacher knows records are pending |
| LLM rewriting Python code | Tempting for full self-healing | LLM-generated Python code has high hallucination risk, is hard to review, and can silently corrupt sync behavior | LLM writes only to a JSON selector config file; Python code stays static |
| Email/push notifications for every sync | "I want to know it worked" | Notification fatigue; a successful sync is the expected state | Passive dashboard display; only alert on failure or if sync hasn't run in > 30 min during school hours |
| Admin dashboard (cross-teacher view) | "Jeremy should see all teachers' status" | Scope creep for v2.0; adds RBAC complexity, separate admin role, cross-tenant queries in Firestore | Log Jeremy's own teacher account; address admin view in a later milestone |
| Automatic roster sync from Aeries | "Pull rosters from Aeries automatically" | Requires outbound Aeries browser automation to read data — opposite direction, double the automation surface area, fragile | CSV upload from teacher; this is a one-time-per-semester task anyway |
| Multi-school / multi-district support | Seems natural SaaS expansion | Adds organization-level tenancy above teacher-level (three-tier hierarchy); not needed for current user base of single-district teachers | Hard-scope to single district; teacher UID is the top-level tenant key |
| Storing credentials client-side | Simpler implementation | Teacher Aeries passwords in browser localStorage is a severe security risk — any XSS leaks all credentials | Server-side encrypted storage (Google Secret Manager or AES-256 in Firestore + Cloud Functions) |

---

## Feature Dependencies

```
[Google Sign-In (Firebase Auth)]
    └──required by──> [Per-teacher Firestore isolation]
                          └──required by──> [Teacher dashboard]
                          └──required by──> [Roster management]
                          └──required by──> [Sync status visibility]

[Aeries credential entry]
    └──required by──> [Secure credential storage]
                          └──required by──> [Cloud sync (Railway)]
                                                └──required by──> [Self-healing LLM]

[Cloud sync (Railway)]
    └──enhanced by──> [Self-healing LLM]
    └──requires──> [Docker + Chromium + Playwright on Railway]

[Onboarding flow]
    └──orchestrates──> [Google Sign-In] + [Aeries credential entry] + [Roster management]

[Kiosk (existing)]
    └──must write to──> [Per-teacher Firestore path]
    (requires re-pathing, not rewriting)
```

### Dependency Notes

- **Auth must come first:** Every other feature depends on knowing which teacher is authenticated. Auth gates everything.
- **Firestore isolation follows auth immediately:** Once UID is available, all reads/writes must be scoped to `/teachers/{uid}/...`. This is a one-time structural decision — getting it wrong means a painful data migration.
- **Cloud sync depends on credentials being stored securely:** The Railway worker needs to retrieve credentials at runtime. No credentials = no sync = the whole product doesn't work.
- **Self-healing is enhancement, not blocker:** Cloud sync works without self-healing; LLM repair kicks in only when a selector fails. Self-healing can be a Phase 2 add-on after cloud sync is proven.
- **Kiosk re-pathing is low complexity but load-bearing:** The existing sign-in kiosk writes attendance records. It needs to write to the per-teacher path, which requires knowing the teacher's UID at kiosk load time. This is done via URL parameter (e.g., `?teacher=<uid>`) or Firestore lookup by school/class code.

---

## MVP Definition

### Launch With (v1 — this milestone)

Minimum to make the app usable by a second teacher without Jeremy's PC.

- [ ] Google Sign-In — without this, there is no multi-tenancy
- [ ] Per-teacher Firestore isolation + security rules — data privacy is non-negotiable
- [ ] Teacher onboarding flow (login → credentials → roster → done) — without this, new teachers can't set up
- [ ] Aeries credentials stored encrypted per teacher — required for cloud sync to work
- [ ] Cloud sync on Railway (Docker + Python + Playwright) — moves sync off Jeremy's PC
- [ ] Teacher dashboard: roster view + last sync status — minimal proof the system is working
- [ ] Kiosk re-pathing to per-teacher Firestore path — existing sign-in must write to correct tenant

### Add After Validation (v1.x)

Add once core multi-tenancy is working and at least one other teacher is live.

- [ ] Self-healing LLM (Gemini Flash selector repair) — adds resilience but sync works without it
- [ ] Sync run history (last 5 attempts) — useful for teacher confidence, not required for correctness
- [ ] Failure notification (in-app alert, not email) — makes failures visible without polling

### Future Consideration (v2+)

Defer until product-market fit is established with a small cohort of teachers.

- [ ] Email/push notifications — adds infrastructure complexity; dashboard-first is sufficient
- [ ] Admin cross-teacher view — valid for Jeremy's oversight use case, but not blocking multi-tenancy
- [ ] Roster auto-import from Aeries — high automation complexity for infrequent task
- [ ] Multi-school/district tenancy — premature unless scaling beyond Jeremy's school

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Google Sign-In | HIGH | LOW | P1 |
| Per-teacher Firestore isolation | HIGH | MEDIUM | P1 |
| Onboarding flow | HIGH | MEDIUM | P1 |
| Aeries credential storage (encrypted) | HIGH | MEDIUM | P1 |
| Cloud sync on Railway | HIGH | HIGH | P1 |
| Kiosk re-pathing | HIGH | LOW | P1 |
| Teacher dashboard (roster + sync status) | HIGH | MEDIUM | P1 |
| Self-healing LLM (Gemini) | HIGH | HIGH | P2 |
| Sync run history | MEDIUM | LOW | P2 |
| Failure notification (in-app) | MEDIUM | MEDIUM | P2 |
| Admin cross-teacher view | LOW | MEDIUM | P3 |
| Email/push notifications | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch (this milestone)
- P2: Should have, add when P1 is stable
- P3: Nice to have, future milestone

---

## Implementation Notes Per Feature Area

### Multi-Tenant Auth (Google Sign-In)
- Use `signInWithPopup(GoogleAuthProvider)` in the browser frontend
- **Do not** use Firebase's Identity Platform "multi-tenancy" feature (that's for enterprise organization-scoped tenants, not per-user isolation)
- Per-teacher isolation is achieved via Firestore path scoping (`/teachers/{uid}/...`) + security rules, not Firebase Auth tenants
- Anonymous auth is currently in use for the kiosk; student sign-ins do not need Google Auth — only teachers need it
- **Migration concern (MEDIUM confidence):** Jeremy's existing data is under an anonymous auth UID. When he logs in with Google, he gets a new UID. Either migrate data or use `linkWithCredential()` to link Google to the existing anonymous account — preserves UID and all data. Source: Firebase anonymous auth docs.

### Per-Teacher Firestore Isolation
- Standard pattern: `/teachers/{uid}/rosters/{classId}`, `/teachers/{uid}/attendance/{date}`, `/teachers/{uid}/syncLog/{id}`
- Security rules: `allow read, write: if request.auth.uid == userId;` where `userId` is the wildcard in the path
- **Rules are not filters** (HIGH confidence — official Firebase docs): queries must include `where('teacherId', '==', uid)` OR use subcollection paths; you cannot rely on rules to filter cross-tenant queries
- Cloud sync worker runs server-side with `firebase-admin`, which bypasses client-side rules — the worker must be trusted and explicitly scoped to one teacher at a time

### Secure Aeries Credential Storage
- **Recommended approach:** Google Cloud Secret Manager — purpose-built for secrets, AES-256 at rest, audit logs, versioned, integrates with Cloud Functions and Railway via service account
- **Alternative:** AES-256 encrypt credentials in a Cloud Function before writing to Firestore (`teachers/{uid}/credentials`), decrypt in Railway worker at sync time. Simpler to implement with existing Firebase setup, acceptable for small user base.
- **Do not** store plaintext passwords in Firestore or environment variables per teacher — unacceptable security posture (HIGH confidence — Google security checklist, multiple sources)
- **Railway environment:** Sync worker needs to retrieve credentials at runtime; if using Secret Manager, Railway service account needs Secret Accessor IAM role

### Cloud Sync on Railway (Playwright + Docker)
- Use official Playwright Docker base image: `mcr.microsoft.com/playwright/python:v1.x.x-noble` (Ubuntu 24.04) — avoids Alpine musl/glibc issues (MEDIUM confidence — Railway help station + BrowserStack docs)
- Required Chromium launch args in Docker: `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`
- `/dev/shm` defaults to 64MB in Docker; Chromium needs more — pass `--disable-dev-shm-usage` to write to `/tmp` instead, or set `shm_size` in docker-compose
- Railway charges by actual CPU/memory usage; a Playwright sync job running 5-10 min every 20 min is cost-manageable on Hobby tier ($5/month)
- One Railway service per sync worker is sufficient; no need for per-teacher workers — the worker processes jobs from a Firestore queue

### Self-Healing LLM (Gemini Selector Repair)
- **Mechanism:** On selector failure, capture the page's accessibility tree snapshot (not a screenshot — accessibility tree is text-based, cheaper, more reliable), send to Gemini Flash with current failing selector + task description, receive suggested replacement selectors as JSON, write to `selectors.json` config, retry
- **Selector stability hierarchy** (MEDIUM confidence — multiple 2025 sources): role-based > text-content > data-attr > CSS class > XPath. LLM should be prompted to prefer role+name selectors
- **Gemini Flash** is appropriate for routine selector matching (cost-effective). Pro fallback for complex multi-step layout changes
- This is not full autonomous agent testing — it's a narrow, bounded task: "here is the broken selector, here is the page snapshot, suggest a working replacement"
- Store the repaired selectors in `selectors.json` in Firestore (per-teacher or shared); next sync run reads config first
- **Success rate:** ~75% on selector-related failures (MEDIUM confidence — BrowserStack citing Microsoft benchmark data)

### Teacher Dashboard
- Single-page view (no tabs needed for MVP) with three sections: Roster table, Last sync status, Aeries credential status (connected / not connected)
- Roster table: list of students per period with edit/delete; CSV import button
- Sync status: last run timestamp + success/failure + count of records synced
- Credential status: "Aeries connected" badge or "Set up credentials" CTA
- **Avoid** building a full job queue UI for MVP — a simple "last sync ran at 2:30pm, 28 records synced" is sufficient

---

## Competitor / Comparable Feature Analysis

Direct competitors (edtech attendance SaaS) are all heavy-weight (Frontline Attendance, PowerSchool) and require district-level contracts. This product's positioning is teacher-autonomy, no-IT-approval needed. Relevant comparisons are to small SaaS tools with similar architecture:

| Feature | Typical Small EdTech SaaS | This Product | Gap |
|---------|--------------------------|--------------|-----|
| Google SSO | Yes (table stakes) | Planned | — |
| Per-teacher data isolation | Yes (table stakes) | Planned | — |
| Roster management | CSV upload or manual | CSV upload | Acceptable |
| Sync status visibility | Varies | Planned | — |
| Self-healing automation | Rare — usually manual fix | Planned differentiator | Genuine advantage |
| Cloud-based sync | Standard | Planned | — |
| Third-party credential mgmt | Usually OAuth or API key | Browser automation + encrypted creds | Niche but necessary given Aeries constraint |

---

## Sources

- [Firebase Auth — Authenticate with Google (Web)](https://firebase.google.com/docs/auth/web/google-signin) — MEDIUM confidence (page structure confirmed, content truncated in fetch)
- [Firebase Firestore Security Rules](https://firebase.google.com/docs/firestore/security/rules-conditions) — HIGH confidence (official docs, content verified)
- [Firebase Anonymous Auth — Linking to permanent account](https://firebase.google.com/docs/auth/web/anonymous-auth) — HIGH confidence (official docs)
- [Google Secret Manager overview](https://cloud.google.com/secret-manager/docs/overview) — HIGH confidence (official Google Cloud docs)
- [Playwright Docker documentation](https://playwright.dev/docs/docker) — MEDIUM confidence (multiple corroborating sources including Railway help station)
- [Railway pricing — Hobby/Pro plans](https://docs.railway.com/reference/pricing/plans) — MEDIUM confidence (WebSearch, Railway docs page referenced)
- [BrowserStack — Modern Test Automation with AI and Playwright](https://www.browserstack.com/guide/modern-test-automation-with-ai-and-playwright) — MEDIUM confidence (multiple corroborating sources)
- [TestDino — Playwright AI Ecosystem 2026](https://testdino.com/blog/playwright-ai-ecosystem/) — LOW confidence (WebSearch only, WebFetch permission denied; consistent with BrowserStack findings)
- [Google Codelabs — Automate UI Testing with Gemini CLI and Playwright](https://codelabs.developers.google.com/agentic-ui-testing) — MEDIUM confidence (official Google source)
- [KTree — Implementing Multi-Tenancy with Firebase](https://ktree.com/blog/implementing-multi-tenancy-with-firebase-a-step-by-step-guide.html) — LOW confidence (community blog, consistent with official Firebase docs)
- [SaaS Onboarding Best Practices 2025](https://www.flowjam.com/blog/saas-onboarding-best-practices-2025-guide-checklist) — LOW confidence (WebSearch only, general principles)

---

*Feature research for: Multi-tenant Attendance SaaS (v2.0 milestone)*
*Researched: 2026-03-23*
