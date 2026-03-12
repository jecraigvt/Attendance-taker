"""
UI Automation for Aeries Attendance (Grid View) - Adjusted for Speed
"""

from playwright.sync_api import sync_playwright
from datetime import datetime
import csv
import os
import logging
from sync_utils import (
    retry_with_backoff, SyncError, log_sync_failure,
    find_element_with_fallback, SELECTOR_STRATEGIES,
    load_failed_students, save_failed_students, clear_failed_students,
    log_sync_intent, log_sync_action
)

logger = logging.getLogger(__name__)

def read_attendance_csv(csv_filepath):
    """Reads the CSV and groups data by Period"""
    attendance_data = {}

    with open(csv_filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            period = row['Period']
            if period not in attendance_data:
                attendance_data[period] = []
            attendance_data[period].append(row)

    return attendance_data


@retry_with_backoff(max_retries=3, base_delay=5)
def _login_to_aeries(page, username, password, login_url):
    """
    Login to Aeries with retry logic

    Retries up to 3 times with exponential backoff: 5s, 15s, 45s
    Raises SyncError on final failure
    """
    try:
        page.goto(login_url, timeout=30000)

        page.wait_for_selector('input[type="text"]', timeout=30000)
        page.fill('input[name="portalAccountUsername"], input[type="text"]', username)
        page.fill('input[name="portalAccountPassword"], input[type="password"]', password)
        page.click('button[type="submit"], input[type="submit"]')

        page.wait_for_url(lambda url: "Login.aspx" not in url, timeout=40000)
        logger.info("Login complete")

    except Exception as e:
        # Convert to SyncError for consistent error handling
        raise SyncError(
            message=f"Login failed: {str(e)}",
            error_type='login_failed',
            original_exception=e
        )

def upload_to_aeries(csv_filepath, username, password):
    """
    Automates the Teacher Attendance grid view with strict row targeting
    """

    LOGIN_URL = "https://adn.fjuhsd.org/Aeries.net/Login.aspx"
    ATTENDANCE_URL = "https://adn.fjuhsd.org/Aeries.net/TeacherAttendance.aspx"

    logger.info(f"Starting UI Automation for {csv_filepath}")

    if not os.path.exists(csv_filepath):
        raise FileNotFoundError(f"CSV file not found: {csv_filepath}")

    period_groups = read_attendance_csv(csv_filepath)
    if not period_groups:
        logger.warning("No data found in CSV")
        return

    # Load any students that failed in previous sync
    previously_failed = load_failed_students()
    current_failures = []

    # Merge previously failed students into period groups for retry
    if previously_failed.get('students'):
        retry_count = 0
        for failed in previously_failed['students']:
            period = failed['period']
            if period in period_groups:
                # Check if this student is already in the list (avoid duplicates)
                existing_ids = [s['StudentID'] for s in period_groups[period]]
                if failed['student_id'] not in existing_ids:
                    # Reconstruct student record for processing, preserving original status
                    period_groups[period].append({
                        'StudentID': failed['student_id'],
                        'Period': period,
                        'Status': failed.get('status', 'Absent'),
                    })
                    retry_count += 1
        if retry_count > 0:
            logger.info(f"Retrying {retry_count} students from previous sync cycle")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=50)
        context = browser.new_context(viewport={'width': 1600, 'height': 900})
        page = context.new_page()

        try:
            # --- LOGIN PHASE ---
            logger.info("Step 1: Logging in...")
            _login_to_aeries(page, username, password, LOGIN_URL)

            # --- NAVIGATION PHASE ---
            logger.info("Step 2: Navigating to Attendance Screen...")
            page.goto(ATTENDANCE_URL, timeout=60000)

            try:
                page.wait_for_selector("select", timeout=30000)
                logger.info("Attendance page loaded")
            except Exception as e:
                logger.warning(f"Page load wait timed out, continuing: {e}")

            # --- PROCESS EACH PERIOD ---
            for period, students in period_groups.items():
                logger.info(f"Processing Period {period} ({len(students)} students)")
                failed_students = []  # Track failed students for this period

                # Select the Period
                try:
                    target_select = None
                    target_option_label = None
                    selects = page.locator("select").all()
                    for select in selects:
                        if not select.is_visible(): continue
                        options = select.locator("option").all_inner_texts()
                        for opt in options:
                            if f"Period {period}" in opt or opt.strip().startswith(f"{period} -"):
                                target_select = select
                                target_option_label = opt
                                break
                        if target_select: break

                    if target_select:
                        current_text = target_select.locator("option:checked").inner_text()
                        if target_option_label not in current_text:
                            logger.info(f"Switching to: {target_option_label}")
                            target_select.select_option(label=target_option_label)
                            page.wait_for_timeout(3000)
                        else:
                            logger.info(f"Already on {target_option_label}")
                    else:
                        logger.warning(f"Could not find dropdown for Period {period}")
                        continue
                except Exception as e:
                    logger.warning(f"Error switching period: {e}")
                    continue

                # Click "All Remaining Students Are Present"
                try:
                    all_present_btn = page.locator("a, input, button").filter(has_text="All Remaining Students Are Present").first
                    if all_present_btn.is_visible():
                        all_present_btn.click()
                        logger.info("Clicked 'All Remaining Students Are Present'")
                        try:
                            page.keyboard.press("Enter")
                        except Exception as e:
                            logger.debug(f"Enter key press after 'All Present' failed: {e}")
                        page.wait_for_timeout(1000)
                except Exception as e:
                    logger.debug(f"'All Remaining Students Are Present' button not found: {e}")

                # --- PROCESS STUDENTS ---
                updates_count = 0

                for student in students:
                    raw_status = student.get('Status', 'Absent')
                    student_id = student.get('StudentID', '')
                    if not student_id:
                        logger.warning("Skipping student with empty StudentID")
                        continue

                    # 1. NORMALIZE STATUS (Map App codes to Aeries)
                    status = raw_status
                    if raw_status in ['Late', 'Truant', 'Cut', 'Late > 20']:
                        status = 'Tardy'
                    elif raw_status in ['On Time', 'Present']:
                        status = 'Present'

                    # Log intent BEFORE checkbox interaction
                    log_sync_intent(
                        student_id=student_id,
                        period=period,
                        intended_status=status,
                        source_status=raw_status,
                        timestamp=datetime.now()
                    )

                    try:
                        # 1. Find the exact cell with the student ID using fallback selectors
                        cell, _ = find_element_with_fallback(page, 'student_cell', {'student_id': student_id})
                        if cell.count() == 0:
                            logger.warning(f"Cell not found for ID {student_id}")
                            continue

                        # 2. Get the specific parent row using XPath ".."
                        row = cell.locator("xpath=..")

                        # 3. Check if attendance is locked for this student
                        locked_indicator = row.locator("span[id$='lblLocked']")
                        if locked_indicator.count() > 0 and locked_indicator.is_visible():
                            locked_text = locked_indicator.inner_text().strip()
                            logger.info(f"Skipping student {student_id}: Locked as '{locked_text}'")
                            log_sync_action(
                                student_id=student_id,
                                period=period,
                                action_taken='skipped_locked',
                                checkbox_state={'absent': None, 'tardy': None},
                                success=True,
                                timestamp=datetime.now()
                            )
                            continue

                        # 4. Now search for checkboxes ONLY inside this specific row using fallback selectors
                        absent_box, _ = find_element_with_fallback(row, 'absent_checkbox', {})
                        tardy_box, _ = find_element_with_fallback(row, 'tardy_checkbox', {})

                        # Safety check: bypass if boxes aren't found for some reason
                        if absent_box.count() == 0 or tardy_box.count() == 0:
                            logger.warning(f"Skipping student {student_id}: Checkboxes not found")
                            continue

                        # CAPTURE PRE-CHANGE CHECKBOX STATE (before any checkbox clicks)
                        was_already_absent = absent_box.is_checked()
                        was_already_tardy = tardy_box.is_checked()

                        # --- CHECKBOX LOGIC WITH DELAYS ---
                        if status == 'Absent':
                            if not was_already_absent:
                                logger.info(f"Marking {student_id} as ABSENT")
                                absent_box.check()
                                page.wait_for_timeout(500)  # Added Delay
                                updates_count += 1
                            if was_already_tardy:
                                tardy_box.uncheck()
                                page.wait_for_timeout(500)  # Added Delay
                            # Log action AFTER checkbox interaction
                            log_sync_action(
                                student_id=student_id,
                                period=period,
                                action_taken='checked_absent' if not was_already_absent else 'no_change',
                                checkbox_state={'absent': True, 'tardy': False},
                                success=True,
                                timestamp=datetime.now()
                            )

                        elif status == 'Tardy':
                            if not was_already_tardy:
                                logger.info(f"Marking {student_id} as TARDY (was '{raw_status}')")
                                tardy_box.check()
                                page.wait_for_timeout(500)  # Added Delay
                                updates_count += 1
                            if was_already_absent:
                                absent_box.uncheck()
                                page.wait_for_timeout(500)  # Added Delay
                            # Log action AFTER checkbox interaction
                            log_sync_action(
                                student_id=student_id,
                                period=period,
                                action_taken='checked_tardy' if not was_already_tardy else 'no_change',
                                checkbox_state={'absent': False, 'tardy': True},
                                success=True,
                                timestamp=datetime.now()
                            )

                        elif status == 'Present':
                            # Correction logic: Uncheck if they were marked by mistake
                            made_correction = False
                            if was_already_absent:
                                logger.info(f"Correcting {student_id}: Was Absent, now Present")
                                absent_box.uncheck()
                                page.wait_for_timeout(500)  # Added Delay
                                updates_count += 1
                                made_correction = True
                            if was_already_tardy:
                                logger.info(f"Correcting {student_id}: Was Tardy, now Present")
                                tardy_box.uncheck()
                                page.wait_for_timeout(500)  # Added Delay
                                updates_count += 1
                                made_correction = True
                            # Log action AFTER checkbox interaction
                            log_sync_action(
                                student_id=student_id,
                                period=period,
                                action_taken='corrected_to_present' if made_correction else 'no_change',
                                checkbox_state={'absent': False, 'tardy': False},
                                success=True,
                                timestamp=datetime.now()
                            )

                    except Exception as e:
                        # Print a shorter error message to avoid cluttering logs
                        error_msg = str(e).split('\n')[0]
                        logger.error(f"Error processing {student_id}: {error_msg}")

                        # Log failed action to audit log
                        log_sync_action(
                            student_id=student_id,
                            period=period,
                            action_taken='failed',
                            checkbox_state={'absent': None, 'tardy': None},
                            success=False,
                            timestamp=datetime.now()
                        )

                        # Log failure to persistent error log
                        log_sync_failure(
                            student_id=student_id,
                            period=period,
                            error=error_msg,
                            attempt_count=1,
                            timestamp=datetime.now()
                        )
                        failed_students.append(student_id)

                        # Track failure for retry in next sync cycle (preserve original status)
                        current_failures.append({
                            'student_id': student_id,
                            'period': period,
                            'status': raw_status,
                            'error': error_msg,
                            'timestamp': datetime.now().isoformat()
                        })

                # Report period summary
                if failed_students:
                    logger.info(f"Period {period} complete. Updates: {updates_count}, Failed: {len(failed_students)}")
                else:
                    logger.info(f"Period {period} verified. Updates made: {updates_count}")

                # Save after each period to avoid losing changes on period switch
                if updates_count > 0:
                    try:
                        save_btn = page.locator("input[value='Save'], button:has-text('Save')").first
                        save_btn.scroll_into_view_if_needed(timeout=5000)
                        save_btn.click()
                        logger.info(f"Saved Period {period}")
                        page.wait_for_timeout(2000)
                    except Exception as e:
                        page.screenshot(path=f'save_error_period_{period}.png')
                        raise SyncError(
                            message=f"Failed to save Period {period} - changes may be lost: {e}",
                            error_type='save_failed',
                            original_exception=e
                        )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            page.screenshot(path=f'aeries_grid_{timestamp}.png', full_page=True)
            logger.info("Final screenshot saved")

            # Save any failures for next sync cycle
            if current_failures:
                save_failed_students(current_failures)
                logger.info(f"{len(current_failures)} students saved for retry in next sync")
            else:
                clear_failed_students()  # All succeeded, clear the retry queue

        except Exception as e:
            logger.error(f"Error during automation: {e}")
            page.screenshot(path='error_state.png')
            raise

        finally:
            browser.close()

if __name__ == "__main__":
    TEST_CSV = "attendance_2024-12-18.csv"
    USERNAME = os.getenv('AERIES_USER')
    PASSWORD = os.getenv('AERIES_PASS')

    upload_to_aeries(TEST_CSV, USERNAME, PASSWORD)
