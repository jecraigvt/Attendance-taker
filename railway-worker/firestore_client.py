"""
Firestore client for Railway sync worker.

Initializes Firebase Admin SDK from the FIREBASE_SERVICE_ACCOUNT env var
(a JSON blob — no key file on disk) and provides all Firestore read/write
helpers needed by sync_engine.py.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

# Period IDs — must match the kiosk app
PERIODS = ["0", "1", "2", "2A", "2B", "3", "4", "5", "6", "7"]

# Settle-time thresholds (same values as attendance_to_aeries.py)
MIN_STUDENTS_BEFORE_SYNC = 5
PERIOD_SETTLE_MINUTES = 15

# Lazy-initialized globals
_db = None
_app = None


def get_db():
    """
    Return a Firestore client, initializing Firebase Admin on first call.

    Reads the full service-account JSON from the FIREBASE_SERVICE_ACCOUNT
    environment variable (not a file path) and initializes the SDK.
    """
    global _db, _app
    if _db is not None:
        return _db

    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if not sa_json:
        raise EnvironmentError(
            "FIREBASE_SERVICE_ACCOUNT environment variable is not set. "
            "Set it to the full service-account JSON string."
        )

    try:
        sa_dict = json.loads(sa_json)
        cred = credentials.Certificate(sa_dict)
        _app = firebase_admin.initialize_app(cred)
    except ValueError:
        # App already initialized (e.g. from a previous call that partially succeeded)
        _app = firebase_admin.get_app()

    _db = firestore.client()
    logger.info("Firebase Admin SDK initialized from FIREBASE_SERVICE_ACCOUNT env var")
    return _db


# ---------------------------------------------------------------------------
# Teacher-collection helpers
# ---------------------------------------------------------------------------

def get_all_teacher_uids() -> list:
    """
    Return a list of all teacher UIDs from the top-level 'teachers' collection.

    Each document ID in the collection is one teacher's Firebase Auth UID.
    Returns an empty list if the collection is empty or unreadable.
    """
    db = get_db()
    try:
        docs = db.collection("teachers").stream()
        uids = [doc.id for doc in docs]
        logger.info(f"[get_all_teacher_uids] Found {len(uids)} teacher(s)")
        return uids
    except Exception as exc:
        logger.error(f"[get_all_teacher_uids] Failed to read teachers collection: {exc}")
        return []


def get_teacher_credentials(uid: str) -> Optional[dict]:
    """
    Return raw (still-encrypted) credentials for one teacher.

    Reads teachers/{uid}/credentials/aeries.
    Returns a dict with 'username' and 'encryptedPassword' keys,
    or None if the document is missing or has no usable fields.
    """
    db = get_db()
    try:
        ref = db.document(f"teachers/{uid}/credentials/aeries")
        doc = ref.get()
        if not doc.exists:
            logger.warning(f"[{uid}] No credentials document at teachers/{uid}/credentials/aeries")
            return None
        data = doc.to_dict()
        username = data.get("username")
        encrypted_password = data.get("encryptedPassword")
        if not username or not encrypted_password:
            logger.warning(f"[{uid}] Credentials document is missing username or encryptedPassword")
            return None
        return {"username": username, "encryptedPassword": encrypted_password}
    except Exception as exc:
        logger.error(f"[{uid}] Error reading credentials: {exc}")
        return None


def get_teacher_attendance(uid: str, date_str: str) -> list:
    """
    Fetch all settled attendance rows for *uid* on *date_str*.

    Mirrors export_attendance_for_teacher() in attendance_to_aeries.py but
    returns a list of dicts instead of CSV rows.  A period is included only
    when it has settled (MIN_STUDENTS_BEFORE_SYNC sign-ins AND
    PERIOD_SETTLE_MINUTES elapsed since the Nth sign-in).

    Returns an empty list on non-school days / periods with no data.

    Each row dict has keys:
        date, period, student_id, last_name, first_name,
        status, sign_in_time, group
    """
    db = get_db()
    rows = []

    for period in PERIODS:
        base_path = f"teachers/{uid}/attendance/{date_str}/periods/{period}"

        try:
            roster_doc = db.document(base_path).get()
            if not roster_doc.exists:
                continue

            roster_data = roster_doc.to_dict()
            roster = roster_data.get("roster_snapshot", [])
            if not roster:
                logger.debug(f"[{uid}] Period {period}: No roster_snapshot (skipping)")
                continue

            # Fetch sign-ins
            signed_in = {
                doc.id: doc.to_dict()
                for doc in db.collection(f"{base_path}/students").stream()
            }

            # Collect timestamps to check settle status
            timestamps = []
            for data in signed_in.values():
                ts = data.get("Timestamp")
                if ts is not None and hasattr(ts, "timestamp"):
                    timestamps.append(ts)

            if len(timestamps) < MIN_STUDENTS_BEFORE_SYNC:
                logger.info(
                    f"[{uid}] Period {period}: Only {len(timestamps)} sign-in(s), "
                    f"need {MIN_STUDENTS_BEFORE_SYNC} — skipping"
                )
                continue

            timestamps.sort()
            nth_ts = timestamps[MIN_STUDENTS_BEFORE_SYNC - 1]
            now_utc = datetime.now(timezone.utc)
            # Ensure timezone-aware comparison (guard against naive by treating as UTC)
            if nth_ts.tzinfo is None:
                nth_ts = nth_ts.replace(tzinfo=timezone.utc)
            minutes_elapsed = (now_utc - nth_ts).total_seconds() / 60

            if minutes_elapsed < PERIOD_SETTLE_MINUTES:
                logger.info(
                    f"[{uid}] Period {period}: {len(signed_in)} sign-in(s) but only "
                    f"{minutes_elapsed:.0f}min since {MIN_STUDENTS_BEFORE_SYNC}th "
                    f"(need {PERIOD_SETTLE_MINUTES}min) — skipping to avoid false absences"
                )
                continue

            # Period has settled — emit one row per roster student
            for student in roster:
                student_id = student.get("StudentID", "")
                if not student_id:
                    logger.warning(f"[{uid}] Period {period}: Skipping student with no StudentID")
                    continue

                if student_id in signed_in:
                    log = signed_in[student_id]
                    rows.append({
                        "date": date_str,
                        "period": period,
                        "student_id": student_id,
                        "last_name": student.get("LastName", ""),
                        "first_name": student.get("FirstName", ""),
                        "status": log.get("Status", "On Time"),
                        "sign_in_time": log.get("SignInTime", ""),
                        "group": log.get("Group", "N/A"),
                    })
                else:
                    rows.append({
                        "date": date_str,
                        "period": period,
                        "student_id": student_id,
                        "last_name": student.get("LastName", ""),
                        "first_name": student.get("FirstName", ""),
                        "status": "Absent",
                        "sign_in_time": "N/A",
                        "group": "N/A",
                    })

            absent_count = sum(1 for r in rows if r["period"] == period and r["status"] == "Absent")
            present_count = len(signed_in)
            logger.info(
                f"[{uid}] Period {period}: {len(roster)} students "
                f"({present_count} present, {absent_count} absent)"
            )

        except Exception as exc:
            logger.warning(f"[{uid}] Period {period}: Error reading attendance — {exc}")
            continue

    return rows


def get_last_sync_time(uid: str) -> Optional[datetime]:
    """
    Return the lastSyncTime from teachers/{uid}/sync/status, or None.

    The field is a Firestore Timestamp; convert to timezone-aware datetime (UTC)
    for comparison against sign-in timestamps.
    """
    db = get_db()
    try:
        doc = db.document(f"teachers/{uid}/sync/status").get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        ts = data.get("lastSyncTime")
        if ts is None:
            return None
        # Firestore Timestamps have a .timestamp() method returning epoch seconds
        if hasattr(ts, "timestamp"):
            return datetime.fromtimestamp(ts.timestamp(), tz=timezone.utc)
        # Fallback: already a datetime
        if isinstance(ts, datetime):
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        return None
    except Exception as exc:
        logger.error(f"[{uid}] Error reading sync/status: {exc}")
        return None


def get_latest_attendance_timestamp(uid: str, date_str: str) -> Optional[datetime]:
    """
    Scan all period subcollections for *date_str* and return the most recent
    student sign-in Timestamp, or None if no data exists.

    Used to decide whether new attendance data has arrived since the last sync.
    """
    db = get_db()
    latest = None

    for period in PERIODS:
        base_path = f"teachers/{uid}/attendance/{date_str}/periods/{period}"
        try:
            students_docs = db.collection(f"{base_path}/students").stream()
            for doc in students_docs:
                data = doc.to_dict()
                ts = data.get("Timestamp")
                if ts is not None and hasattr(ts, "timestamp"):
                    ts_dt = datetime.fromtimestamp(ts.timestamp(), tz=timezone.utc)
                    if latest is None or ts_dt > latest:
                        latest = ts_dt
        except Exception as exc:
            logger.debug(f"[{uid}] Period {period}: Error scanning timestamps — {exc}")
            continue

    return latest


def write_sync_status(
    uid: str,
    status: str,
    error: str = None,
    error_category: str = None,
    periods_processed: int = None,
    unsyncable: list = None,
) -> None:
    """
    Write sync status to teachers/{uid}/sync/status (merge).

    Fields written:
        status            — 'success' | 'failed' | 'skipped'
        lastSyncTime      — SERVER_TIMESTAMP
        error             — friendly error string, or deleted if None
        periodsProcessed  — integer, omitted if None
        unsyncableStudents — list of {studentId, period, reason}, omitted if None

    This document is the one the dashboard's watchSyncStatus() reads via onSnapshot.
    """
    db = get_db()
    try:
        doc_data = {
            "status": status,
            "lastSyncTime": firestore.SERVER_TIMESTAMP,
        }

        if error is not None:
            doc_data["error"] = error
        else:
            # Explicitly delete the error field if it existed from a prior failure
            doc_data["error"] = firestore.DELETE_FIELD

        if error_category is not None:
            doc_data["errorCategory"] = error_category
        else:
            doc_data["errorCategory"] = firestore.DELETE_FIELD

        if periods_processed is not None:
            doc_data["periodsProcessed"] = periods_processed

        if unsyncable is not None:
            doc_data["unsyncableStudents"] = unsyncable

        db.document(f"teachers/{uid}/sync/status").set(doc_data, merge=True)
        logger.info(f"[{uid}] Wrote sync status: {status}")
    except Exception as exc:
        logger.error(f"[{uid}] Failed to write sync status: {exc}")


def is_sync_enabled(uid: str) -> bool:
    """
    Return True if the teacher has syncEnabled set to True in config/main.

    Sync is OFF by default — the admin must explicitly enable it per teacher
    by setting syncEnabled: true in teachers/{uid}/config/main.
    """
    db = get_db()
    try:
        doc = db.document(f"teachers/{uid}/config/main").get()
        if not doc.exists:
            return False
        return doc.to_dict().get("syncEnabled", False) is True
    except Exception as exc:
        logger.error(f"[{uid}] Error checking syncEnabled: {exc}")
        return False  # fail-closed: don't sync if we can't confirm it's enabled


def is_sync_blocked(uid: str) -> bool:
    """
    Return True if the teacher's sync is blocked due to credentials_invalid
    AND the failure happened less than 2 hours ago.

    This auto-expires so a single transient Aeries login failure doesn't
    permanently block auto-sync.  If credentials are truly wrong the block
    will be re-set on the next attempt.
    """
    db = get_db()
    try:
        doc = db.document(f"teachers/{uid}/sync/status").get()
        if not doc.exists:
            return False
        data = doc.to_dict()
        if data.get("errorCategory") != "credentials_invalid":
            return False
        # Auto-expire after 2 hours
        last_sync = data.get("lastSyncTime")
        if last_sync is not None:
            if hasattr(last_sync, "seconds"):
                last_dt = datetime.fromtimestamp(last_sync.seconds, tz=timezone.utc)
            else:
                last_dt = last_sync
            if datetime.now(timezone.utc) - last_dt > timedelta(hours=2):
                return False  # block expired — retry
        return True
    except Exception as exc:
        logger.error(f"[{uid}] Error checking sync block status: {exc}")
        return False


# ---------------------------------------------------------------------------
# Self-healing event helpers
# ---------------------------------------------------------------------------

def write_healing_event(
    element_type: str,
    model: str,
    candidate: Optional[str],
    success: bool,
    teacher_uid: Optional[str] = None,
    format_args: Optional[dict] = None,
) -> None:
    """
    Write a healing attempt event to the global `healing_events` collection.

    This collection is NOT per-teacher — it lives at the top level so the
    developer can review all healing activity in one place.

    Document structure:
        timestamp       — SERVER_TIMESTAMP (UTC)
        elementType     — e.g. "absent_checkbox"
        model           — "gemini-2.0-flash" or "gemini-2.0-pro"
        candidateSelector — the selector Gemini returned (or None)
        success         — bool: whether the selector validated on the page
        teacherUid      — optional: which teacher's sync triggered healing
        formatArgs      — optional: the format_args dict (e.g. {"student_id": "..."})
    """
    db = get_db()
    try:
        doc_data = {
            "timestamp": firestore.SERVER_TIMESTAMP,
            "elementType": element_type,
            "model": model,
            "candidateSelector": candidate,
            "success": success,
        }
        if teacher_uid is not None:
            doc_data["teacherUid"] = teacher_uid
        if format_args is not None:
            # Serialize format_args as a string to avoid type issues with non-string keys
            doc_data["formatArgs"] = {str(k): str(v) for k, v in format_args.items()}

        db.collection("healing_events").add(doc_data)
        logger.info(
            f"[healing] Logged event: element={element_type} model={model} "
            f"success={success}"
        )
    except Exception as exc:
        # Non-fatal — don't let a logging failure break the sync
        logger.error(f"[healing] Failed to write healing event: {exc}")


def get_healing_call_count_today() -> int:
    """
    Return the number of healing events logged today (UTC).

    Used to enforce the DAILY_HEALING_CAP before making a Gemini API call.
    Returns 0 on any error (fail-open: prefer attempting healing over blocking it).
    """
    db = get_db()
    try:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        query = (
            db.collection("healing_events")
            .where("timestamp", ">=", today_start)
        )
        docs = list(query.stream())
        count = len(docs)
        logger.debug(f"[healing] Healing call count today: {count}")
        return count
    except Exception as exc:
        logger.error(f"[healing] Failed to count today's healing events: {exc}")
        return 0  # fail-open


def get_teacher_profile(uid: str) -> dict:
    """
    Return the teacher's profile from teachers/{uid}/profile/info.

    Falls back to a safe default dict if the document is missing.
    Callers can check profile.get('timezone', 'America/Los_Angeles').
    """
    db = get_db()
    try:
        doc = db.document(f"teachers/{uid}/profile/info").get()
        if doc.exists:
            return doc.to_dict() or {}
        logger.debug(f"[{uid}] No profile/info document — using defaults")
        return {}
    except Exception as exc:
        logger.error(f"[{uid}] Error reading profile/info: {exc}")
        return {}
