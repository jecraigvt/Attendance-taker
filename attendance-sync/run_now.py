import os
import time
import logging
from datetime import datetime
from attendance_to_aeries import export_attendance_to_csv
from upload_to_aeries import upload_to_aeries

# --- CONFIG ---
FOLDER_PATH = os.path.dirname(os.path.abspath(__file__))
CLEANUP_DAYS = 30

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
                    logging.warning(f"Failed to remove old file {filename}: {e}")

if __name__ == "__main__":
    print(f"--- 🚀 Starting Sync Job: {datetime.now().strftime('%H:%M:%S')} ---")
    
    aeries_user = os.getenv('AERIES_USER')
    aeries_pass = os.getenv('AERIES_PASS')
    today_str = datetime.now().strftime('%Y-%m-%d')

    if aeries_user and aeries_pass:
        try:
            # STEP 1: Fetch latest data from Firebase (Creates the CSV)
            print("Step 1: Fetching from Firebase...")
            csv_path = export_attendance_to_csv(today_str)

            # STEP 2: Upload that new CSV to Aeries
            print(f"Step 2: Uploading {os.path.basename(csv_path)}...")
            upload_to_aeries(csv_path, aeries_user, aeries_pass)
            
            # STEP 3: Cleanup
            cleanup_old_files()
            print("✅ SUCCESS!")
            time.sleep(5)
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            time.sleep(60) # Keep window open if it fails
    else:
        print("❌ Error: Missing Environment Variables")
        time.sleep(10)