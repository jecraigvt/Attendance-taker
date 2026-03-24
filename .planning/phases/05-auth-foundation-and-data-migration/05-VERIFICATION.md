---
phase: 05-auth-foundation-and-data-migration
verified: 2026-03-24T04:32:00Z
status: gaps_found
score: 4/5 must-haves verified
gaps:
  - truth: Kiosk links to specific teacher UID after first login; subsequent sign-ins go to that teacher path
    status: partial
    reason: teacherUid persists in localStorage and teacherPath() is used for all Firestore writes, but Firebase Auth token is NOT restored on page reload. Online writes fail with permission-denied once the custom token expires (~1 hour), because Firestore rules require request.auth.uid == uid.
    artifacts:
      - path: attendance v 2.5.html
        issue: Lines 776-798 load kiosk binding without calling signInWithCustomToken(). Comment at line 784 explicitly acknowledges this gap.
    missing:
      - Re-authenticate with Firebase Auth on page load when a kiosk binding exists
      - OR update Firestore rules to allow unauthenticated kiosk writes based on a kiosk binding document
      - The offline persistence cache masks this bug in short sessions but fails in online use after token expiry
human_verification:
  - test: Teacher sees only their own data, not another teacher data
    expected: After signing in as Teacher A, no Teacher B roster or attendance data is visible
    why_human: Cannot verify cross-tenant isolation without two live Firebase Auth accounts and actual rule evaluation in production
  - test: Student sign-in writes to correct tenant path after page reload
    expected: After page reload using localStorage binding, student sign-in writes to teachers/{uid}/attendance/... successfully
    why_human: Auth token expiry gap requires a timed real-world test
  - test: Aeries credentials are encrypted at rest in Firestore
    expected: Firebase Console teachers/{uid}/credentials/aeries encryptedPassword starts with gAAAAA (Fernet format), not plaintext
    why_human: Requires live Firebase Console inspection with FERNET_KEY configured
---

# Phase 5: Auth Foundation and Data Migration - Verification Report

**Phase Goal:** Teachers have isolated accounts with their own data, the existing data is safely migrated, and kiosk sign-ins write to the correct tenant.

**Verified:** 2026-03-24T04:32:00Z
**Status:** gaps_found
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Teacher can sign in with Aeries username/password and see a teacher-specific view | VERIFIED | Login screen exists (lines 87-117). handleLogin() calls httpsCallable authenticateTeacher, signs in with custom token, shows kiosk or PIN setup. Playwright E2E verification recorded in SUMMARY. |
| 2 | Jeremy existing attendance data accessible after migration, kiosk accepts student sign-ins | VERIFIED | migrate-to-tenants.js (391 lines) copies from flat path to teachers/{uid}/. Idempotency implemented. SUMMARY: 5 roster docs + 1 config doc migrated. Old paths preserved. All kiosk writes use teacherPath(). |
| 3 | A second teacher data is invisible to the first teacher via Firestore security rules | VERIFIED (structurally) | firestore.rules line 11: request.auth.uid == uid enforces isolation. Credentials sub-collection has allow: if false override. Rules deployed per SUMMARY. Human verification needed for two-account runtime test. |
| 4 | Kiosk links to specific teacher UID; subsequent student sign-ins go to correct path | PARTIAL | teacherUid persists in localStorage. All 23 Firestore writes use teacherPath(). BUT on page reload, Firebase Auth session is NOT restored. Custom token expires in ~1 hour. Online writes fail with permission-denied after expiry. |
| 5 | Aeries credentials stored encrypted at rest, plaintext never written to Firestore | VERIFIED | functions/index.js: password goes to fernetEncrypt() before Firestore write (lines 265-285). HTML: password only sent to httpsCallable (line 947), never written client-side. FERNET_KEY from process.env only. |

**Score:** 4/5 truths verified (1 partial)

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| migrate-to-tenants.js | VERIFIED | 391 lines. Idempotency check, count verification table, batch writes, teacher profile at teachers/{uid}/profile/main. |
| package.json | VERIFIED | Contains firebase-admin dependency. |
| functions/index.js | VERIFIED | 354 lines. Exports authenticateTeacher via onCall. Aeries validation, Fernet encryption, custom token. FERNET_KEY from env only. |
| functions/package.json | VERIFIED | firebase-admin, firebase-functions, fernet, cheerio. Node 20 engine. |
| firestore.rules | VERIFIED | 54 lines. request.auth.uid == uid with recursive wildcard. Credentials locked. Legacy paths open. |
| firebase.json | VERIFIED | Contains functions and firestore sections alongside hosting. |
| attendance v 2.5.html | VERIFIED | 2284 lines. Login screen, PIN setup/entry, screen navigation, teacherPath() used 23 times, zero artifacts/ path references remain. |
| public/index.html | VERIFIED | 2284 lines. diff against source returns empty - files are identical. |
| attendance-sync/attendance_to_aeries.py | VERIFIED | get_all_teacher_uids(), per-teacher paths, legacy fallback to artifacts/ if no teachers collection found. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| attendance v 2.5.html | Cloud Function authenticateTeacher | httpsCallable | WIRED | Line 946: httpsCallable(functions, authenticateTeacher) called with username and password. |
| attendance v 2.5.html | teachers/{uid}/attendance | teacherPath() helper | WIRED | 23 teacherPath() usages covering all Firestore writes. Zero artifacts/ references remain. |
| attendance v 2.5.html | localStorage kiosk binding | saveKioskBinding and loadKioskBinding | WIRED | Both functions implemented and called at login and page init. |
| attendance v 2.5.html | Firebase Auth on reload | signInWithCustomToken | NOT WIRED | Called on first login (line 951). NOT called on page reload from stored binding (lines 776-798). This is the SC4 gap. |
| functions/index.js | Aeries login endpoint | HTTP POST | WIRED | fetchAeriesFormTokens() plus validateAeriesCredentials(). Graceful degradation if unreachable. |
| functions/index.js | teachers/{uid}/credentials/aeries | admin SDK write | WIRED | credentialsRef set with encryptedPassword. Plaintext password never persisted. |
| firestore.rules | teachers/{uid}/ | uid match | WIRED | Line 11: request.auth.uid == uid with recursive wildcard. Credentials at lines 20-23 overridden with allow: if false. |
| migrate-to-tenants.js | artifacts/{APP_ID}/public (source read) | firebase-admin | WIRED | SRC_ROOT constant used across all source reads. |
| migrate-to-tenants.js | teachers/{uid}/ (target write) | firebase-admin | WIRED | All writes target teachers/{uid}/... paths with even-segment fix applied. |
| attendance-sync/attendance_to_aeries.py | teachers/{uid}/attendance | firebase-admin read | WIRED | base_path = teachers/{teacher_uid}/attendance/{date_str}/periods/{period} |

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| Teacher signs in with Aeries username and password | SATISFIED | - |
| Jeremy existing data accessible after migration | SATISFIED | - |
| Second teacher data invisible to first teacher | SATISFIED structurally | Human verification needed for runtime confirmation |
| Kiosk links to teacher UID; student sign-ins go to correct path | PARTIAL | Auth token not restored on page reload |
| Aeries credentials encrypted at rest | SATISFIED | - |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| attendance v 2.5.html | 784 | Comment documents token expiry gap: re-auth happens on next login | Warning | SC4 partial gap - acknowledged but not resolved |
| attendance v 2.5.html | 789-795 | Local mode sets teacherUid=local and teacherPin=0000 | Info | Deliberate offline fallback. No security issue since db is null. |

No blocking stubs, empty handlers, or critical TODO comments found in key paths.

### Human Verification Required

#### 1. Cross-Tenant Isolation in Production

**Test:** Sign in as Jeremy. In a separate incognito window, create a second test teacher account. Attempt to access the first teacher data from the second account.
**Expected:** Firestore returns permission-denied for any cross-tenant read.
**Why human:** Requires two live Firebase Auth accounts and real Firestore rule evaluation in production.

#### 2. Kiosk Persistence After Token Expiry

**Test:** Log in as a teacher, verify kiosk works. Wait 1+ hours (or clear Firebase Auth session via browser devtools -> Application -> Clear storage). Enter a student ID.
**Expected:** Either sign-in succeeds (app handles re-auth) OR fails with a clear prompt to re-login, not a silent failure.
**Why human:** Auth token expiry gap requires a timed real-world test. Current code does NOT handle token expiry after page reload.

#### 3. Encrypted Credentials in Firestore

**Test:** After logging in, open Firebase Console -> Firestore -> teachers -> {your-uid} -> credentials -> aeries. Inspect the encryptedPassword field.
**Expected:** Field value starts with gAAAAA (Fernet token format), not a recognizable password string.
**Why human:** Requires live Firebase Console access with FERNET_KEY configured and a real login having occurred.

### Gaps Summary

One structural gap was found affecting Success Criterion 4:

**Auth token not restored on kiosk reload.** When the kiosk loads from a stored binding in localStorage (the common case after initial setup), the code correctly restores teacherUid/teacherName/teacherPin but does NOT call signInWithCustomToken() to restore the Firebase Auth session. Firestore security rules require request.auth.uid == uid, so any online write to teachers/{uid}/attendance/... will fail with permission-denied once the custom token expires (~1 hour after the initial login).

The app comment at line 784 documents this: the custom token is short-lived and re-auth happens on next login. The Firestore offline persistence cache buffers writes locally but online writes fail silently after token expiry. This was not caught in Playwright testing because tests ran within the token validity window.

**Mitigation options for Phase 6 planning:**
- On page load with a stored binding, call the Cloud Function to obtain a fresh custom token and re-authenticate with signInWithCustomToken before showing kiosk mode
- Use anonymous Firebase Auth as kiosk fallback with a Firestore rule allowing anonymous writes to the bound teacher attendance path
- Require teacher to re-login once per day (acceptable for classroom use but writes silently drop between logins in the current implementation)

---

_Verified: 2026-03-24T04:32:00Z_
_Verifier: Claude (gsd-verifier)_
