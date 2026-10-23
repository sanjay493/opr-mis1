"""Operational repository on the v2 schema: app_user (v1 users),
allowed_email, otp_code, activity_log, page_visit, admin_notification,
extraction_log, todo_job and daily_work_log.

Same public names, signatures, return shapes, row types and exceptions as
repo/ops.py. Renamed columns are aliased back to their v1 names
(activity_log / page_visits `timestamp`, allowed_emails `added_by` /
`added_at`, extraction_log `logged_at`); `SELECT *` readers list the v1
columns in v1 order, so cur.description and dict keys are unchanged.

TIMESTAMPS (repo.v2codec per-column map). Every timestamp column is a
DATETIME(6) rendered back, in SQL (_keys.iso_sql, so the rows keep the
caller's own row type), to the exact string v1 stored: UTC ISO with
'+00:00' for users / allowed_emails / otp_codes / activity_log /
page_visits / admin_notifications; naive local ISO for todo_jobs and
daily_work_log; 'YYYY-MM-DD HH:MM:SS' for extraction_log. Writers that take
the v1 string from the caller parse it with the column's format; the
internal writers store the same instant their v1 counterpart formatted
(datetime.now(timezone.utc), datetime.now(), strftime). "Since" filters
(page_visit_rows_since, the anon-visit window) convert the ISO bound to
the stored UTC wall-clock datetime in Python, never through MySQL's
time-zone-aware literal parsing. A string that is not in the column's
canonical form is refused (OutOfModelError, parity_exceptions.md §2).
todo_jobs.due_date / daily_work_log.work_date are DATEs: a non-canonical
date is refused the same way.

BUMPS. users, allowed_emails, otp_codes, the logs, to-do and work-log
tables are exempt from data_version bumping, as in v1 (no report page
reads them); log_extraction bumps, as v1 (page 4 reads extraction_log).

extraction_log has no month or plant FK: 'TESTPLANT' and '2099-01' work.
"""
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional

import pymysql

from dbengine import Row, connect
from repo import version as _ver
from repo import _keys
from repo.v2codec import ISO_LOCAL, ISO_UTC, SQL_SECONDS

_I = _keys.iso_sql


def _utc(col, alias=None):
    return f"{_I(col, ISO_UTC)} AS `{alias or col}`"


def _local(col, alias=None):
    return f"{_I(col, ISO_LOCAL)} AS `{alias or col}`"


_USER_COLS = ("id, email, password_hash, name, role, profile_pic, " + _utc("created_at") + ", "
              + _utc("updated_at") + ", allowed_pages, can_delete")
_ALLOWED_COLS = ("email, created_by AS added_by, " + _utc("created_at", "added_at")
                 + ", barred, barred_by, " + _utc("barred_at"))
_ACTIVITY_COLS = "id, user_email, user_name, action, entity, details, " + _utc("created_at", "timestamp")
_VISIT_COLS = "id, " + _utc("created_at", "timestamp") + ", ip_address, user_email, user_name, path"
_TODO_COLS = ("id, subject, details, recipient, due_date, priority, status, " + _local("created_at") + ", "
              + _local("completed_at") + ", remark")
_WORKLOG_COLS = "id, work_date, description, remarks, " + _local("created_at")


def _naive_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _key(col, direction="ASC"):
    """ORDER BY terms reproducing how v1 sorted its UTC ISO text. Under
    utf8mb4_0900_ai_ci '.' sorts before '+', so within one second a value
    with a fraction ('...:05.250000+00:00') sorts BEFORE the whole-second
    one ('...:05+00:00'), the reverse of datetime order; fractions then
    compare numerically. Key = (second, no-fraction?, microsecond)."""
    return (f"DATE_FORMAT({col}, '%%Y-%%m-%%d %%H:%%i:%%s') {direction}, "
            f"IF(MICROSECOND({col}) = 0, 1, 0) {direction}, MICROSECOND({col}) {direction}")


def _key_ge(col, value, column):
    """(SQL, params) for v1's `col >= value` string comparison (same key)."""
    dt = _keys.stamp(ISO_UTC, value, column)
    return (f"(DATE_FORMAT({col}, '%%Y-%%m-%%d %%H:%%i:%%s'), IF(MICROSECOND({col}) = 0, 1, 0), "
            f"MICROSECOND({col})) >= (%s, %s, %s)",
            (dt.strftime("%Y-%m-%d %H:%M:%S"), 1 if dt.microsecond == 0 else 0, dt.microsecond))


# ── Moved from db.py ─────────────────────────────────────────────────────────

def log_page_visit(ip_address: str, user: Optional[dict], path: str) -> None:
    """Appends one row to page_visits — a frontend navigation to `path`,
    from `ip_address`, by `user` (the get_current_user_optional dict) or
    anonymously if `user` is None. See api_visits.py's POST /api/log-visit."""
    now = datetime.now(timezone.utc)
    conn = connect()
    conn.execute("""
        INSERT INTO page_visit (created_at, ip_address, user_email, user_name, path)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        _naive_utc(now),
        ip_address or None,
        user.get("email") if user else None,
        user.get("name") if user else None,
        path,
    ))
    conn.commit()
    conn.close()


ANON_VISIT_NOTIFY_WINDOW_MINUTES = 30


def add_admin_notification(kind: str, ip_address: str = "", user: Optional[dict] = None,
                           path: Optional[str] = None) -> None:
    """Records one event for the admin notification bell. kind is 'sign_in'
    or 'anon_visit'. An 'anon_visit' is skipped when the same IP already
    raised one in the last ANON_VISIT_NOTIFY_WINDOW_MINUTES, so a visitor
    clicking around doesn't produce one alert per page.

    Best-effort: a failure here is logged and swallowed — it must never
    break the sign-in or visit request that triggered it."""
    try:
        _add_admin_notification(kind, ip_address, user, path)
    except Exception as e:
        print(f"[admin_notifications] could not record {kind}: {e}")


def _add_admin_notification(kind, ip_address, user, path) -> None:
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    conn = connect()
    try:
        if kind == "anon_visit":
            since = (now - timedelta(minutes=ANON_VISIT_NOTIFY_WINDOW_MINUTES)).isoformat()
            cond, cparams = _key_ge("created_at", since, "since")
            row = conn.execute(
                "SELECT 1 FROM admin_notification WHERE kind = 'anon_visit' AND ip_address = %s "
                f"AND {cond} LIMIT 1",
                (ip_address or None, *cparams),
            ).fetchone()
            if row:
                return
        conn.execute("""
            INSERT INTO admin_notification (created_at, kind, user_email, user_name, ip_address, path)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            _naive_utc(now),
            kind,
            user.get("email") if user else None,
            user.get("name") if user else None,
            ip_address or None,
            path,
        ))
        conn.commit()
    finally:
        conn.close()


def list_admin_notifications(limit: int = 30) -> List[Dict[str, Any]]:
    """Newest-first admin notification events (see add_admin_notification)."""
    conn = connect()
    conn.row_factory = Row
    try:
        rows = conn.execute(
            "SELECT id, " + _utc("created_at") + ", kind, user_email, user_name, ip_address, path "
            "FROM admin_notification ORDER BY id DESC LIMIT %s",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Is a month's production data final? (page 4's "Tentative" label) ──────
# A month is final once each of these plants has its FINAL monthly report in
# extraction_log for that month; interim uploads (daily/morning reports, DSP's
# pcontrep/mcr1, BSL's DPR mail) don't count. BSP/ASP/SSP/VISL aren't
# checked (per direct instruction, 2026-10-04: BSP re-uploads the same PPC MIS
# workbook through and after the month, so no upload marks it final).
# Months before _FINAL_STATUS_FROM predate the log tracking these uploads
# (their final figures came from backfills), so they always count as final.
_FINAL_STATUS_FROM = "2026-04"


_FINAL_REPORT_RULES = {
    "RSP": lambda src, fname, ym: src.startswith("Final Monthly Report"),
    "ISP": lambda src, fname, ym: src.startswith(("Final Monthly Report", "Summarized Monthly Report")),
    "BSL": lambda src, fname, ym: src.startswith("BSL Production of Main Products (PDF)"),
    # DSP's monthly MIS PDF is named for its month: mis0826.pdf = Aug'26.
    "DSP": lambda src, fname, ym: src == "DSP OMI PDF Report" and re.match(
        rf"(?i)mis{ym[5:7]}{ym[2:4]}\b", fname or "") is not None,
}


def _production_month_status(report_month: str, log_rows) -> dict:
    """Pure rule: log_rows = [(plant_name, source_type, file_name), ...] for
    report_month -> {"tentative": bool, "missing": [plants without a final
    monthly report]}."""
    if report_month < _FINAL_STATUS_FROM:
        return {"tentative": False, "missing": []}
    missing = [plant for plant, rule in _FINAL_REPORT_RULES.items()
               if not any(p == plant and rule(src or "", fname, report_month) for p, src, fname in log_rows)]
    return {"tentative": bool(missing), "missing": missing}


def production_month_status(report_month: str) -> dict:
    """{"tentative", "missing"} for report_month from extraction_log — see
    _production_month_status."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT plant_name, source_type, file_name FROM extraction_log WHERE report_month = %s "
                    "ORDER BY id", (report_month,))
        return _production_month_status(report_month, cur.fetchall())
    finally:
        conn.close()


def log_extraction(plant: str, report_month: str, file_name: str, sheet_name: str,
                   source_type: str, items_extracted: int, conn=None):
    """Appends a record to the extraction audit log.

    `conn`: see merge_upsert_techno_data's docstring — when reused, this
    does NOT commit; the caller owns the transaction boundary (see
    _raw_upsert_techno_data's docstring for why that matters here)."""
    logged_at = datetime.now().replace(microsecond=0)         # strftime("%Y-%m-%d %H:%M:%S")
    _keys.fits("plant_name", plant, 32, nullable=False)
    _keys.fits("report_month", report_month, 7, nullable=False)
    stored_month = _keys.fit_month(report_month)
    owns_conn = conn is None
    if owns_conn:
        conn = connect()
    _ver.bump(conn)       # page 4's "tentative" flag reads extraction_log
    conn.execute("""
        INSERT INTO extraction_log (created_at, plant_name, report_month, file_name, sheet_name, source_type, items_extracted)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (logged_at, plant, stored_month, file_name, sheet_name, source_type, items_extracted))
    if owns_conn:
        conn.commit()
        conn.close()


def get_extraction_logs(limit: int = 60, plant: Optional[str] = None,
                         source_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns the most recent extraction log entries, newest first.
    Optional plant/source_type filters let a page (e.g. /data-entry/techno)
    show only its own entries from this shared log table."""
    conn = connect()
    conn.row_factory = Row
    clauses, params = [], []
    if plant:
        clauses.append("plant_name = %s")
        params.append(plant)
    if source_type:
        clauses.append("source_type = %s")
        params.append(source_type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = conn.execute(f"""
        SELECT id, {_I('created_at', SQL_SECONDS)} AS logged_at, plant_name, report_month, file_name, sheet_name,
               source_type, items_extracted
        FROM extraction_log
        {where}
        ORDER BY id DESC
        LIMIT %s
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Moved from auth.py ────────────────────────────────────────────────────────

def get_user_by_email(email: str) -> Optional[dict]:
    conn = connect()
    conn.row_factory = Row
    cur = conn.cursor()
    cur.execute(f"SELECT {_USER_COLS} FROM app_user WHERE email=%s", (email,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = connect()
    conn.row_factory = Row
    cur = conn.cursor()
    cur.execute(f"SELECT {_USER_COLS} FROM app_user WHERE id=%s", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def is_email_allowed(email: str) -> bool:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT barred FROM allowed_email WHERE email=%s", (email,))
    row = cur.fetchone()
    conn.close()
    return row is not None and row[0] == 0


def _is_barred(email: str) -> bool:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT barred FROM allowed_email WHERE email=%s", (email,))
    row = cur.fetchone()
    conn.close()
    return bool(row and row[0] == 1)


def log_activity(user: Optional[dict], action: str, entity: str, details: str = "") -> None:
    """action: 'insert' | 'update' | 'delete'."""
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO activity_log (user_email, user_name, action, entity, details, created_at)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (
            user.get("email") if user else None,
            user.get("name") if user else None,
            action,
            entity,
            details,
            _naive_utc(datetime.now(timezone.utc)),
        ),
    )
    conn.commit()
    conn.close()


# ── otp_codes (auth.py) ──────────────────────────────────────────────────────

def otp_invalidate_unused(cur, email, purpose):
    """Mark every unused code for email+purpose used, on the caller's cursor.
    auth.generate_and_store_otp."""
    cur.execute(
        "UPDATE otp_code SET used=1 WHERE email=%s AND purpose=%s AND used=0",
        (email, purpose),
    )


def otp_insert(cur, email, purpose, code_hash, expires_at, created_at):
    """Store a new hashed code on the caller's cursor; the caller commits.
    expires_at / created_at are ISO strings. auth.generate_and_store_otp."""
    _keys.fits("expires_at", expires_at, 40)
    _keys.fits("created_at", created_at, 40)
    expires = _keys.stamp(ISO_UTC, expires_at, "expires_at")
    created = _keys.stamp(ISO_UTC, created_at, "created_at")
    cur.execute(
        """INSERT INTO otp_code (email, purpose, code_hash, expires_at, used, created_at)
           VALUES (%s, %s, %s, %s, 0, %s)""",
        (email, purpose, code_hash, expires, created),
    )


def otp_latest_created_row(cur, email, purpose):
    """fetchone() of (created_at,) of the newest code for email+purpose.
    auth.otp_resend_wait_seconds."""
    cur.execute(
        f"""SELECT {_utc('created_at')} FROM otp_code WHERE email=%s AND purpose=%s
           ORDER BY id DESC LIMIT 1""",
        (email, purpose),
    )
    return cur.fetchone()


def otp_latest_unused_row(cur, email, purpose):
    """fetchone() of (id, code_hash, expires_at) of the newest unused code.
    auth.verify_otp."""
    cur.execute(
        f"""SELECT id, code_hash, {_utc('expires_at')} FROM otp_code
           WHERE email=%s AND purpose=%s AND used=0
           ORDER BY id DESC LIMIT 1""",
        (email, purpose),
    )
    return cur.fetchone()


def otp_mark_used(cur, otp_id):
    """Burn one code on the caller's cursor; the caller commits. auth.verify_otp."""
    cur.execute("UPDATE otp_code SET used=1 WHERE id=%s", (otp_id,))


# ── users (api_auth.py / api_admin.py) ───────────────────────────────────────

def insert_user(cur, email, password_hash, name, created_at, updated_at):
    """Create an account (role NULL) on the caller's cursor; the caller reads
    cur.lastrowid and commits. api_auth register_verify."""
    _keys.fits("created_at", created_at, 40, nullable=False)
    _keys.fits("updated_at", updated_at, 40)
    created = _keys.stamp(ISO_UTC, created_at, "created_at")
    updated = _keys.stamp(ISO_UTC, updated_at, "updated_at")
    try:
        cur.execute(
            """INSERT INTO app_user (email, password_hash, name, role, profile_pic, created_at, updated_at)
               VALUES (%s, %s, %s, NULL, '', %s, %s)""",
            (email, password_hash, name, created, updated),
        )
    except pymysql.err.IntegrityError as e:
        if e.args and e.args[0] == 1062:            # v1's unique key was users.email
            raise type(e)(e.args[0], str(e.args[1]).replace("app_user.uq_app_user_email", "users.email")) from None
        raise


def update_password(cur, password_hash, updated_at, email):
    """api_auth password_verify; the caller commits."""
    _keys.fits("updated_at", updated_at, 40)
    cur.execute(
        "UPDATE app_user SET password_hash=%s, updated_at=%s WHERE email=%s",
        (password_hash, _keys.stamp(ISO_UTC, updated_at, "updated_at"), email),
    )


def update_user_fields(cur, updates, params):
    """UPDATE users SET <updates> WHERE id=%s; `updates` are the caller's
    "col=%s" fragments, `params` their values followed by the user id.
    api_auth update_profile; the caller commits."""
    params = list(params)
    for i, frag in enumerate(updates):
        col = frag.split("=")[0].strip()
        if col in ("created_at", "updated_at"):
            _keys.fits(col, params[i], 40, nullable=col == "updated_at")
            params[i] = _keys.stamp(ISO_UTC, params[i], col)
    try:
        cur.execute(f"UPDATE app_user SET {', '.join(updates)} WHERE id=%s", params)
    except pymysql.err.IntegrityError as e:
        if e.args and e.args[0] == 1062:
            raise type(e)(e.args[0], str(e.args[1]).replace("app_user.uq_app_user_email", "users.email")) from None
        raise


def user_row(cur, user_id):
    """fetchone() of SELECT * for one user (cur.description stays readable).
    api_auth update_profile."""
    cur.execute(f"SELECT {_USER_COLS} FROM app_user WHERE id=%s", (user_id,))
    return cur.fetchone()


def user_list_rows(cur):
    """fetchall() of the admin user list, newest first. api_admin list_users."""
    cur.execute(
        "SELECT id, email, name, role, profile_pic, allowed_pages, can_delete, " + _utc("created_at")
        + ", " + _utc("updated_at") + " FROM app_user ORDER BY " + _key("created_at", "DESC") + ", id"
    )
    return cur.fetchall()


def user_email_row(cur, user_id):
    """fetchone() of (email,) for one user, or None. api_admin."""
    cur.execute("SELECT email FROM app_user WHERE id=%s", (user_id,))
    return cur.fetchone()


def set_user_permissions(cur, allowed_pages, can_delete, updated_at, user_id):
    """api_admin set_user_permissions; the caller commits."""
    _keys.fits("updated_at", updated_at, 40)
    cur.execute(
        "UPDATE app_user SET allowed_pages=%s, can_delete=%s, updated_at=%s WHERE id=%s",
        (
            allowed_pages,
            can_delete,
            _keys.stamp(ISO_UTC, updated_at, "updated_at"),
            user_id,
        ),
    )


def set_user_role(cur, role, updated_at, user_id):
    """api_admin set_user_role; the caller commits."""
    _keys.fits("updated_at", updated_at, 40)
    cur.execute(
        "UPDATE app_user SET role=%s, updated_at=%s WHERE id=%s",
        (role, _keys.stamp(ISO_UTC, updated_at, "updated_at"), user_id),
    )


def delete_user(cur, user_id):
    """api_admin delete_user; the caller commits."""
    cur.execute("DELETE FROM app_user WHERE id=%s", (user_id,))


# ── allowed_emails (api_admin.py) ────────────────────────────────────────────

def allowed_email_rows(cur):
    """fetchall() of SELECT * FROM allowed_emails, newest first."""
    cur.execute(f"SELECT {_ALLOWED_COLS} FROM allowed_email ORDER BY {_key('created_at', 'DESC')}, email")
    return cur.fetchall()


def upsert_allowed_email(cur, email, added_by, added_at):
    """Add (or un-bar) an email on the caller's cursor; the caller commits."""
    _keys.fits("added_at", added_at, 40, nullable=False)
    cur.execute(
        """INSERT INTO allowed_email (email, created_by, created_at, barred)
           VALUES (%s, %s, %s, 0)
           AS new ON DUPLICATE KEY UPDATE barred=0, created_by=new.created_by, created_at=new.created_at""",
        (email, added_by, _keys.stamp(ISO_UTC, added_at, "added_at")),
    )


def delete_allowed_email(cur, email):
    """The caller commits."""
    cur.execute("DELETE FROM allowed_email WHERE email=%s", (email,))


def allowed_email_exists_row(cur, email):
    """fetchone() of (1,) when the email is on the allow-list, else None."""
    cur.execute("SELECT 1 FROM allowed_email WHERE email=%s", (email,))
    return cur.fetchone()


def set_allowed_email_barred(cur, barred, barred_by, barred_at, email):
    """The caller commits."""
    _keys.fits("barred_at", barred_at, 40)
    cur.execute(
        "UPDATE allowed_email SET barred=%s, barred_by=%s, barred_at=%s WHERE email=%s",
        (barred, barred_by,
         _keys.stamp(ISO_UTC, barred_at, "barred_at"), email),
    )


# ── activity_log / page_visits (api_admin.py) ────────────────────────────────

def activity_log_user_rows(cur):
    """fetchall() of (user_email,), distinct, sorted."""
    cur.execute("SELECT DISTINCT user_email FROM activity_log WHERE user_email IS NOT NULL ORDER BY user_email")
    return cur.fetchall()


def activity_log_action_rows(cur):
    """fetchall() of (action,), distinct, sorted."""
    cur.execute("SELECT DISTINCT action FROM activity_log WHERE action IS NOT NULL ORDER BY action")
    return cur.fetchall()


def activity_log_rows(cur, clause, params, limit, offset):
    """fetchall() of SELECT * FROM activity_log <clause>, newest first;
    `clause` is the caller's "WHERE ..." (or "") over `params`."""
    cur.execute(
        f"SELECT {_ACTIVITY_COLS} FROM activity_log {clause} ORDER BY id DESC LIMIT %s OFFSET %s",
        (*params, limit, offset),
    )
    return cur.fetchall()


def page_visit_rows_since(cur, since):
    """fetchall() of SELECT * FROM page_visits from `since` (ISO string)."""
    cond, cparams = _key_ge("created_at", since, "since")
    cur.execute(f"SELECT {_VISIT_COLS} FROM page_visit WHERE {cond} ORDER BY {_key('created_at')}, id ASC", cparams)
    return cur.fetchall()


def page_visit_rows(cur):
    """fetchall() of SELECT * FROM page_visits."""
    cur.execute(f"SELECT {_VISIT_COLS} FROM page_visit ORDER BY {_key('created_at')}, id ASC")
    return cur.fetchall()


# ── todo_jobs (api_todo.py; on the caller's connection) ──────────────────────

def todo_job_row(conn, job_id):
    """fetchone() of SELECT * for one job."""
    return conn.execute(f"SELECT {_TODO_COLS} FROM todo_job WHERE id=%s", (job_id,)).fetchone()


def todo_all_jobs(conn):
    """The cursor of SELECT * over every job."""
    return conn.execute(f"SELECT {_TODO_COLS} FROM todo_job ORDER BY due_date ASC, id ASC")


def todo_jobs_by_status(conn, status):
    """The cursor of SELECT * over the jobs with `status`."""
    return conn.execute(
                f"SELECT {_TODO_COLS} FROM todo_job WHERE status=%s ORDER BY due_date ASC, id ASC",
                (status,),
            )


def insert_todo_job(conn, subject, details, recipient, due_date, priority, created_at):
    """The cursor (lastrowid); the caller commits."""
    _keys.fits("due_date", due_date, 10, nullable=False)
    _keys.fits("created_at", created_at, 40, nullable=False)
    due = _keys.day("due_date", due_date)
    created = _keys.stamp(ISO_LOCAL, created_at, "created_at")
    return conn.execute(
            """INSERT INTO todo_job
               (subject, details, recipient, due_date, priority, status, created_at)
               VALUES (%s, %s, %s, %s, %s, 'pending', %s)""",
            (subject, details, recipient, due,
             priority, created),
        )


def _convert(fields, values, conversions):
    """values with the entries of the "col = %s" `fields` named in
    `conversions` ({col: fn}) converted for the v2 column type."""
    values = list(values)
    for i, frag in enumerate(fields):
        fn = conversions.get(frag.split("=")[0].strip())
        if fn is not None:
            values[i] = fn(values[i])
    return values


def update_todo_job(conn, fields, values, job_id):
    """UPDATE todo_jobs SET <fields>; `fields` are the caller's "col = %s"
    fragments. The cursor (rowcount); the caller commits."""
    values = _convert(fields, values, {
        "due_date": lambda v: (_keys.fits("due_date", v, 10, nullable=False), _keys.day("due_date", v))[1],
        "created_at": lambda v: _keys.stamp(ISO_LOCAL, v, "created_at"),
        "completed_at": lambda v: _keys.stamp(ISO_LOCAL, v, "completed_at")})
    return conn.execute(
            f"UPDATE todo_job SET {', '.join(fields)} WHERE id = %s",
            (*values, job_id),
        )


def complete_todo_job(conn, completed_at, job_id):
    """The cursor (rowcount); the caller commits."""
    _keys.fits("completed_at", completed_at, 40)
    return conn.execute(
            "UPDATE todo_job SET status='done', completed_at=%s WHERE id=%s",
            (_keys.stamp(ISO_LOCAL, completed_at, "completed_at"), job_id),
        )


def reopen_todo_job(conn, job_id):
    """The cursor (rowcount); the caller commits."""
    return conn.execute(
            "UPDATE todo_job SET status='pending', completed_at=NULL WHERE id=%s",
            (job_id,),
        )


def delete_todo_job(conn, job_id):
    """The cursor (rowcount); the caller commits."""
    return conn.execute("DELETE FROM todo_job WHERE id=%s", (job_id,))


# ── daily_work_log (api_worklog.py; on the caller's connection) ──────────────

def worklog_entry_row(conn, entry_id):
    """fetchone() of SELECT * for one entry."""
    return conn.execute(f"SELECT {_WORKLOG_COLS} FROM daily_work_log WHERE id=%s", (entry_id,)).fetchone()


def worklog_rows(conn, where_sql, params):
    """The cursor of SELECT * FROM daily_work_log <where_sql>, newest first;
    `where_sql` is the caller's "WHERE ..." (or "") over `params`."""
    return conn.execute(
            f"SELECT {_WORKLOG_COLS} FROM daily_work_log {where_sql} ORDER BY work_date DESC, id DESC",
            params,
        )


def insert_worklog_entry(conn, work_date, description, remarks, created_at):
    """The cursor (lastrowid); the caller commits."""
    _keys.fits("work_date", work_date, 10, nullable=False)
    _keys.fits("created_at", created_at, 40, nullable=False)
    day = _keys.day("work_date", work_date)
    created = _keys.stamp(ISO_LOCAL, created_at, "created_at")
    return conn.execute(
            """INSERT INTO daily_work_log (work_date, description, remarks, created_at)
               VALUES (%s, %s, %s, %s)""",
            (day, description, remarks,
             created),
        )


def update_worklog_entry(conn, fields, values, entry_id):
    """UPDATE daily_work_log SET <fields>; `fields` are the caller's
    "col = %s" fragments. The cursor (rowcount); the caller commits."""
    values = _convert(fields, values, {
        "work_date": lambda v: (_keys.fits("work_date", v, 10, nullable=False), _keys.day("work_date", v))[1],
        "created_at": lambda v: _keys.stamp(ISO_LOCAL, v, "created_at")})
    return conn.execute(
            f"UPDATE daily_work_log SET {', '.join(fields)} WHERE id = %s",
            (*values, entry_id),
        )


def delete_worklog_entry(conn, entry_id):
    """The cursor (rowcount); the caller commits."""
    return conn.execute("DELETE FROM daily_work_log WHERE id=%s", (entry_id,))


# ── Admin backup / restore (api_admin_backup), on the caller's cursor ───────
# The named-lock pair runs on the dedicated connection api_admin_backup
# holds for the whole backup / restore: GET_LOCK is connection-scoped, so the
# lock lives exactly as long as that connection (released explicitly, then
# the connection is closed). Both statements mark the connection non-poolable
# in dbengine, as before. Identical to v1: not table SQL.

def table_name_rows(cur):
    """fetchall() of SHOW TABLES. api_admin_backup._live_table_counts."""
    cur.execute("SHOW TABLES")
    return cur.fetchall()


def table_count_row(cur, table):
    """fetchone() of (COUNT(*),) for one table (a name SHOW TABLES returned).
    api_admin_backup._live_table_counts."""
    cur.execute(f"SELECT COUNT(*) FROM `{table}`")
    return cur.fetchone()


def get_lock_row(cur, name):
    """fetchone() of (GET_LOCK(name, 0),): 1 when this connection now holds
    the lock. api_admin_backup._acquire_admin_lock."""
    cur.execute("SELECT GET_LOCK(%s, 0)", (name,))
    return cur.fetchone()


def release_lock(cur, name):
    """RELEASE_LOCK(name) on the holding connection.
    api_admin_backup._release_admin_lock."""
    cur.execute("SELECT RELEASE_LOCK(%s)", (name,))
