"""
Admin-only database backup & restore.

Wired to the same `mis_app` credentials the app already connects with
(backend/.env) — never root; mis_app already holds ALL PRIVILEGES on
mis_reports.*, which is everything mysqldump/mysql need for a single-database
dump/restore. Shells out to the same mysqldump.exe/mysql.exe binaries the
scheduled backup_mysql.bat uses, so behaviour matches the trusted daily job.

Restore always strips the GTID_PURGED / SQL_LOG_BIN lines mysqldump emits
when the source server has GTID or binary logging enabled: setting either
needs a global admin privilege (SUPER/SYSTEM_VARIABLES_ADMIN) that a
database-scoped user like mis_app doesn't have, so `mysql < dump` would abort
on the very first statement otherwise. Dropping them is safe — they're
replication bookkeeping, not data.
"""
import glob
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException

import auth
import data_version
import dbengine
from repo import conn as rc
from repo import ops as rop
from repo import schema as rsch

router = APIRouter(prefix="/api/admin/backups", tags=["admin-backup"], dependencies=[Depends(auth.require_admin)])

# All backup/restore timestamps (filenames and the modified_at shown in the
# admin UI) are explicit IST — this app and its operators are India-based,
# and relying on "the server's OS clock happens to be set to IST" (the
# previous behaviour: datetime.now() for filenames, but tz=timezone.utc for
# modified_at, which silently disagreed with each other) breaks the moment
# either fact stops being true.
IST = ZoneInfo("Asia/Kolkata")

BACKUP_DIR = Path(os.environ.get(
    "DB_BACKUP_DIR",
    Path(__file__).resolve().parent.parent / "Report_format" / "db_backup",
))
_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.sql$")
_STRIP_RE = re.compile(r"^SET @@GLOBAL\.GTID_PURGED|SQL_LOG_BIN")

_MYSQL_CFG = {
    "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
    "port": os.environ.get("MYSQL_PORT", "3306"),
    "database": os.environ.get("MYSQL_DB", "mis_reports_v2"),
    "user": os.environ.get("MYSQL_USER", "mis_app"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
}


def _db_name() -> str:
    """The database the app is connected to (MYSQL_DB); names the dumps and
    is the one dumped and restored."""
    return dbengine._MYSQL_CFG.get("database") or _MYSQL_CFG["database"]


def _require_mysql():
    """MySQL is the only engine now; kept so call sites stay unchanged."""
    return None


_BIN_DIR_GLOBS = [
    "{drive}:/mysql/mysql-*-winx64/bin",
    "{drive}:/sql/mysql-*-winx64/bin",
    "{drive}:/MySQL/mysql-*-winx64/bin",
    "{drive}:/Program Files/MySQL/mysql-*-winx64/bin",
]


def _mysql_bin_dir() -> Path:
    """Resolves the folder holding mysqldump.exe/mysql.exe.

    MYSQL_BIN_DIR in .env is authoritative and machine-specific by design —
    it's excluded from git (see docs/SETUP.md), so each machine (home,
    Office, or wherever this runs next) sets its own value to wherever
    MySQL actually lives there, no code change needed when that moves.
    The glob below is only a best-effort fallback for when it's unset.
    """
    configured = os.environ.get("MYSQL_BIN_DIR")
    if configured:
        return Path(configured)

    patterns = [p.format(drive=d) for d in "CDEF" for p in _BIN_DIR_GLOBS]
    matches = sorted(m for pat in patterns for m in glob.glob(pat))
    if not matches:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not locate mysqldump/mysql automatically. "
                f"Set MYSQL_BIN_DIR in backend/.env to this machine's MySQL bin folder "
                f"(tried: {', '.join(patterns)})."
            ),
        )
    return Path(matches[-1])


def _open_backup(path: Path, mode: str, **kwargs):
    """open() with a short retry on PermissionError.

    Report_format/ is a Google Drive for Desktop synced folder (see the
    .tmp.driveupload staging dir it creates), and Drive grabs a brief
    no-sharing handle on each freshly written .sql while it uploads it —
    so a restore kicked off seconds after a backup, or during one of
    Drive's upload retries, hits `PermissionError: [Errno 13]` opening the
    file. The lock window is short; a few retries clears it. If it's still
    held after that, surface a 503 that names the actual cause instead of
    a raw 500 traceback."""
    last_exc = None
    for attempt in range(6):
        try:
            return open(path, mode, **kwargs)
        except PermissionError as e:
            last_exc = e
            time.sleep(1)
    raise HTTPException(
        status_code=503,
        detail=(
            f"Could not read backup file \"{path.name}\" — it's locked by another "
            "process (Google Drive for Desktop is most likely still uploading it). "
            "Wait for Drive to finish syncing and retry."
        ),
    ) from last_exc


def _safe_path(filename: str) -> Path:
    if not _FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Invalid backup filename.")
    path = (BACKUP_DIR / filename).resolve()
    if path.parent != BACKUP_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid backup filename.")
    return path


def _client_ini() -> str:
    """Throwaway [client] ini with mis_app's creds, so the password never
    appears on the process command line / in process listings."""
    fd, path = tempfile.mkstemp(suffix=".cnf", prefix="mis_backup_")
    with os.fdopen(fd, "w") as f:
        f.write("[client]\n")
        f.write(f"user={_MYSQL_CFG['user']}\n")
        f.write(f"password={_MYSQL_CFG['password']}\n")
        f.write(f"host={_MYSQL_CFG['host']}\n")
        f.write(f"port={_MYSQL_CFG['port']}\n")
    return path


def _run_dump(dest: Path) -> None:
    """mysqldump -> dest, via a temp file first so a failed/partial dump
    never overwrites a good one (same discipline as backup_mysql.bat)."""
    bin_dir = _mysql_bin_dir()
    ini_path = _client_ini()
    tmp_dest = dest.with_name(f".{dest.name}.tmp")
    try:
        with open(tmp_dest, "wb") as out:
            try:
                result = subprocess.run(
                    [
                        str(bin_dir / "mysqldump.exe"),
                        f"--defaults-extra-file={ini_path}",
                        "--single-transaction", "--no-tablespaces", "--routines", "--triggers",
                        "--set-gtid-purged=OFF",
                        _db_name(),
                    ],
                    stdout=out, stderr=subprocess.PIPE, timeout=180,
                )
            except subprocess.TimeoutExpired:
                raise HTTPException(
                    status_code=504,
                    detail="mysqldump timed out after 180s — likely blocked by a long-running "
                           "query or open transaction on mis_reports. Check SHOW FULL PROCESSLIST "
                           "/ information_schema.innodb_trx and retry.",
                )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"mysqldump failed: {result.stderr.decode(errors='replace')[:500]}")
        if tmp_dest.stat().st_size < 1024:
            raise HTTPException(status_code=500, detail="Backup dump is suspiciously small — aborted, nothing was overwritten.")
        with open(tmp_dest, "rb") as f:
            f.seek(-200, os.SEEK_END)
            if b"Dump completed on" not in f.read():
                raise HTTPException(status_code=500, detail="Backup dump looks truncated — aborted, nothing was overwritten.")
        tmp_dest.replace(dest)
    finally:
        os.remove(ini_path)
        if tmp_dest.exists():
            tmp_dest.unlink()


def _sanitize_for_restore(src: Path) -> Path:
    """Drops the GTID_PURGED / SQL_LOG_BIN admin-only SET statements.
    Only checked against the first 80 chars of each line — these are always
    short leading SET statements, so this can't accidentally match the
    substring inside a large data row later in the line."""
    fd, path = tempfile.mkstemp(suffix=".sql", prefix="mis_restore_")
    with os.fdopen(fd, "w", encoding="utf-8") as out, _open_backup(src, "r", encoding="utf-8") as f:
        for line in f:
            if not _STRIP_RE.search(line[:80]):
                out.write(line)
    return Path(path)


# Data-loss guard for restore, added after an incident (2026-08-21) where a
# restore silently emptied capital_repair_table: every OTHER table matched
# that same evening's row counts almost exactly, so a same-day admin backup
# still isn't proof a given table survived in it — mysqldump simply omits
# the INSERT entirely for a table with zero rows, and nothing before this
# surfaced that difference to whoever clicked Restore. See docs/SETUP.md.
_INSERT_LINE_RE = re.compile(r"^INSERT INTO `(\w+)` VALUES (.*);\s*$")


def _source_table_counts(path: Path) -> dict:
    """{table: row_count} parsed from a mysqldump .sql file's own INSERT
    statements — no DB connection needed, so this works against the backup
    file exactly as it sits on disk. mysqldump's --extended-insert (the
    default) writes one INSERT per table as a single very long line, but
    sums across every matching line regardless, in case a table's data was
    ever split across more than one statement."""
    counts: dict = {}
    with _open_backup(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _INSERT_LINE_RE.match(line.rstrip("\n"))
            if not m:
                continue
            table, values = m.group(1), m.group(2)
            counts[table] = counts.get(table, 0) + values.count("),(") + 1
    return counts


def _live_table_counts() -> dict:
    """{table: row_count} for every table currently in mis_reports, via the
    app's own MySQL connection (db.py) rather than shelling out."""
    conn = dbengine.connect()
    try:
        cur = conn.cursor()
        tables = [r[0] for r in rop.table_name_rows(cur)]
        counts = {}
        for t in tables:
            counts[t] = rop.table_count_row(cur, t)[0]
        return counts
    finally:
        conn.close()


def _tables_at_risk(src: Path) -> list:
    """Tables that currently hold data but would come back EMPTY if `src`
    were restored — the exact failure mode from the 2026-08-21 incident.
    Returns [(table, live_count), ...] sorted by live_count descending, or
    [] if nothing would be lost."""
    source_counts = _source_table_counts(src)
    live_counts = _live_table_counts()
    # data_version is a write counter, not data; a dump taken before it
    # existed leaves it alone, and the restore resets it anyway.
    at_risk = [
        (t, live_counts[t]) for t in live_counts
        if live_counts[t] > 0 and source_counts.get(t, 0) == 0 and t != "data_version"
    ]
    at_risk.sort(key=lambda x: -x[1])
    return at_risk


_V1_TABLE_MARK = b"CREATE TABLE `techno_data`"


def _is_v1_dump(path: Path) -> bool:
    """True if the dump file creates the v1 table `techno_data`. Read in 1 MB
    chunks (with an overlap so a match across a chunk edge is found), never
    the whole file at once."""
    keep = len(_V1_TABLE_MARK) - 1
    tail = b""
    with _open_backup(path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                return False
            buf = tail + chunk
            if _V1_TABLE_MARK in buf:
                return True
            tail = buf[-keep:]


def _live_is_v2() -> bool:
    with rc.cursor() as cur:
        return rsch.schema_state(cur)[0]


_LOCK_NAME = "mis_admin_backup_restore"


def _acquire_admin_lock():
    """A MySQL named lock (GET_LOCK), not a Python threading.Lock — this
    machine's dev server ends up with two independent uvicorn processes
    bound to the same port (the reloader + its worker; see
    docs/SETUP.md / duplicate-processes note), so an in-process lock
    wouldn't stop a request landing on the *other* process from racing a
    restore's table-by-table DROP/CREATE. GET_LOCK is server-side and
    connection-scoped, so it serializes across processes too; held for the
    life of `conn`, released by closing it (or explicitly via
    RELEASE_LOCK before that)."""
    conn = dbengine.connect()
    cur = conn.cursor()
    if rop.get_lock_row(cur, _LOCK_NAME)[0] != 1:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Another backup/restore operation is already in progress. Wait for it to finish and try again.",
        )
    return conn


def _release_admin_lock(conn) -> None:
    try:
        cur = conn.cursor()
        rop.release_lock(cur, _LOCK_NAME)
    finally:
        conn.close()


@router.get("")
def list_backups():
    _require_mysql()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for p in BACKUP_DIR.glob("*.sql"):
        st = p.stat()
        files.append({
            "filename": p.name,
            "size_bytes": st.st_size,
            "modified_at": datetime.fromtimestamp(st.st_mtime, tz=IST).isoformat(),
        })
    files.sort(key=lambda f: f["modified_at"], reverse=True)
    return {"backups": files}


@router.post("")
def create_backup(admin: dict = Depends(auth.require_admin)):
    _require_mysql()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    lock = _acquire_admin_lock()
    try:
        stamp = datetime.now(IST).strftime("%Y-%m-%d_%H%M%S")
        filename = f"{_db_name()}_admin_{stamp}.sql"
        _run_dump(BACKUP_DIR / filename)
    finally:
        _release_admin_lock(lock)
    auth.log_activity(admin, "backup", _db_name(), f"created {filename}")
    return {"status": "ok", "filename": filename}


@router.post("/{filename}/restore")
def restore_backup(filename: str, confirm_data_loss: bool = False, admin: dict = Depends(auth.require_admin)):
    _require_mysql()
    src = _safe_path(filename)
    if not src.exists():
        raise HTTPException(status_code=404, detail="Backup file not found.")

    # A v1 dump into a v2 database would put the old tables beside the new ones
    # and break the app. Not overridable by confirm_data_loss.
    if _live_is_v2() and _is_v1_dump(src):
        raise HTTPException(
            status_code=409,
            detail=(
                f"\"{filename}\" is a dump of the old (v1) schema (it creates the table techno_data), "
                f"but the live database {_db_name()} is the v2 schema. Restoring it would break the app. "
                "Choose a backup taken after the v2 cutover."
            ),
        )

    lock = _acquire_admin_lock()
    try:
        # Refuse (unless explicitly confirmed) to restore a file that would
        # wipe out any table that currently has data — this is what actually
        # happened on 2026-08-21: the chosen backup was missing
        # capital_repair_table entirely while every other table matched that
        # day's data almost exactly, so nothing about the file list or its
        # size gave any hint.
        if not confirm_data_loss:
            at_risk = _tables_at_risk(src)
            if at_risk:
                summary = ", ".join(f"{t} ({n} rows)" for t, n in at_risk[:10])
                more = f" and {len(at_risk) - 10} more" if len(at_risk) > 10 else ""
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Restoring \"{filename}\" would empty {len(at_risk)} table(s) that currently "
                        f"have data: {summary}{more}. If this is intentional, confirm to proceed anyway."
                    ),
                )

        # Safety net: snapshot current state before overwriting anything.
        prerestore_stamp = datetime.now(IST).strftime("%Y-%m-%d_%H%M%S")
        prerestore_name = f"{_db_name()}_prerestore_{prerestore_stamp}.sql"
        _run_dump(BACKUP_DIR / prerestore_name)

        bin_dir = _mysql_bin_dir()
        ini_path = _client_ini()
        sanitized = _sanitize_for_restore(src)
        try:
            with open(sanitized, "rb") as stdin_file:
                try:
                    result = subprocess.run(
                        [str(bin_dir / "mysql.exe"), f"--defaults-extra-file={ini_path}", _db_name()],
                        stdin=stdin_file, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180,
                    )
                except subprocess.TimeoutExpired:
                    raise HTTPException(
                        status_code=504,
                        detail=(
                            "Restore timed out after 180s — likely blocked by a long-running query or "
                            "open transaction on mis_reports. Check SHOW FULL PROCESSLIST / "
                            "information_schema.innodb_trx, clear the blocker, and retry. "
                            f"Data was not changed — pre-restore snapshot saved as {prerestore_name}."
                        ),
                    )
            if result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Restore failed: {result.stderr.decode(errors='replace')[:500]} "
                        f"— pre-restore snapshot saved as {prerestore_name}, data was not changed until this point."
                    ),
                )
        finally:
            os.remove(ini_path)
            sanitized.unlink(missing_ok=True)
            # The import bypassed repo writes and may have brought back an
            # older data_version (or stopped part-way): move it to a value
            # never used before and drop the in-process caches. Runs on every
            # path that may have touched the data, before the lock is freed.
            try:
                data_version.after_restore()
            except Exception:  # noqa: BLE001 - must not mask the restore's own outcome
                import logging
                logging.getLogger(__name__).exception("restore: data_version.after_restore failed")
    finally:
        _release_admin_lock(lock)

    note = f"restored from {filename}; pre-restore snapshot saved as {prerestore_name}"
    if confirm_data_loss:
        note += " (confirmed despite data-loss warning)"
    auth.log_activity(admin, "restore", _db_name(), note)
    return {"status": "ok", "restored_from": filename, "prerestore_snapshot": prerestore_name}
