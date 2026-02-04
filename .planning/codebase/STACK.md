# Technology Stack

**Analysis Date:** 2026-02-04

## Languages

**Primary:**
- JavaScript/HTML (ES2022+) - Client-side kiosk application (`attendance v 2.2.html`)
- Python 3 - Backend automation scripts for Firebase export and Aeries upload (`attendance-sync/*.py`)

**Secondary:**
- CSV - Data interchange format for Aeries import/export

## Runtime

**Environment:**
- Node.js runtime (for any build/dev tooling - not explicitly used in current codebase)
- Python 3.x - Required for sync automation scripts

**Package Manager:**
- pip (Python dependency manager)
- None detected for JavaScript (uses CDN imports only)

**Lockfile:**
- Missing for Python (no requirements.txt or Pipenv file detected)
- N/A for JavaScript (no npm/yarn used)

## Frameworks

**Frontend:**
- Tailwind CSS 4.x - Utility-first CSS framework via CDN (`https://cdn.tailwindcss.com`)
- Firebase SDK 10.12.2 (modular) - Real-time database and authentication
- Vanilla JavaScript (no frontend framework)

**Backend/Automation:**
- Playwright (sync_api) - Browser automation for Aeries UI interaction (`upload_to_aeries.py`)
- Firebase Admin SDK - Server-side Firestore access for attendance export (`attendance_to_aeries.py`)

**Build/Dev:**
- No build tool detected
- No test framework detected

## Key Dependencies

**Critical:**
- `firebase_admin` (Python) - Firebase server SDK for Firestore database access
  - Used in: `attendance_to_aeries.py`
  - Purpose: Fetch attendance records from Firebase for CSV export

- `firebase-app.js`, `firebase-auth.js`, `firebase-firestore.js` (v10.12.2) - Firebase web SDK
  - Used in: `attendance v 2.2.html`
  - Purpose: Real-time sync of rosters, attendance logs, and exceptions to Firestore

- `playwright` (Python) - Browser automation library for Aeries integration
  - Used in: `upload_to_aeries.py`
  - Purpose: Automate login and attendance grid entry in Aeries web interface

**Infrastructure:**
- `csv` (Python stdlib) - CSV file reading/writing for Aeries format
  - Used in: `attendance_to_aeries.py`, `upload_to_aeries.py`

- `logging` (Python stdlib) - Application logging with file rotation
  - Used in: All sync scripts
  - Features: Date-based log files, console + file output

- `datetime`, `os`, `time` (Python stdlib) - Date/time and system operations

## Configuration

**Environment Variables:**
All credentials and paths are environment-based (Windows Environment Variables):

- `AERIES_USER` - Aeries portal username (required for sync)
- `AERIES_PASS` - Aeries portal password (required for sync)
- `FIREBASE_KEY_PATH` - Path to Firebase service account key JSON
  - Default: `C:/Users/Jeremy/attendance-sync/attendance-sync/attendance-key.json`
  - Fallback: Configured in code if env var not set

**Firebase Configuration (Client):**
Embedded in HTML head (`attendance v 2.2.html` lines 44-52):
```javascript
window.__firebase_config = {
  apiKey: "AIzaSyDelYxA0NGfGakd3T8wd8PxfZu2sFJZrDA",
  authDomain: "attendance-taker-56916.firebaseapp.com",
  projectId: "attendance-taker-56916",
  storageBucket: "attendance-taker-56916.firebasestorage.app",
  messagingSenderId: "709493952046",
  appId: "1:709493952046:web:3266a6e1d706bdfe9059bf",
  measurementId: "G-LBLM1420GZ"
};
window.__app_id = 'attendance-taker-56916';
```

**Firebase Service Account:**
- Location: `attendance-sync/attendance-key.json` (NOT committed, Git ignored)
- Format: JSON service account credentials for server-side Firebase Admin SDK

**.env Example:**
`attendance-sync/.env.example` documents required variables:
```
AERIES_USER=your_username
AERIES_PASS=your_password
FIREBASE_KEY_PATH=C:/Users/Jeremy/attendance-sync/attendance-sync/attendance-key.json
```

## Build Configuration

**HTML:**
- Single-file HTML application (no build step)
- Loads Tailwind CSS via CDN
- Loads Firebase SDK modules from CDN

**Python Scripts:**
- Executed directly with `python script.py`
- No compilation or build artifacts

**Startup Scripts:**
- `run_attendance.bat` - Batch file to run the kiosk HTML file (OS-level launcher)
- `run_attendance_sync.py` - Scheduled sync runner (can be invoked manually or via Windows Task Scheduler)
- `run_now.py` - Manual on-demand sync trigger

## Platform Requirements

**Development:**
- Windows OS (scripts reference Windows paths, env vars)
- Python 3.7+
- Browser with modern JavaScript support (ES2022+)
- Text editor for HTML/Python modification

**Production/Deployment:**
- Windows OS (hard requirement for batch files and Aeries login via Playwright)
- Python 3.7+ with pip
- Chrome/Chromium browser (Playwright launches headless Chromium)
- Network access to:
  - Firebase Firestore (`attendance-taker-56916.firebaseapp.com`)
  - Aeries portal (`https://adn.fjuhsd.org`)
  - Tailwind CSS CDN (`cdn.tailwindcss.com`)
  - Firebase SDK CDN (`www.gstatic.com/firebasejs/`)

**Sync Schedule:**
- Windows Task Scheduler capable of running Python scripts
- Configured to run 7 times per day at:
  - 08:40, 09:42, 11:02, 12:04, 13:41, 14:43, 15:30 (see `run_attendance_sync.py` SYNC_SCHEDULE)

---

*Stack analysis: 2026-02-04*
