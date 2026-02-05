"""
UI Automation for Aeries Attendance (Grid View) - Adjusted for Speed
"""

from playwright.sync_api import sync_playwright
from datetime import datetime
import csv
import os
import time
from sync_utils import retry_with_backoff, SyncError, log_sync_failure

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
        print("   ✓ Login complete")

    except Exception as e:
        # Convert to SyncError for consistent error handling
        raise SyncError(
            message=f"Login failed: {str(e)}",
            error_type='login_failed',
            original_exception=e
        )

def upload_to_aeries(csv_filepath, aeries_base_url, username, password):
    """
    Automates the Teacher Attendance grid view with strict row targeting
    """
    
    LOGIN_URL = "https://adn.fjuhsd.org/Aeries.net/Login.aspx"
    ATTENDANCE_URL = "https://adn.fjuhsd.org/Aeries.net/TeacherAttendance.aspx"
    
    print(f"🌐 Starting UI Automation for {csv_filepath}...")
    
    if not os.path.exists(csv_filepath):
        raise FileNotFoundError(f"CSV file not found: {csv_filepath}")
    
    period_groups = read_attendance_csv(csv_filepath)
    if not period_groups:
        print("   ⚠ No data found in CSV.")
        return

    with sync_playwright() as p:
        # slow_mo helps globally, but we add specific waits below for the grid
        browser = p.chromium.launch(headless=False, slow_mo=50) 
        context = browser.new_context(viewport={'width': 1600, 'height': 900})
        page = context.new_page()
        
        try:
            # --- LOGIN PHASE ---
            print("   Step 1: Logging in...")
            _login_to_aeries(page, username, password, LOGIN_URL)
            
            # --- NAVIGATION PHASE ---
            print("   Step 2: Navigating to Attendance Screen...")
            page.goto(ATTENDANCE_URL, timeout=60000)
            
            try:
                page.wait_for_selector("select", timeout=30000)
                print("   ✓ Attendance page loaded")
            except:
                print("   ⚠ Page load wait timed out, but continuing...")

            # --- PROCESS EACH PERIOD ---
            for period, students in period_groups.items():
                print(f"\n   Processing Period {period} ({len(students)} students)...")
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
                            print(f"   Switching to: {target_option_label}...")
                            target_select.select_option(label=target_option_label)
                            page.wait_for_timeout(3000) 
                        else:
                            print(f"   Already on {target_option_label}")
                    else:
                        print(f"   ⚠ Could not find dropdown for Period {period}")
                        continue
                except Exception as e:
                    print(f"   ⚠ Error switching period: {e}")
                    continue

                # Click "All Remaining Students Are Present"
                try:
                    all_present_btn = page.locator("a, input, button").filter(has_text="All Remaining Students Are Present").first
                    if all_present_btn.is_visible():
                        all_present_btn.click()
                        print("   ✓ Clicked 'All Remaining Students Are Present'")
                        try: page.keyboard.press("Enter") 
                        except: pass
                        page.wait_for_timeout(1000)
                except: pass

                # --- PROCESS STUDENTS ---
                updates_count = 0
                
                for student in students:
                    raw_status = student['Status']
                    student_id = student['StudentID']
                    
                    # 1. NORMALIZE STATUS (Map App codes to Aeries)
                    status = raw_status 
                    if raw_status in ['Late', 'Truant', 'Cut', 'Late > 20']:
                        status = 'Tardy'  
                    elif raw_status in ['On Time', 'Present', 'Excused']:
                        status = 'Present'
                    
                    try:
                        # 1. Find the exact cell with the student ID
                        cell = page.locator(f"td[data-studentid='{student_id}']")
                        if cell.count() == 0:
                            print(f"        ⚠ Cell not found for ID {student_id}")
                            continue
                            
                        # 2. Get the specific parent row using XPath ".."
                        row = cell.locator("xpath=..")
                        
                        # 3. Check if attendance is locked for this student
                        locked_indicator = row.locator("span[id$='lblLocked']")
                        if locked_indicator.count() > 0 and locked_indicator.is_visible():
                            locked_text = locked_indicator.inner_text().strip()
                            print(f"        🔒 Skipping student {student_id}: Locked as '{locked_text}'")
                            continue
                            
                        # 4. Now search for checkboxes ONLY inside this specific row
                        absent_box = row.locator("span[data-cd='A'] input")
                        tardy_box = row.locator("span[data-cd='T'] input")
                        
                        # Safety check: bypass if boxes aren't found for some reason
                        if absent_box.count() == 0 or tardy_box.count() == 0:
                            print(f"        ⚠ Skipping student {student_id}: Checkboxes not found")
                            continue

                        # --- CHECKBOX LOGIC WITH DELAYS ---
                        if status == 'Absent':
                            if not absent_box.is_checked():
                                print(f"      - Marking {student_id} as ABSENT")
                                absent_box.check()
                                page.wait_for_timeout(500) # Added Delay
                                updates_count += 1
                            if tardy_box.is_checked(): 
                                tardy_box.uncheck()
                                page.wait_for_timeout(500) # Added Delay

                        elif status == 'Tardy':
                            if not tardy_box.is_checked():
                                print(f"      - Marking {student_id} as TARDY (was '{raw_status}')")
                                tardy_box.check()
                                page.wait_for_timeout(500) # Added Delay
                                updates_count += 1
                            if absent_box.is_checked(): 
                                absent_box.uncheck()
                                page.wait_for_timeout(500) # Added Delay

                        elif status == 'Present':
                            # Correction logic: Uncheck if they were marked by mistake
                            if absent_box.is_checked():
                                print(f"      - Correcting {student_id}: Was Absent, now Present")
                                absent_box.uncheck()
                                page.wait_for_timeout(500) # Added Delay
                                updates_count += 1
                            if tardy_box.is_checked():
                                print(f"      - Correcting {student_id}: Was Tardy, now Present")
                                tardy_box.uncheck()
                                page.wait_for_timeout(500) # Added Delay
                                updates_count += 1
                                
                    except Exception as e:
                        # Print a shorter error message to avoid cluttering logs
                        error_msg = str(e).split('\n')[0]
                        print(f"        ❌ Error processing {student_id}: {error_msg}")

                        # Log failure to persistent error log
                        log_sync_failure(
                            student_id=student_id,
                            period=period,
                            error=error_msg,
                            attempt_count=1,
                            timestamp=datetime.now()
                        )
                        failed_students.append(student_id)

                # Report period summary
                if failed_students:
                    print(f"   ✓ Period {period} complete. Updates: {updates_count}, Failed: {len(failed_students)}")
                else:
                    print(f"   ✓ Period {period} verified. Updates made: {updates_count}")
            
            # Save
            try:
                save_btn = page.locator("input[value='Save'], button:has-text('Save')").first
                if save_btn.is_visible():
                    save_btn.click()
                    print("   ✓ Clicked Save")
            except: pass

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            page.screenshot(path=f'aeries_grid_{timestamp}.png', full_page=True)
            print(f"   📸 Final screenshot saved")

        except Exception as e:
            print(f"\n❌ Error during automation: {e}")
            page.screenshot(path='error_state.png')
            raise
        
        finally:
            browser.close()

if __name__ == "__main__":
    TEST_CSV = "attendance_2024-12-18.csv"
    USERNAME = os.getenv('AERIES_USER')
    PASSWORD = os.getenv('AERIES_PASS')
    
    upload_to_aeries(TEST_CSV, "", USERNAME, PASSWORD)