# External Integrations

**Analysis Date:** 2026-02-04

## APIs & External Services

**Firebase Cloud Services:**
- Firestore - Real-time document database for rosters, attendance logs, exceptions
  - SDK: `firebase-admin` (Python), `firebase-firestore.js` (JavaScript)
  - Auth: Service account key (`attendance-key.json`) for backend; anonymous auth for frontend
  - Project ID: `attendance-taker-56916`
  - Paths:
    - Rosters: `artifacts/attendance-taker-56916/public/rosters/periods/{period}`
    - Attendance: `artifacts/attendance-taker-56916/public/data/attendance/{date}/periods/{period}/students`
    - Exceptions: `artifacts/attendance-taker-56916/public/exceptions`

- Firebase Storage - File storage for screenshots and exports
  - Bucket: `attendance-taker-56916.firebasestorage.app`
  - Used for: Screenshot storage during automation

**Aeries Portal:**
- URL: `https://adn.fjuhsd.org/Aeries.net/`
- Integration: UI automation via Playwright browser
  - Login endpoint: `Login.aspx`
  - Attendance grid: `TeacherAttendance.aspx`
  - Credentials: Username/password (env vars: `AERIES_USER`, `AERIES_PASS`)
  - Authentication: Form-based login with username/password inputs
  - Interaction: Automated form filling, period selection, checkbox toggling for attendance status

## Data Storage

**Databases:**
- Firebase Firestore (Cloud)
  - Type: NoSQL document database
  - Connection: `firebase-admin` SDK (backend), `firebase-firestore.js` (frontend)
  - Auth: Service account key for backend, anonymous auth for client
  - Data models:
    - Rosters: Period-based student lists (StudentID, FirstName, LastName)
    - Attendance logs: Per-period sign-in records with timestamps and status
    - Exceptions: Seating exceptions and student pairing rules

- LocalStorage (Client-side)
  - Fallback when Firebase unavailable
  - Keys: `logs:{date}|{period}`, `allRosters`, `exceptions`
  - Used in: `attendance v 2.2.html`

**File Storage:**
- Local filesystem (Windows)
  - CSV files: `attendance_{YYYY-MM-DD}.csv` - Generated for each sync
  - Logs: `sync_log_{YYYY-MM}.txt` - Monthly log rotation
  - Error logs: `sync_errors_{YYYY-MM}.log` - Monthly error tracking
  - Screenshots: `aeries_grid_{timestamp}.png`, `error_state.png`
  - Location: `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\`

**Caching:**
- In-memory caches in Python:
  - `attendance_to_aeries.py`: Lazy Firebase DB initialization (`_db`, `_app` globals)
  - `upload_to_aeries.py`: Playwright browser context with session persistence

## Authentication & Identity

**Client (Kiosk):**
- Firebase anonymous auth via `signInAnonymously()`
- No student authentication - attendance sign-in is ID-based only
- Fallback: Local browser localStorage when cloud unavailable

**Backend (Sync):**
- Firebase service account authentication
  - Key file: `attendance-sync/attendance-key.json`
  - Loaded via: `firebase_admin.credentials.Certificate()`
  - Scope: Full Firestore read/write access

- Aeries portal authentication
  - Type: Form-based with username/password
  - Selectors: `input[name="portalAccountUsername"]`, `input[name="portalAccountPassword"]`, submit button
  - Session: Persisted in Playwright browser context during automation

**Admin Access:**
- HTML: Teacher code hardcoded in application (`TEACHER_CODE = "****"` in `attendance v 2.2.html`)
- Admin panel access: Toggle via hide/show buttons

## Monitoring & Observability

**Error Tracking:**
- Python logging module (stdlib)
- Separate files per month:
  - Success logs: `sync_log_{YYYY-MM}.txt`
  - Error logs: `sync_errors_{YYYY-MM}.log`

**Logs:**
- Format: `%(asctime)s - %(levelname)s - %(message)s`
- Timestamp format: `%Y-%m-%d %H:%M:%S`
- Output: Console (stdout) + file handlers
- Browser console: JavaScript `console.log()` for frontend debugging
- Screenshots: Automated on Aeries page load and error states

**Metrics:**
- Attendance counts: Per-period summary (on-time, late, truant, absent)
- Sync records: Total records exported per sync
- Status indicators: Period-specific attendance status tracking

## CI/CD & Deployment

**Hosting:**
- Client: Single HTML file served locally or via static HTTP
  - Deployment: Copy `attendance v 2.2.html` to kiosk machines

- Backend: Python scripts executed via Windows Task Scheduler
  - Execution: Manual or scheduled via `.bat` files
  - No cloud deployment

**CI Pipeline:**
- None detected
- Manual testing via Python test scripts:
  - `test_login.py` - Validates Aeries login
  - `run_now.py` - On-demand sync runner

**Deployment Method:**
- Kiosk: File copy to target machine + shortcut creation
- Sync automation: Copy Python files to target, set environment variables, configure Task Scheduler

## Environment Configuration

**Required Environment Variables:**

- `AERIES_USER` - Aeries login username (string, required)
- `AERIES_PASS` - Aeries login password (string, required)
- `FIREBASE_KEY_PATH` - Path to service account JSON (string, optional)
  - Default: `C:/Users/Jeremy/attendance-sync/attendance-sync/attendance-key.json`

**Configuration Location:**
- Windows: System Environment Variables or User Environment Variables
- Instructions in `run_attendance_sync.py` (lines 103-110):
  1. Search 'Environment Variables' in Windows
  2. Click 'Edit environment variables for your account'
  3. Add AERIES_USER and AERIES_PASS variables
  4. Restart applications to reload

**Secrets Management:**
- Service account key: `attendance-sync/attendance-key.json` (NOT in repo, Git ignored)
- Must be obtained from Firebase Console and placed locally
- Access: Referenced by `FIREBASE_KEY_PATH` env var

## Webhooks & Callbacks

**Incoming:**
- None detected
- Application does not expose public endpoints

**Outgoing:**
- Aeries portal: One-way form submission (no webhooks)
- Firebase: Push notifications via `onSnapshot()` listeners for real-time roster/exception updates
  - Firestore collection listener: `artifacts/{APP_ID}/public/rosters/periods`
  - Real-time updates trigger UI re-render

## Data Flow Architecture

**Kiosk Application Flow:**
1. Student scans ID → `handleSignIn()` → Firebase document write
2. Firebase `onSnapshot()` listener detects new sign-in
3. Attendance log updates in real-time
4. UI re-renders with updated counts/status

**Sync Automation Flow:**
1. `run_attendance_sync.py` checks schedule (7x daily or on-demand)
2. Calls `export_attendance_to_csv(date)`:
   - Fetches roster + sign-ins from Firebase
   - Generates CSV with status mapping (Late→Tardy, etc.)
3. Calls `upload_to_aeries(csv)`:
   - Playwright launches Chrome and logs into Aeries
   - Iterates periods and marks attendance via checkbox clicks
   - Saves changes in Aeries UI
4. Logs success/failure to monthly log files

**Firebase Data Paths (Server):**
```
artifacts/
├── attendance-taker-56916/
    ├── public/
    │   ├── rosters/
    │   │   └── periods/
    │   │       ├── 0 → {roster: [{StudentID, LastName, FirstName}, ...]}
    │   │       ├── 1 → {...}
    │   │       └── 6 → {...}
    │   ├── data/
    │   │   └── attendance/
    │   │       └── 2026-02-04/
    │   │           └── periods/
    │   │               └── 1/
    │   │                   ├── (document): {roster_snapshot: [...]}
    │   │                   └── students/
    │   │                       ├── S12345 → {Status, SignInTime, Group}
    │   │                       └── S12346 → {...}
    │   └── exceptions/
    │       ├── frontRow → {frontRow: []}
    │       └── avoidPairs → {avoidPairs: []}
```

---

*Integration audit: 2026-02-04*
