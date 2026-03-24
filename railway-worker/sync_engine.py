"""
Per-teacher sync engine for the Railway cloud worker.

Adapts the existing upload_to_aeries.py (Playwright + checkbox logic) and
attendance_to_aeries.py (Firestore read patterns) to work in the cloud context.

Main entry point: sync_teacher(uid) -> dict
"""

import functools
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

from playwright.sync_api import sync_playwright

from firestore_client import (
    get_teacher_attendance,
    get_teacher_credentials,
    get_last_sync_time,
    get_latest_attendance_timestamp,
    is_sync_blocked,
    is_sync_enabled,
    write_sync_status,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Selector strategies — loaded from selectors.json at module import time
# ---------------------------------------------------------------------------

# Safety net: hardcoded defaults if selectors.json is missing
_DEFAULT_SELECTORS = {
    "student_cell": [
        "td[data-studentid='{student_id}']",           # Primary: data attribute
        "td:has-text('{student_id}')",                 # Fallback 1: text content
        "xpath=.//td[contains(@id, '{student_id}')]",  # Fallback 2: XPath id contains (relative)
    ],
    "absent_checkbox": [
        "span[data-cd='A'] input",                     # Primary: data-cd attribute
        "input[type='checkbox'][name*='Absent']",      # Fallback 1: name contains
        "span:has-text('A') input[type='checkbox']",   # Fallback 2: text label
    ],
    "tardy_checkbox": [
        "span[data-cd='T'] input",                     # Primary: data-cd attribute
        "input[type='checkbox'][name*='Tardy']",       # Fallback 1: name contains
        "span:has-text('T') input[type='checkbox']",   # Fallback 2: text label
    ],
    "period_dropdown": [
        "select",                                      # Primary: any select
        "select[id*='Period']",                        # Fallback 1: id contains Period
        "xpath=.//select[contains(@name, 'Period')]",  # Fallback 2: XPath name contains (relative)
    ],
}

def _load_selectors() -> dict:
    """Load selector strategies from selectors.json next to this file."""
    selectors_path = os.path.join(os.path.dirname(__file__), "selectors.json")
    try:
        with open(selectors_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logging.getLogger(__name__).debug(
            f"Loaded {len(data)} selector types from {selectors_path}"
        )
        return data
    except FileNotFoundError:
        logging.getLogger(__name__).error(
            f"selectors.json not found at {selectors_path} — using hardcoded defaults"
        )
        return _DEFAULT_SELECTORS
    except json.JSONDecodeError as exc:
        logging.getLogger(__name__).error(
            f"selectors.json is invalid JSON: {exc} — using hardcoded defaults"
        )
        return _DEFAULT_SELECTORS


SELECTOR_STRATEGIES = _load_selectors()

# Aeries URLs
LOGIN_URL = "https://adn.fjuhsd.org/Aeries.net/Login.aspx"
ATTENDANCE_URL = "https://adn.fjuhsd.org/Aeries.net/TeacherAttendance.aspx"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class SyncEngineError(Exception):
    """Raised for categorized sync errors."""
    def __init__(self, message: str, category: str):
        super().__init__(message)
        self.category = category


def find_element_with_fallback(page, element_type: str, format_args: dict, teacher_uid=None):
    """
    Locate an element using SELECTOR_STRATEGIES with automatic fallback.

    When all static selectors fail, attempts self-healing via Gemini LLM before
    raising SyncEngineError.

    Returns (locator, strategy_index).
    strategy_index == len(strategies) signals the element was found via healing.
    Raises SyncEngineError if all strategies AND self-healing fail.
    """
    if element_type not in SELECTOR_STRATEGIES:
        raise ValueError(f"Unknown element_type: {element_type}")

    strategies = SELECTOR_STRATEGIES[element_type]

    for index, template in enumerate(strategies):
        try:
            selector = template.format(**format_args)
            element = page.locator(selector)
            if element.count() > 0:
                if index > 0:
                    logger.warning(
                        f"Using fallback selector {index} for {element_type} — "
                        "Aeries UI may have changed"
                    )
                return element, index
        except Exception as exc:
            logger.debug(f"Selector strategy {index} failed for {element_type}: {exc}")
            continue

    # All static selectors failed — attempt self-healing
    logger.warning(f"All static selectors failed for {element_type} — attempting self-healing")
    try:
        from healer import attempt_heal
        healed_selector = attempt_heal(
            page=page,
            element_type=element_type,
            format_args=format_args,
            original_selectors=[t.format(**format_args) for t in strategies],
            teacher_uid=teacher_uid,
        )
        if healed_selector:
            element = page.locator(healed_selector)
            if element.count() > 0:
                logger.info(f"Self-healing succeeded for {element_type}: {healed_selector}")
                return element, len(strategies)  # index = len(strategies) signals "healed"
    except Exception as heal_exc:
        logger.error(f"Self-healing error for {element_type}: {heal_exc}")

    raise SyncEngineError(
        f"All selector strategies and self-healing failed for {element_type}",
        category="selector_broken",
    )


def categorize_error(exception: Exception, context: str = "") -> Tuple[str, str]:
    """
    Map an exception to (category, friendly_message).

    Categories match what the dashboard expects:
        credentials_invalid   — bad username/password
        aeries_unreachable    — network or timeout
        selector_broken       — Aeries page layout changed
        unknown               — catch-all
    """
    if isinstance(exception, SyncEngineError):
        category = exception.category
    else:
        category = "unknown"

    err_str = str(exception).lower()

    # Override category based on error text heuristics
    if "login" in err_str or "credentials" in context.lower() or "password" in err_str:
        if "timeout" not in err_str and "network" not in err_str:
            category = "credentials_invalid"
    if any(kw in err_str for kw in ("timeout", "net::", "connection", "unreachable", "dns")):
        category = "aeries_unreachable"
    if "selector" in err_str or category == "selector_broken":
        category = "selector_broken"

    messages = {
        "credentials_invalid": (
            "Your Aeries password may have changed. Please update it in Settings."
        ),
        "aeries_unreachable": (
            "Couldn't reach Aeries. We'll retry next cycle."
        ),
        "selector_broken": (
            "Aeries page changed and auto-repair failed — developer notified"
        ),
        "unknown": (
            "Sync encountered an unexpected error. We'll retry next cycle."
        ),
    }

    friendly = messages.get(category, messages["unknown"])
    return category, friendly


def retry_login(func):
    """
    Decorator: retry the wrapped function up to 3 times with 5 / 15 / 45 s backoff.
    Only applied to the login step.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        delays = [5, 15, 45]
        last_exc = None
        for attempt, delay in enumerate(delays, start=1):
            try:
                logger.info(f"Login attempt {attempt}/3")
                result = func(*args, **kwargs)
                if attempt > 1:
                    logger.info(f"Login succeeded on attempt {attempt}")
                return result
            except Exception as exc:
                last_exc = exc
                err_short = str(exc).split("\n")[0]
                if attempt < 3:
                    logger.warning(
                        f"Login attempt {attempt} failed: {err_short}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Login failed after 3 attempts: {err_short}")
        raise last_exc
    return wrapper


@retry_login
def _login_to_aeries(page, username: str, password: str):
    """
    Navigate to Aeries login page and authenticate.

    Raises on failure; the retry_login decorator handles retries.
    """
    page.goto(LOGIN_URL, timeout=30000)
    page.wait_for_selector('input[type="text"]', timeout=30000)
    page.fill('input[name="portalAccountUsername"], input[type="text"]', username)
    page.fill('input[name="portalAccountPassword"], input[type="password"]', password)
    page.click('button[type="submit"], input[type="submit"]')
    page.wait_for_url(lambda url: "Login.aspx" not in url, timeout=40000)
    logger.info("Login complete")


def _normalize_status(raw_status: str) -> str:
    """Map kiosk statuses to Aeries checkbox targets."""
    if raw_status in ("Late", "Truant", "Cut", "Late > 20"):
        return "Tardy"
    if raw_status in ("On Time", "Present"):
        return "Present"
    return raw_status  # 'Absent' passes through unchanged


# ---------------------------------------------------------------------------
# Main sync function
# ---------------------------------------------------------------------------

def sync_teacher(uid: str) -> dict:
    """
    Sync one teacher's attendance to Aeries.

    Returns a result dict:
        {
            'status':           'success' | 'failed' | 'skipped',
            'reason':           str (for 'skipped'),
            'periods_processed': int (for 'success'),
            'error':            str (for 'failed'),
            'unsyncable':       list (for 'success'),
        }

    Never raises — all exceptions are caught and reflected in the result dict
    and in the Firestore sync/status document.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info(f"[{uid}] Starting sync for {today}")

    # ------------------------------------------------------------------
    # Step 0a: Check if sync is enabled for this teacher
    # ------------------------------------------------------------------
    if not is_sync_enabled(uid):
        logger.info(f"[{uid}] Sync not enabled — skipping")
        return {"status": "skipped", "reason": "sync_not_enabled"}

    # ------------------------------------------------------------------
    # Step 0b: Check if sync is blocked (e.g. invalid credentials)
    # ------------------------------------------------------------------
    if is_sync_blocked(uid):
        logger.info(
            f"[{uid}] Sync blocked — credentials_invalid. "
            "Skipping until teacher updates credentials in Settings."
        )
        return {"status": "skipped", "reason": "credentials_blocked"}

    # ------------------------------------------------------------------
    # Step 1: Check for new data
    # ------------------------------------------------------------------
    try:
        last_sync_time = get_last_sync_time(uid)
        latest_ts = get_latest_attendance_timestamp(uid, today)

        if latest_ts is None:
            logger.info(f"[{uid}] No attendance data for today — skipping")
            return {"status": "skipped", "reason": "no_data"}

        if last_sync_time is not None:
            # Make sure both datetimes are timezone-aware before comparing
            if last_sync_time.tzinfo is None:
                last_sync_time = last_sync_time.replace(tzinfo=timezone.utc)
            if latest_ts.tzinfo is None:
                latest_ts = latest_ts.replace(tzinfo=timezone.utc)
            if last_sync_time >= latest_ts:
                logger.info(
                    f"[{uid}] No new data since last sync "
                    f"(last={last_sync_time.isoformat()}, latest={latest_ts.isoformat()}) — skipping"
                )
                return {"status": "skipped", "reason": "already_synced"}
    except Exception as exc:
        logger.error(f"[{uid}] Error during data-freshness check: {exc}")
        # Proceed anyway — better to sync than to silently skip on a check error

    # ------------------------------------------------------------------
    # Step 2: Get and decrypt credentials
    # ------------------------------------------------------------------
    creds = get_teacher_credentials(uid)
    if creds is None:
        msg = "No Aeries credentials configured. Please add your credentials in Settings."
        logger.warning(f"[{uid}] {msg}")
        write_sync_status(uid, "failed", error=msg, error_category="credentials_invalid")
        return {"status": "failed", "error": msg}

    try:
        fernet_key = os.environ.get("FERNET_KEY")
        if not fernet_key:
            raise EnvironmentError("FERNET_KEY environment variable is not set")

        from cryptography.fernet import Fernet, InvalidToken
        f = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)
        encrypted = creds["encryptedPassword"]
        # Fernet.decrypt accepts bytes; the stored value may be a str
        if isinstance(encrypted, str):
            encrypted = encrypted.encode()
        password = f.decrypt(encrypted).decode()
        username = creds["username"]
    except (ImportError, InvalidToken, Exception) as exc:
        msg = "Credential decryption failed. Please re-enter your password in Settings."
        logger.error(f"[{uid}] {msg} — {exc}")
        write_sync_status(uid, "failed", error=msg, error_category="credentials_invalid")
        return {"status": "failed", "error": msg}

    # ------------------------------------------------------------------
    # Step 3: Fetch attendance rows from Firestore
    # ------------------------------------------------------------------
    rows = get_teacher_attendance(uid, today)
    if not rows:
        logger.info(f"[{uid}] Attendance data disappeared between check and fetch — skipping")
        write_sync_status(uid, "skipped")
        return {"status": "skipped", "reason": "no_data_after_fetch"}

    # Group rows by period (mirrors read_attendance_csv in upload_to_aeries.py)
    period_groups: dict = {}
    for row in rows:
        period = row["period"]
        period_groups.setdefault(period, []).append(row)

    logger.info(
        f"[{uid}] Attendance fetched: {len(rows)} student-records across "
        f"{len(period_groups)} period(s)"
    )

    # ------------------------------------------------------------------
    # Step 4: Playwright upload to Aeries
    # ------------------------------------------------------------------
    unsyncable = []
    periods_processed = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, slow_mo=50)
            context = browser.new_context(viewport={"width": 1600, "height": 900})
            page = context.new_page()

            try:
                # --- LOGIN ---
                try:
                    _login_to_aeries(page, username, password)
                except Exception as login_exc:
                    # Distinguish credential failures from network failures
                    if "Login.aspx" in page.url:
                        category, friendly = "credentials_invalid", (
                            "Your Aeries password may have changed. Please update it in Settings."
                        )
                    else:
                        category, friendly = categorize_error(login_exc, context="login")
                    logger.error(f"[{uid}] Login failed ({category}): {login_exc}")
                    write_sync_status(uid, "failed", error=friendly, error_category=category)
                    return {"status": "failed", "error": friendly, "category": category}

                # --- NAVIGATE TO ATTENDANCE ---
                logger.info(f"[{uid}] Navigating to TeacherAttendance.aspx")
                page.goto(ATTENDANCE_URL, timeout=60000)
                try:
                    page.wait_for_selector("select", timeout=30000)
                    logger.info(f"[{uid}] Attendance page loaded")
                except Exception:
                    logger.warning(f"[{uid}] Page load wait timed out — continuing anyway")

                # --- PROCESS EACH PERIOD ---
                for period, students in period_groups.items():
                    logger.info(f"[{uid}] Period {period}: {len(students)} student(s)")
                    updates_count = 0

                    # Select the period in the dropdown
                    try:
                        target_select = None
                        target_option_label = None
                        selects = page.locator("select").all()
                        for sel in selects:
                            if not sel.is_visible():
                                continue
                            options = sel.locator("option").all_inner_texts()
                            for opt in options:
                                if f"Period {period}" in opt or opt.strip().startswith(f"{period} -"):
                                    target_select = sel
                                    target_option_label = opt
                                    break
                            if target_select:
                                break

                        if target_select:
                            current_text = target_select.locator("option:checked").inner_text()
                            if target_option_label not in current_text:
                                logger.info(f"[{uid}] Switching to: {target_option_label}")
                                target_select.select_option(label=target_option_label)
                                page.wait_for_timeout(3000)
                            else:
                                logger.info(f"[{uid}] Already on {target_option_label}")
                        else:
                            logger.warning(f"[{uid}] Period {period}: Dropdown not found — skipping")
                            continue
                    except Exception as exc:
                        logger.warning(f"[{uid}] Period {period}: Error selecting dropdown — {exc}")
                        continue

                    # Click "All Remaining Students Are Present"
                    try:
                        all_present_btn = page.locator(
                            "a, input, button"
                        ).filter(has_text="All Remaining Students Are Present").first
                        if all_present_btn.is_visible():
                            all_present_btn.click()
                            logger.info(f"[{uid}] Clicked 'All Remaining Students Are Present'")
                            try:
                                page.keyboard.press("Enter")
                            except Exception:
                                pass
                            page.wait_for_timeout(1000)
                    except Exception as exc:
                        logger.debug(
                            f"[{uid}] Period {period}: 'All Present' button not found — {exc}"
                        )

                    # --- PROCESS EACH STUDENT ---
                    for student in students:
                        student_id = student.get("student_id", "")
                        raw_status = student.get("status", "Absent")

                        if not student_id:
                            logger.warning(f"[{uid}] Skipping student with no student_id")
                            continue

                        # Normalize app status to Aeries checkbox target
                        status = _normalize_status(raw_status)

                        try:
                            # Find the student's cell
                            cell, _ = find_element_with_fallback(
                                page, "student_cell", {"student_id": student_id},
                                teacher_uid=uid,
                            )
                            if cell.count() == 0:
                                logger.warning(f"[{uid}] Student {student_id} cell not found")
                                unsyncable.append({
                                    "studentId": student_id,
                                    "period": period,
                                    "reason": "student_not_in_grid",
                                })
                                continue

                            # Get parent row
                            row = cell.locator("xpath=..")

                            # Check if attendance is locked
                            locked = row.locator("span[id$='lblLocked']")
                            if locked.count() > 0 and locked.is_visible():
                                locked_text = locked.inner_text().strip()
                                logger.info(
                                    f"[{uid}] Student {student_id}: Locked as '{locked_text}' — skipping"
                                )
                                continue

                            # Find checkboxes within this row
                            absent_box, _ = find_element_with_fallback(
                                row, "absent_checkbox", {}, teacher_uid=uid
                            )
                            tardy_box, _ = find_element_with_fallback(
                                row, "tardy_checkbox", {}, teacher_uid=uid
                            )

                            if absent_box.count() == 0 or tardy_box.count() == 0:
                                logger.warning(
                                    f"[{uid}] Student {student_id}: Checkboxes not found"
                                )
                                unsyncable.append({
                                    "studentId": student_id,
                                    "period": period,
                                    "reason": "checkboxes_not_found",
                                })
                                continue

                            was_absent = absent_box.is_checked()
                            was_tardy = tardy_box.is_checked()

                            # Apply checkbox logic (mirrors upload_to_aeries.py exactly)
                            if status == "Absent":
                                if not was_absent:
                                    logger.info(
                                        f"[{uid}] Student {student_id}: Marking ABSENT"
                                    )
                                    absent_box.check()
                                    page.wait_for_timeout(500)
                                    updates_count += 1
                                if was_tardy:
                                    tardy_box.uncheck()
                                    page.wait_for_timeout(500)

                            elif status == "Tardy":
                                if not was_tardy:
                                    logger.info(
                                        f"[{uid}] Student {student_id}: Marking TARDY "
                                        f"(was '{raw_status}')"
                                    )
                                    tardy_box.check()
                                    page.wait_for_timeout(500)
                                    updates_count += 1
                                if was_absent:
                                    absent_box.uncheck()
                                    page.wait_for_timeout(500)

                            elif status == "Present":
                                if was_absent:
                                    logger.info(
                                        f"[{uid}] Student {student_id}: Correcting to PRESENT "
                                        "(was Absent)"
                                    )
                                    absent_box.uncheck()
                                    page.wait_for_timeout(500)
                                    updates_count += 1
                                if was_tardy:
                                    logger.info(
                                        f"[{uid}] Student {student_id}: Correcting to PRESENT "
                                        "(was Tardy)"
                                    )
                                    tardy_box.uncheck()
                                    page.wait_for_timeout(500)
                                    updates_count += 1

                        except SyncEngineError as exc:
                            # Selector failure — log and continue
                            logger.warning(
                                f"[{uid}] Student {student_id} Period {period}: "
                                f"Selector error — {exc}"
                            )
                            unsyncable.append({
                                "studentId": student_id,
                                "period": period,
                                "reason": exc.category,
                            })
                        except Exception as exc:
                            error_short = str(exc).split("\n")[0]
                            logger.error(
                                f"[{uid}] Student {student_id} Period {period}: "
                                f"Unexpected error — {error_short}"
                            )
                            unsyncable.append({
                                "studentId": student_id,
                                "period": period,
                                "reason": "unexpected_error",
                            })
                        # Individual student failure does NOT break the loop

                    logger.info(
                        f"[{uid}] Period {period} complete. "
                        f"Updates: {updates_count}, Unsyncable: "
                        f"{sum(1 for u in unsyncable if u['period'] == period)}"
                    )
                    periods_processed += 1

                    # Save after each period
                    if updates_count > 0:
                        try:
                            save_btn = page.locator(
                                "input[value='Save'], button:has-text('Save')"
                            ).first
                            save_btn.scroll_into_view_if_needed(timeout=5000)
                            save_btn.click()
                            logger.info(f"[{uid}] Saved Period {period}")
                            page.wait_for_timeout(2000)
                        except Exception as save_exc:
                            logger.error(
                                f"[{uid}] Period {period}: Save failed — {save_exc}"
                            )
                            raise SyncEngineError(
                                f"Failed to save Period {period}: {save_exc}",
                                category="unknown",
                            )

            finally:
                browser.close()

    except SyncEngineError as exc:
        category, friendly = categorize_error(exc, context="playwright_upload")
        logger.error(f"[{uid}] Sync failed ({category}): {exc}")
        write_sync_status(uid, "failed", error=friendly, error_category=category)
        return {"status": "failed", "error": friendly, "category": category}
    except Exception as exc:
        category, friendly = categorize_error(exc, context="playwright_upload")
        logger.error(f"[{uid}] Unexpected sync error ({category}): {exc}")
        write_sync_status(uid, "failed", error=friendly, error_category=category)
        return {"status": "failed", "error": friendly, "category": category}

    # ------------------------------------------------------------------
    # Step 5: Write success status to Firestore
    # ------------------------------------------------------------------
    if unsyncable:
        logger.warning(
            f"[{uid}] {len(unsyncable)} student(s) could not be synced: "
            + ", ".join(f"{u['studentId']} P{u['period']}" for u in unsyncable)
        )

    write_sync_status(
        uid,
        "success",
        periods_processed=periods_processed,
        unsyncable=unsyncable if unsyncable else None,
    )
    logger.info(
        f"[{uid}] Sync complete: {periods_processed} period(s) processed, "
        f"{len(unsyncable)} unsyncable student(s)"
    )
    return {
        "status": "success",
        "periods_processed": periods_processed,
        "unsyncable": unsyncable,
    }
