"""
Sync utilities for retry logic and error logging
"""

import functools
import logging
import time
import json
import os
from datetime import datetime
from typing import Optional, Callable, Any, Tuple

# Configure logging
logger = logging.getLogger(__name__)


# Failed students tracking file
FAILED_STUDENTS_FILE = "failed_students.json"


# Selector strategies with fallback options for Aeries UI resilience
SELECTOR_STRATEGIES = {
    'student_cell': [
        "td[data-studentid='{student_id}']",           # Primary: data attribute
        "td:has-text('{student_id}')",                 # Fallback 1: text content
        "//td[contains(@id, '{student_id}')]",         # Fallback 2: XPath id contains
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
        "//select[contains(@name, 'Period')]",         # Fallback 2: XPath name contains
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
            f"error={error[:50]}..."
        )
    except Exception as e:
        logger.error(f"Failed to write to error log: {e}")
