# Attendance Taker

Classroom attendance sign-in system with automated Aeries sync.

Students scan their ID at a kiosk tablet. Teachers manage everything from a dashboard. Attendance syncs to Aeries automatically every 30 minutes via a cloud worker.

## Architecture

```
public/index.html     - Kiosk sign-in + Teacher dashboard (Firebase Hosting)
functions/index.js    - Cloud Functions: authenticateTeacher, fetchRoster
railway-worker/       - Sync worker: Playwright uploads attendance to Aeries
firestore.rules       - Firestore security rules
```

## Setup

### Prerequisites

- Node.js 20+
- Python 3.11+
- Firebase CLI (`npm i -g firebase-tools`)
- Railway CLI (`npm i -g @railway/cli`)

### Firebase

```bash
firebase login
firebase use attendance-taker-56916

# Deploy hosting (frontend)
firebase deploy --only hosting

# Deploy functions
cd functions && npm install && cd ..
firebase deploy --only functions

# Deploy Firestore rules
firebase deploy --only firestore:rules
```

### Firebase Secrets (already set)

```bash
# Fernet encryption key for teacher credentials
firebase functions:secrets:set FERNET_KEY
```

### Railway (sync worker)

The sync worker runs in a Docker container on Railway. It uses Playwright to automate Aeries attendance uploads.

```bash
cd railway-worker

# Required environment variables (set in Railway dashboard):
# FIREBASE_SERVICE_ACCOUNT  - Full JSON blob of Firebase service account key
# FERNET_KEY                - Same Fernet key used by Cloud Functions
#
# Optional:
# GEMINI_API_KEY            - Enables self-healing when Aeries UI changes
```

Railway auto-deploys from the `railway-worker/` directory using the Dockerfile.

## Dashboard Tabs

| Tab | Purpose |
|-----|---------|
| **Attendance** | Period selector, absent list, group assignments, CSV export |
| **Roster** | Fetch from Aeries or upload CSV, manage student names |
| **Seating** | Configure groups, seats, per-period overrides, exceptions |
| **Apps** | Timer, Seating Chart, Name Picker, QR Code, Group Maker |
| **Settings** | Update Aeries password, change kiosk PIN, account info |
| **Sync** | Enable/disable Aeries sync, view sync status (hidden by default - type "sync" on dashboard to reveal) |

## Sync Feature Gate

Aeries attendance sync is **off by default** for all teachers. To enable:

1. Teacher types "sync" on their keyboard while on the dashboard
2. The hidden Sync tab appears
3. Toggle sync on

Or set `syncEnabled: true` in Firestore at `teachers/{uid}/config/main`.

The Railway worker skips teachers without `syncEnabled: true`. Roster fetching is unaffected.

## Self-Healing

When Aeries UI changes break selectors, the system automatically tries to repair them using Gemini Flash (with Pro fallback). Requires `GEMINI_API_KEY` in Railway env vars.

- Selectors are externalized to `railway-worker/selectors.json`
- Daily cap: 25 Gemini calls
- Healing events logged to Firestore `healing_events` collection
- Silent to teachers on success; shows error on failure
