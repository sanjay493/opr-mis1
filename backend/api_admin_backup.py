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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import auth
from dbengine import DB_ENGINE

router = APIRouter(prefix="/api/admin/backups", tags=["admin-backup"], dependencies=[Depends(auth.require_admin)])

BACKUP_DIR = Path(os.environ.get(
    "DB_BACKUP_DIR",
    Path(__file__).resolve().parent.parent / "Report_format" / "db_backup",
))
_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.sql$")
_STRIP_RE = re.compile(r"^SET @@GLOBAL\.GTID_PURGED|SQL_LOG_BIN")

_MYSQL_CFG = {
    "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
    "port": os.environ.get("MYSQL_PORT", "3306"),
    "database": os.environ.get("MYSQL_DB", "mis_reports"),
    "user": os.environ.get("MYSQL_USER", "mis_app"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
}


class RestoreRequest(BaseModel):
    filename: str


def _require_mysql():
    if DB_ENGINE != "mysql":
        raise HTTPException(status_code=400, detail="Backup/restore is only available when DB_ENGINE=mysql.")


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
            result = subprocess.run(
                [
                    str(bin_dir / "mysqldump.exe"),
                    f"--defaults-extra-file={ini_path}",
                    "--single-transaction", "--no-tablespaces", "--routines", "--triggers",
                    "--set-gtid-purged=OFF",
                    _MYSQL_CFG["database"],
                ],
                stdout=out, stderr=subprocess.PIPE, timeout=180,
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
    with os.fdopen(fd, "w", encoding="utf-8") as out, open(src, "r", encoding="utf-8") as f:
        for line in f:
            if not _STRIP_RE.search(line[:80]):
                out.write(line)
    return Path(path)


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
            "modified_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        })
    files.sort(key=lambda f: f["modified_at"], reverse=True)
    return {"backups": files}


@router.post("")
def create_backup(admin: dict = Depends(auth.require_admin)):
    _require_mysql()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"mis_reports_admin_{stamp}.sql"
    _run_dump(BACKUP_DIR / filename)
    auth.log_activity(admin, "backup", "mis_reports", f"created {filename}")
    return {"status": "ok", "filename": filename}


@router.post("/{filename}/restore")
def restore_backup(filename: str, admin: dict = Depends(auth.require_admin)):
    _require_mysql()
    src = _safe_path(filename)
    if not src.exists():
        raise HTTPException(status_code=404, detail="Backup file not found.")

    # Safety net: snapshot current state before overwriting anything.
    prerestore_stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    prerestore_name = f"mis_reports_prerestore_{prerestore_stamp}.sql"
    _run_dump(BACKUP_DIR / prerestore_name)

    bin_dir = _mysql_bin_dir()
    ini_path = _client_ini()
    sanitized = _sanitize_for_restore(src)
    try:
        with open(sanitized, "rb") as stdin_file:
            result = subprocess.run(
                [str(bin_dir / "mysql.exe"), f"--defaults-extra-file={ini_path}", _MYSQL_CFG["database"]],
                stdin=stdin_file, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180,
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

    auth.log_activity(
        admin, "restore", "mis_reports",
        f"restored from {filename}; pre-restore snapshot saved as {prerestore_name}",
    )
    return {"status": "ok", "restored_from": filename, "prerestore_snapshot": prerestore_name}
