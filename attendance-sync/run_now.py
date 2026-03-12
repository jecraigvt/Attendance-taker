import os
import time
import logging
import sys
from datetime import datetime
from attendance_to_aeries import export_attendance_to_csv
from upload_to_aeries import upload_to_aeries

# --- CONFIG ---
FOLDER_PATH = os.path.dirname(os.path.abspath(__file__))
CLEANUP_DAYS = 30

# Configure logging to match run_attendance_sync.py
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

def cleanup_old_files():
    """Deletes old CSVs and screenshots to keep folder clean"""
    current_time = time.time()
    day_in_seconds = 86400
    for filename in os.listdir(FOLDER_PATH):
        is_old_csv = filename.startswith("attendance_") and filename.endswith(".csv")
        is_old_screenshot = filename.startswith("aeries_grid_") and filename.endswith(".png")
        if is_old_csv or is_old_screenshot:
            filepath = os.path.join(FOLDER_PATH, filename)
            file_age = (current_time - os.path.getmtime(filepath)) / day_in_seconds
            if file_age > CLEANUP_DAYS:
                try:
                    os.remove(filepath)
                except Exception as e:
                    logger.warning(f"Failed to remove old file {filename}: {e}")

if __name__ == "__main__":
    logger.info(f"Starting manual sync job: {datetime.now().strftime('%H:%M:%S')}")

    aeries_user = os.getenv('AERIES_USER')
    aeries_pass = os.getenv('AERIES_PASS')
    today_str = datetime.now().strftime('%Y-%m-%d')

    if aeries_user and aeries_pass:
        try:
            # STEP 1: Fetch latest data from Firebase (Creates the CSV)
            logger.info("Step 1: Fetching from Firebase...")
            csv_path = export_attendance_to_csv(today_str)

            # STEP 2: Upload that new CSV to Aeries
            logger.info(f"Step 2: Uploading {os.path.basename(csv_path)}...")
            upload_to_aeries(csv_path, aeries_user, aeries_pass)

            # STEP 3: Cleanup
            cleanup_old_files()
            logger.info("Sync completed successfully")
            time.sleep(5)

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            time.sleep(60) # Keep window open if it fails
    else:
        logger.error("Missing AERIES_USER and/or AERIES_PASS environment variables")
        time.sleep(10)
