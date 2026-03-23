# Stack Research

**Domain:** Multi-tenant attendance SaaS with cloud browser automation
**Researched:** 2026-03-23
**Confidence:** HIGH (all versions verified via PyPI, official docs, Firebase release notes)

---

## Scope

This file covers only NEW stack additions for the v2.0 milestone. The existing
stack (single HTML file + Tailwind CDN, Firebase Firestore, Playwright Python,
firebase-admin) is validated and not re-researched here.

The five capability gaps being filled:

1. Firebase Auth (Google login + per-teacher data isolation)
2. Cloud Playwright deployment on Railway
3. Self-healing selectors via Gemini LLM
4. Encrypted credential storage
5. Teacher dashboard (sync status, credential management)

---

## Recommended Stack

### Core Technologies (New Additions)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Firebase JS SDK | 12.11.0 | Google sign-in, auth state, Firestore security rules | Current stable; project already uses Firebase modular SDK pattern. Auth is just another import from `firebase/auth`. No new service needed. |
| firebase-admin Python | 7.3.0 | Server-side auth token verification in Railway container | Must match client-side Firebase project. Used to verify teacher UIDs when the sync worker fetches per-teacher credentials. |
| google-genai Python | 1.68.0 | Gemini API calls for self-healing selector repair | Official Google SDK (replaces deprecated `google-generativeai`). Supports both Gemini 2.5 Flash and 2.5 Pro with same client. |
| playwright Python | 1.58.0 | Browser automation (already in use; version pinned for Docker) | Must match Docker image version exactly. Currently at 1.58.x in Docker. |
| cryptography Python | 46.0.5 | Fernet symmetric encryption for Aeries passwords at rest | Python standard for this. AES-128-CBC + HMAC-SHA256. Four-line implementation. Actively maintained (updated Feb 2026). |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | latest | Load `.env` in Railway container for secrets | Railway injects env vars natively; use dotenv only for local dev parity |
| requests (already stdlib-adjacent) | — | HTTP calls if any webhook/notification pattern added | Not needed for core sync; add only if status webhooks are added |

### Infrastructure

| Component | Technology | Why |
|-----------|------------|-----|
| Cloud sync host | Railway (existing account) | User already has account. Supports Docker, has native cron scheduling (min 5-min interval fits 20-min sync). Hobby plan ($5/mo) required — free tier (0.5 GB RAM) is insufficient for Playwright. |
| Container base image | `mcr.microsoft.com/playwright/python:v1.58.0-noble` | Official Microsoft image. Ubuntu 24.04, Chromium pre-installed, Python included. Must pin version to match `playwright==1.58.0` Python package. |
| Gemini model (primary) | `gemini-2.5-flash` | Cheapest capable model for DOM/selector analysis. Self-healing runs only on sync failure, so cost is negligible per call (~$0.02). |
| Gemini model (fallback) | `gemini-2.5-pro` | More capable reasoning when Flash cannot identify the correct selector. Same SDK, just swap model string. |
| Encryption key storage | Railway environment variable | Fernet key is a 44-char base64 string. Store as `FERNET_KEY` env var in Railway service settings. Never in Firestore. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Railway CLI (`railway`) | Deploy and manage Railway services locally | `npm install -g @railway/cli` or download binary. Used to set env vars and trigger deploys. |
| Firebase CLI (`firebase`) | Deploy Firestore security rules | Already in use for Firebase Hosting. Add `firestore:deploy` to workflow. |

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `playwright==1.58.0` | `mcr.microsoft.com/playwright/python:v1.58.0-noble` | Must match exactly. Mismatched versions cause "browser executable not found" at runtime. |
| `google-genai>=1.68.0` | Python >=3.10 | The Railway Docker image (Ubuntu 24.04 / Python 3.12) satisfies this. |
| `cryptography>=46.0.0` | Python >=3.8 | No conflicts with existing dependencies. |
| `firebase-admin==7.3.0` | Python >=3.9 | No change from existing requirement; just version-pin it. |
| Firebase JS SDK 12.11.0 | Firebase Hosting (existing) | Drop-in CDN URL update. The `firebase/auth` modular import pattern is unchanged from v10. |

---

## Installation

### Railway Docker container (Dockerfile additions)

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Browsers already installed in base image — do NOT run playwright install again
COPY . .

CMD ["python", "sync_worker.py"]
```

### requirements.txt (updated)

```
firebase-admin==7.3.0
playwright==1.58.0
google-genai==1.68.0
cryptography==46.0.5
python-dotenv>=1.0.0
```

### Firebase JS SDK (CDN update in HTML)

The existing project loads Firebase from CDN. Update the version string from 10.12.2 to 12.11.0, then add the auth import:

```html
<!-- Replace existing CDN imports with v12.11.0 -->
<script type="module">
  import { initializeApp } from 'https://www.gstatic.com/firebasejs/12.11.0/firebase-app.js';
  import { getAuth, signInWithPopup, GoogleAuthProvider, onAuthStateChanged }
    from 'https://www.gstatic.com/firebasejs/12.11.0/firebase-auth.js';
  import { getFirestore } from 'https://www.gstatic.com/firebasejs/12.11.0/firebase-firestore.js';
</script>
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `google-genai` (new SDK) | `google-generativeai` (old SDK) | Never for new code. `google-generativeai` is deprecated as of 2025. `google-genai` is the unified production SDK. |
| Fernet (`cryptography` package) | Google Cloud KMS / AWS Secrets Manager | Use KMS if the project scales to 100+ teachers or requires key rotation audit logs. For current scale (single school), Fernet + Railway env var is simpler and free. |
| Railway cron service | Separate cron-trigger service (supercronic) | Railway's built-in cron scheduling is sufficient. The 5-minute minimum interval is not a constraint (sync runs every 20 minutes). Use a separate cron container only if sub-5-minute sync is needed. |
| `mcr.microsoft.com/playwright/python` base image | Custom Dockerfile from `python:3.12-slim` + apt-get | Custom builds are fragile (missing system libs for Chromium). Use official image and add your packages on top. |
| Firebase Auth (Google provider) | Auth0, Supabase Auth, Clerk | Firebase Auth is free, already integrated in the project, and teachers already have school Google accounts. No reason to introduce a second auth service. |
| Firestore per-user path isolation (`/users/{uid}/...`) | Separate Firestore collections per tenant | Path isolation with security rules is the Firebase-recommended pattern for this scale. Separate projects would require separate Firebase credentials and add operational overhead. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `google-generativeai` (PyPI) | Deprecated as of 2025. Google's official docs now point exclusively to `google-genai`. | `google-genai==1.68.0` |
| Firebase JS SDK v10.12.2 (current in project) | Still functional, but v12 is current stable. The gap matters for `firebase/auth` feature completeness. Update before adding auth features. | Firebase JS SDK 12.11.0 |
| Railway free tier (0.5 GB RAM) | Playwright with Chromium requires ~300-500 MB just to launch. 0.5 GB will OOM during sync. | Railway Hobby plan ($5/month). The cron service costs compute only while running — real cost is low. |
| `playwright install` in Dockerfile when using official image | The official `mcr.microsoft.com/playwright/python` image already has browsers installed. Running `playwright install` again wastes 300 MB of build space and causes version conflicts. | Use the base image as-is; only install Python packages. |
| Storing the Fernet encryption key in Firestore | Key-in-database is circular — if Firestore is compromised, both encrypted data and the key are exposed. | Store Fernet key as Railway environment variable only. |
| Anonymous-to-Google upgrade flow | Firebase supports `linkWithCredential` to upgrade anonymous → Google, but it adds merge-conflict edge cases with existing data. Given existing data is single-teacher, a clean migration is simpler. | Migrate existing data to teacher's UID at first login. Do not use the anonymous upgrade flow. |

---

## Stack Patterns by Variant

**If Railway Hobby plan cost is a concern:**
- Use cron schedule mode (service exits after each sync run) rather than a long-running worker
- Railway charges only for active compute; cron service sleeping between runs costs nothing
- 20-minute sync interval = ~72 runs/day × ~60 seconds/run = ~72 minutes of compute/day

**If Gemini self-healing is too slow for sync loop:**
- Cache healed selectors to a JSON file committed to the repo (or Firestore document)
- Only call Gemini on first failure; subsequent syncs use cached selector
- This is the AutoHeal pattern: ~$0.02 per heal, not per sync run

**If Firebase SDK v12 CDN upgrade breaks existing kiosk behavior:**
- v10 → v12 is backward-compatible for Firestore and anonymous auth patterns in use
- The only breaking change relevant to this project: `firebase/vertexai` → `firebase/ai` (not used here)
- Test CDN update in isolation before adding auth features

---

## Firestore Data Isolation Pattern

This is the architectural choice that makes multi-tenancy work in Firestore. Document it here because it drives security rules and SDK usage:

```
/users/{uid}/profile          — teacher info, Aeries URL, encrypted_password
/users/{uid}/rosters/{id}     — class rosters
/users/{uid}/attendance/{id}  — attendance records
/users/{uid}/sync_status      — last sync time, last error
/users/{uid}/selector_cache   — healed Playwright selectors (shared benefit)
```

Security rule pattern (Firestore):
```
match /users/{uid}/{document=**} {
  allow read, write: if request.auth.uid == uid;
}
```

This rule means: a logged-in teacher can only read/write their own subtree. No per-document tenantId field needed. Google login UID is the tenant key.

---

## Sources

- Firebase JS SDK release notes (firebase.google.com/support/release-notes/js) — v12.11.0 confirmed current stable, March 19, 2026. HIGH confidence.
- firebase-admin PyPI (pypi.org/project/firebase-admin/) — v7.3.0 confirmed current stable, March 19, 2026. HIGH confidence.
- google-genai PyPI (pypi.org/project/google-genai/) — v1.68.0 confirmed current stable, March 18, 2026. HIGH confidence.
- Google Gen AI SDK docs (googleapis.github.io/python-genai/) — `from google import genai` import pattern, `client.models.generate_content()` API. HIGH confidence.
- Gemini API models page (ai.google.dev/gemini-api/docs/models) — `gemini-2.5-flash` and `gemini-2.5-pro` as current production model IDs. HIGH confidence.
- cryptography PyPI (pypi.org/project/cryptography/) — v46.0.5, released Feb 10, 2026. HIGH confidence.
- playwright PyPI (pypi.org/project/playwright/) — v1.58.0, released Jan 30, 2026. HIGH confidence.
- Microsoft Playwright Docker image (mcr.microsoft.com/en-us/product/playwright/python/about) — v1.58.0-noble, Ubuntu 24.04. HIGH confidence.
- Railway cron docs (docs.railway.com/reference/cron-jobs) — 5-minute minimum interval, UTC scheduling, service must exit after task. HIGH confidence.
- Railway pricing (docs.railway.com/pricing/plans) — Free tier: 0.5 GB RAM. Hobby: 48 GB, $5/month. HIGH confidence.
- Firebase Auth modular SDK docs (firebase.google.com/docs/auth/web/google-signin) — `signInWithPopup`, `GoogleAuthProvider`, `onAuthStateChanged` import paths. HIGH confidence.
- Firestore security rules (firebase.google.com/docs/firestore/security/rules-conditions) — `request.auth.uid` pattern for per-user isolation. HIGH confidence.
- SanjayPG/playwright-autoheal-locators-demo (github.com) — DOM + screenshot → Gemini → healed selector pattern. MEDIUM confidence (community project, verified pattern is consistent with official Playwright accessibility snapshot API).

---

*Stack research for: Multi-tenant attendance SaaS (v2.0 milestone)*
*Researched: 2026-03-23*
