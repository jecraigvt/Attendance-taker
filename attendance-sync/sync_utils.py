"""
Sync utilities for retry logic and error logging
"""

import functools
import logging
import time
import json
import os
import csv
from datetime import datetime
from typing import Optional, Callable, Any, Tuple, List, Dict

# Configure logging
logger = logging.getLogger(__name__)


# Failed students tracking file
FAILED_STUDENTS_FILE = "failed_students.json"


# Selector strategies with fallback options for Aeries UI resilience
SELECTOR_STRATEGIES = {
    'student_cell': [
        "td[data-studentid='{student_id}']",           # Primary: data attribute
        "td:has-text('{student_id}')",                 # Fallback 1: text content
        "xpath=.//td[contains(@id, '{student_id}')]",  # Fallback 2: XPath id contains (relative)
    ],
    'absent_checkbox': [
        "span[data-cd='A'] input",                     # Primary: data-cd attribute
        "input[type='checkbox'][name*='Absent']",      # Fallback 1: name contains
        "span:has-text('A') input[type='checkbox']",   # Fallback 2: text label
    ],
    'tardy_checkbox': [
        "span[data-cd='T'] input",                     # Primary: data-cd attribute
        "input[type='checkbox'][name*='Tardy']",       # Fallback 1: name contains
        "span:has-text('T') input[type='checkbox']",   # Fallback 2: text label
    ],
    'period_dropdown': [
        "select",                                      # Primary: any select
        "select[id*='Period']",                        # Fallback 1: id contains Period
        "xpath=.//select[contains(@name, 'Period')]",  # Fallback 2: XPath name contains (relative)
    ],
}


class SyncError(Exception):
    """
    Custom exception for sync failures with full context
    """
    def __init__(
        self,
        message: str,
        error_type: str = 'unknown',
        student_id: Optional[str] = None,
        period: Optional[str] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.student_id = student_id
        self.period = period
        self.original_exception = original_exception
        self.timestamp = datetime.now()

    def __str__(self):
        parts = [self.message]
        if self.error_type:
            parts.append(f"type={self.error_type}")
        if self.student_id:
            parts.append(f"student_id={self.student_id}")
        if self.period:
            parts.append(f"period={self.period}")
        return f"SyncError({', '.join(parts)})"


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 5,
    backoff_multiplier: float = 3
) -> Callable:
    """
    Decorator that retries a function with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 5)
        backoff_multiplier: Multiplier for exponential backoff (default: 3)

    Delays between retries: 5s, 15s, 45s (with defaults)

    Example:
        @retry_with_backoff(max_retries=3, base_delay=5)
        def login_to_aeries(page, username, password):
            # login logic here
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"Attempt {attempt}/{max_retries} for {func.__name__}")
                    result = func(*args, **kwargs)
                    if attempt > 1:
                        logger.info(f"{func.__name__} succeeded on attempt {attempt}")
                    return result

                except Exception as e:
                    last_exception = e
                    error_msg = str(e).split('\n')[0]  # First line only

                    if attempt < max_retries:
                        delay = base_delay * (backoff_multiplier ** (attempt - 1))
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt}/{max_retries}): {error_msg}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        # Final failure
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {error_msg}"
                        )

            # If we get here, all retries failed
            raise SyncError(
                message=f"Failed after {max_retries} attempts: {str(last_exception)}",
                error_type='retry_exhausted',
                original_exception=last_exception
            )

        return wrapper
    return decorator


def find_element_with_fallback(page, element_type: str, format_args: dict) -> Tuple[Any, int]:
    """
    Find element using fallback selector strategies

    Args:
        page: Playwright page or locator object
        element_type: Key from SELECTOR_STRATEGIES dict
        format_args: Dict of values for string formatting (e.g., {'student_id': '123456'})

    Returns:
        Tuple of (element, strategy_index) where strategy_index is 0 for primary, 1+ for fallbacks

    Raises:
        SyncError: If all selector strategies fail
    """
    if element_type not in SELECTOR_STRATEGIES:
        raise ValueError(f"Unknown element_type: {element_type}")

    strategies = SELECTOR_STRATEGIES[element_type]

    for index, selector_template in enumerate(strategies):
        try:
            # Format selector with provided args
            selector = selector_template.format(**format_args)

            # Try to locate element
            element = page.locator(selector)

            # Check if element exists
            if element.count() > 0:
                # Log warning if using fallback
                if index > 0:
                    logger.warning(
                        f"Using fallback selector {index} for {element_type} - Aeries UI may have changed"
                    )

                    # Also log to alerts file for admin visibility
                    _log_selector_alert(element_type, index, selector)

                return (element, index)

        except Exception as e:
            # Continue to next strategy
            logger.debug(f"Selector strategy {index} failed for {element_type}: {e}")
            continue

    # All strategies failed
    raise SyncError(
        message=f"All selector strategies failed for {element_type}",
        error_type='selector_failed'
    )


def _log_selector_alert(element_type: str, fallback_index: int, selector_used: str) -> None:
    """
    Log selector fallback usage to monthly alert file

    Args:
        element_type: Type of element (from SELECTOR_STRATEGIES keys)
        fallback_index: Which fallback was used (1, 2, etc.)
        selector_used: The actual selector string that worked
    """
    alert_file = f"selector_alerts_{datetime.now().strftime('%Y-%m')}.log"

    alert_entry = {
        "timestamp": datetime.now().isoformat(),
        "element_type": element_type,
        "fallback_index": fallback_index,
        "selector_used": selector_used
    }

    try:
        with open(alert_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(alert_entry) + '\n')
    except Exception as e:
        logger.error(f"Failed to write selector alert: {e}")


def load_failed_students() -> dict:
    """
    Load failed students from previous sync cycle

    Returns:
        Dict with structure {"date": "YYYY-MM-DD", "students": [{"student_id": "...", "period": "...", "error": "...", "timestamp": "..."}]}
        Returns empty structure if file doesn't exist or date doesn't match today
    """
    today = datetime.now().strftime('%Y-%m-%d')

    try:
        if not os.path.exists(FAILED_STUDENTS_FILE):
            return {"date": today, "students": []}

        with open(FAILED_STUDENTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # If date doesn't match today, return empty (old failures)
        if data.get('date') != today:
            logger.info(f"Failed students file is from {data.get('date')}, not today - starting fresh")
            return {"date": today, "students": []}

        logger.info(f"Loaded {len(data.get('students', []))} failed students from previous sync")
        return data

    except Exception as e:
        logger.error(f"Failed to load failed students file: {e}")
        return {"date": today, "students": []}


def save_failed_students(failed_list: list) -> None:
    """
    Save failed students to JSON file for retry in next sync cycle

    Args:
        failed_list: List of dicts with student_id, period, error, timestamp
    """
    today = datetime.now().strftime('%Y-%m-%d')

    data = {
        "date": today,
        "students": failed_list
    }

    try:
        with open(FAILED_STUDENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved {len(failed_list)} failed students for retry")

    except Exception as e:
        logger.error(f"Failed to save failed students file: {e}")


def clear_failed_students() -> None:
    """
    Clear the failed students file (all succeeded or end of day)
    """
    try:
        if os.path.exists(FAILED_STUDENTS_FILE):
            os.remove(FAILED_STUDENTS_FILE)
            logger.info("Cleared failed students file")
    except Exception as e:
        logger.error(f"Failed to clear failed students file: {e}")


# Audit log file template (daily files)
AUDIT_LOG_FILE_TEMPLATE = "sync_audit_{date}.log"


def log_sync_intent(
    student_id: str,
    period: str,
    intended_status: str,
    source_status: str,
    timestamp: datetime
) -> None:
    """
    Log sync intent BEFORE checkbox interaction

    Args:
        student_id: Student ID being processed
        period: Period number
        intended_status: What we plan to set (Absent, Tardy, Present)
        source_status: Original status from Firebase/CSV
        timestamp: When the intent was logged

    Log file format: sync_audit_{YYYY-MM-DD}.log (daily file)
    Each line is a JSON object for easy parsing
    """
    log_file = AUDIT_LOG_FILE_TEMPLATE.format(date=timestamp.strftime('%Y-%m-%d'))

    log_entry = {
        "type": "intent",
        "timestamp": timestamp.isoformat(),
        "student_id": student_id,
        "period": period,
        "intended_status": intended_status,
        "source_status": source_status
    }

    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        logger.error(f"Failed to write audit intent log: {e}")


def log_sync_action(
    student_id: str,
    period: str,
    action_taken: str,
    checkbox_state: dict,
    success: bool,
    timestamp: datetime
) -> None:
    """
    Log sync action AFTER checkbox interaction

    Args:
        student_id: Student ID being processed
        period: Period number
        action_taken: What we did (checked_absent, unchecked_absent, checked_tardy,
                      unchecked_tardy, no_change, skipped_locked, corrected_to_present, failed)
        checkbox_state: Final state {'absent': bool/None, 'tardy': bool/None}
        success: Whether the action completed without error
        timestamp: When the action was logged

    Log file format: sync_audit_{YYYY-MM-DD}.log (daily file)
    Each line is a JSON object for easy parsing
    """
    log_file = AUDIT_LOG_FILE_TEMPLATE.format(date=timestamp.strftime('%Y-%m-%d'))

    log_entry = {
        "type": "action",
        "timestamp": timestamp.isoformat(),
        "student_id": student_id,
        "period": period,
        "action_taken": action_taken,
        "checkbox_state": checkbox_state,
        "success": success
    }

    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        logger.error(f"Failed to write audit action log: {e}")


def get_audit_entries(date_str: str) -> list:
    """
    Get all audit log entries for a given date

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        List of parsed JSON objects from the audit log
        Returns empty list if file doesn't exist
    """
    log_file = AUDIT_LOG_FILE_TEMPLATE.format(date=date_str)

    if not os.path.exists(log_file):
        return []

    entries = []
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping malformed audit log line: {e}")
    except Exception as e:
        logger.error(f"Failed to read audit log file: {e}")

    return entries


def get_sync_run_entries(date_str: str, run_start_timestamp: str) -> list:
    """
    Get audit log entries from a specific sync run

    Args:
        date_str: Date string in YYYY-MM-DD format
        run_start_timestamp: ISO format timestamp of when the sync run started

    Returns:
        List of parsed JSON objects where timestamp >= run_start_timestamp
        Useful for generating verification report for just the current run
    """
    all_entries = get_audit_entries(date_str)

    # Filter entries where timestamp >= run_start_timestamp
    run_entries = [
        entry for entry in all_entries
        if entry.get('timestamp', '') >= run_start_timestamp
    ]

    return run_entries


def log_sync_failure(
    student_id: str,
    period: str,
    error: str,
    attempt_count: int,
    timestamp: datetime
) -> None:
    """
    Log a sync failure to persistent error log file

    Args:
        student_id: Student ID that failed
        period: Period number
        error: Error message
        attempt_count: Number of attempts made
        timestamp: When the error occurred

    Log file format: sync_errors_{YYYY-MM}.log
    Each line is a JSON object for easy parsing
    """
    log_file = f"sync_errors_{timestamp.strftime('%Y-%m')}.log"

    log_entry = {
        "timestamp": timestamp.isoformat(),
        "student_id": student_id,
        "period": period,
        "error": error,
        "attempts": attempt_count
    }

    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')

        logger.error(
            f"Logged failure: student_id={student_id}, period={period}, "
            f"error={error[:50]}{'...' if len(error) > 50 else ''}"
        )
    except Exception as e:
        logger.error(f"Failed to write to error log: {e}")


# Verification report file template
VERIFICATION_REPORT_TEMPLATE = "sync_verification_{timestamp}"


def generate_verification_report(
    csv_filepath: str,
    run_start_timestamp: datetime,
    output_dir: str = "."
) -> Dict:
    """
    Generate verification report comparing CSV source data against audit log

    Args:
        csv_filepath: Path to the CSV file that was synced (Firebase export)
        run_start_timestamp: datetime object of when the sync run started
        output_dir: Directory to write report files (default: current dir)

    Returns:
        Dict with summary, by_period breakdown, and discrepancies list

    The CSV file IS the authoritative Firebase export - comparing CSV to audit log
    IS comparing Firebase source data to sync actions.
    """
    report_timestamp = datetime.now()
    timestamp_str = report_timestamp.strftime('%Y-%m-%d_%H%M%S')
    date_str = run_start_timestamp.strftime('%Y-%m-%d')
    run_start_iso = run_start_timestamp.isoformat()

    # Read CSV source data
    csv_students = _read_csv_students(csv_filepath)

    # Get audit log entries for this sync run
    audit_entries = get_sync_run_entries(date_str, run_start_iso)

    # Build lookup dicts from audit entries
    intent_lookup = {}  # (student_id, period) -> intent entry
    action_lookup = {}  # (student_id, period) -> action entry

    for entry in audit_entries:
        key = (entry.get('student_id'), entry.get('period'))
        if entry.get('type') == 'intent':
            intent_lookup[key] = entry
        elif entry.get('type') == 'action':
            action_lookup[key] = entry

    # Normalization map: app statuses -> Aeries statuses (must match upload_to_aeries.py)
    def _normalize_status(raw):
        if raw in ['Late', 'Truant', 'Cut', 'Late > 20']:
            return 'Tardy'
        elif raw in ['On Time', 'Present']:
            return 'Present'
        elif raw == 'Absent':
            return 'Absent'
        return raw

    # Compare CSV against audit log
    discrepancies = []
    by_period = {}
    total_synced = 0
    total_failed = 0
    total_skipped_locked = 0

    for student in csv_students:
        student_id = student['student_id']
        period = student['period']
        expected_status = student['status']
        key = (student_id, period)

        # Initialize period stats
        if period not in by_period:
            by_period[period] = {'synced': 0, 'failed': 0, 'locked': 0}

        intent = intent_lookup.get(key)
        action = action_lookup.get(key)

        # Check for discrepancies
        if not intent:
            # No intent logged - processing was skipped entirely
            discrepancies.append({
                'type': 'missing_intent',
                'student_id': student_id,
                'period': period,
                'expected_status': expected_status,
                'actual': 'No intent logged'
            })
        elif not action:
            # Intent logged but no action - processing started but didn't complete
            discrepancies.append({
                'type': 'missing_action',
                'student_id': student_id,
                'period': period,
                'expected_status': expected_status,
                'actual': 'No action logged'
            })
        else:
            # Check if intent status matches expected (normalize CSV status first)
            intent_status = intent.get('intended_status', '')
            normalized_expected = _normalize_status(expected_status)
            if intent_status.lower() != normalized_expected.lower():
                # Real status mismatch between CSV and intent
                discrepancies.append({
                    'type': 'status_mismatch',
                    'student_id': student_id,
                    'period': period,
                    'expected_status': expected_status,
                    'actual': f'Intent logged as {intent_status}'
                })

            # Check action success
            action_taken = action.get('action_taken', '')
            success = action.get('success', False)

            if action_taken == 'skipped_locked':
                total_skipped_locked += 1
                by_period[period]['locked'] += 1
            elif action_taken == 'failed' or not success:
                total_failed += 1
                by_period[period]['failed'] += 1
                discrepancies.append({
                    'type': 'action_failed',
                    'student_id': student_id,
                    'period': period,
                    'expected_status': expected_status,
                    'actual': f'Action failed: {action_taken}'
                })
            else:
                total_synced += 1
                by_period[period]['synced'] += 1

    # Build report dict
    report = {
        'timestamp': report_timestamp.isoformat(),
        'csv_file': os.path.basename(csv_filepath),
        'summary': {
            'total_students': len(csv_students),
            'total_synced': total_synced,
            'total_failed': total_failed,
            'total_skipped_locked': total_skipped_locked,
            'total_discrepancies': len(discrepancies)
        },
        'by_period': by_period,
        'discrepancies': discrepancies
    }

    # Write report files
    _write_verification_report_txt(report, output_dir, timestamp_str)
    _write_verification_report_json(report, output_dir, timestamp_str)

    logger.info(f"Verification report generated: sync_verification_{timestamp_str}.txt/.json")

    return report


def _read_csv_students(csv_filepath: str) -> List[Dict]:
    """
    Read student records from CSV file

    Args:
        csv_filepath: Path to CSV file

    Returns:
        List of dicts with student_id, period, status
    """
    students = []

    try:
        with open(csv_filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Handle different possible column names
                student_id = row.get('student_id') or row.get('StudentID') or row.get('id')
                period = row.get('period') or row.get('Period')
                status = row.get('status') or row.get('Status')

                if student_id and period and status:
                    students.append({
                        'student_id': str(student_id),
                        'period': str(period),
                        'status': status
                    })
    except Exception as e:
        logger.error(f"Failed to read CSV file {csv_filepath}: {e}")
        raise

    if not students:
        logger.warning(f"No student records found in CSV file {csv_filepath}")

    return students


def _write_verification_report_txt(report: Dict, output_dir: str, timestamp_str: str) -> None:
    """
    Write human-readable verification report to text file

    Args:
        report: Report dict
        output_dir: Directory to write to
        timestamp_str: Timestamp string for filename
    """
    filepath = os.path.join(output_dir, f"sync_verification_{timestamp_str}.txt")

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("SYNC VERIFICATION REPORT\n")
            f.write(f"Generated: {report['timestamp']}\n")
            f.write(f"CSV File: {report['csv_file']}\n")
            f.write("=" * 70 + "\n\n")

            # Summary section
            summary = report['summary']
            f.write("SUMMARY\n")
            f.write("-" * 70 + "\n")
            f.write(f"  Total students in CSV:    {summary['total_students']}\n")
            f.write(f"  Successfully synced:      {summary['total_synced']}\n")
            f.write(f"  Failed:                   {summary['total_failed']}\n")
            f.write(f"  Skipped (locked):         {summary['total_skipped_locked']}\n")
            f.write(f"  Discrepancies found:      {summary['total_discrepancies']}\n")
            f.write("\n")

            # By Period section
            f.write("BY PERIOD\n")
            f.write("-" * 70 + "\n")
            for period in sorted(report['by_period'].keys(), key=lambda x: int(x) if x.isdigit() else 999):
                stats = report['by_period'][period]
                f.write(f"  Period {period}: {stats['synced']} synced, {stats['failed']} failed, {stats['locked']} locked\n")
            f.write("\n")

            # Discrepancies section
            if report['discrepancies']:
                f.write("DISCREPANCIES\n")
                f.write("-" * 70 + "\n")
                for i, disc in enumerate(report['discrepancies'], 1):
                    f.write(f"  {i}. [{disc['type']}] Student {disc['student_id']} Period {disc['period']}\n")
                    f.write(f"     Expected: {disc['expected_status']}\n")
                    f.write(f"     Actual: {disc['actual']}\n")
                    f.write("\n")
            else:
                f.write("DISCREPANCIES\n")
                f.write("-" * 70 + "\n")
                f.write("  No discrepancies found. All students synced as expected.\n")

            f.write("\n" + "=" * 70 + "\n")
            f.write("END OF REPORT\n")
            f.write("=" * 70 + "\n")

    except Exception as e:
        logger.error(f"Failed to write verification report TXT: {e}")


def _write_verification_report_json(report: Dict, output_dir: str, timestamp_str: str) -> None:
    """
    Write verification report to JSON file

    Args:
        report: Report dict
        output_dir: Directory to write to
        timestamp_str: Timestamp string for filename
    """
    filepath = os.path.join(output_dir, f"sync_verification_{timestamp_str}.json")

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write verification report JSON: {e}")


def generate_daily_summary(date_str: str, output_dir: str = ".") -> Dict:
    """
    Generate end-of-day summary report aggregating all sync runs

    Args:
        date_str: Date in YYYY-MM-DD format
        output_dir: Directory to write report (default: current)

    Returns:
        Dict with daily totals and breakdown by sync run
    """
    # 1. Read all audit entries for the date
    audit_entries = get_audit_entries(date_str)

    # 2. Read sync_errors file and filter to today
    year_month = date_str[:7]  # YYYY-MM
    error_log_file = f"sync_errors_{year_month}.log"
    retries_from_error_log = 0

    if os.path.exists(error_log_file):
        try:
            with open(error_log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            if entry.get('timestamp', '').startswith(date_str):
                                retries_from_error_log += 1
                        except json.JSONDecodeError:
                            # Handle non-JSON format lines
                            if date_str in line:
                                retries_from_error_log += 1
        except Exception as e:
            logger.warning(f"Failed to read error log: {e}")

    # 3. Read failed_students.json for unresolved failures
    unresolved_failures = []
    if os.path.exists(FAILED_STUDENTS_FILE):
        try:
            with open(FAILED_STUDENTS_FILE, 'r', encoding='utf-8') as f:
                failed_data = json.load(f)
                if failed_data.get('date') == date_str:
                    unresolved_failures = failed_data.get('students', [])
        except Exception as e:
            logger.warning(f"Failed to read failed students file: {e}")

    # 4. Aggregate totals from audit entries
    intents = [e for e in audit_entries if e.get('type') == 'intent']
    actions = [e for e in audit_entries if e.get('type') == 'action']

    # Unique student_id + period combinations from intents
    unique_student_periods = set()
    for intent in intents:
        key = (intent.get('student_id'), intent.get('period'))
        unique_student_periods.add(key)
    total_students_processed = len(unique_student_periods)

    # Count distinct time windows (by truncating timestamp to minute)
    sync_run_times = set()
    for entry in audit_entries:
        ts = entry.get('timestamp', '')
        if ts:
            # Truncate to 5-minute window to group entries from same sync run
            minute_ts = ts[:16]  # YYYY-MM-DDTHH:MM
            sync_run_times.add(minute_ts)
    total_sync_runs = len(sync_run_times)

    # Count action outcomes
    total_successful_actions = 0
    total_failed_actions = 0
    total_skipped_locked = 0

    for action in actions:
        action_taken = action.get('action_taken', '')
        success = action.get('success', False)

        if action_taken == 'skipped_locked':
            total_skipped_locked += 1
        elif action_taken == 'failed' or not success:
            total_failed_actions += 1
        else:
            total_successful_actions += 1

    # 5. Build summary
    summary = {
        'date': date_str,
        'total_students_processed': total_students_processed,
        'total_sync_runs': total_sync_runs,
        'total_successful_actions': total_successful_actions,
        'total_failed_actions': total_failed_actions,
        'total_skipped_locked': total_skipped_locked,
        'total_retries_from_error_log': retries_from_error_log,
        'unresolved_failures': unresolved_failures
    }

    # Write summary files
    _write_daily_summary_txt(summary, output_dir, date_str)
    _write_daily_summary_json(summary, output_dir, date_str)

    logger.info(f"Daily summary generated: daily_summary_{date_str}.txt/.json")

    return summary


def _write_daily_summary_txt(summary: Dict, output_dir: str, date_str: str) -> None:
    """
    Write human-readable daily summary to text file

    Args:
        summary: Summary dict
        output_dir: Directory to write to
        date_str: Date string for filename
    """
    filepath = os.path.join(output_dir, f"daily_summary_{date_str}.txt")

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("DAILY SYNC SUMMARY\n")
            f.write(f"Date: {date_str}\n")
            f.write("=" * 70 + "\n\n")

            f.write("TOTALS\n")
            f.write("-" * 70 + "\n")
            f.write(f"  Total sync runs:           {summary['total_sync_runs']}\n")
            f.write(f"  Students processed:        {summary['total_students_processed']}\n")
            f.write(f"  Successful actions:        {summary['total_successful_actions']}\n")
            f.write(f"  Failed actions:            {summary['total_failed_actions']}\n")
            f.write(f"  Skipped (locked):          {summary['total_skipped_locked']}\n")
            f.write(f"  Retries (from error log):  {summary['total_retries_from_error_log']}\n")
            f.write("\n")

            # Unresolved failures section
            unresolved = summary.get('unresolved_failures', [])
            if unresolved:
                f.write("UNRESOLVED FAILURES\n")
                f.write("-" * 70 + "\n")
                for i, failure in enumerate(unresolved, 1):
                    f.write(f"  {i}. Student {failure.get('student_id')} Period {failure.get('period')}\n")
                    f.write(f"     Error: {failure.get('error', 'Unknown')}\n")
                f.write("\n")
            else:
                f.write("UNRESOLVED FAILURES\n")
                f.write("-" * 70 + "\n")
                f.write("  None - all students synced successfully.\n")
                f.write("\n")

            f.write("=" * 70 + "\n")
            f.write("END OF DAILY SUMMARY\n")
            f.write("=" * 70 + "\n")

    except Exception as e:
        logger.error(f"Failed to write daily summary TXT: {e}")


def _write_daily_summary_json(summary: Dict, output_dir: str, date_str: str) -> None:
    """
    Write daily summary to JSON file

    Args:
        summary: Summary dict
        output_dir: Directory to write to
        date_str: Date string for filename
    """
    filepath = os.path.join(output_dir, f"daily_summary_{date_str}.json")

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write daily summary JSON: {e}")
