"""
Export attendance from Firebase to CSV for Aeries import

Supports per-teacher paths (v2.0+): teachers/{teacher_uid}/attendance/{date}/...
Falls back to legacy paths (v1.x): artifacts/{APP_ID}/public/data/attendance/{date}/...
"""

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone
import csv
import os
import logging

logger = logging.getLogger(__name__)

# Firebase configuration
FIREBASE_KEY_PATH = os.getenv('FIREBASE_KEY_PATH', 'C:/Users/Jeremy/attendance-sync/attendance-key.json')

# Legacy path support (v1.x) — used as fallback only
LEGACY_APP_ID = 'attendance-taker-56916'

# Period settle threshold: don't sync a period until this many minutes after
# the Nth student signs in, to avoid marking a full class as absent while
# students are still arriving.
MIN_STUDENTS_BEFORE_SYNC = 5   # Must match TARDY_AFTER_NTH in HTML app
PERIOD_SETTLE_MINUTES = 15

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
        try:
            cred = credentials.Certificate(FIREBASE_KEY_PATH)
            _app = firebase_admin.initialize_app(cred)
        except ValueError:
            # App already initialized (e.g. partial failure on previous call)
            _app = firebase_admin.get_app()
        _db = firestore.client()
    return _db


def get_all_teacher_uids():
    """
    Return a list of all teacher UIDs that have data in Firestore.

    Reads the top-level 'teachers' collection. Each document ID is a teacher UID.
    Returns an empty list if the collection doesn't exist or is empty.
    """
    db = get_db()
    try:
        teachers_ref = db.collection('teachers')
        teacher_docs = teachers_ref.stream()
        uids = [doc.id for doc in teacher_docs]
        logger.info(f"[get_all_teacher_uids] Found {len(uids)} teacher(s): {uids}")
        return uids
    except Exception as e:
        logger.warning(f"[get_all_teacher_uids] Error reading teachers collection: {e}")
        return []


def export_attendance_for_teacher(date_str, teacher_uid):
    """
    Fetch attendance from Firebase for a single teacher and return CSV rows.

    Args:
        date_str:    Date in format "YYYY-MM-DD" (e.g., "2024-12-18")
        teacher_uid: The Firebase Auth UID of the teacher

    Returns:
        list of row lists (without the header row)
    """
    logger.info(f"[{teacher_uid}] Fetching attendance for {date_str}...")

    db = get_db()

    # All possible periods from your schedule
    periods = ["0", "1", "2", "2A", "2B", "3", "4", "5", "6", "7"]

    rows = []

    for period in periods:
        base_path = f'teachers/{teacher_uid}/attendance/{date_str}/periods/{period}'

        try:
            # 1. Get roster snapshot for this period
            roster_doc_ref = db.document(base_path)
            roster_doc = roster_doc_ref.get()

            if not roster_doc.exists:
                continue  # Skip periods with no data

            roster_data = roster_doc.to_dict()
            roster = roster_data.get('roster_snapshot', [])

            if not roster:
                logger.debug(f"[{teacher_uid}] Period {period}: No roster snapshot found (skipping)")
                continue

            # 2. Get all students who signed in
            students_ref = db.collection(f'{base_path}/students')
            students_docs = students_ref.stream()
            signed_in = {doc.id: doc.to_dict() for doc in students_docs}

            # 3. Check if period has settled (enough students + enough time elapsed)
            #    Prevents marking an entire class absent while students are still arriving
            timestamps = []
            for data in signed_in.values():
                ts = data.get('Timestamp')
                if ts is not None and hasattr(ts, 'timestamp'):
                    # Firestore Timestamp -> timezone-aware datetime (UTC)
                    timestamps.append(ts)

            if len(timestamps) < MIN_STUDENTS_BEFORE_SYNC:
                logger.info(
                    f"[{teacher_uid}] Period {period}: Only {len(timestamps)} sign-ins so far, "
                    f"skipping sync (need {MIN_STUDENTS_BEFORE_SYNC})"
                )
                continue

            timestamps.sort()
            nth_timestamp = timestamps[MIN_STUDENTS_BEFORE_SYNC - 1]
            now_utc = datetime.now(timezone.utc)
            # Ensure timezone-aware comparison (Firestore returns UTC-aware timestamps;
            # guard against naive by treating as UTC)
            if nth_timestamp.tzinfo is None:
                nth_timestamp = nth_timestamp.replace(tzinfo=timezone.utc)
            minutes_elapsed = (now_utc - nth_timestamp).total_seconds() / 60

            if minutes_elapsed < PERIOD_SETTLE_MINUTES:
                logger.info(
                    f"[{teacher_uid}] Period {period}: {len(signed_in)} students signed in, but only "
                    f"{minutes_elapsed:.0f}min since {MIN_STUDENTS_BEFORE_SYNC}th sign-in "
                    f"(need {PERIOD_SETTLE_MINUTES}min). Skipping to avoid false absences."
                )
                continue

            # 4. Period has settled — generate rows
            period_count = 0
            present_count = len(signed_in)
            for student in roster:
                student_id = student.get('StudentID', '')
                if not student_id:
                    logger.warning(f"[{teacher_uid}] Period {period}: Skipping student with empty StudentID")
                    continue

                if student_id in signed_in:
                    log = signed_in[student_id]
                    rows.append([
                        date_str,
                        period,
                        student_id,
                        student.get("LastName", ""),
                        student.get("FirstName", ""),
                        log.get('Status', 'On Time'),
                        log.get('SignInTime', ''),
                        log.get('Group', 'N/A')
                    ])
                else:
                    rows.append([
                        date_str,
                        period,
                        student_id,
                        student.get("LastName", ""),
                        student.get("FirstName", ""),
                        'Absent',
                        'N/A',
                        'N/A'
                    ])
                period_count += 1

            # Warn about students who signed in but aren't in the roster
            roster_ids = {student.get('StudentID', '') for student in roster}
            unrostered = set(signed_in.keys()) - roster_ids
            if unrostered:
                logger.warning(
                    f"[{teacher_uid}] Period {period}: "
                    f"{len(unrostered)} signed-in student(s) not in roster: {unrostered}"
                )

            absent_count = period_count - present_count
            logger.info(
                f"[{teacher_uid}] Period {period}: "
                f"{period_count} records ({present_count} present, {absent_count} absent)"
            )

        except Exception as e:
            logger.warning(f"[{teacher_uid}] Period {period}: Error - {e}")
            continue

    return rows


def export_attendance_to_csv(date_str, teacher_uid=None):
    """
    Fetch attendance from Firebase and generate CSV for Aeries.

    v2.0 multi-teacher: if teacher_uid is None, exports all teachers found in
    the 'teachers' collection, merging their rows into a single CSV.

    Falls back to the legacy path (artifacts/{APP_ID}/...) if no teacher UIDs
    are found in the new structure.

    Args:
        date_str:    Date in format "YYYY-MM-DD" (e.g., "2024-12-18")
        teacher_uid: Optional specific teacher UID to export (single-teacher mode)

    Returns:
        filename: Path to generated CSV file
    """
    logger.info(f"Fetching attendance for {date_str}...")

    db = get_db()

    # CSV headers matching Aeries import format
    header = ["Date", "Period", "StudentID", "LastName", "FirstName", "Status", "SignInTime", "Group"]
    rows = [header]

    if teacher_uid:
        # Single-teacher mode (explicit UID provided)
        teacher_rows = export_attendance_for_teacher(date_str, teacher_uid)
        rows.extend(teacher_rows)
    else:
        # Multi-teacher mode: export all teachers
        uids = get_all_teacher_uids()

        if uids:
            for uid in uids:
                teacher_rows = export_attendance_for_teacher(date_str, uid)
                rows.extend(teacher_rows)
                logger.info(f"[{uid}] Contributed {len(teacher_rows)} rows")
        else:
            # Fallback: no teachers found in new structure — try legacy path
            logger.warning(
                "No teachers found in 'teachers' collection. "
                f"Falling back to legacy path: artifacts/{LEGACY_APP_ID}/..."
            )
            rows.extend(_export_legacy(date_str, db))

    total_records = len(rows) - 1  # Subtract header row

    if total_records == 0:
        raise Exception("No attendance data found for this date. Make sure students have signed in.")

    # Write to CSV (use absolute path so it works regardless of CWD)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(script_dir, f'attendance_{date_str}.csv')
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    logger.info(f"Exported {total_records} total records to {filename}")
    return filename


def _export_legacy(date_str, db):
    """
    Backward-compatible export using the old artifacts/{APP_ID}/public/... paths.
    Used as fallback when no per-teacher data is found.

    Returns:
        list of row lists (without header)
    """
    logger.info(f"[legacy] Fetching attendance for {date_str} from old paths...")

    periods = ["0", "1", "2", "2A", "2B", "3", "4", "5", "6", "7"]
    rows = []

    for period in periods:
        base_path = f'artifacts/{LEGACY_APP_ID}/public/data/attendance/{date_str}/periods/{period}'

        try:
            roster_doc_ref = db.document(base_path)
            roster_doc = roster_doc_ref.get()

            if not roster_doc.exists:
                continue

            roster_data = roster_doc.to_dict()
            roster = roster_data.get('roster_snapshot', [])

            if not roster:
                continue

            students_ref = db.collection(f'{base_path}/students')
            students_docs = students_ref.stream()
            signed_in = {doc.id: doc.to_dict() for doc in students_docs}

            timestamps = []
            for data in signed_in.values():
                ts = data.get('Timestamp')
                if ts is not None and hasattr(ts, 'timestamp'):
                    timestamps.append(ts)

            if len(timestamps) < MIN_STUDENTS_BEFORE_SYNC:
                logger.info(
                    f"[legacy] Period {period}: Only {len(timestamps)} sign-ins so far, "
                    f"skipping sync (need {MIN_STUDENTS_BEFORE_SYNC})"
                )
                continue

            timestamps.sort()
            nth_timestamp = timestamps[MIN_STUDENTS_BEFORE_SYNC - 1]
            now_utc = datetime.now(timezone.utc)
            if nth_timestamp.tzinfo is None:
                nth_timestamp = nth_timestamp.replace(tzinfo=timezone.utc)
            minutes_elapsed = (now_utc - nth_timestamp).total_seconds() / 60

            if minutes_elapsed < PERIOD_SETTLE_MINUTES:
                logger.info(
                    f"[legacy] Period {period}: {len(signed_in)} students signed in, but only "
                    f"{minutes_elapsed:.0f}min since {MIN_STUDENTS_BEFORE_SYNC}th sign-in. "
                    f"Skipping to avoid false absences."
                )
                continue

            for student in roster:
                student_id = student.get('StudentID', '')
                if not student_id:
                    continue

                if student_id in signed_in:
                    log = signed_in[student_id]
                    rows.append([
                        date_str, period, student_id,
                        student.get("LastName", ""), student.get("FirstName", ""),
                        log.get('Status', 'On Time'), log.get('SignInTime', ''), log.get('Group', 'N/A')
                    ])
                else:
                    rows.append([
                        date_str, period, student_id,
                        student.get("LastName", ""), student.get("FirstName", ""),
                        'Absent', 'N/A', 'N/A'
                    ])

        except Exception as e:
            logger.warning(f"[legacy] Period {period}: Error - {e}")
            continue

    logger.info(f"[legacy] Fetched {len(rows)} rows from legacy path")
    return rows


if __name__ == "__main__":
    # Test the export for today
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        csv_file = export_attendance_to_csv(today)
        print(f"Success! CSV file created: {csv_file}")
    except Exception as e:
        print(f"Error: {e}")
