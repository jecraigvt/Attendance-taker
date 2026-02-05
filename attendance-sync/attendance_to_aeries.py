"""
Export attendance from Firebase to CSV for Aeries import
"""

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import csv
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Firebase configuration
FIREBASE_KEY_PATH = os.getenv('FIREBASE_KEY_PATH', 'C:/Users/Jeremy/attendance-sync/attendance-sync/attendance-key.json')
APP_ID = 'attendance-taker-56916'

# Lazy initialization for Firebase
_db = None
_app = None


def get_db():
    """
    Get Firestore client with lazy initialization.
    Prevents issues when module is imported but not used.
    """
    global _db, _app
    if _db is None:
        if not os.path.exists(FIREBASE_KEY_PATH):
            raise FileNotFoundError(f"Firebase key not found at: {FIREBASE_KEY_PATH}")
        cred = credentials.Certificate(FIREBASE_KEY_PATH)
        _app = firebase_admin.initialize_app(cred)
        _db = firestore.client()
    return _db


def export_attendance_to_csv(date_str):
    """
    Fetch attendance from Firebase and generate CSV for Aeries
    
    Args:
        date_str: Date in format "YYYY-MM-DD" (e.g., "2024-12-18")
    
    Returns:
        filename: Path to generated CSV file
    """
    
    logger.info(f"Fetching attendance for {date_str}...")
    
    db = get_db()
    
    # CSV headers matching Aeries import format
    rows = [["Date", "Period", "StudentID", "LastName", "FirstName", "Status", "SignInTime", "Group"]]
    
    # All possible periods from your schedule
    periods = ["0", "1", "2", "2A", "2B", "3", "4", "5", "6", "7"]
    
    total_records = 0
    
    for period in periods:
        base_path = f'artifacts/{APP_ID}/public/data/attendance/{date_str}/periods/{period}'
        
        try:
            # 1. Get roster snapshot for this period
            roster_doc_ref = db.document(base_path)
            roster_doc = roster_doc_ref.get()
            
            if not roster_doc.exists:
                continue  # Skip periods with no data
            
            roster_data = roster_doc.to_dict()
            roster = roster_data.get('roster_snapshot', [])
            
            if not roster:
                logger.debug(f"Period {period}: No roster snapshot found (skipping)")
                continue
            
            # 2. Get all students who signed in
            students_ref = db.collection(f'{base_path}/students')
            students_docs = students_ref.stream()
            signed_in = {doc.id: doc.to_dict() for doc in students_docs}
            
            period_count = 0
            present_count = len(signed_in)
            
            # 3. Generate rows for present and absent students
            for student in roster:
                student_id = student.get('StudentID', '')
                
                if student_id in signed_in:
                    # Student signed in
                    log = signed_in[student_id]
                    rows.append([
                        date_str,
                        period,
                        student_id,
                        student.get("LastName", ""),  # Fixed: no manual quoting
                        student.get("FirstName", ""),  # Fixed: no manual quoting
                        log.get('Status', 'On Time'),
                        log.get('SignInTime', ''),
                        log.get('Group', 'N/A')
                    ])
                else:
                    # Student was absent
                    rows.append([
                        date_str,
                        period,
                        student_id,
                        student.get("LastName", ""),  # Fixed: no manual quoting
                        student.get("FirstName", ""),  # Fixed: no manual quoting
                        'Absent',
                        'N/A',
                        'N/A'
                    ])
                period_count += 1
            
            total_records += period_count
            absent_count = period_count - present_count
            logger.info(f"   Period {period}: {period_count} records ({present_count} present, {absent_count} absent)")
        
        except Exception as e:
            logger.warning(f"   Period {period}: Error - {e}")
            continue
    
    if total_records == 0:
        raise Exception("No attendance data found for this date. Make sure students have signed in.")
    
    # Write to CSV
    filename = f'attendance_{date_str}.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    logger.info(f"Exported {total_records} total records to {filename}")
    return filename


if __name__ == "__main__":
    # Test the export for today
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        csv_file = export_attendance_to_csv(today)
        print(f"Success! CSV file created: {csv_file}")
    except Exception as e:
        print(f"Error: {e}")
