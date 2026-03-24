"""
Analyze Firebase attendance records against student correction requests
"""

import firebase_admin
from firebase_admin import credentials, firestore
import csv
import os
from datetime import datetime

# Firebase configuration
FIREBASE_KEY_PATH = os.getenv('FIREBASE_KEY_PATH')
if not FIREBASE_KEY_PATH:
    raise RuntimeError("FIREBASE_KEY_PATH environment variable is required")
APP_ID = 'attendance-taker-56916'

# Initialize Firebase
if not os.path.exists(FIREBASE_KEY_PATH):
    raise FileNotFoundError(f"Firebase key not found at: {FIREBASE_KEY_PATH}")

cred = credentials.Certificate(FIREBASE_KEY_PATH)
app = firebase_admin.initialize_app(cred)
db = firestore.client()

def convert_date(issue_date):
    """Convert issue date like '2/4' or '1/28' to '2026-02-04' format"""
    # Handle different formats
    parts = issue_date.replace('-', '/').split('/')
    if len(parts) == 2:
        month, day = parts
        # Assume 2026 for dates in Jan/Feb, could be 2025 for earlier dates
        year = '2026' if int(month) <= 2 else '2026'
    elif len(parts) == 3:
        month, day, year = parts
        if len(year) == 2:
            year = '20' + year
    else:
        return None

    return f"{year}-{int(month):02d}-{int(day):02d}"

def find_student_in_firebase(db, date_str, student_id):
    """
    Search all periods for a student on a given date.
    Returns dict with findings.
    """
    periods = ["0", "1", "2", "2A", "2B", "3", "4", "5", "6", "7"]

    results = {
        'date': date_str,
        'student_id': student_id,
        'found_in_roster': [],
        'signed_in': [],
        'firebase_status': None,
        'sign_in_time': None,
        'periods_checked': 0,
        'error': None
    }

    for period in periods:
        base_path = f'artifacts/{APP_ID}/public/data/attendance/{date_str}/periods/{period}'

        try:
            # Check roster snapshot
            roster_doc = db.document(base_path).get()
            if not roster_doc.exists:
                continue

            results['periods_checked'] += 1
            roster_data = roster_doc.to_dict()
            roster = roster_data.get('roster_snapshot', [])

            # Check if student is in roster
            in_roster = any(s.get('StudentID') == student_id for s in roster)
            if in_roster:
                results['found_in_roster'].append(period)

            # Check if student signed in
            student_doc = db.document(f'{base_path}/students/{student_id}').get()
            if student_doc.exists:
                data = student_doc.to_dict()
                results['signed_in'].append(period)
                results['firebase_status'] = data.get('Status', 'Unknown')
                results['sign_in_time'] = data.get('SignInTime', 'Unknown')

        except Exception as e:
            results['error'] = str(e)

    return results

def main():
    # Fix Windows console encoding
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    # Read the corrections CSV
    corrections_file = r'C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\attendance_corrections.csv'

    corrections = []
    with open(corrections_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            corrections.append(row)

    print(f"Analyzing {len(corrections)} correction requests against Firebase...\n")
    print("=" * 100)

    # Group by date for efficiency
    by_date = {}
    for c in corrections:
        date_str = convert_date(c['Issue Date'])
        if date_str:
            if date_str not in by_date:
                by_date[date_str] = []
            by_date[date_str].append(c)

    # Results tracking
    results = []

    for date_str in sorted(by_date.keys()):
        print(f"\n[DATE] {date_str}")
        print("-" * 100)

        for correction in by_date[date_str]:
            student_name = correction['Student Name']
            student_id = correction['Student ID']
            reported_issue = correction['Issue Type']

            # Query Firebase
            fb_result = find_student_in_firebase(db, date_str, student_id)

            # Analyze the findings
            in_roster = len(fb_result['found_in_roster']) > 0
            signed_in = len(fb_result['signed_in']) > 0
            fb_status = fb_result['firebase_status']
            sign_time = fb_result['sign_in_time']

            # Determine the diagnosis
            if not in_roster:
                diagnosis = "[?] NOT IN ROSTER - Student wasn't in any period roster for this date"
            elif not signed_in:
                diagnosis = "[X] NO SIGN-IN - Student in roster but NO sign-in record in Firebase"
            elif fb_status == 'Absent':
                diagnosis = "[!] FIREBASE SAYS ABSENT - Sign-in record exists but status is 'Absent' (bug?)"
            elif fb_status == 'Late' or fb_status == 'Tardy':
                if reported_issue in ['TARDY', 'LATE']:
                    diagnosis = "[~] FIREBASE AGREES - Firebase shows Late/Tardy, student disputes this"
                else:
                    diagnosis = f"[~] STATUS MISMATCH - Firebase: {fb_status}, Student claims: {reported_issue}"
            elif fb_status == 'On Time':
                diagnosis = "[OK] FIREBASE SHOWS ON TIME - Sync to Aeries may have failed"
            else:
                diagnosis = f"[?] UNKNOWN STATUS - Firebase shows: {fb_status}"

            # Store result
            result = {
                'Date': date_str,
                'Student': student_name,
                'StudentID': student_id,
                'Reported': reported_issue,
                'InRoster': 'Yes' if in_roster else 'No',
                'SignedIn': 'Yes' if signed_in else 'No',
                'FirebaseStatus': fb_status or 'N/A',
                'SignInTime': sign_time or 'N/A',
                'Periods': ','.join(fb_result['found_in_roster']) if fb_result['found_in_roster'] else 'None',
                'Diagnosis': diagnosis
            }
            results.append(result)

            # Print findings
            print(f"\n  {student_name} (ID: {student_id})")
            print(f"     Reported Issue: {reported_issue}")
            print(f"     In Roster: {'Yes - Period(s): ' + ','.join(fb_result['found_in_roster']) if in_roster else 'NO'}")
            print(f"     Signed In: {'Yes - Period(s): ' + ','.join(fb_result['signed_in']) if signed_in else 'NO'}")
            if signed_in:
                print(f"     Firebase Status: {fb_status}")
                print(f"     Sign-in Time: {sign_time}")
            print(f"     >> {diagnosis}")

    # Write analysis results to CSV
    output_file = r'C:\Users\Jeremy\Documents\Vibe coding\Attendance Taker\firebase_analysis.csv'
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['Date', 'Student', 'StudentID', 'Reported', 'InRoster', 'SignedIn',
                      'FirebaseStatus', 'SignInTime', 'Periods', 'Diagnosis']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("\n" + "=" * 100)
    print(f"\n=== SUMMARY ===")
    print("-" * 50)

    # Categorize results
    no_signin = [r for r in results if r['SignedIn'] == 'No']
    has_signin = [r for r in results if r['SignedIn'] == 'Yes']
    firebase_ontime = [r for r in has_signin if r['FirebaseStatus'] == 'On Time']
    firebase_late = [r for r in has_signin if r['FirebaseStatus'] in ['Late', 'Tardy']]

    print(f"Total corrections: {len(results)}")
    print(f"  [X] No sign-in record in Firebase: {len(no_signin)}")
    print(f"  [OK] Has sign-in record: {len(has_signin)}")
    print(f"      - Firebase shows 'On Time': {len(firebase_ontime)} (Aeries sync issue)")
    print(f"      - Firebase shows 'Late/Tardy': {len(firebase_late)} (Status dispute)")

    print(f"\nFull analysis saved to: {output_file}")

    if no_signin:
        print(f"\n*** STUDENTS WITH NO FIREBASE SIGN-IN ({len(no_signin)}) ***")
        print("    These students may have forgotten to sign in, or sign-in failed:")
        for r in no_signin:
            print(f"    - {r['Date']}: {r['Student']}")

if __name__ == '__main__':
    main()
