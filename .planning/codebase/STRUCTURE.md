# Codebase Structure

**Analysis Date:** 2026-02-04

## Directory Layout

```
Attendance Taker/
├── .claude/                    # Claude Code workspace metadata
├── .git/                       # Git repository
├── .planning/
│   └── codebase/              # GSD documentation (this analysis)
├── attendance-sync/            # Main application directory
│   ├── attendance_to_aeries.py        # Data extraction & transformation
│   ├── upload_to_aeries.py            # Aeries UI automation
│   ├── run_attendance_sync.py          # Scheduled sync orchestrator
│   ├── run_now.py                     # Direct execution utility
│   ├── test_login.py                  # Credential validation
│   ├── run_attendance.bat              # Windows Task Scheduler entry point
│   ├── .env.example                   # Environment variable template
│   ├── attendance-key.json            # Firebase service account credentials
│   ├── attendance_YYYY-MM-DD.csv      # Generated CSV files (ephemeral)
│   ├── sync_log_YYYY-MM.txt          # Monthly execution logs
│   ├── sync_errors_YYYY-MM.log       # Monthly error logs
│   ├── aeries_grid_YYYYMMDD_HHMMSS.png    # Audit screenshots (per sync)
│   └── __pycache__/                  # Python cache (not committed)
├── attendance v 2.2.html             # Frontend/documentation (separate app)
└── [root files]                      # Git, README, etc.
```

## Directory Purposes

**attendance-sync:**
- Purpose: Core application for syncing attendance from Firebase to Aeries
- Contains: Python modules, configuration files, generated outputs, logs
- Key files: `attendance_to_aeries.py`, `upload_to_aeries.py`, `run_attendance_sync.py`

**.planning/codebase:**
- Purpose: GSD-generated analysis documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Contains: Markdown documents describing codebase patterns and structure
- Key files: This file and related analysis documents

## Key File Locations

**Entry Points:**
- `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\run_attendance.bat`: Windows Task Scheduler entry point (calls run_attendance_sync.py)
- `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\run_attendance_sync.py`: Main orchestrator with schedule validation and error handling
- `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\run_now.py`: Direct execution without schedule checks

**Configuration:**
- `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\.env.example`: Template for required environment variables
- `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\attendance-key.json`: Firebase service account credentials (must exist)
- Windows Environment Variables: AERIES_USER, AERIES_PASS (set via Windows System Properties)

**Core Logic:**
- `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\attendance_to_aeries.py`: Firebase data extraction and CSV generation
  - `get_db()`: Lazy Firebase client initialization
  - `export_attendance_to_csv(date_str)`: Main export function
- `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\upload_to_aeries.py`: Aeries UI automation
  - `read_attendance_csv(csv_filepath)`: Parse CSV and group by period
  - `upload_to_aeries(csv_filepath, aeries_base_url, username, password)`: Main upload function

**Testing:**
- `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\test_login.py`: Validates Aeries credentials without full sync

**Outputs:**
- `attendance_YYYY-MM-DD.csv`: Generated once per sync, one file per day
- `sync_log_YYYY-MM.txt`: Appended monthly, contains all execution messages
- `sync_errors_YYYY-MM.log`: Appended monthly, contains only error lines with timestamp
- `aeries_grid_YYYYMMDD_HHMMSS.png`: Screenshot captured at end of each successful sync
- `error_state.png`: Screenshot captured if browser automation fails

## Naming Conventions

**Files:**
- Module files: `lowercase_with_underscores.py` (e.g., `attendance_to_aeries.py`)
- CSV exports: `attendance_YYYY-MM-DD.csv` (date-based, one per day max)
- Log files: `sync_log_YYYY-MM.txt`, `sync_errors_YYYY-MM.log` (month-based, appended)
- Screenshots: `aeries_grid_YYYYMMDD_HHMMSS.png` (timestamp-based for uniqueness)
- Configuration: `.env.example`, `attendance-key.json` (service account key)

**Directories:**
- Package: `attendance-sync/` (lowercase with hyphen, no spaces)
- Planning: `.planning/` (hidden, dot-prefixed for IDE/tools organization)
- Metadata: `.claude/`, `.git/` (tool-specific directories)

**Functions:**
- Snake_case: `export_attendance_to_csv()`, `read_attendance_csv()`, `get_current_sync_label()`
- Private/internal: `_db`, `_app` (underscore prefix for module-level singletons)

**Variables:**
- Constants: `UPPERCASE_WITH_UNDERSCORES` (e.g., `FIREBASE_KEY_PATH`, `SYNC_SCHEDULE`, `SYNC_WINDOW_MINUTES`)
- Configuration: `SYNC_SCHEDULE` dict, `periods` list
- Dynamic: Lowercase (e.g., `csv_file`, `period`, `student_id`)

**Comments:**
- Docstrings: Triple-quoted strings on function definitions
- Inline: Hash prefix with space (e.g., `# Skip periods with no data`)

## Where to Add New Code

**New Feature:**
- Primary code: Add to appropriate file in `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\`
  - Data extraction logic: `attendance_to_aeries.py`
  - Aeries UI changes: `upload_to_aeries.py`
  - Scheduling/orchestration: `run_attendance_sync.py`
- Tests: Create `test_*.py` in same directory (following existing test_login.py pattern)
- Documentation: Add to `.planning/codebase/` as GSD analysis documents

**New Module:**
- Implementation: Create `new_module.py` in `attendance-sync/` directory
- Naming: Use `lowercase_with_underscores.py`
- Initialization: Add `get_X()` lazy-init pattern if module interacts with external services
- Imports: Add to orchestrator (`run_attendance_sync.py`) or utility script (`run_now.py`)

**Utilities:**
- Shared helpers: Create as functions in relevant module or in new utility file
- Period lists: Reference `periods = ["0", "1", "2", "2A", "2B", "3", "4", "5", "6", "7"]` from `attendance_to_aeries.py`
- Status mapping: Keep in `upload_to_aeries.py` near usage in student processing loop
- Time utilities: Keep in `run_attendance_sync.py` (SYNC_SCHEDULE dict, get_current_sync_label function)

**Logging:**
- Each module: Initialize its own logger: `logger = logging.getLogger(__name__)`
- Root config: Done once in orchestrator (`run_attendance_sync.py`)
- Handlers: Dual output (console + file) set in orchestrator, inherited by module loggers

**Configuration:**
- Environment variables: Document in `.env.example` and read via `os.getenv()` in appropriate module
- Hard-coded constants: Place at module top level:
  - `attendance_to_aeries.py`: `FIREBASE_KEY_PATH`, `APP_ID`, periods list
  - `upload_to_aeries.py`: `LOGIN_URL`, `ATTENDANCE_URL`, status mapping logic
  - `run_attendance_sync.py`: `SYNC_SCHEDULE`, `SYNC_WINDOW_MINUTES`

## Special Directories

**attendance-sync/__pycache__:**
- Purpose: Python bytecode cache (generated automatically)
- Generated: Yes (by Python runtime)
- Committed: No (ignored by .gitignore)

**.planning/codebase:**
- Purpose: GSD-generated codebase analysis documents
- Generated: Yes (by Claude Code GSD tools)
- Committed: Yes (intended for version control)

**.claude:**
- Purpose: Claude Code workspace settings and metadata
- Generated: Yes (by Claude Code)
- Committed: Yes (for team sync)

**.git:**
- Purpose: Git repository metadata
- Generated: Yes (by git init)
- Committed: N/A (repository structure)

## Adding New Components

**New API Integration:**
1. Create module `new_api.py` in `attendance-sync/`
2. Implement lazy initialization function (`get_client()`) if needed
3. Add configuration to `.env.example`
4. Import in orchestrator or utility that calls it
5. Document path in ARCHITECTURE.md "Key Abstractions" section

**New Data Source (besides Firebase):**
1. Create extraction function in new module or extend `attendance_to_aeries.py`
2. Ensure output is CSV format compatible with Aeries (Date, Period, StudentID, LastName, FirstName, Status, SignInTime, Group)
3. Update transformation logic in `export_attendance_to_csv()` or new equivalent function
4. Document in ARCHITECTURE.md "Data Flow" section

**New Reporting/Logging:**
1. Add handlers to logging config in `run_attendance_sync.py`
2. Reference module loggers: `logging.getLogger(__name__)`
3. Store reports in `attendance-sync/` with pattern `report_YYYY-MM-DD.txt` or `report_YYYY-MM.log`

**New Schedule Window:**
1. Add entry to `SYNC_SCHEDULE` dict in `run_attendance_sync.py`
2. Key: Time string "HH:MM" (24-hour format)
3. Value: Descriptive label for logging
4. Increase `SYNC_WINDOW_MINUTES` if more windows make the 5-min window too tight
