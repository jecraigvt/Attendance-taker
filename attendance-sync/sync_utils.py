"""
Sync utilities for retry logic and error logging
"""

import functools
import logging
import time
import json
from datetime import datetime
from typing import Optional, Callable, Any

# Configure logging
logger = logging.getLogger(__name__)


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
