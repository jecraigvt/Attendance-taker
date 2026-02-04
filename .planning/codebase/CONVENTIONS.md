# Coding Conventions

**Analysis Date:** 2026-02-04

## Naming Patterns

**Files:**
- Snake case with `.py` extension: `attendance_to_aeries.py`, `upload_to_aeries.py`, `run_attendance_sync.py`
- Functional naming that describes purpose: script files start with action verb (`run_`, `test_`, `upload_`)

**Functions:**
- Snake case: `export_attendance_to_csv()`, `get_current_sync_label()`, `sync_attendance_to_aeries()`
- Descriptive names indicating both action and object
- Constants follow UPPER_SNAKE_CASE: `FIREBASE_KEY_PATH`, `AERIES_URL`, `SYNC_WINDOW_MINUTES`

**Variables:**
- Snake case throughout: `csv_file`, `period_groups`, `attendance_data`, `total_records`
- Private/module-level globals use leading underscore: `_db`, `_app`
- Loop variables follow context: `period`, `student`, `row`, `opt` for options

**Types:**
- No type hints used in codebase (Python 3 but not annotated)
- String format for date references: `'YYYY-MM-DD'`

## Code Style

**Formatting:**
- 4-space indentation (Python standard)
- Line length: Variable, no strict limit enforced
- Blank lines separate logical sections
- Triple-quoted docstrings for module and function documentation

**Linting:**
- No `.pylintrc`, `.flake8`, or similar linting config detected
- No automated formatting tool configured (no black, autopep8, etc.)

**Imports:**
- Standard library imports at top: `import os`, `import sys`, `import logging`, `import csv`, `import time`
- Third-party imports follow: `import firebase_admin`, `from firebase_admin import...`, `from playwright.sync_api import sync_playwright`
- Local module imports last: `from attendance_to_aeries import export_attendance_to_csv`
- No circular imports detected

## Import Organization

**Order:**
1. Standard library imports (`os`, `sys`, `datetime`, `csv`, `logging`, `time`)
2. Third-party SDK imports (`firebase_admin`, `playwright`)
3. Relative module imports (from sister modules in same package)

**Path Aliases:**
- No alias imports used (no `import X as Y` pattern)
- Direct imports with full module paths

## Error Handling

**Patterns:**
- Broad `except Exception as e` with logging: `try/except` blocks catch exceptions and log via logger
- Graceful degradation: Failed periods skip with `continue` rather than halting (`attendance_to_aeries.py` lines 70-130)
- User-facing errors logged with context: `logger.error()` or `logger.warning()`
- Exception re-raising for critical failures: `raise FileNotFoundError()` when config files missing
- Temporary failures with retry delay: `page.wait_for_timeout()` adds stability to browser automation

**Example from `attendance_to_aeries.py`:**
```python
try:
    # 1. Get roster snapshot for this period
    roster_doc_ref = db.document(base_path)
    roster_doc = roster_doc_ref.get()
    # ... process data ...
except Exception as e:
    logger.warning(f"   Period {period}: Error - {e}")
    continue
```

**Example from `upload_to_aeries.py`:**
```python
try:
    # Process attendance update
    absent_box.check()
    page.wait_for_timeout(500)
    updates_count += 1
except Exception as e:
    error_msg = str(e).split('\n')[0]
    print(f"        ❌ Error processing {student_id}: {error_msg}")
```

## Logging

**Framework:** Standard Python `logging` module

**Configuration (from `run_attendance_sync.py` lines 14-24):**
```python
log_date = datetime.now().strftime('%Y-%m')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'sync_log_{log_date}.txt', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)
```

**Patterns:**
- `logger.info()`: Normal operation status and progress milestones
- `logger.warning()`: Non-critical issues (missing data, skipped records)
- `logger.debug()`: Detailed operational info for debugging
- `logger.error()`: Critical failures with required action
- Direct `print()` statements also used for user-facing output (UI automation steps)
- Log files named by month: `sync_log_2025-12.txt`, `sync_errors_2025-12.log`

**Example from `attendance_to_aeries.py`:**
```python
logger.info(f"Fetching attendance for {date_str}...")
logger.debug(f"Period {period}: No roster snapshot found (skipping)")
logger.warning(f"   Period {period}: Error - {e}")
logger.info(f"   Period {period}: {period_count} records ({present_count} present, {absent_count} absent)")
```

## Comments

**When to Comment:**
- Code is self-documenting where possible (function names, variable names explain intent)
- Comments used for non-obvious logic: Why a delay is needed (`# Added Delay`), why a check is necessary
- Comments explain business logic transitions: Status mapping rationale, Aeries grid interaction quirks

**JSDoc/TSDoc:**
- Not applicable (Python codebase)
- Function docstrings follow Google/NumPy style with Args and Returns sections

**Docstring Example from `attendance_to_aeries.py`:**
```python
def export_attendance_to_csv(date_str):
    """
    Fetch attendance from Firebase and generate CSV for Aeries

    Args:
        date_str: Date in format "YYYY-MM-DD" (e.g., "2024-12-18")

    Returns:
        filename: Path to generated CSV file
    """
```

## Function Design

**Size:**
- Small focused functions (20-60 lines typical)
- `export_attendance_to_csv()`: 98 lines (data processing with nested loops)
- `upload_to_aeries()`: 190 lines (browser automation with multiple phases)
- Helper functions for single responsibilities: `get_db()`, `get_current_sync_label()`, `read_attendance_csv()`

**Parameters:**
- Minimal parameters (1-3 typical)
- Configuration passed via environment variables rather than parameters
- Date strings as parameters: `date_str` parameter format standardized as `'YYYY-MM-DD'`

**Return Values:**
- Functions return single values: CSV filepath, sync label, attendance dictionary
- CSV data structures: `dict[period: list[dict]]` for grouped attendance
- Boolean patterns not used (functions succeed or raise exceptions)

## Module Design

**Exports:**
- Each module exports primary function: `export_attendance_to_csv()`, `upload_to_aeries()`, `sync_attendance_to_aeries()`
- Helper functions (prefixed with `get_`, like `get_db()`) meant as internal but still accessible
- Global initialization functions for lazy-loading (`get_db()` for Firebase)

**Module Structure:**
- Constants at top: `FIREBASE_KEY_PATH`, `APP_ID`, `SYNC_SCHEDULE`
- Lazy-loaded globals: `_db`, `_app` initialized on first use
- Main workflows in functions, orchestrated by `if __name__ == "__main__"` blocks

**Example from `attendance_to_aeries.py`:**
```python
# Constants
FIREBASE_KEY_PATH = os.getenv('FIREBASE_KEY_PATH', 'C:/Users/Jeremy/attendance-sync/attendance-sync/attendance-key.json')
APP_ID = 'attendance-taker-56916'

# Lazy-loaded state
_db = None
_app = None

# Initialization function
def get_db():
    global _db, _app
    # ... initialization logic ...
    return _db

# Main export function
def export_attendance_to_csv(date_str):
    # ... uses get_db() internally ...
```

## Configuration Management

**Environment Variables:**
- `AERIES_USER`, `AERIES_PASS`: Aeries login credentials (required)
- `FIREBASE_KEY_PATH`: Firebase service account key (optional, has default)
- Validated at runtime with helpful error messages if missing
- Default values provided in code for non-critical configs

**Configuration Examples:**
- Firebase key path: `os.getenv('FIREBASE_KEY_PATH', 'default/path')`
- Credentials checked before processing: Lines 103-110 in `run_attendance_sync.py`

---

*Convention analysis: 2026-02-04*
