# Architecture Research

**Domain:** Multi-tenant SaaS — Cloud-sync attendance platform with self-healing browser automation
**Researched:** 2026-03-23
**Confidence:** HIGH (existing codebase inspected directly) / MEDIUM (new components verified via official docs and WebSearch)

---

## Current Architecture (Baseline)

Before documenting the target, it is essential to understand what already exists, because this milestone extends — not replaces — the existing system.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  EXISTING (v1.0)                                                          │
│                                                                           │
│  Student signs in on tablet                                               │
│      ↓                                                                    │
│  Single HTML file (rollcall.it.com)                                       │
│      ↓ Firebase SDK (anonymous auth)                                      │
│  Firestore: artifacts/attendance-taker-56916/public/...                   │
│      ↓ (read by Python service-account)                                   │
│  Windows Task Scheduler → run_attendance.bat → run_attendance_sync.py     │
│      ↓                                                                    │
│  attendance_to_aeries.py  →  CSV  →  upload_to_aeries.py (Playwright)    │
│                                          ↓                                │
│                                      Aeries SIS                           │
└──────────────────────────────────────────────────────────────────────────┘
```

**What changes in this milestone:**
- Anonymous auth → Google sign-in per teacher
- Single global Firestore path → per-teacher isolated paths
- Local Windows Task Scheduler → cloud cron on Railway
- Local Python + Playwright → Docker container on Railway
- Hardcoded selectors with fallbacks → self-healing via Gemini LLM
- Hardcoded TEACHER_CODE in HTML → teacher dashboard with credential management

---

## Target Architecture (v2.0 Multi-Tenant)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  BROWSER LAYER (unchanged kiosk + new teacher dashboard)                         │
│                                                                                   │
│  ┌──────────────────────────────┐    ┌──────────────────────────────────────┐    │
│  │  Student Sign-In Kiosk       │    │  Teacher Dashboard (same HTML file)  │    │
│  │  (unchanged UI)              │    │  - Google login                      │    │
│  │  Anonymous sign-in still     │    │  - Roster upload                     │    │
│  │  works for students          │    │  - Aeries credential entry           │    │
│  └──────────┬───────────────────┘    │  - Sync status display               │    │
│             │                        └──────────────┬───────────────────────┘    │
│             │ writes attendance                      │ reads sync status          │
└─────────────┼──────────────────────────────────────-┼────────────────────────────┘
              │                                        │
              ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  FIREBASE LAYER                                                                   │
│                                                                                   │
│  Firebase Auth (Google provider)                                                  │
│                                                                                   │
│  Firestore:                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │  teachers/{uid}/                                                            │  │
│  │    ├── profile          (name, email, school)                               │  │
│  │    ├── credentials      (encrypted Aeries username + password)              │  │
│  │    ├── sync_status      (last run, last success, error count)               │  │
│  │    ├── rosters/periods/{period}  (class roster snapshots)                  │  │
│  │    ├── config           (bell schedule, exceptions, avoidPairs, frontRow)   │  │
│  │    └── attendance/{date}/periods/{period}/                                  │  │
│  │         ├── [doc]       (roster_snapshot)                                   │  │
│  │         └── students/{studentId}  (sign-in records)                         │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
│  Security Rules: request.auth.uid == uid on all teachers/{uid}/... paths          │
└─────────────────────┬───────────────────────────────────────────────────────────┘
                      │ (Firebase Admin SDK — service account)
                      │ reads teachers/{uid}/* for all teachers on schedule
                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  RAILWAY CLOUD SYNC SERVICE (Docker container)                                    │
│                                                                                   │
│  Image: mcr.microsoft.com/playwright/python:v1.x-noble                           │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐     │
│  │  Scheduler (APScheduler or cron)                                         │     │
│  │    Every 20 min, 08:00–15:45 school days                                 │     │
│  │              │                                                            │     │
│  │              ▼                                                            │     │
│  │  Orchestrator (per-teacher loop)                                          │     │
│  │    For each teacher with active credentials:                              │     │
│  │      1. fetch_attendance(teacher_uid) → attendance_to_aeries.py          │     │
│  │      2. decrypt_credentials(teacher_uid) → Aeries user/pass              │     │
│  │      3. upload_to_aeries(csv, user, pass) → upload_to_aeries.py          │     │
│  │      4. write sync_status → Firestore teachers/{uid}/sync_status         │     │
│  │              │                                                            │     │
│  │              ▼ (on selector failure)                                      │     │
│  │  Self-Healing Layer                                                       │     │
│  │    1. capture_dom_snapshot(page, failed_selector_key)                    │     │
│  │    2. call Gemini Flash API with (dom_snippet, context, failed_key)       │     │
│  │    3. parse returned CSS selector string                                  │     │
│  │    4. validate new selector finds element on page                         │     │
│  │    5. if valid → write to selector_overrides.json in Firestore           │     │
│  │    6. retry sync with new selector                                        │     │
│  │    7. if Gemini Flash fails → escalate to Gemini Pro, then alert          │     │
│  └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                   │
│  Secrets (Railway env vars):                                                      │
│  - FIREBASE_SERVICE_ACCOUNT_JSON (base64 encoded)                                │
│  - ENCRYPTION_KEY (AES key for credential decrypt)                               │
│  - GEMINI_API_KEY                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  AERIES SIS (external, push-only)                                                 │
│  https://adn.fjuhsd.org/Aeries.net/TeacherAttendance.aspx                        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

### Unchanged Components

| Component | Status | Notes |
|-----------|--------|-------|
| Student sign-in kiosk UI | Unchanged | Same HTML, Tailwind, Firebase SDK |
| Firebase Hosting (rollcall.it.com) | Unchanged | Single HTML file |
| Playwright automation logic | Extended | Wrapped with self-healing layer |
| CSV format / Aeries URL | Unchanged | No Aeries API access |
| Per-period settle logic (5th student + 15 min) | Unchanged | Working correctly |

### Modified Components

| Component | Change | Reason |
|-----------|--------|--------|
| Firebase Auth | Replace anonymous with Google sign-in | Per-teacher identity |
| Firestore paths | `artifacts/{APP_ID}/public/...` → `teachers/{uid}/...` | Multi-tenant isolation |
| `attendance_to_aeries.py` | Add `teacher_uid` parameter; read from new path | Per-teacher data fetch |
| `upload_to_aeries.py` | Accept decrypted credentials; delegate selector resolution to self-healing layer | Cloud credentials, self-healing |
| HTML app — admin panel | Replace hardcoded TEACHER_CODE with Firebase Auth; add dashboard sections | Real auth, per-teacher config |
| Firebase Security Rules | Add `request.auth.uid == uid` for `teachers/{uid}/...` | Enforce isolation |

### New Components

| Component | Where | Responsibility |
|-----------|-------|----------------|
| Google Sign-In flow | HTML app | Firebase Auth with `signInWithPopup(GoogleAuthProvider)` |
| Teacher dashboard | HTML app (new section in existing file) | Roster mgmt, sync status, credential entry |
| Credential encryption | Railway sync service | AES-256 encrypt/decrypt for Aeries passwords |
| Self-healing layer | Railway sync service (`selector_healer.py`) | LLM-based selector repair on failure |
| Selector override store | Firestore `config/selector_overrides` | Persist healed selectors across runs |
| Cloud sync orchestrator | Railway sync service (`cloud_sync.py`) | Loop over teachers, schedule, status writes |
| APScheduler / cron | Railway container entrypoint | Replace Windows Task Scheduler |
| Sync status writer | Railway sync service | Write last-run result to `teachers/{uid}/sync_status` |

---

## Recommended Architecture Patterns

### Pattern 1: Per-Teacher Firestore Path with Security Rules

**What:** Restructure all data under `teachers/{uid}/` instead of the current global path. Apply security rules that allow each teacher only to read/write their own subtree.

**When to use:** Always — this is the foundation of multi-tenancy.

**Trade-offs:**
- Pro: Security is enforced at the database layer, not just at the app layer
- Pro: Clean isolation; no risk of teacher A reading teacher B's data
- Con: Requires a data migration step for the existing teacher (one-time copy of existing data to new path)
- Con: Existing anonymous auth sessions must be replaced — cannot migrate in-place without a reset

**Implementation note:** The existing global path (`artifacts/{APP_ID}/public/...`) can remain as a fallback for kiosks that haven't updated, but all new writes go to `teachers/{uid}/...`. Security rules should lock down the new paths immediately.

```javascript
// Firebase Security Rules
match /teachers/{uid}/{document=**} {
  allow read, write: if request.auth != null && request.auth.uid == uid;
}
// Cloud sync server uses Admin SDK — bypasses security rules (correct for server-side)
```

### Pattern 2: Encrypted Credential Storage in Firestore

**What:** Teacher enters Aeries username/password in the dashboard. The HTML app encrypts the password using AES-256 (via a derived key) before writing to `teachers/{uid}/credentials`. The Railway sync service decrypts at runtime using an `ENCRYPTION_KEY` stored in Railway environment variables.

**When to use:** Any time third-party credentials are stored server-side.

**Trade-offs:**
- Pro: Credentials are never in plaintext in Firestore
- Pro: Even if Firestore is compromised, attacker needs the encryption key (stored only in Railway env vars)
- Con: Key rotation requires re-encrypting all stored credentials
- Con: If ENCRYPTION_KEY is lost, credentials are irrecoverable — teachers must re-enter
- Practical note: For a small number of teachers, this is acceptable. Implement with `cryptography` Python library (AES-256-GCM or Fernet).

**Encryption boundary:** Encryption happens on the Railway server side (not in the browser) when credentials are first verified. The HTML app sends credentials over HTTPS to a small Firebase Cloud Function (or directly via a protected Firestore write), and the function encrypts before persisting. This keeps the encryption key out of client-side JavaScript entirely.

**Alternative (simpler but less secure):** Encrypt in the browser using Web Crypto API. Eliminates need for Cloud Function but browser-held keys are less safe.

**Recommendation:** Encrypt on server side using a Cloud Function for key hygiene. If Cloud Functions are out of scope, browser-side Web Crypto with a strong key derivation function (PBKDF2) is acceptable for a small school district.

### Pattern 3: Self-Healing Selector Architecture

**What:** When `find_element_with_fallback()` exhausts all defined strategies for a given element, instead of failing the entire sync, the system pauses and invokes Gemini Flash with a minimal DOM snapshot and element description. Gemini returns a new CSS selector. The system validates the selector finds exactly one element on the current page, then stores it as an override in Firestore and retries the sync.

**When to use:** After all static fallback selectors have failed (not before — LLM adds latency and cost).

**Trade-offs:**
- Pro: Extends automation lifetime when Aeries UI changes without developer intervention
- Pro: Selector overrides persist in Firestore — subsequent syncs use the healed selector without re-calling Gemini
- Con: Gemini API adds 1-3 seconds latency per healed element; acceptable for batch sync
- Con: LLM hallucination risk — selector may look valid but match wrong element; requires validation step
- Con: Full page source is large — use minimal DOM snippet (just the relevant table or section) to reduce tokens

**DOM snapshot approach (verified pattern):**
Instead of sending the entire page source, extract only the relevant DOM section:
```python
# In selector_healer.py
def extract_dom_snippet(page, context_selector="table.attendance-grid"):
    """Extract minimal DOM around the target area to reduce LLM token usage."""
    return page.evaluate(f"""
        () => {{
            const el = document.querySelector('{context_selector}');
            return el ? el.outerHTML.slice(0, 8000) : document.body.innerHTML.slice(0, 8000);
        }}
    """)

def heal_selector(page, element_type, failed_selectors, context_description):
    """Call Gemini to find a new selector for a broken element."""
    dom_snippet = extract_dom_snippet(page)

    prompt = f"""
    I am automating a school attendance web application.
    I need to find this element: {context_description}

    These CSS selectors no longer work: {failed_selectors}

    Here is the relevant DOM:
    {dom_snippet}

    Return ONLY a single CSS selector string that uniquely identifies this element.
    No explanation, no markdown, just the selector.
    """

    response = gemini_flash.generate_content(prompt)
    new_selector = response.text.strip()

    # Validate before using
    if page.locator(new_selector).count() == 1:
        return new_selector
    return None  # Healing failed, escalate
```

**Selector override storage:**
```
Firestore: config/selector_overrides/{element_type} → { selector: "...", healed_at: timestamp }
```

### Pattern 4: Per-Teacher Sync Loop in Cloud Container

**What:** The Railway container runs a scheduler that fires every 20 minutes. On each tick, it fetches all teachers who have credentials configured, and runs the full sync pipeline for each in sequence.

**When to use:** This is the cloud-migration pattern for the existing local sync.

**Trade-offs:**
- Pro: Single container, simple deployment
- Pro: Sequential processing prevents concurrent Playwright sessions from fighting over memory
- Con: If one teacher's sync takes too long, it delays others — add per-teacher timeout
- Con: Railway Hobby plan has limited RAM; Playwright + Chromium uses ~300-500 MB per instance; sequential processing ensures only one browser is open at a time

**Scheduler approach:** APScheduler (`BlockingScheduler`) is the standard Python option for this pattern. Alternatively, use a simple `while True: sleep(20*60)` loop for simplicity. APScheduler is recommended for production — it handles missed fires and provides better logging.

```python
# cloud_sync.py (entrypoint)
from apscheduler.schedulers.blocking import BlockingScheduler
import pytz

def run_all_teachers():
    """Fetch all active teachers and sync each in sequence."""
    teachers = get_active_teachers_from_firestore()
    for teacher in teachers:
        try:
            sync_teacher(teacher['uid'])
        except Exception as e:
            log_sync_error(teacher['uid'], e)
            write_sync_status(teacher['uid'], error=str(e))

scheduler = BlockingScheduler(timezone=pytz.timezone('America/Los_Angeles'))
scheduler.add_job(run_all_teachers, 'cron',
                  day_of_week='mon-fri',
                  hour='8-15',
                  minute='0,20,40')
scheduler.start()
```

---

## Data Flow Changes

### Current Data Flow (v1.0)

```
Student sign-in
    ↓ write
artifacts/attendance-taker-56916/public/data/attendance/{date}/periods/{p}/students/{id}
    ↓ read (service account)
attendance_to_aeries.py → CSV → upload_to_aeries.py
    ↓ write
Aeries SIS
```

### New Data Flow (v2.0)

```
Student sign-in (anonymous auth, unchanged on kiosk side)
    ↓ write
teachers/{uid}/attendance/{date}/periods/{p}/students/{id}
    ↓ read (Admin SDK, per-teacher loop)
attendance_to_aeries.py(uid) → CSV → decrypt_creds(uid) → upload_to_aeries.py
    ↓ on selector failure
selector_healer.py → Gemini Flash API → validate → store override
    ↓ retry
upload_to_aeries.py (with healed selector)
    ↓ write
Aeries SIS
    ↓ write status
teachers/{uid}/sync_status → { last_run, last_success, last_error, error_count }
    ↓ read
Teacher dashboard (HTML app) → displays sync status
```

### Auth Flow Change

```
Current:
  HTML app → signInAnonymously() → Firebase anonymous UID → access global path

New:
  Teacher:
    HTML app → signInWithPopup(GoogleAuthProvider) → Firebase UID (stable, per-account)
             → access teachers/{uid}/...

  Student (kiosk, unchanged):
    HTML app → signInAnonymously() → anonymous UID
             → write to teachers/{teacher_uid}/... (requires knowing teacher_uid)

    PROBLEM: Student kiosk needs to know the teacher UID.
    SOLUTION: Teacher configures a "kiosk code" or the kiosk URL includes the teacher UID.
              Simpler: Teacher pre-configures the kiosk by logging in as teacher,
              then switches to kiosk mode — the teacher UID is stored locally.
```

**Important:** The student-kiosk-to-teacher-path linkage is a critical design decision. Options:
1. Teacher logs in on kiosk tablet, sets "active teacher" cookie/localStorage, switches to kiosk mode.
2. URL parameter: `rollcall.it.com?uid=abc123` (simpler but UID is visible in URL).
3. Short room code: teacher generates a 4-digit room code that maps to their UID in Firestore.

**Recommendation:** Option 1 (teacher logs in, then switches to kiosk mode) — aligns with existing admin panel pattern where teacher enters teacher code. Now the teacher code becomes Google Sign-In → then clicks "Enter Kiosk Mode" in dashboard.

---

## Integration Points with Existing Components

### HTML App Integration Points

| Existing Feature | How It Integrates | Risk |
|------------------|-------------------|------|
| `signInAnonymously()` | Removed for teacher, kept for students | Must not break kiosk sign-in flow |
| `const TEACHER_CODE = "****"` | Replaced by Firebase Auth check | One-time change; test thoroughly |
| `artifacts/{APP_ID}/public/...` paths | Updated to `teachers/${uid}/...` | All Firestore doc refs need updating |
| `window.__app_id` | Repurposed or removed | No longer needed for path construction |
| Admin panel HTML | Extended with dashboard tabs | Additive change — low risk |
| Bell schedule config (Firebase) | Moves to `teachers/{uid}/config` | Read path changes |
| Roster upload | Writes to `teachers/{uid}/rosters/periods/` | Write path changes |

### Python Sync Integration Points

| Existing Function | How It Integrates | Change Required |
|-------------------|-------------------|-----------------|
| `export_attendance_to_csv(date_str)` | Accepts `teacher_uid` param; reads from `teachers/{uid}/attendance/...` | Add uid param, update path string |
| `upload_to_aeries(csv, username, password)` | Credentials now come from decrypted Firestore; self-healing wraps selector failures | Caller provides creds; healer wraps find_element_with_fallback |
| `SELECTOR_STRATEGIES` dict | Becomes starting point; Firestore overrides take precedence at runtime | Load overrides from Firestore before each sync run |
| `find_element_with_fallback()` | On all-strategies-exhausted, call `heal_selector()` instead of raising | Add healing callback parameter |
| `run_attendance_sync.py` | Replaced by `cloud_sync.py` (APScheduler, per-teacher loop) | New file; old orchestrator retired |
| `run_attendance.bat` | Retired — replaced by Railway container always-on | No changes needed |
| `FIREBASE_KEY_PATH` env var | Replaced by `FIREBASE_SERVICE_ACCOUNT_JSON` (base64 inline) | Better for Docker environments |

---

## Suggested Build Order (Dependencies)

The suggested order reflects what blocks what. Each phase must be complete before the next can be tested end-to-end.

```
Phase A: Firebase Auth + Data Migration
    - Add Google Sign-In to HTML app
    - Create teachers/{uid}/... path structure in Firestore
    - Update all Firestore write paths in HTML app
    - Update Security Rules
    - Write data migration script (copy existing teacher's data to new path)
    Blocks: Everything below — nothing works without the new path structure

Phase B: Teacher Dashboard
    - Add dashboard UI to HTML app (roster, sync status, credential entry)
    - Teacher configures Aeries credentials through UI
    - Credentials stored encrypted in Firestore
    Blocks: Cloud sync (needs credentials to exist before sync can run)

Phase C: Railway Cloud Sync
    - Dockerfile using mcr.microsoft.com/playwright/python
    - cloud_sync.py with APScheduler
    - Per-teacher orchestration loop
    - Credential decryption
    - Sync status writes back to Firestore
    Blocks: Self-healing (needs working sync before adding healing layer)

Phase D: Self-Healing Layer
    - selector_healer.py
    - Gemini Flash API integration
    - Selector override storage in Firestore
    - Fallback to Gemini Pro on Flash failure
    - Alert mechanism (sync_status error field visible in dashboard)
    Blocks: Nothing — this is the last layer
```

---

## Scalability Considerations

This is a small-school-district deployment. Scalability beyond ~50 teachers is not a design goal, but the architecture choices have implications even at small scale.

| Concern | At 1-5 teachers (current target) | At 10-50 teachers | Notes |
|---------|----------------------------------|-------------------|-------|
| Playwright memory | 1 browser at a time, ~400 MB — fine on Railway Hobby | Sequential still fine; 50 teachers × 2 min sync = 100 min, exceeds 20-min window | Add parallelism only if needed |
| Firestore reads | Trivial | Trivial | No concern at school scale |
| Gemini API calls | Rare (only on selector failure) | Rare | Flash is cheap ($0.075/1M tokens); not a cost concern |
| Railway container cost | Hobby plan (~$5/mo + usage) — always-on is ~$5-8/mo | Same | Acceptable for educational tool |
| Aeries portal rate limiting | Low risk — same teacher, different periods | Possible if many teachers hit portal simultaneously | Sequential processing mitigates this |

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Shared Firestore Path for Multiple Teachers

**What people do:** Keep the global `artifacts/{APP_ID}/public/...` path and add a teacher field to each document.

**Why it's wrong:** Security rules cannot isolate teachers from each other without per-document checks. Firestore subcollection security rules only apply to the exact path matched — all teachers would need read access to the shared root path to list documents. Also complicates queries significantly.

**Do this instead:** Per-teacher top-level path (`teachers/{uid}/...`) with uid-based security rules. Admin SDK bypasses rules for server-side access, so the sync service can still read all teachers.

### Anti-Pattern 2: Storing Encrypted Credentials in Client-Accessible Storage

**What people do:** Encrypt credentials in the browser using a key hardcoded in the JavaScript, store ciphertext in Firestore.

**Why it's wrong:** The encryption key is visible in the HTML source to anyone who opens DevTools. The encryption provides no real protection.

**Do this instead:** Encryption key lives only in Railway environment variables. Encryption/decryption runs server-side only. Browser sends credentials over HTTPS to a Cloud Function that encrypts before writing, or browser writes directly to a Firestore field that only the server reads.

### Anti-Pattern 3: Calling Gemini for Every Sync Attempt

**What people do:** Send page source to Gemini on every sync run to find elements dynamically.

**Why it's wrong:** Adds 1-3 seconds of LLM latency to every student's attendance record across every period. Costs multiply quickly. Gemini's output is non-deterministic — a selector that works today may not work tomorrow.

**Do this instead:** Use static selectors (existing `SELECTOR_STRATEGIES`) as the primary path. Call Gemini only when all static strategies fail. Cache healed selectors in Firestore so subsequent runs use the cached selector without calling Gemini again.

### Anti-Pattern 4: Running Multiple Playwright Browser Instances Concurrently in Railway

**What people do:** Process multiple teachers in parallel to speed up sync.

**Why it's wrong:** Playwright with Chromium uses ~300-500 MB RAM per browser instance. Railway Hobby plan provides ~0.5 GB. Two concurrent instances risk OOM crashes.

**Do this instead:** Sequential teacher processing. Monitor memory usage. If more than 5-10 teachers need syncing and the window becomes too tight, upgrade to Railway Pro (1 GB RAM, better CPU) before adding concurrency.

### Anti-Pattern 5: Migrating to a New Frontend Framework

**What people do:** Decide that "while we're refactoring," the single HTML file should become a React/Vue app.

**Why it's wrong:** The kiosk is in active use by students. A frontend rewrite risks introducing bugs in the student-facing sign-in flow. The existing HTML works; the new features (auth, dashboard) can be added within the existing file's structure.

**Do this instead:** Keep the single HTML file. Add new dashboard sections as additional `<div>` panels toggled by the auth state. The file will get larger, but it is already 78 KB and works well.

---

## Sources

- Existing codebase inspection: `attendance-sync/*.py`, `attendance v 2.5.html`, `.planning/codebase/ARCHITECTURE.md` (HIGH confidence — direct code read)
- Firebase Security Rules per-user isolation: [Firebase Docs — Security Rules and Auth](https://firebase.google.com/docs/rules/rules-and-auth) (HIGH confidence — official documentation)
- Firebase anonymous account upgrade / linkWithCredential: [Firebase Docs — Anonymous Auth](https://firebase.google.com/docs/auth/web/anonymous-auth), [Firebase Blog — Best Practices for Anonymous Authentication](https://firebase.blog/posts/2023/07/best-practices-for-anonymous-authentication/) (MEDIUM confidence — official docs verified)
- Playwright official Docker image (`mcr.microsoft.com/playwright/python`): [Playwright Python Docker Hub](https://hub.docker.com/r/microsoft/playwright-python) (HIGH confidence — official image registry)
- Railway pricing and Hobby plan resource limits: [Railway Pricing](https://railway.com/pricing), [Railway Docs — Pricing Plans](https://docs.railway.com/reference/pricing/plans) (MEDIUM confidence — verified via WebSearch, official docs partially fetched)
- Self-healing selector architecture (DOM snapshot → LLM → validate → cache): [BrowserStack — Modern Test Automation with AI and Playwright](https://www.browserstack.com/guide/modern-test-automation-with-ai-and-playwright), [LangChain + Playwright MCP self-healing agents](https://markaicode.com/langchain-playwright-self-healing-test-agents/) (MEDIUM confidence — multiple sources agree on pattern; not verified against official Gemini SDK docs)
- Gemini Flash latency and token pricing: [Gemini 2.5 Flash Preview docs](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-preview-09-2025) (MEDIUM confidence — WebSearch verified; exact pricing of Gemini 3.1 Flash Lite found at $0.25/1M input as of March 2026)

---

*Architecture research for: Multi-tenant attendance SaaS with cloud sync and self-healing automation*
*Researched: 2026-03-23*
