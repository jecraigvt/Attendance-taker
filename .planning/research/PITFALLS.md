# Pitfalls Research

**Domain:** Multi-tenant school attendance SaaS — adding auth, cloud automation, and LLM self-healing to an existing single-teacher app
**Researched:** 2026-03-23
**Confidence:** MEDIUM-HIGH — critical pitfalls verified against official Firebase docs, Playwright Docker docs, and multiple community sources; LLM self-healing section is MEDIUM (newer pattern, less established guidance)

---

## Critical Pitfalls

### Pitfall 1: Existing Firebase Data Becomes Inaccessible After Restructuring for Multi-Tenancy

**What goes wrong:**
The current Firestore path is `artifacts/attendance-taker-56916/public/...` — a flat single-tenant structure with no teacher namespace. When multi-tenancy is added, if the path structure is changed to `users/{teacherUid}/...` or similar, all existing attendance records, rosters, and exceptions become unreachable by the new code. Jeremy's existing records from daily use are silently orphaned. The app appears to work (no errors) but shows empty data.

**Why it happens:**
Developers treat the data migration as an afterthought. They build the new multi-tenant structure first, confirm it works with fresh data, then realize the old data never got migrated. Because Firestore doesn't enforce schema, reading from the wrong path returns an empty result — not an error.

**How to avoid:**
1. Write a one-time migration script before changing any application code. Run it, verify it, then flip the code.
2. Keep the old path readable for a transition window — read from both old and new, write only to new.
3. Confirm migration with a record count check: old path record count should equal new path record count before decommissioning old paths.

**Warning signs:**
- App loads with no data after auth is added
- No error messages, just empty attendance lists
- "Works for new signups but not for existing teacher"

**Phase to address:** Multi-tenancy data migration phase — must be the first step, before any auth code is written

---

### Pitfall 2: Firestore Security Rules Don't Actually Isolate Tenants

**What goes wrong:**
A teacher can read another teacher's student attendance records. This is the most common multi-tenant Firestore failure mode. Rules are written to check `request.auth != null` (user is logged in) without checking that the logged-in user owns the document being read. Any authenticated teacher can query any other teacher's data by constructing the right path.

**Why it happens:**
Firebase doesn't automatically enforce tenant isolation — the developer must explicitly encode it in Security Rules. The failure is silent: the app works perfectly, all data returns correctly, and there is no error. The bug is only discovered via audit or if a teacher accidentally sees another class's attendance.

**How to avoid:**
- Every Firestore path containing teacher data must include the teacher's UID in the path: `users/{teacherUid}/rosters/...`
- Security Rules must check `request.auth.uid == teacherUid` at the collection level, not just that auth exists
- Example rule pattern:
  ```
  match /users/{teacherUid}/{document=**} {
    allow read, write: if request.auth.uid == teacherUid;
  }
  ```
- Never trust client-supplied tenant identifiers — use `request.auth.uid` from the token, not a field in the document

**Warning signs:**
- Security rules check `request.auth != null` but don't check UID equality
- Document paths don't include a teacher UID segment
- App passes all functional tests but no tenant isolation test was written

**Phase to address:** Auth + data model design phase — security rules must be written and tested before any production teacher is onboarded

---

### Pitfall 3: Playwright Crashes in Docker Due to Shared Memory Limits

**What goes wrong:**
Playwright on Railway works in local testing, fails silently in production. The Docker container's default `/dev/shm` (shared memory) is 64MB. Chromium uses shared memory heavily for its render pipeline. When it fills up, the browser crashes without a clear error — the Playwright process may remain "running" as a zombie while all automation silently fails. Attendance never syncs, but no alert fires.

**Why it happens:**
The current sync script runs on Windows where `/dev/shm` doesn't apply. When the identical code is containerized for Railway, the Docker default is 64MB — far too small for Chromium. This is a container-specific requirement that doesn't surface during local development.

**How to avoid:**
- Use the official Playwright Docker image: `mcr.microsoft.com/playwright:v1.XX.0-jammy` — it includes all required dependencies
- Add `--disable-dev-shm-usage` to Chromium launch args to use `/tmp` instead of `/dev/shm`
- Add `--no-sandbox` only if running as root in container (Railway default); document why it's necessary
- Full required args: `['--disable-dev-shm-usage', '--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']`
- Set `--shm-size=1gb` in the Railway service's Docker run config if using custom image
- Match Docker image version exactly to installed Playwright version — version mismatch causes "browser executable not found" with no helpful error

**Warning signs:**
- Browser starts, navigates one page, then goes silent
- No error in Python logs but also no sync completion log
- Works locally, fails on Railway
- Log shows "Target page, context or browser has been closed" (already seen in existing `sync_errors_2025-12.log`)

**Phase to address:** Cloud infrastructure phase — must be validated with a live Railway deployment before adding multi-teacher logic

---

### Pitfall 4: One Teacher's Playwright Crash Kills All Other Teachers' Syncs

**What goes wrong:**
When N teachers' sync jobs run concurrently in a single container process, an unhandled exception in one teacher's Playwright session (Aeries timeout, bad selector, network error) causes the entire process to crash. All other in-progress syncs are killed. Teachers whose attendance was mid-sync get partial or no data in Aeries. This is worse than single-tenant failure because the blast radius grows with every teacher added.

**Why it happens:**
The current code runs synchronously and is designed for one teacher. When wrapped in a loop to handle multiple teachers, a bare exception in the upload layer (already documented in CONCERNS.md) propagates to the orchestrator and terminates the process.

**How to avoid:**
- Run each teacher's sync job in a fully isolated subprocess or async task with its own error boundary
- Use a task queue (e.g., Railway cron + Redis/queue, or simply separate Railway services per teacher) rather than a loop in one process
- Implement per-teacher sync state tracking — each teacher has an independent "last synced", "in progress", "failed" status
- Circuit breaker pattern: if one teacher's Aeries credentials fail 3× in a row, mark that teacher's job as suspended and stop retrying until they re-authenticate

**Warning signs:**
- Sync loop processes teachers sequentially without try/except around each teacher's block
- A single unhandled Playwright exception in any teacher's block terminates the main process
- No per-teacher error isolation in the job runner

**Phase to address:** Cloud sync architecture phase — job isolation design must be decided before writing multi-teacher orchestration code

---

### Pitfall 5: Aeries Credentials Stored Weakly in Firestore Are a School Security Incident Waiting to Happen

**What goes wrong:**
Teacher Aeries passwords, stored plaintext or with weak encryption in Firestore, are exposed if: Firestore security rules have any misconfiguration, a Firebase project is misconfigured (happens more often than expected), or a developer accidentally logs a document's contents. A leaked Aeries password is a direct breach of a school district's student information system — this triggers mandatory notification requirements and potentially ends the project.

**Why it happens:**
"Encrypted" often means base64-encoded (which is not encryption) or AES with a hardcoded key in the application source code (which provides minimal protection). Developers underestimate that the encryption key's storage is where the real security lives — not the encrypted value.

**How to avoid:**
- Never store the encryption key in Firestore, environment variables readable by the client, or source code
- Use Google Cloud Secret Manager (accessible from Railway) or Firebase App Check with server-side key management
- Recommended pattern: Credentials are encrypted server-side using a key stored in Secret Manager that is never accessible to client-side code. The Firestore document holds only the ciphertext.
- Add a Firestore Security Rule that prevents client-side reads of the credential document entirely — only the Railway sync server (via service account) should read these
- Consider whether Firestore is even the right store: Railway environment variables set per-teacher at onboarding time avoids storing credentials in a database at all (simpler threat model for small scale)

**Warning signs:**
- Encryption key is in the HTML file, a Firestore document, or a client-accessible path
- Security rule for the credentials collection allows `request.auth != null` instead of service-account-only access
- The credential document is readable in Firebase Console without special permissions

**Phase to address:** Credential storage design — must be finalized in a dedicated security design step before any teacher onboarding UI is built

---

### Pitfall 6: Adding Auth Breaks the Existing Kiosk Sign-In Flow

**What goes wrong:**
The student kiosk currently uses Firebase anonymous auth. When Firebase Auth is added for teachers, the anonymous auth changes or the security rules are updated, and suddenly the kiosk tablets stop recording attendance. Students sign in, the UI confirms it, but nothing writes to Firestore because the anonymous auth token no longer has write permission.

**Why it happens:**
Firestore security rules are updated to require `request.auth.uid == teacherUid`, which correctly blocks cross-tenant access — but also breaks anonymous kiosk access which has a different UID than the teacher. Developers test the teacher dashboard and forget to regression-test the kiosk sign-in path.

**How to avoid:**
- Keep anonymous auth explicitly enabled in Firebase project settings (it's a separate toggle from Google auth)
- Write Security Rules that handle both auth types: teacher-scoped writes use `request.auth.uid == teacherUid`, kiosk writes use a separate path scoped by a kiosk token or by anonymous auth
- Explicitly regression-test kiosk sign-in after every security rules change
- Consider a separate Firestore collection path for kiosk writes so rules don't interact: `kiosk/{teacherCode}/signins/` with anonymous write, `users/{teacherUid}/` with authenticated read-only

**Warning signs:**
- Security rules are deployed and tested only via the teacher dashboard
- Kiosk devices are not in the test plan for the auth migration
- Anonymous auth is disabled in Firebase Console "since we're adding real auth now"

**Phase to address:** Auth migration phase — kiosk sign-in must be in the acceptance criteria

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store Aeries password as base64 in Firestore | Fast to implement, no extra services | Not encrypted; any Firebase rule gap exposes plaintext passwords | Never — use real encryption with external key |
| Single Railway service running all teachers' syncs in one process | Cheaper (one container) | One teacher's Aeries failure kills all other syncs | Only at 1 teacher (current) |
| Hardcode teacher UID in migration script | Gets existing data moved quickly | Script breaks for second teacher; encourages copy-paste multi-tenant bugs | OK for one-time migration of Jeremy's data, must be parameterized after |
| Skip Firestore Security Rules during development | Faster iteration | Any authenticated user can read any teacher's data; easy to ship to production this way | Development only, never on the hosted domain |
| LLM selector repair without a human approval step | Fully automated | LLM can generate a plausible-looking but wrong selector; attendance gets silently wrong | Only acceptable with a validation step (dry-run, confirmation log, or diff display) |
| Use Railway free/hobby tier for the sync server | $0-5/month | Memory limit may OOM-kill Playwright processes; no SLA for a daily-use school tool | Fine for testing, must evaluate memory before first external teacher onboards |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Firebase Auth + Firestore Security Rules | Deploying rules that only check `request.auth != null` — any teacher reads any other teacher's data | Rules must check `request.auth.uid == teacherUid` at every collection that contains teacher-specific data |
| Playwright in Docker (Railway) | Using default Docker image without Playwright-specific args; browser crashes silently on `/dev/shm` exhaustion | Use official Playwright image; add `--disable-dev-shm-usage` to Chromium launch args |
| Gemini API for selector repair | Sending raw HTML to Gemini without constraining the response format; model returns prose explanation instead of a usable selector | Use structured output (JSON mode) with a strict schema: `{"selector": "...", "confidence": "...", "reasoning": "..."}` |
| Aeries (multi-teacher) | Using a shared Playwright browser context across teachers; one teacher's session bleeds into another's, causing cross-teacher attendance updates | Each teacher sync must use a completely separate browser context with its own cookies/session |
| Firebase Admin SDK on Railway | Using a service account JSON file committed to the repo or baked into the Docker image | Store service account JSON as a Railway environment variable (base64-encoded); decode at runtime |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Sequential teacher sync (teacher 1 → teacher 2 → ...) in a tight schedule | Sync for teacher 7 starts after the window closes; some teachers get no sync for a period | Parallelize teacher syncs or stagger schedules; implement async job dispatch | ~5 teachers with 10 periods each, using 20-minute windows |
| One Playwright browser per sync run (not pooled) | Memory spikes at every 20-minute interval; Railway OOM kills process after ~3 concurrent teachers | Browser pool with max concurrency limit (semaphore); recycle contexts, not full browsers | 3-4 concurrent teachers on Railway Hobby tier (~512MB-1GB) |
| Firebase reads for all teachers on every sync interval | Firestore read costs grow linearly with teacher count; slow query time | Only fetch data for teachers whose sync window is active; use server timestamps to query only changed records | ~20 teachers generating noticeable Firestore read costs |
| LLM API call on every selector failure without caching | Gemini API latency (1-3s) adds to each sync; cost grows with instability | Cache repaired selectors per site version; only call LLM when cached selector fails | Every sync with >1 broken selector; costs and latency accumulate |
| Screenshot stored in container filesystem | Screenshots lost on Railway redeploy; no audit trail | Write screenshots to Firebase Storage (already configured) not local disk | First Railway redeploy |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing Aeries password with encryption key accessible to client JS | Any teacher's browser can decrypt any other teacher's Aeries password if rules fail | Encryption/decryption only on Railway server-side; key in Secret Manager, never in client code |
| Logging full Aeries credentials in Railway logs | Passwords appear in Railway's log UI, accessible to anyone with Railway project access | Explicitly redact AERIES_PASS from all log output; log "AERIES_USER=X, AERIES_PASS=[redacted]" |
| Firebase service account with full Firestore access used as the sync credential | Compromise of service account gives attacker full read/write to all teachers' data | Use least-privilege service account scoped to only the collections the sync needs |
| Student attendance records cross-visible between teachers | FERPA violation — teacher A can see teacher B's students' attendance status | Tenant isolation enforced at both Security Rules level AND application query level (defense in depth) |
| Gemini API key stored in client-accessible config | Anyone who views page source can make Gemini API calls billed to the project | Gemini API calls must be server-side only (Railway), never from browser JavaScript |
| No rate limiting on LLM self-healing | A broken Aeries update could trigger 100s of Gemini calls in a failure loop, generating large API bills | Add a per-teacher, per-day cap on Gemini calls (e.g., max 10 LLM calls/teacher/day); alert if cap is hit |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing "Sync successful" when sync ran but Aeries rejected some students | Teacher trusts the sync; students are marked absent in Aeries incorrectly | Show per-period status with student-level failures highlighted; never report success unless all students were updated |
| No notification when LLM self-healing fires | Teacher doesn't know selectors broke and were auto-repaired; no way to verify repair was correct | Log self-healing events to teacher dashboard with "repaired selector for [element]" notification and a way to force-verify |
| Requiring Aeries credentials during onboarding without explaining why | Teachers refuse to enter their SIS password into an unfamiliar app | Explain exactly what credentials are used for, how they're stored, and that the developer cannot see them |
| Auth gate on the kiosk sign-in screen | Students cannot sign in until a teacher is logged in; breaks autonomous kiosk operation | Kiosk sign-in must remain unauthenticated (anonymous auth) — auth gate is only for the teacher dashboard |
| Sync status visible only in Railway logs | Teachers have no visibility into whether their attendance is syncing | Teacher dashboard must show: last sync time, records synced, any failures — without requiring access to Railway |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Multi-tenancy:** Teacher login works and data saves — verify that Teacher A cannot read Teacher B's data by testing cross-tenant reads directly
- [ ] **Data migration:** Existing records appear in new structure — verify record count matches between old path and new path before decommissioning old path
- [ ] **Credential storage:** Encryption is implemented — verify the encryption key is NOT in Firestore, NOT in client JS, and NOT in the repository
- [ ] **Playwright on Railway:** Container deploys and runs — verify it successfully completes a full Aeries sync (not just starts) under Railway memory limits
- [ ] **Self-healing automation:** LLM returns a selector — verify the returned selector actually locates the correct element before applying it to a live Aeries session
- [ ] **Kiosk sign-in:** Teacher dashboard works after auth migration — verify kiosk anonymous sign-in still writes to Firestore on a tablet
- [ ] **Concurrent teacher syncs:** Two teachers sync at the same time — verify their Aeries sessions are completely isolated (no cross-contamination of student records)
- [ ] **Error isolation:** One teacher's Aeries credentials are wrong — verify other teachers' syncs complete normally and are not affected

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Existing data orphaned by path restructure | HIGH | Write reverse-migration script to copy data from new path back to old; restore from Firebase daily backup if available |
| Cross-tenant data visible (security rules gap) | HIGH | Immediately lock down rules; audit Firestore access logs for unauthorized reads; notify affected teachers |
| Playwright OOM kills Railway process | LOW | Add `--disable-dev-shm-usage` flag; redeploy; syncs resume at next scheduled window |
| LLM returns wrong selector, updates wrong Aeries field | MEDIUM | Roll back to last known-good selector config; add human approval gate for LLM repairs; affected teachers must manually verify Aeries records for that day |
| Kiosk sign-in broken by security rules update | MEDIUM | Revert Security Rules to previous version (Firebase Console has version history); kiosk catches up via next sync window |
| Aeries credentials decryptable from client | CRITICAL | Rotate all teachers' Aeries passwords immediately; re-encrypt with server-side key; audit for any unauthorized Aeries access |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Existing data orphaned | Data migration phase (first, before auth code) | Record count comparison: old path vs new path |
| Tenant isolation failure in Firestore rules | Auth + data model design phase | Write a cross-tenant read test; it must return permission-denied |
| Playwright crashes in Docker | Cloud infrastructure phase | Full Aeries sync completes on Railway deployment, not just locally |
| One teacher's crash kills all | Cloud sync architecture phase | Kill one teacher's sync mid-run; verify others complete |
| Aeries credentials exposed | Credential storage design phase | Security review: encryption key unreachable from client |
| Kiosk broken by auth migration | Auth migration phase | Kiosk sign-in is in acceptance criteria, not an afterthought |
| LLM returns wrong selector | Self-healing phase | Dry-run mode: LLM suggests selector, human confirms before first live use |
| Screenshot audit trail lost on redeploy | Cloud infrastructure phase | Verify screenshots persist to Firebase Storage after container restart |

---

## Sources

- Firebase Security Rules documentation: https://firebase.google.com/docs/firestore/security/rules-structure
- Firebase Anonymous Authentication: https://firebase.google.com/docs/auth/web/anonymous-auth
- Multi-tenancy with Firebase (KTree guide): https://ktree.com/blog/implementing-multi-tenancy-with-firebase-a-step-by-step-guide.html
- Firestore multi-tenancy community discussion: https://groups.google.com/g/firebase-talk/c/yMCfM5jmU4g
- Playwright Docker official docs: https://playwright.dev/docs/docker
- Railway + Playwright worker timeouts issue: https://station.railway.com/questions/worker-timeouts-and-playwright-browser-e-d6499ade
- Playwright memory production experience ("8GB Was a Lie"): https://medium.com/@onurmaciit/8gb-was-a-lie-playwright-in-production-c2bdbe4429d6
- Playwright MCP memory optimization 2025: https://markaicode.com/playwright-mcp-memory-leak-fixes-2025/
- Self-healing LLM test automation (BrowserStack): https://www.browserstack.com/guide/modern-test-automation-with-ai-and-playwright
- LLM self-healing pitfalls (Bug0 Playwright agents): https://bug0.com/blog/playwright-test-agents
- Tenant isolation architecture (Security Boulevard): https://securityboulevard.com/2025/12/tenant-isolation-in-multi-tenant-systems-architecture-identity-and-security/
- FERPA compliance for EdTech 2025: https://www.hireplicity.com/blog/ferpa-compliance-checklist-2025
- Project codebase concerns: `.planning/codebase/CONCERNS.md` (existing issues with selector brittleness, bare exceptions, global Firebase state)
- Existing sync error logs: `attendance-sync/sync_errors_2025-12.log` (browser context closed errors, selector timeouts — directly informs Docker failure modes)

---
*Pitfalls research for: multi-tenant attendance SaaS — adding auth, cloud Playwright, and LLM self-healing*
*Researched: 2026-03-23*
