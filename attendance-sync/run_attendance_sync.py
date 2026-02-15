"""
Main script to run attendance sync from Firebase to Aeries
Runs every 20 minutes during school hours (8:00 AM - 3:45 PM)
"""

from datetime import datetime
from attendance_to_aeries import export_attendance_to_csv
from upload_to_aeries import upload_to_aeries
from sync_utils import SyncError, generate_verification_report, generate_daily_summary
import os
import sys
import logging
import json

# Configure logging with date-based log file
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

# Sync schedule (every 20 minutes during school hours)
SYNC_SCHEDULE = {
    "08:00": "Morning sync 1",
    "08:20": "Morning sync 2",
    "08:40": "Morning sync 3",
    "09:00": "Morning sync 4",
    "09:20": "Morning sync 5",
    "09:40": "Morning sync 6",
    "10:00": "Mid-morning sync 1",
    "10:20": "Mid-morning sync 2",
    "10:40": "Mid-morning sync 3",
    "11:00": "Mid-morning sync 4",
    "11:20": "Late morning sync 1",
    "11:40": "Late morning sync 2",
    "12:00": "Lunch sync 1",
    "12:20": "Lunch sync 2",
    "12:40": "Lunch sync 3",
    "13:00": "Afternoon sync 1",
    "13:20": "Afternoon sync 2",
    "13:40": "Afternoon sync 3",
    "14:00": "Afternoon sync 4",
    "14:20": "Late afternoon sync 1",
    "14:40": "Late afternoon sync 2",
    "15:00": "Late afternoon sync 3",
    "15:20": "Late afternoon sync 4",
    "15:40": "Pre-final sync",
    "15:45": "END OF DAY - FINAL SYNC"
}

# Time window in minutes (increased from 2 to 5 for reliability)
SYNC_WINDOW_MINUTES = 5


def get_current_sync_label():
    """
    Check if current time matches a scheduled sync time
    Returns the label if it's time to sync, None otherwise
    """
    now = datetime.now()
    
    # Check if we're within the window of a scheduled sync time
    for sync_time, label in SYNC_SCHEDULE.items():
        scheduled = datetime.strptime(sync_time, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )
        diff_minutes = abs((now - scheduled).total_seconds() / 60)
        
        if diff_minutes <= SYNC_WINDOW_MINUTES:
            return label
    
    return None


def sync_attendance_to_aeries(force=False):
    """
    Complete workflow: Firebase → CSV → Aeries
    
    Args:
        force: If True, skip time check and run anyway
    """
    
    # Check if it's time to sync (unless forced)
    sync_label = get_current_sync_label()
    if not force and not sync_label:
        current_time = datetime.now().strftime('%I:%M %p')
        logger.info(f"Not a scheduled sync time. Current time: {current_time}")
        logger.info("Next scheduled syncs:")
        now = datetime.now()
        for sync_time, label in SYNC_SCHEDULE.items():
            scheduled = datetime.strptime(sync_time, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day
            )
            if scheduled > now:
                logger.info(f"   • {sync_time} - {label}")
        return
    
    if force:
        sync_label = "MANUAL RUN (forced)"
    
    # Print header
    header = f"""
{'='*70}
  ATTENDANCE SYNC TO AERIES
  {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}
  Sync Type: {sync_label}
{'='*70}
"""
    logger.info(header)
    
    # Configuration
    AERIES_USERNAME = os.getenv('AERIES_USER')
    AERIES_PASSWORD = os.getenv('AERIES_PASS')
    
    # Validate credentials
    if not AERIES_USERNAME or not AERIES_PASSWORD:
        logger.error("AERIES_USER and AERIES_PASS environment variables not set!")
        logger.error("Please set them in Windows Environment Variables")
        logger.info("Instructions:")
        logger.info("   1. Search 'Environment Variables' in Windows")
        logger.info("   2. Click 'Edit environment variables for your account'")
        logger.info("   3. Add AERIES_USER and AERIES_PASS variables")
        return
    
    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        # Step 1: Export from Firebase
        logger.info("STEP 1: Exporting attendance from Firebase")
        logger.info("-" * 70)
        csv_file = export_attendance_to_csv(today)

        # Step 2: Upload to Aeries
        logger.info("")
        logger.info("STEP 2: Uploading to Aeries")
        logger.info("-" * 70)
        sync_start_time = datetime.now()  # Record for verification report
        upload_to_aeries(csv_file, AERIES_USERNAME, AERIES_PASSWORD)

        # Step 3: Generate verification report
        logger.info("")
        logger.info("STEP 3: Generating Verification Report")
        logger.info("-" * 70)
        verification_passed = True
        try:
            report = generate_verification_report(
                csv_filepath=csv_file,
                run_start_timestamp=sync_start_time,
                output_dir="."
            )

            # Log summary
            summary = report['summary']
            logger.info(f"   Total students: {summary['total_students']}")
            logger.info(f"   Synced: {summary['total_synced']}")
            logger.info(f"   Failed: {summary['total_failed']}")
            logger.info(f"   Skipped (locked): {summary['total_skipped_locked']}")

            if summary['total_discrepancies'] > 0:
                verification_passed = False
                logger.warning(f"   !! DISCREPANCIES FOUND: {summary['total_discrepancies']}")
                for disc in report['discrepancies'][:5]:  # Show first 5
                    logger.warning(f"      - {disc['type']}: Student {disc['student_id']} Period {disc['period']}")
                if len(report['discrepancies']) > 5:
                    logger.warning(f"      ... and {len(report['discrepancies']) - 5} more (see report file)")
            else:
                logger.info("   No discrepancies found")

        except Exception as e:
            logger.error(f"   Failed to generate verification report: {e}")
            verification_passed = False

        # Step 4: Generate daily summary (only at END OF DAY sync)
        if "END OF DAY" in sync_label:
            logger.info("")
            logger.info("STEP 4: Generating Daily Summary")
            logger.info("-" * 70)
            try:
                daily_summary = generate_daily_summary(today, output_dir=".")
                logger.info(f"   Total sync runs today: {daily_summary['total_sync_runs']}")
                logger.info(f"   Total students processed: {daily_summary['total_students_processed']}")
                logger.info(f"   Successful: {daily_summary['total_successful_actions']}")
                logger.info(f"   Failed: {daily_summary['total_failed_actions']}")
                logger.info(f"   Locked (skipped): {daily_summary['total_skipped_locked']}")
                if daily_summary.get('unresolved_failures'):
                    logger.warning(f"   !! UNRESOLVED: {len(daily_summary['unresolved_failures'])} students")
            except Exception as e:
                logger.error(f"   Failed to generate daily summary: {e}")

        # Count failures from error log for summary
        error_log_file = f'sync_errors_{log_date}.log'
        student_failures = 0
        if os.path.exists(error_log_file):
            try:
                with open(error_log_file, 'r', encoding='utf-8') as f:
                    # Count JSON lines from today's sync
                    today_str = datetime.now().strftime('%Y-%m-%d')
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            if entry.get('timestamp', '').startswith(today_str):
                                student_failures += 1
                        except json.JSONDecodeError:
                            pass  # Non-JSON lines (e.g. plain-text error entries)
            except Exception as e:
                logger.warning(f"Failed to read error log for summary: {e}")

        # Success with verification and retry summary
        verification_status = 'PASSED' if verification_passed else 'DISCREPANCIES FOUND'
        success_msg = f"""
{'='*70}
  SYNC COMPLETE
  Successfully synced attendance for {today}
  Sync Type: {sync_label}
  Verification: {verification_status}
"""
        if student_failures > 0:
            success_msg += f"  Note: {student_failures} student(s) failed and were logged\n"
        success_msg += f"{'='*70}\n"
        logger.info(success_msg)

    except SyncError as e:
        # SyncError with enhanced context
        error_msg = f"""
{'='*70}
  ✗ SYNC FAILED ✗
  Error Type: {e.error_type}
  Error: {e.message}
"""
        if e.student_id:
            error_msg += f"  Student ID: {e.student_id}\n"
        if e.period:
            error_msg += f"  Period: {e.period}\n"
        error_msg += f"{'='*70}\n"
        logger.error(error_msg)

        # Log error to dedicated error file with date
        error_log_file = f'sync_errors_{log_date}.log'
        with open(error_log_file, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now()} - FAILED - {sync_label} - {e.error_type}: {e.message}\n")

    except Exception as e:
        # Generic exception fallback
        error_msg = f"""
{'='*70}
  ✗ SYNC FAILED ✗
  Error: {e}
{'='*70}
"""
        logger.error(error_msg)

        # Log error to dedicated error file with date
        error_log_file = f'sync_errors_{log_date}.log'
        with open(error_log_file, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now()} - FAILED - {sync_label} - {e}\n")


if __name__ == "__main__":
    # Check if --force flag is passed
    force = "--force" in sys.argv or "-f" in sys.argv
    
    if force:
        logger.info("Force mode enabled - running regardless of schedule\n")
    
    sync_attendance_to_aeries(force=force)
