"""Daily backup scheduler for mis_reports.db.

Usage:
    python scheduler.py              # runs immediately then daily at 02:00
    python scheduler.py --now        # one-shot backup and exit
    python scheduler.py --time 03:30 # custom daily backup time

Rotation: keeps the 7 most recent dated backups; deletes anything older.
Backups are written to  archive/mis_reports_YYYY-MM-DD.db
"""

import argparse
import glob
import logging
import os
import shutil
import sys
import time
from datetime import datetime

import schedule

# ---------------------------------------------------------------------------
# Paths — resolved relative to this file so the script works from any cwd
# ---------------------------------------------------------------------------
_ROOT      = os.path.dirname(os.path.abspath(__file__))
DB_PATH    = os.path.join(_ROOT, "backend", "mis_reports.db")
BACKUP_DIR = os.path.join(_ROOT, "archive")
LOG_PATH   = os.path.join(_ROOT, "backup.log")

MAX_BACKUPS  = 7
BACKUP_GLOB  = "mis_reports_????-??-??.db"   # matches dated backups only

# ---------------------------------------------------------------------------
# Logging — both file and console
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("db_backup")


# ---------------------------------------------------------------------------
# Core backup logic
# ---------------------------------------------------------------------------

def run_backup() -> bool:
    """Copy the live DB to a dated backup file, then prune old backups.

    Returns True on success, False on error.
    """
    if not os.path.exists(DB_PATH):
        logger.error("Source DB not found: %s", DB_PATH)
        return False

    os.makedirs(BACKUP_DIR, exist_ok=True)

    stamp   = datetime.now().strftime("%Y-%m-%d")
    dst     = os.path.join(BACKUP_DIR, f"mis_reports_{stamp}.db")
    src_kb  = os.path.getsize(DB_PATH) // 1024

    try:
        shutil.copy2(DB_PATH, dst)
    except OSError as exc:
        logger.error("Backup copy failed: %s", exc)
        return False

    logger.info("Backup OK -> %s  (%d KB)", os.path.basename(dst), src_kb)

    _prune_old_backups()
    return True


def _prune_old_backups():
    """Delete the oldest backups, keeping only MAX_BACKUPS files."""
    pattern = os.path.join(BACKUP_DIR, BACKUP_GLOB)
    # Lexicographic sort on YYYY-MM-DD filenames = chronological order
    backups = sorted(glob.glob(pattern))
    excess  = len(backups) - MAX_BACKUPS

    if excess <= 0:
        logger.info(
            "Rotation: %d/%d backup(s) kept - nothing to delete.",
            len(backups), MAX_BACKUPS,
        )
        return

    for old in backups[:excess]:
        try:
            os.remove(old)
            logger.info("Rotation: deleted old backup  %s", os.path.basename(old))
        except OSError as exc:
            logger.warning("Could not delete %s: %s", old, exc)

    remaining = len(backups) - excess
    logger.info("Rotation: %d backup(s) retained.", remaining)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Daily mis_reports.db backup scheduler")
    parser.add_argument("--now",  action="store_true", help="Run one backup immediately and exit")
    parser.add_argument("--time", default="02:00",     help="Daily backup time HH:MM (default 02:00)")
    args = parser.parse_args()

    if args.now:
        success = run_backup()
        sys.exit(0 if success else 1)

    # Validate time format
    try:
        datetime.strptime(args.time, "%H:%M")
    except ValueError:
        parser.error(f"--time must be HH:MM, got {args.time!r}")

    logger.info("Scheduler started. Daily backup at %s. Max backups: %d.", args.time, MAX_BACKUPS)

    # Run once immediately so the user gets a backup right away
    run_backup()

    schedule.every().day.at(args.time).do(run_backup)

    logger.info("Waiting for next scheduled run. Press Ctrl+C to stop.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
