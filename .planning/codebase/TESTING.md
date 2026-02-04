# Testing Patterns

**Analysis Date:** 2026-02-04

## Test Framework

**Status:** No automated testing framework configured

**Current State:**
- No `pytest.ini`, `setup.cfg`, `tox.ini`, or test configuration files
- No `unittest`, `pytest`, or `nose` imports in codebase
- No test discovery patterns (no `test_*.py` or `*_test.py` files in source)
- Single manual test file exists: `test_login.py` (diagnostic/verification script, not automated)

**Implication:**
Testing is manual and verification-based rather than automated. Quality assurance depends on:
- Manual browser testing via Playwright (visual confirmation)
- Diagnostic scripts for individual component validation
- Integration testing via actual system runs

## Manual Testing Approach

**Test File: `test_login.py`**
- Location: `C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance-sync\test_login.py`
- Purpose: Diagnostic script to verify Aeries login credentials and selectors work
- Type: Manual verification, not automated test suite
- Pattern: Opens browser, performs login, checks URL for success indicator

**Execution:**
```bash
python test_login.py
```

**Verification Logic:**
```python
# From test_login.py lines 60-64
current_url = page.url
if "Login.aspx" not in current_url:
    print("\n✓✓✓ LOGIN SUCCESSFUL! ✓✓✓")
else:
    print("\n⚠ Still on login page - check credentials or selectors")
    page.screenshot(path='login_test.png')
```

## Test Structure Patterns

**Module-Level Testing:**
- Each script has optional `if __name__ == "__main__"` block for direct execution
- Functions can be imported and called programmatically
- Example from `attendance_to_aeries.py` lines 145-152:
```python
if __name__ == "__main__":
    # Test the export for today
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        csv_file = export_attendance_to_csv(today)
        print(f"Success! CSV file created: {csv_file}")
    except Exception as e:
        print(f"Error: {e}")
```

**Validation Through Execution:**
- Functions validate inputs on call: FileNotFoundError raised if Firebase key missing
- Environment variables checked at runtime before processing
- CSV output validated by attempting to read and parse

## Mocking and Isolation

**Framework:** No mocking framework (no `unittest.mock`, `pytest-mock`, `responses`)

**Current Isolation Approach:**
- Firebase client lazy-loaded and cached globally: `get_db()` in `attendance_to_aeries.py`
- Browser automation uses real Aeries server (no test environment)
- No test doubles or stubs

**Playwright Browser Usage (from `upload_to_aeries.py`):**
```python
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=50)
    context = browser.new_context(viewport={'width': 1600, 'height': 900})
    page = context.new_page()
    # ... real browser interaction with live Aeries server ...
```

**Dependencies on External Services:**
- Firebase: Live authentication, live data access (no test fixtures)
- Aeries: Live web interface automation (no staging environment)
- No dependency injection or abstraction layer for swapping implementations

## Test Data and Fixtures

**Current Practice:**
- No fixture files or factories
- Test data comes from live Firebase during manual testing
- CSV files generated and stored: `attendance_2026-02-04.csv` etc.
- Historical CSV files kept for reference/auditing

**Data Location:**
- Live data path: `artifacts/{APP_ID}/public/data/attendance/{date_str}/periods/{period}`
- Generated CSVs: Same directory as scripts, named `attendance_YYYY-MM-DD.csv`
- Configuration: `.env.example` shows required env vars but no test-specific config

**Example from `run_attendance_sync.py`:**
```python
today_str = datetime.now().strftime('%Y-%m-%d')
csv_filename = export_attendance_to_csv(today_str)  # Generates from live Firebase data
```

## Coverage

**Requirements:** Not enforced or measured

**Current State:**
- No coverage tool configuration (no `.coveragerc`, `coverage` settings)
- No coverage target or threshold
- No code coverage metrics collected

**Test Execution Paths:**
- Happy path tested manually: credential validation → Firebase export → CSV generation → Aeries upload → save
- Error paths not systematically tested: Missing Firebase key, invalid credentials, network failures
- Edge cases not covered: Empty rosters, malformed data, locked attendance records

## Test Types

**Unit Tests:**
- Not implemented
- Functions could be unit tested: `get_current_sync_label()`, `read_attendance_csv()`, status normalization logic
- Example testable function from `run_attendance_sync.py` lines 41-58:
```python
def get_current_sync_label():
    """Returns sync label if within scheduled window, None otherwise"""
    now = datetime.now()
    for sync_time, label in SYNC_SCHEDULE.items():
        scheduled = datetime.strptime(sync_time, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )
        diff_minutes = abs((now - scheduled).total_seconds() / 60)
        if diff_minutes <= SYNC_WINDOW_MINUTES:
            return label
    return None
```

**Integration Tests:**
- Partially tested manually during daily operation
- Full workflow: Firebase → CSV → Aeries upload
- Verification by screenshot: `page.screenshot(path=f'aeries_grid_{timestamp}.png')`
- Error logging: Failed syncs logged to `sync_errors_2025-12.log`

**E2E Tests:**
- Not formalized, but functional E2E testing occurs daily
- Full attendance sync pipeline runs on schedule (7 times per day)
- Success verified by Aeries grid state and screenshot comparison
- Issues surfaced as browser screenshots: `error_state.png`, `login_error.png`

## Error Handling in Testing

**Current Pattern:**
- Errors printed to console and logged to files
- Browser errors captured as screenshots for debugging
- Example from `upload_to_aeries.py` lines 210-213:
```python
except Exception as e:
    print(f"\n❌ Error during automation: {e}")
    page.screenshot(path='error_state.png')
    raise
```

## Debugging and Diagnostics

**Tools Available:**
- Browser automation visibility: `headless=False` in Playwright shows browser during test
- Screenshots on failure: Automatic screenshot capture at key points
- Console/log output: Both print statements and logging module

**Debugging Approach from `upload_to_aeries.py` lines 43-46:**
```python
browser = p.chromium.launch(headless=False, slow_mo=50)
# headless=False: See browser interact in real-time
# slow_mo=50: 50ms delay between actions for observation
context = browser.new_context(viewport={'width': 1600, 'height': 900})
```

**Log Files Generated:**
- `sync_log_YYYY-MM.txt`: Overall sync execution log
- `sync_errors_YYYY-MM.log`: Error-only log for quick issue review
- Screenshots: `aeries_grid_YYYYMMDD_HHMMSS.png`, `error_state.png`

## Test Execution Commands

**No Automated Test Runner**

**Manual Testing Approach:**

```bash
# Test Firebase export
python attendance_to_aeries.py

# Test Aeries login
python test_login.py

# Run full sync workflow
python run_attendance_sync.py

# Run with force flag (bypass schedule check)
python run_attendance_sync.py --force

# Quick sync (run_now.py)
python run_now.py
```

**Scheduled Execution:**
- Daily via Windows scheduler (referenced in `.bat` file)
- 7 execution points: 08:40, 09:42, 11:02, 12:04, 13:41, 14:43, 15:30
- Defined in `SYNC_SCHEDULE` dict in `run_attendance_sync.py` lines 27-35

## Testing Gaps and Risks

**Critical Untested Scenarios:**
- Firebase key file missing or invalid (only caught at runtime)
- Network timeout during Firebase fetch (caught but not specifically tested)
- Aeries UI selector changes break automation (no test for selector robustness)
- Empty rosters or rosters with missing data (handled with `continue` but not tested)
- Locked attendance records (handled gracefully but not verified)

**Data Integrity Gaps:**
- CSV validation: No schema validation before upload
- Field mapping: Status code normalization happens in code but not validated
- Date formatting: Assumes input format `YYYY-MM-DD` but doesn't validate

**Infrastructure Gaps:**
- Environment variables assumed present (validated but no fallback)
- File permissions not tested (assume working directory writable)
- Concurrency: No locking if script runs twice simultaneously

## Recommendations for Testing

**Quick Wins (if testing were to be added):**
1. Add unit tests for time-window logic: `get_current_sync_label()` with parameterized times
2. Add CSV parsing tests: `read_attendance_csv()` with malformed data
3. Add status mapping tests: Verify all status transitions work correctly
4. Screenshot comparison: Save baseline screenshots, compare with current runs

**Medium Effort:**
1. Create fixture data: Mock Firebase responses for consistent testing
2. Add integration tests: Test export→upload flow with fake Aeries server
3. Add error scenario tests: Simulate Firebase failures, network timeouts

**Larger Effort:**
1. Set up pytest framework with test structure
2. Create staging Aeries environment for safe testing
3. Add mock Firebase with test datasets
4. Implement continuous testing via CI/CD

---

*Testing analysis: 2026-02-04*
