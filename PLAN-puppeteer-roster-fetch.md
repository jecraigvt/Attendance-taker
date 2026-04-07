# Plan: Move All Aeries Interaction to the Cloud

## Problem

The app currently has two Aeries integrations, and both are broken or fragile:

1. **Roster fetching** (pull FROM Aeries) — Cloud Function uses `cheerio` HTTP
   scraping which fails because Aeries requires a real browser. Returns
   `roster_requires_browser` every time. **Completely broken.**

2. **Attendance sync** (push TO Aeries) — Runs locally on Jeremy's Windows PC via
   Python + Playwright + Task Scheduler. Works, but **requires his computer to be
   running.** The whole point of moving to the cloud is to eliminate this dependency.

## Goal

**All Aeries interaction runs in Cloud Functions with Puppeteer (headless Chrome).**
Jeremy's computer is no longer needed for anything. The local `attendance-sync/`
scripts become legacy.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Cloud Functions                        │
│                                                          │
│  fetchRoster (httpsCallable)                             │
│    ► Puppeteer → login to Aeries → scrape rosters       │
│    ► Write to Firestore teachers/{uid}/rosters/{period}  │
│    ► Triggered by: "Fetch from Aeries" button            │
│                                                          │
│  syncAttendance (scheduled)                              │
│    ► Read attendance from Firestore                      │
│    ► Puppeteer → login to Aeries → update attendance     │
│    ► Runs every 20 min during school hours (8am-3:45pm)  │
│    ► Logs results to Firestore for dashboard visibility  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Part 1: Roster Fetching (fetchRoster)

### What changes

**`functions/package.json`**
- Add `puppeteer` dependency
- Remove `cheerio` (only used by roster fetch)

**`functions/index.js`**
- Remove: `aeriesGet()`, `parseAeriesClassList()`, `parseAeriesRosterPage()`,
  `cheerio` require
- Add: `puppeteer` require
- Replace: Steps 4-6 of `fetchRoster` with Puppeteer browser automation
- Keep: Steps 1-3 (auth, credential decrypt), Step 7 (Firestore merge write),
  Step 8 (response format)

**Function config changes:**
- Memory: `1GiB` (Chromium needs ~512MB+)
- Timeout: keep `120s` (login + 5 roster pages ≈ 30-60s)

### Puppeteer flow (replacing cheerio scraping)

```
1. puppeteer.launch({ headless: true, args: ['--no-sandbox'] })
2. Navigate to https://adn.fjuhsd.org/Aeries.net/Login.aspx
3. Fill credentials (same selectors as upload_to_aeries.py)
4. Wait for redirect past login page
5. Navigate to class list page (try /Classes.aspx, fallbacks)
6. page.evaluate() → extract period/class links from rendered DOM
7. For each class link:
   a. Navigate to roster page
   b. Wait for student table
   c. page.evaluate() → extract StudentID, LastName, FirstName
8. browser.close()
9. Return data → existing Firestore merge write (unchanged)
```

### What stays the same
- Frontend: same `httpsCallable('fetchRoster')` call
- Response format: same `{ success, periods, message }`
- Firestore paths: same `teachers/{uid}/rosters/{period}`
- Merge logic: same preferred-name preservation
- `authenticateTeacher` function: untouched

---

## Part 2: Attendance Sync (new syncAttendance function)

This replaces the entire local `attendance-sync/` pipeline:
- `run_attendance_sync.py` (orchestrator + schedule)
- `attendance_to_aeries.py` (Firebase → CSV export)
- `upload_to_aeries.py` (Playwright → Aeries UI automation)
- `sync_utils.py` (retry, selectors, error tracking)
- Windows Task Scheduler

### New Cloud Function: `syncAttendance`

**Trigger:** Firebase Scheduled Function (Cloud Scheduler)
- Runs every 20 minutes: `*/20 8-15 * * 1-5` (Mon-Fri 8am-3:40pm)
- Plus a final run at 3:45pm

**Flow:**
```
1. Query Firestore for all teacher UIDs (teachers/ collection)
2. For each teacher:
   a. Read attendance data from Firestore
      (teachers/{uid}/attendance/{today}/periods/{p}/students/*)
   b. Read roster snapshot for comparison
   c. Apply settle logic (skip periods with <5 sign-ins or <15 min elapsed)
   d. Decrypt Aeries credentials from Firestore
   e. Launch Puppeteer, login to Aeries
   f. For each settled period:
      - Select period in dropdown
      - Click "All Remaining Students Are Present"
      - For each student: check/uncheck Absent/Tardy boxes
      - Save
   g. Close browser
   h. Write sync log to Firestore (teachers/{uid}/syncLogs/{timestamp})
3. Screenshots stored in Firebase Storage (for audit trail)
```

**Config:**
- Memory: `2GiB` (browser + multiple page navigations)
- Timeout: `540s` (9 minutes — processing multiple periods takes time)
- Region: `us-central1`

### Key logic ported from Python

| Python source | Cloud Function equivalent |
|---------------|--------------------------|
| `attendance_to_aeries.py` — Firebase read + CSV export | Direct Firestore reads (no CSV intermediate) |
| `upload_to_aeries.py` — Playwright login | Puppeteer login (same selectors) |
| `upload_to_aeries.py` — period switching | Puppeteer period dropdown selection |
| `upload_to_aeries.py` — checkbox logic | Puppeteer checkbox check/uncheck |
| `sync_utils.py` — SELECTOR_STRATEGIES | Same selector fallbacks in JS |
| `sync_utils.py` — retry_with_backoff | JS retry wrapper |
| `sync_utils.py` — SyncError | Custom error class |
| `run_attendance_sync.py` — schedule check | Cloud Scheduler cron expression |
| `run_attendance_sync.py` — settle logic | Same MIN_STUDENTS + elapsed time check |
| Local file logging | Firestore sync logs + Cloud Logging |
| Local screenshots | Firebase Storage screenshots |

### Sync status in the dashboard

The existing Sync tab in the dashboard can show live status:
- Last sync time (from Firestore `syncLogs`)
- Per-period results (synced/failed/skipped)
- Any errors or discrepancies

---

## Part 3: Credential Management

Currently Aeries credentials are stored two ways:
- **Cloud Function**: Encrypted in Firestore with Fernet, decrypted at runtime
- **Local scripts**: Windows environment variables (`AERIES_USER`, `AERIES_PASS`)

After migration, only the Firestore-encrypted credentials are needed. The Cloud
Functions already handle decryption. No changes needed here.

---

## Files Modified

| File | Change |
|------|--------|
| `functions/package.json` | Add `puppeteer`, remove `cheerio` |
| `functions/index.js` | Replace cheerio scraping with Puppeteer in `fetchRoster`; add new `syncAttendance` scheduled function |

## Files That Become Legacy (no longer needed)

| File | Was |
|------|-----|
| `attendance-sync/run_attendance_sync.py` | Local orchestrator |
| `attendance-sync/attendance_to_aeries.py` | Firebase → CSV export |
| `attendance-sync/upload_to_aeries.py` | Playwright Aeries automation |
| `attendance-sync/sync_utils.py` | Utilities |
| `attendance-sync/run_attendance.bat` | Windows Task Scheduler entry |
| `attendance-sync/run_now.py` | Manual trigger |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Puppeteer deploy size (~200MB) | Firebase 2nd gen handles this fine |
| Cold start 5-10s | Acceptable — sync runs on schedule, not user-facing |
| 9-min timeout for sync | Process one teacher at a time; most syncs finish in 2-3 min |
| Aeries selector changes | Same fallback strategy as existing Python code |
| Cloud Scheduler cost | Free tier covers 3 jobs/month; this is 1 job |
| Concurrent sync runs | Use Firestore lock doc to prevent overlapping runs |

## Implementation Order

1. **Part 1 first** — Get `fetchRoster` working with Puppeteer (smaller scope,
   validates that Puppeteer works in Cloud Functions with Aeries)
2. **Part 2 second** — Port the attendance sync once Part 1 proves the approach
3. **Part 3** — Update Sync tab UI to show cloud sync status
4. **Cleanup** — Mark local scripts as legacy
