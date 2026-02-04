# Architecture

**Analysis Date:** 2026-02-04

## Pattern Overview

**Overall:** Three-layer sync pipeline with scheduled batch processing

**Key Characteristics:**
- Separation between data extraction (Firebase), transformation (CSV), and upload (Aeries UI)
- Time-based scheduling with 7 daily sync windows aligned to school periods
- Browser automation using Playwright for UI interactions with locked/unlocked student states
- Lazy initialization of Firebase client to prevent import-time failures

## Layers

**Data Extraction Layer:**
- Purpose: Fetch attendance data from Firebase Firestore
- Location: `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\attendance_to_aeries.py`
- Contains: Firebase client initialization, roster/student data retrieval, period-based grouping
- Depends on: Firebase Admin SDK, environment variables (FIREBASE_KEY_PATH), Firestore database
- Used by: Main sync orchestrator (`run_attendance_sync.py`), direct execution utilities

**Transformation Layer:**
- Purpose: Convert Firebase attendance records into Aeries-compatible CSV format
- Location: `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\attendance_to_aeries.py` (export_attendance_to_csv function)
- Contains: CSV row generation, status mapping, absent/present record creation
- Depends on: Data extraction layer
- Used by: Upload layer

**Upload Layer:**
- Purpose: Automate browser interactions with Aeries TeacherAttendance.aspx grid
- Location: `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\upload_to_aeries.py`
- Contains: Playwright browser automation, DOM traversal, checkbox state management, period selection
- Depends on: Playwright sync API, CSV parsing, environment credentials
- Used by: Main sync orchestrator

**Orchestration Layer:**
- Purpose: Coordinate the three-layer pipeline and enforce scheduled execution
- Location: `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\run_attendance_sync.py`
- Contains: Schedule validation, error handling, logging, force-run capability
- Depends on: Data extraction, transformation, upload layers
- Used by: Windows Task Scheduler (via `run_attendance.bat`)

## Data Flow

**Scheduled Sync Flow:**

1. Windows Task Scheduler triggers `run_attendance.bat` at 08:40, 09:42, 11:02, 12:04, 13:41, 14:43, 15:30
2. Batch file executes `run_attendance_sync.py`
3. Orchestrator validates current time against SYNC_SCHEDULE (7 predefined times with ±5 min window)
4. If within sync window, retrieves today's date (YYYY-MM-DD)
5. Extraction layer connects to Firebase via lazy-initialized client
6. For each of 10 periods (0, 1, 2, 2A, 2B, 3, 4, 5, 6, 7):
   - Fetches roster_snapshot from Firebase document
   - Retrieves all students with signin records in period subcollection
   - Compares roster against signin records to identify absences
7. Transformation creates CSV with headers: Date, Period, StudentID, LastName, FirstName, Status, SignInTime, Group
8. Upload layer reads CSV, groups rows by period
9. For each period:
   - Navigates to Aeries TeacherAttendance.aspx
   - Selects period from dropdown
   - Clicks "All Remaining Students Are Present" (bulk default)
   - Iterates through CSV students and updates checkboxes:
     - Absent checkbox if Status = 'Absent'
     - Tardy checkbox if Status in [Late, Truant, Cut, Late>20]
     - Both unchecked if Status = 'Present' (correction logic)
10. Clicks Save button
11. Captures screenshot for audit trail
12. Logs success or failure with timestamp

**Manual Force Flow:**

User executes: `python run_now.py` or `python run_attendance_sync.py --force`
- Skips time validation
- Executes full pipeline immediately
- Cleans up CSV files older than 30 days

**State Management:**

- **Firebase State:** Documents and subcollections persist; read-only during sync
- **CSV State:** Generated fresh each sync, stored as `attendance_YYYY-MM-DD.csv` in same directory
- **Aeries State:** Updated via checkbox state changes in grid; no export/persist mechanism
- **Session State:** Per-run logging in `sync_log_YYYY-MM.txt` and error logs `sync_errors_YYYY-MM.log`

## Key Abstractions

**Firebase Client:**
- Purpose: Abstract Firestore connection and prevent redundant initialization
- Examples: `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\attendance_to_aeries.py` (get_db function)
- Pattern: Lazy initialization with global state (prevent repeated app initialization)

**Period Iteration:**
- Purpose: Standardize processing of school's 10 periods
- Examples: `attendance_to_aeries.py` (periods list: 0, 1, 2, 2A, 2B, 3, 4, 5, 6, 7)
- Pattern: Single source of truth for period structure

**CSV Grouping:**
- Purpose: Organize student records by period before upload
- Examples: `upload_to_aeries.py` (read_attendance_csv function)
- Pattern: Dictionary keyed by period with lists of student dicts

**DOM Targeting Strategy:**
- Purpose: Locate and interact with Aeries grid elements reliably
- Examples: `upload_to_aeries.py` (CSS selectors like `td[data-studentid='{student_id}']`, `span[data-cd='A']`)
- Pattern: Row-based scoping (find cell → parent row → search within row for checkboxes)

**Status Normalization:**
- Purpose: Map application-specific status codes to Aeries codes
- Examples: `upload_to_aeries.py` (Late, Truant, Cut, Late>20 → Tardy; On Time, Present, Excused → Present)
- Pattern: Simple if/elif mapping applied before checkbox interaction

## Entry Points

**Scheduled Sync:**
- Location: `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\run_attendance.bat`
- Triggers: Windows Task Scheduler at 7 times daily (08:40, 09:42, 11:02, 12:04, 13:41, 14:43, 15:30)
- Responsibilities: Execute Python script in correct directory context

**Direct Orchestrator:**
- Location: `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\run_attendance_sync.py`
- Triggers: Manual execution, called by batch file, accepts --force/-f flag
- Responsibilities: Validate schedule, coordinate layers, log results

**Direct Executor:**
- Location: `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\run_now.py`
- Triggers: Manual execution for immediate sync
- Responsibilities: Skip scheduling, execute pipeline, cleanup old CSVs

**Utilities:**
- `test_login.py`: Validates Aeries credentials without running full sync
- `attendance_to_aeries.py`: Can be executed directly to test Firebase export for a specific date

## Error Handling

**Strategy:** Per-layer exception logging with graceful degradation

**Patterns:**

- **Firebase Errors:** Warning-level log per period, continue with other periods (don't fail entire sync if one period fails)
- **CSV Generation:** Raises exception if total_records == 0 (validation gate—prevents empty uploads)
- **Aeries Login:** Raises exception; caught by orchestrator and logged to error file with timestamp
- **Aeries Upload:** Per-student exception with shortened error message; continues to next student
- **Aeries Period Selection:** Warning if dropdown not found; continues to next period
- **Browser/Playwright Errors:** Screenshots captured (`error_state.png`, `aeries_grid_TIMESTAMP.png`) for audit trail

## Cross-Cutting Concerns

**Logging:**
- Approach: Python logging module with dual handlers (console + file)
- Files: `sync_log_YYYY-MM.txt` (all runs), `sync_errors_YYYY-MM.log` (errors only)
- Format: `%(asctime)s - %(levelname)s - %(message)s` with 24-hour timestamps
- Module-specific: Each module (attendance_to_aeries, upload_to_aeries, run_attendance_sync) has its own logger

**Validation:**

- Environment variables: AERIES_USER, AERIES_PASS checked before sync (logs helpful instructions if missing)
- Firebase credentials: FileNotFoundError if FIREBASE_KEY_PATH doesn't exist
- CSV integrity: Exception raised if no periods have data
- Schedule validation: Checks current time against SYNC_SCHEDULE with configurable SYNC_WINDOW_MINUTES (currently 5 min)

**Authentication:**

- Firebase: Service account key via `FIREBASE_KEY_PATH` env var (JSON credentials file)
- Aeries: Username/password from Windows environment variables (AERIES_USER, AERIES_PASS)
- Browser: Playwright handles HTTP Basic Auth and form submission via selectors
