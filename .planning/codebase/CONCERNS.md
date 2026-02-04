# Codebase Concerns

**Analysis Date:** 2026-02-04

## Fragile Areas

**UI Automation with Playwright (attendance sync to Aeries):**
- Files: `attendance-sync/upload_to_aeries.py`
- Why fragile: The system depends heavily on CSS selectors and HTML structure of the Aeries web UI. Any UI changes break automation. Multiple fallback selector attempts (e.g., line 55: `'input[name="portalAccountUsername"], input[type="text"]'`) indicate selector brittleness.
- Safe modification: Maintain comprehensive selector lists and add visual debugging (screenshots are already captured on errors). Document each selector's rationale.
- Test coverage: No automated tests. Errors only discovered during manual runs.
- Evidence: Error log shows repeated selector timeouts: "Page.wait_for_selector: Timeout 10000ms exceeded" and "Page.fill: Timeout 30000ms exceeded"

**Playwright Synchronization Delays:**
- Files: `attendance-sync/upload_to_aeries.py` (lines 96, 114, 162, 166, 172, 176, 183, 188)
- Why fragile: Hard-coded `page.wait_for_timeout()` values (3000ms, 1000ms, 500ms) are timing-based workarounds. Network latency, server load, or browser performance variations can cause races.
- Safe modification: Replace with explicit Playwright wait conditions (`wait_for_load_state()`, `wait_for_function()`) instead of blind delays.
- Priority: High - these delays significantly slow the automation pipeline.

**Firebase Lazy Initialization:**
- Files: `attendance-sync/attendance_to_aeries.py` (lines 24-41)
- Why fragile: Global `_db` and `_app` singletons are initialized on first use. If Firebase initialization fails silently or partially, subsequent calls will fail with unclear error messages.
- Safe modification: Add explicit initialization health checks and clear error messages.
- Evidence: File not found error on line 37 suggests this path has failed before.

## Performance Bottlenecks

**Playwright Browser Automation Speed:**
- Problem: Full browser automation with delays takes significant time per period (period loop at line 73). Each student update includes 500ms waits, and there are multiple students per period.
- Files: `attendance-sync/upload_to_aeries.py` (lines 73-196)
- Cause: Conservative delay strategy to handle Aeries server lag and UI rendering. `slow_mo=50` on line 45 adds additional latency globally.
- Improvement path: Profile actual response times, replace blind waits with conditional waits. Parallel processing of periods may be possible if Aeries supports session isolation.
- Impact: With 10 periods × ~30 students × 500ms per update = 150+ seconds minimum per sync, plus login/navigation time.

**CSV I/O Operations:**
- Problem: CSV files are written to disk (line 136) and then read back (line 38 in upload_to_aeries.py) as intermediate step.
- Files: `attendance-sync/attendance_to_aeries.py`, `attendance-sync/upload_to_aeries.py`
- Cause: Two-phase export-then-upload design.
- Improvement path: Pass data structures directly between functions instead of serializing/deserializing CSV.

**Firebase Query Inefficiency:**
- Problem: Code fetches entire roster snapshot then makes separate collection query for students (lines 71-88 in attendance_to_aeries.py). Iterates through all roster entries even if signed_in is small.
- Files: `attendance-sync/attendance_to_aeries.py` (lines 86-88)
- Cause: Current Firebase data structure requires two queries per period.
- Improvement path: Consider compound index or batch read if Firebase quota allows.

## Security Considerations

**Hardcoded Firebase Key Path:**
- Risk: Line 21 in `attendance_to_aeries.py` has hardcoded absolute path `'C:/Users/Jeremy/attendance-sync/attendance-sync/attendance-key.json'`. This is Windows-specific and breaks on other machines. Also suggests key is stored in source control or shared location.
- Files: `attendance-sync/attendance_to_aeries.py` (line 21)
- Current mitigation: Falls back to `FIREBASE_KEY_PATH` env var with default, but default is still hardcoded.
- Recommendations:
  - Remove hardcoded path, only use env var
  - Ensure `attendance-key.json` is in `.gitignore`
  - Document key placement in README

**Credentials in Environment Variables:**
- Risk: Aeries username/password stored in Windows environment variables (referenced throughout). While better than hardcoding, environment variables can be read by any process with user privileges.
- Files: `attendance-sync/run_attendance_sync.py` (lines 99-100), `attendance-sync/upload_to_aeries.py` (lines 220-221), `attendance-sync/run_now.py` (lines 26-27)
- Current mitigation: Documented in comments but not enforced.
- Recommendations:
  - Document credential storage policy clearly
  - Consider Windows Credential Manager or .env file (with proper .gitignore) as alternative
  - Add validation that credentials are set before running

**Cleartext Logging of Errors:**
- Risk: Error log file (`sync_errors_2025-12.log`) and screenshot files accumulate indefinitely in source directory. Errors may contain sensitive information.
- Files: `attendance-sync/run_attendance_sync.py` (lines 148-150), `attendance-sync/upload_to_aeries.py` (lines 207, 212)
- Current mitigation: run_now.py has 30-day cleanup (lines 11-21) but only for CSV files, not logs or screenshots.
- Recommendations:
  - Apply same 30-day cleanup to `.log` and `.png` files
  - Consider redacting URLs and sensitive data from error logs

**Screenshot File Accumulation:**
- Risk: Hundreds of timestamped screenshots in directory (aeries_grid_*.png, error_state.png visible in directory listing). Each 100-200KB, consuming significant disk space. Could contain sensitive school/student information.
- Files: `attendance-sync/upload_to_aeries.py` (lines 207, 212)
- Current mitigation: Screenshots only on error or final state, but no cleanup policy.
- Recommendations:
  - Delete screenshots after successful sync
  - Apply retention policy (keep last N or last X days)
  - Consider not taking final screenshot on success

## Tech Debt

**Selector Redundancy:**
- Issue: Multiple selector patterns in single `.fill()` or `.click()` call (e.g., `'input[name="portalAccountUsername"], input[type="text"]'`) indicate UI selectors are brittle and changing.
- Files: `attendance-sync/upload_to_aeries.py` (lines 55-57), `attendance-sync/test_login.py` (lines 41, 45, 50)
- Impact: Makes debugging harder; unclear which selector is actually matched.
- Fix approach: Test selectors individually, document which one is correct for current Aeries version. Add version detection or inline comments explaining selector choice.

**Magic Numbers Throughout:**
- Issue: Hard-coded period list, timeout values, window sizes scattered across code.
- Files: `attendance-sync/attendance_to_aeries.py` (line 63), `attendance-sync/run_attendance_sync.py` (line 38), `attendance-sync/upload_to_aeries.py` (lines 45-46, 96, 162, 166, 172, 176, 183, 188)
- Impact: Makes configuration and experimentation difficult.
- Fix approach: Create configuration module with constants (PERIODS, TIMEOUT_LOGIN_MS, TIMEOUT_GRID_MS, BROWSER_WIDTH, etc.).

**Bare Exception Handlers:**
- Issue: Multiple `except: pass` statements (e.g., lines 115, 204 in upload_to_aeries.py, line 21 in run_now.py) that silently swallow all errors.
- Files: `attendance-sync/upload_to_aeries.py` (lines 69, 115, 204), `attendance-sync/run_now.py` (lines 20-21)
- Impact: Bugs become invisible. Hard to debug automation failures.
- Fix approach: Replace with specific exception types and at least log the error, even if recovery strategy is "continue".

**Inconsistent Logging:**
- Issue: Mix of `print()` and `logging` module. Some scripts use logging (run_attendance_sync.py), others use print (upload_to_aeries.py). No unified log levels.
- Files: All files in `attendance-sync/`
- Impact: Difficult to aggregate logs, inconsistent formatting.
- Fix approach: Use logging module exclusively. Set log levels from config.

**Global State with Firebase:**
- Issue: Module-level globals `_db` and `_app` (lines 25-26 in attendance_to_aeries.py) are initialized once and reused. No explicit cleanup.
- Files: `attendance-sync/attendance_to_aeries.py`
- Impact: Cannot re-initialize if credentials change or connection dies.
- Fix approach: Use context manager pattern or explicit lifecycle methods.

## Missing Critical Features

**No Retry Logic:**
- Problem: If sync fails (network timeout, browser crash), no automatic retry. User must manually re-run.
- Files: `attendance-sync/run_attendance_sync.py` (lines 115-145), `attendance-sync/upload_to_aeries.py` (lines 43-216)
- Blocks: Unreliable operation; requires manual monitoring.
- Recommendation: Add exponential backoff retry for transient failures (network, timeouts). Fail immediately on auth errors.

**No Validation of CSV Data:**
- Problem: Code assumes Firebase data is well-formed (e.g., `student.get('StudentID', '')` will always find IDs). No checks for duplicate students, missing required fields, or malformed data.
- Files: `attendance-sync/attendance_to_aeries.py` (lines 94-122)
- Blocks: Silent data corruption possible if Firebase data is inconsistent.
- Recommendation: Add validation schema and error reporting before Aeries upload.

**No Audit Trail:**
- Problem: Once attendance is synced to Aeries, no record of what was synced or when. Only error logs exist.
- Files: All sync files
- Blocks: Cannot track sync success/failure history or audit compliance.
- Recommendation: Log successful syncs with record counts and checksums.

**No Rollback Capability:**
- Problem: If a sync is incorrect, no way to rollback Aeries state without manual correction.
- Files: `attendance-sync/upload_to_aeries.py`
- Blocks: Mistakes persist until manually fixed in Aeries.
- Recommendation: Consider backing up Aeries grid state before sync, or implement rollback endpoint.

## Test Coverage Gaps

**No Unit Tests:**
- What's not tested: CSV export logic, Firebase queries, status mapping, Aeries cell selection logic
- Files: `attendance-sync/attendance_to_aeries.py`, `attendance-sync/upload_to_aeries.py`
- Risk: Regressions in core logic (e.g., status mapping on lines 125-129) are only discovered in production.
- Priority: High - these are core business logic.

**No Integration Tests:**
- What's not tested: Full sync pipeline, Aeries login with real credentials, CSV upload flow
- Files: All files in `attendance-sync/`
- Risk: End-to-end failures only discovered when script runs manually.
- Priority: Medium - requires test Aeries account or mocking.

**Limited Selector Testing:**
- What's not tested: Whether CSS selectors work on current Aeries version
- Files: `attendance-sync/upload_to_aeries.py`
- Risk: Selectors break silently when Aeries UI updates.
- Priority: High - automation depends entirely on selectors.

**No Data Integrity Tests:**
- What's not tested: Whether exported CSV matches Firebase state, whether uploaded data matches CSV
- Files: `attendance-sync/attendance_to_aeries.py`, `attendance-sync/upload_to_aeries.py`
- Risk: Data corruption undetected until users notice discrepancies.
- Priority: High - data integrity is critical.

## Known Issues

**Aeries UI Selector Brittleness:**
- Symptoms: Frequent "Timeout" errors in sync_errors log, requiring manual re-runs
- Files: `attendance-sync/upload_to_aeries.py`
- Trigger: When Aeries UI changes or loads slowly, selectors fail to find elements
- Workaround: Run script manually with visible browser to debug; take screenshots for comparison
- Evidence: Error log shows multiple timeout failures on same selectors

**Browser Context Timeout on Slow Networks:**
- Symptoms: "Target page, context or browser has been closed" (sync_errors_2025-12.log line 10)
- Files: `attendance-sync/upload_to_aeries.py` (lines 43-216)
- Trigger: Network slowdown causes browser operations to timeout, process exits abruptly
- Workaround: Increase timeout values in code or improve network
- Evidence: sync_errors_2025-12.log, 2025-12-18 09:23:18

**Hard-Coded Path Breaks Cross-Machine Compatibility:**
- Symptoms: Script fails on any machine where user path is not `C:\Users\Jeremy\...`
- Files: `attendance-sync/attendance_to_aeries.py` (line 21)
- Trigger: Running on different machine or user account
- Workaround: Set FIREBASE_KEY_PATH env var explicitly
- Evidence: Path is Windows-absolute and user-specific

**Window Size Not Adaptive:**
- Symptoms: Grid layout may not fit in viewport (1600x900), causing scroll/selection issues
- Files: `attendance-sync/upload_to_aeries.py` (line 46)
- Trigger: On smaller displays or with different Aeries grid layout
- Workaround: Run on machine with sufficient resolution
- Evidence: Hard-coded viewport size suggests this was tuned for specific machine

**CSV Export Generates Rows for Absent Students (Potential Performance Issue):**
- Symptoms: CSV file grows large if many students are absent across many periods
- Files: `attendance-sync/attendance_to_aeries.py` (lines 110-121)
- Trigger: Any date with significant absences
- Workaround: None; this is by design to sync absence data
- Evidence: Code explicitly generates rows for absent students

---

*Concerns audit: 2026-02-04*
