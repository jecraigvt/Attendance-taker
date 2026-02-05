import os
import time
from datetime import datetime
from attendance_to_aeries import export_attendance_to_csv # <--- ADDED THIS IMPORT
from upload_to_aeries import upload_to_aeries

# --- CONFIG ---
FOLDER_PATH = os.path.dirname(os.path.abspath(__file__))
CLEANUP_DAYS = 30

def cleanup_old_files():
    """Deletes old CSVs to keep folder clean"""
    current_time = time.time()
    day_in_seconds = 86400
    for filename in os.listdir(FOLDER_PATH):
        if filename.startswith("attendance_") and filename.endswith(".csv"):
            filepath = os.path.join(FOLDER_PATH, filename)
            file_age = (current_time - os.path.getmtime(filepath)) / day_in_seconds
            if file_age > CLEANUP_DAYS:
                try: os.remove(os.path.join(FOLDER_PATH, filename))
                except: pass

if __name__ == "__main__":
    print(f"--- 🚀 Starting Sync Job: {datetime.now().strftime('%H:%M:%S')} ---")
    
    aeries_user = os.getenv('AERIES_USER')
    aeries_pass = os.getenv('AERIES_PASS')
    today_str = datetime.now().strftime('%Y-%m-%d')

    if aeries_user and aeries_pass:
        try:
            # STEP 1: Fetch latest data from Firebase (Creates the CSV)
            print("Step 1: Fetching from Firebase...")
            csv_filename = export_attendance_to_csv(today_str)
            csv_full_path = os.path.join(FOLDER_PATH, csv_filename)
            
            # STEP 2: Upload that new CSV to Aeries
            print(f"Step 2: Uploading {csv_filename}...")
            upload_to_aeries(csv_full_path, "", aeries_user, aeries_pass)
            
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