"""
Railway sync worker — main entry point.

APScheduler-based orchestrator that wakes every 30 minutes during school hours
(8:00 AM – 4:00 PM Pacific, weekdays only) and syncs all teachers' attendance
to Aeries via Playwright.

Architecture:
- BlockingScheduler runs in the main thread (single-process worker)
- Each sync cycle calls sync_teacher() for every teacher sequentially
- One teacher's failure never blocks other teachers
- SIGTERM/SIGINT → graceful shutdown (Railway sends SIGTERM on redeploy)
"""

import logging
import os
import signal
import sys
from datetime import datetime

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler

from firestore_client import get_all_teacher_uids, get_db
from sync_engine import sync_teacher

logger = logging.getLogger(__name__)

PACIFIC_TZ = pytz.timezone("America/Los_Angeles")
SCHOOL_HOUR_START = 8   # 08:00 Pacific
SCHOOL_HOUR_END = 16    # 16:00 Pacific (4 PM)


# ---------------------------------------------------------------------------
# Scheduled job
# ---------------------------------------------------------------------------

def run_all_teachers():
    """
    Iterate every teacher in Firestore and call sync_teacher() for each one.

    Returns early (without syncing) if the current Pacific time is outside
    school hours (08:00–16:00) or on a weekend.

    Logs a per-teacher result and a summary at the end of each cycle.
    """
    now_pt = datetime.now(PACIFIC_TZ)
    logger.info(f"Sync cycle fired at {now_pt.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Time-of-day guard
    if now_pt.weekday() >= 5:  # Saturday=5, Sunday=6
        logger.info("Skipping sync — weekend")
        return
    if not (SCHOOL_HOUR_START <= now_pt.hour < SCHOOL_HOUR_END):
        logger.info(
            f"Skipping sync — outside school hours "
            f"(current={now_pt.hour:02d}:{now_pt.minute:02d}, "
            f"window={SCHOOL_HOUR_START:02d}:00–{SCHOOL_HOUR_END:02d}:00 PT)"
        )
        return

    # Fetch all teacher UIDs
    uids = get_all_teacher_uids()
    if not uids:
        logger.warning("No teachers found in Firestore — nothing to sync")
        return

    logger.info(f"Starting sync cycle: {len(uids)} teacher(s)")

    successes = 0
    failures = 0
    skipped = 0

    for uid in uids:
        logger.info(f"[{uid}] Starting sync...")
        try:
            result = sync_teacher(uid)
            status = result.get("status", "unknown")
            reason = result.get("reason", "")
            logger.info(
                f"[{uid}] Result: {status}"
                + (f" ({reason})" if reason else "")
            )

            if status == "success":
                successes += 1
            elif status == "failed":
                failures += 1
            else:
                skipped += 1

        except Exception as exc:
            # Safety net — sync_teacher() should catch everything, but just in case
            logger.error(
                f"[{uid}] Unhandled exception escaped sync_teacher: {exc}",
                exc_info=True,
            )
            failures += 1
            # Continue to the next teacher

    logger.info(
        f"Sync cycle complete: {len(uids)} teacher(s) processed — "
        f"{successes} success, {failures} failed, {skipped} skipped"
    )


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

_scheduler: BlockingScheduler = None


def _handle_shutdown(signum, frame):
    """Handle SIGTERM or SIGINT by shutting down the scheduler."""
    sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
    logger.info(f"Received {sig_name}, shutting down gracefully...")
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    global _scheduler

    # Configure logging (Railway streams stdout to its log viewer)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info("Railway sync worker starting...")

    # Validate required env vars — fail fast before any heavy lifting
    missing = [var for var in ("FIREBASE_SERVICE_ACCOUNT", "FERNET_KEY") if not os.environ.get(var)]
    if missing:
        logger.error(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them in Railway's Variables panel and redeploy."
        )
        sys.exit(1)

    # GEMINI_API_KEY is optional — warn but do not exit (self-healing degrades gracefully)
    if not os.environ.get("GEMINI_API_KEY"):
        logger.warning(
            "GEMINI_API_KEY not set — self-healing disabled. "
            "Selector failures will not be auto-repaired. "
            "Set it in Railway Variables to enable LLM self-healing."
        )

    # Initialize Firebase — fail fast if service account is malformed
    try:
        get_db()
        logger.info("Firebase connection verified")
    except Exception as exc:
        logger.error(f"Failed to initialize Firebase: {exc}")
        sys.exit(1)

    # Run one immediate sync cycle so the first run doesn't wait 30 minutes
    logger.info("Running immediate sync cycle on startup...")
    run_all_teachers()

    # Register signal handlers for Railway's SIGTERM on redeploy/restart
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    # Create and configure the scheduler
    _scheduler = BlockingScheduler(timezone="America/Los_Angeles")
    _scheduler.add_job(
        run_all_teachers,
        "interval",
        minutes=30,
        id="sync_job",
        replace_existing=True,
    )

    logger.info(
        "Scheduler started — sync_job will run every 30 minutes "
        f"(school hours: {SCHOOL_HOUR_START:02d}:00–{SCHOOL_HOUR_END:02d}:00 PT, weekdays only)"
    )

    try:
        _scheduler.start()  # Blocks until shutdown() is called
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker stopped")


if __name__ == "__main__":
    main()
