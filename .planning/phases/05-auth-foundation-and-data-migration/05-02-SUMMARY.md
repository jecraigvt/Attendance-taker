---
phase: 05-auth-foundation-and-data-migration
plan: 02
subsystem: auth
tags: [firebase, cloud-functions, firestore, fernet, encryption, security-rules, aeries, custom-token]

# Dependency graph
requires:
  - phase: 05-01
    provides: "Firebase project initialized; hosting and .firebaserc in place"
provides:
  - "Cloud Function authenticateTeacher: validates Aeries creds, encrypts password with Fernet, issues Firebase custom auth token"
  - "Fernet encryption of Aeries passwords stored at teachers/{uid}/credentials/aeries"
  - "Firebase Auth user created per teacher using synthetic email ({username}@aeries.attendance.local)"
  - "Firestore security rules enforcing per-teacher data isolation"
  - "Credentials sub-collection locked to admin SDK only"
  - "Legacy artifact paths remain accessible during Phase 5 migration"
affects:
  - 05-03-kiosk-linkage
  - 06-migration
  - 07-cloud-sync

# Tech tracking
tech-stack:
  added:
    - firebase-functions v5 (Cloud Functions v2 HTTPS callable)
    - firebase-admin v12
    - fernet npm package (Fernet symmetric encryption, Node-compatible with Python cryptography.Fernet)
    - cheerio (ASP.NET form token extraction from Aeries HTML)
  patterns:
    - "Fernet encryption boundary: only Cloud Function holds plaintext password in memory; only encryptedPassword goes to Firestore"
    - "Synthetic email pattern: {aeriesUsername}@aeries.attendance.local for Firebase Auth records"
    - "Admin SDK bypasses Firestore security rules; credentials sub-collection protected by allow: if false for client SDK"
    - "Graceful degradation: if Aeries server unreachable, proceed and flag validated: false rather than blocking login"

key-files:
  created:
    - functions/index.js
    - functions/package.json
    - functions/.eslintrc.js
    - functions/package-lock.json
    - firestore.rules
  modified:
    - firebase.json

key-decisions:
  - "fernet npm package chosen for Node compatibility with Python cryptography.Fernet (Railway will decrypt in Phase 7)"
  - "Credentials stored as sub-document at teachers/{uid}/credentials/aeries (not top-level) for cleaner Firestore structure"
  - "Graceful degradation when Aeries is unreachable: store credentials with validated: false rather than rejecting login"
  - "Node 18 specified in package.json engines (Firebase Functions runtime)"
  - "Node built-in fetch used (Node 18+) — no node-fetch dependency needed"

patterns-established:
  - "Cloud Function is the ONLY component that handles plaintext passwords"
  - "FERNET_KEY read from process.env at call time (not module load) to allow test environment override"
  - "Custom auth token flow: client calls authenticateTeacher -> gets customToken -> calls signInWithCustomToken"

# Metrics
duration: 2min
completed: 2026-03-23
---

# Phase 5 Plan 02: Auth Infrastructure Summary

**Firebase Cloud Function authenticateTeacher: validates Aeries ASP.NET credentials, Fernet-encrypts the password (key from env only), stores encrypted creds in Firestore via admin SDK, and issues Firebase custom auth tokens for per-teacher multi-tenancy**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-23T21:27:00Z
- **Completed:** 2026-03-23T21:29:21Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Cloud Function `authenticateTeacher` handles first-time signup and password updates in a single flow
- Fernet encryption boundary enforced: the only place a plaintext Aeries password exists in memory is inside the Cloud Function; it is never written to Firestore, never returned to the client, never logged
- Firestore security rules isolate all teacher data under `teachers/{uid}/` with `request.auth.uid == uid`; credentials sub-collection locked to admin SDK only via `allow read/write: if false`

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Cloud Function for auth and credential encryption** - `8571db2` (feat)
2. **Task 2: Create Firestore security rules and update firebase.json** - `5a89459` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `functions/index.js` - HTTPS callable Cloud Function `authenticateTeacher` (Aeries validation, Fernet encryption, custom token)
- `functions/package.json` - Node 18 dependencies: firebase-admin, firebase-functions, fernet, cheerio
- `functions/.eslintrc.js` - ESLint config for Cloud Functions
- `functions/package-lock.json` - Locked dependency tree (npm install completed cleanly)
- `firestore.rules` - Per-teacher isolation rules with credentials sub-collection locked to admin SDK
- `firebase.json` - Added functions and firestore sections alongside existing hosting config

## Decisions Made

- **fernet npm package** chosen specifically because it produces tokens compatible with Python's `cryptography.Fernet` — Railway (Phase 7) can decrypt what this Cloud Function encrypted.
- **Graceful degradation on Aeries unreachable**: The Aeries login page is an ASP.NET WebForms page that could be unreachable or slow. Rather than blocking teacher login, the function proceeds with `validated: false` and sets a flag in Firestore. The cloud sync in Phase 7 will re-validate on first sync.
- **Credentials stored as sub-document** `teachers/{uid}/credentials/aeries` rather than top-level, keeping the Firestore structure consistent with future kiosk and config sub-collections.
- **Synthetic email** `{username}@aeries.attendance.local` — Aeries usernames are not real email addresses, but Firebase Auth requires email format. This domain is clearly internal and cannot receive real email.

## Deviations from Plan

None — plan executed exactly as written.

The plan mentioned `node-fetch` as an optional dependency. Node 24 (local dev) and Node 18 (Firebase runtime) both have native `fetch` built in, so `node-fetch` was not added as a dependency. This reduces the dependency footprint.

## Issues Encountered

None — npm install completed without errors (deprecation warnings only, not errors). Syntax check passed. Export verification confirmed `authenticateTeacher` is the sole export.

## User Setup Required

**External services require manual configuration before deploying or testing this function.**

### Firebase Authentication
- Location: Firebase Console -> Authentication -> Sign-in method -> Email/Password -> Enable
- Why: The Cloud Function creates Firebase Auth users with email/password; the provider must be enabled

### Firebase Blaze Plan
- Location: Firebase Console -> Upgrade (bottom left)
- Why: Cloud Functions require the Blaze (pay-as-you-go) plan

### Fernet Key
- Generate: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Set for Cloud Functions: `firebase functions:secrets:set FERNET_KEY` (paste generated key)
- Why: The Cloud Function reads `process.env.FERNET_KEY` — without this, credential encryption will fail
- Store the same key in Railway env vars for Phase 7 (cloud sync needs to decrypt)

### Deploying
- Files are ready but NOT deployed. To deploy when ready: `firebase deploy --only functions,firestore:rules`

## Next Phase Readiness

- Cloud Function is complete and ready to deploy; waiting for user to enable Firebase Auth and Blaze plan
- Firestore rules are complete and ready to deploy
- Phase 05-03 (kiosk linkage) can proceed — it depends on the `teachers/{uid}/` Firestore path structure established here
- Phase 06 (migration) can proceed — the `teachers/{uid}/` document structure is defined

Blockers:
- FERNET_KEY must be set in Firebase Functions environment before first deployment
- Firebase Auth Email/Password provider must be enabled in console
- Blaze plan required for Cloud Functions deployment

---
*Phase: 05-auth-foundation-and-data-migration*
*Completed: 2026-03-23*
