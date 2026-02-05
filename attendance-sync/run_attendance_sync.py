"""
Main script to run attendance sync from Firebase to Aeries
Runs 7 times daily: after each period starts + end of day final sync
"""

from datetime import datetime
from attendance_to_aeries import export_attendance_to_csv
from upload_to_aeries import upload_to_aeries
import os
import sys
import logging

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

# Sync schedule (7 times per day)
SYNC_SCHEDULE = {
    "08:40": "Period 1 (10 min in)",
    "09:42": "Period 2 (10 min in)",
    "11:02": "Period 3 (10 min in)",
    "12:04": "Period 4 (10 min in)",
    "13:41": "Period 5 (10 min in)",
    "14:43": "Period 6 (10 min in)",
    "15:30": "END OF DAY - FINAL SYNC"
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
    AERIES_URL = "https://adn.fjuhsd.org/Aeries.net/Login.aspx"
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
        upload_to_aeries(csv_file, AERIES_URL, AERIES_USERNAME, AERIES_PASSWORD)
        
        # Success
        success_msg = f"""
{'='*70}
  ✓✓✓ SYNC COMPLETE ✓✓✓
  Successfully synced attendance for {today}
  Sync Type: {sync_label}
{'='*70}
"""
        logger.info(success_msg)
        
    except Exception as e:
        # Failure
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
