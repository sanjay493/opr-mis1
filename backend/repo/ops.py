"""Operational repository: accounts and sign-in (users, allowed_emails,
otp_codes), audit and traffic logs (activity_log, page_visits,
admin_notifications, extraction_log) and the operator's own lists
(todo_jobs, daily_work_log).

The db.py / auth.py functions moved here verbatim and are re-exported from
those modules (auth.get_user_by_id, auth._is_barred and auth.log_activity
are what main.py's editor gate middleware calls on every gated request).
The named queries further down are the statements that used to live inline
in auth.py / api_auth.py / api_admin.py / api_todo.py / api_worklog.py,
moved verbatim: each runs on the caller's cursor (or, for the to-do and
work-log routers, the caller's connection, whose execute() they used), so
the caller's connection, transaction, commit point and row type are
unchanged. Each returns what the caller used to read off the statement: the
cursor, fetchone() or fetchall().
"""
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional

from dbengine import Row, connect


# ── Moved from db.py ─────────────────────────────────────────────────────────

def log_page_visit(ip_address: str, user: Optional[dict], path: str) -> None:
    """Appends one row to page_visits — a frontend navigation to `path`,
    from `ip_address`, by `user` (the get_current_user_optional dict) or
    anonymously if `user` is None. See api_visits.py's POST /api/log-visit."""
    conn = connect()
    conn.execute("""
        INSERT INTO page_visits (timestamp, ip_address, user_email, user_name, path)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        datetime.now(timezone.utc).isoformat(),
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
            row = conn.execute(
                "SELECT 1 FROM admin_notifications WHERE kind = 'anon_visit' AND ip_address = %s AND created_at >= %s LIMIT 1",
                (ip_address or None, since),
            ).fetchone()
            if row:
                return
        conn.execute("""
            INSERT INTO admin_notifications (created_at, kind, user_email, user_name, ip_address, path)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            now.isoformat(),
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
            "SELECT id, created_at, kind, user_email, user_name, ip_address, path "
            "FROM admin_notifications ORDER BY id DESC LIMIT %s",
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
        cur.execute("SELECT plant_name, source_type, file_name FROM extraction_log WHERE report_month = %s",
                    (report_month,))
        return _production_month_status(report_month, cur.fetchall())
    finally:
        conn.close()


def log_extraction(plant: str, report_month: str, file_name: str, sheet_name: str,
                   source_type: str, items_extracted: int, conn=None):
    """Appends a record to the extraction audit log.

    `conn`: see merge_upsert_techno_data's docstring — when reused, this
    does NOT commit; the caller owns the transaction boundary (see
    _raw_upsert_techno_data's docstring for why that matters here)."""
    from datetime import datetime
    owns_conn = conn is None
    if owns_conn:
        conn = connect()
    conn.execute("""
        INSERT INTO extraction_log (logged_at, plant_name, report_month, file_name, sheet_name, source_type, items_extracted)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), plant, report_month, file_name, sheet_name, source_type, items_extracted))
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
        SELECT id, logged_at, plant_name, report_month, file_name, sheet_name, source_type, items_extracted
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
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = connect()
    conn.row_factory = Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def is_email_allowed(email: str) -> bool:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT barred FROM allowed_emails WHERE email=%s", (email,))
    row = cur.fetchone()
    conn.close()
    return row is not None and row[0] == 0


def _is_barred(email: str) -> bool:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT barred FROM allowed_emails WHERE email=%s", (email,))
    row = cur.fetchone()
    conn.close()
    return bool(row and row[0] == 1)


def log_activity(user: Optional[dict], action: str, entity: str, details: str = "") -> None:
    """action: 'insert' | 'update' | 'delete'."""
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO activity_log (user_email, user_name, action, entity, details, timestamp)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (
            user.get("email") if user else None,
            user.get("name") if user else None,
            action,
            entity,
            details,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


# ── otp_codes (auth.py) ──────────────────────────────────────────────────────

def otp_invalidate_unused(cur, email, purpose):
    """Mark every unused code for email+purpose used, on the caller's cursor.
    auth.generate_and_store_otp."""
    cur.execute(
        "UPDATE otp_codes SET used=1 WHERE email=%s AND purpose=%s AND used=0",
        (email, purpose),
    )


def otp_insert(cur, email, purpose, code_hash, expires_at, created_at):
    """Store a new hashed code on the caller's cursor; the caller commits.
    expires_at / created_at are ISO strings. auth.generate_and_store_otp."""
    cur.execute(
        """INSERT INTO otp_codes (email, purpose, code_hash, expires_at, used, created_at)
           VALUES (%s, %s, %s, %s, 0, %s)""",
        (email, purpose, code_hash, expires_at, created_at),
    )


def otp_latest_created_row(cur, email, purpose):
    """fetchone() of (created_at,) of the newest code for email+purpose.
    auth.otp_resend_wait_seconds."""
    cur.execute(
        """SELECT created_at FROM otp_codes WHERE email=%s AND purpose=%s
           ORDER BY id DESC LIMIT 1""",
        (email, purpose),
    )
    return cur.fetchone()


def otp_latest_unused_row(cur, email, purpose):
    """fetchone() of (id, code_hash, expires_at) of the newest unused code.
    auth.verify_otp."""
    cur.execute(
        """SELECT id, code_hash, expires_at FROM otp_codes
           WHERE email=%s AND purpose=%s AND used=0
           ORDER BY id DESC LIMIT 1""",
        (email, purpose),
    )
    return cur.fetchone()


def otp_mark_used(cur, otp_id):
    """Burn one code on the caller's cursor; the caller commits. auth.verify_otp."""
    cur.execute("UPDATE otp_codes SET used=1 WHERE id=%s", (otp_id,))


# ── users (api_auth.py / api_admin.py) ───────────────────────────────────────

def insert_user(cur, email, password_hash, name, created_at, updated_at):
    """Create an account (role NULL) on the caller's cursor; the caller reads
    cur.lastrowid and commits. api_auth register_verify."""
    cur.execute(
        """INSERT INTO users (email, password_hash, name, role, profile_pic, created_at, updated_at)
           VALUES (%s, %s, %s, NULL, '', %s, %s)""",
        (email, password_hash, name, created_at, updated_at),
    )


def update_password(cur, password_hash, updated_at, email):
    """api_auth password_verify; the caller commits."""
    cur.execute(
        "UPDATE users SET password_hash=%s, updated_at=%s WHERE email=%s",
        (password_hash, updated_at, email),
    )


def update_user_fields(cur, updates, params):
    """UPDATE users SET <updates> WHERE id=%s; `updates` are the caller's
    "col=%s" fragments, `params` their values followed by the user id.
    api_auth update_profile; the caller commits."""
    cur.execute(f"UPDATE users SET {', '.join(updates)} WHERE id=%s", params)


def user_row(cur, user_id):
    """fetchone() of SELECT * for one user (cur.description stays readable).
    api_auth update_profile."""
    cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    return cur.fetchone()


def user_list_rows(cur):
    """fetchall() of the admin user list, newest first. api_admin list_users."""
    cur.execute(
        "SELECT id, email, name, role, profile_pic, allowed_pages, can_delete, created_at, updated_at "
        "FROM users ORDER BY created_at DESC"
    )
    return cur.fetchall()


def user_email_row(cur, user_id):
    """fetchone() of (email,) for one user, or None. api_admin."""
    cur.execute("SELECT email FROM users WHERE id=%s", (user_id,))
    return cur.fetchone()


def set_user_permissions(cur, allowed_pages, can_delete, updated_at, user_id):
    """api_admin set_user_permissions; the caller commits."""
    cur.execute(
        "UPDATE users SET allowed_pages=%s, can_delete=%s, updated_at=%s WHERE id=%s",
        (
            allowed_pages,
            can_delete,
            updated_at,
            user_id,
        ),
    )


def set_user_role(cur, role, updated_at, user_id):
    """api_admin set_user_role; the caller commits."""
    cur.execute(
        "UPDATE users SET role=%s, updated_at=%s WHERE id=%s",
        (role, updated_at, user_id),
    )


def delete_user(cur, user_id):
    """api_admin delete_user; the caller commits."""
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))


# ── allowed_emails (api_admin.py) ────────────────────────────────────────────

def allowed_email_rows(cur):
    """fetchall() of SELECT * FROM allowed_emails, newest first."""
    cur.execute("SELECT * FROM allowed_emails ORDER BY added_at DESC")
    return cur.fetchall()


def upsert_allowed_email(cur, email, added_by, added_at):
    """Add (or un-bar) an email on the caller's cursor; the caller commits."""
    cur.execute(
        """INSERT INTO allowed_emails (email, added_by, added_at, barred)
           VALUES (%s, %s, %s, 0)
           AS new ON DUPLICATE KEY UPDATE barred=0, added_by=new.added_by, added_at=new.added_at""",
        (email, added_by, added_at),
    )


def delete_allowed_email(cur, email):
    """The caller commits."""
    cur.execute("DELETE FROM allowed_emails WHERE email=%s", (email,))


def allowed_email_exists_row(cur, email):
    """fetchone() of (1,) when the email is on the allow-list, else None."""
    cur.execute("SELECT 1 FROM allowed_emails WHERE email=%s", (email,))
    return cur.fetchone()


def set_allowed_email_barred(cur, barred, barred_by, barred_at, email):
    """The caller commits."""
    cur.execute(
        "UPDATE allowed_emails SET barred=%s, barred_by=%s, barred_at=%s WHERE email=%s",
        (barred, barred_by,
         barred_at, email),
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
        f"SELECT * FROM activity_log {clause} ORDER BY id DESC LIMIT %s OFFSET %s",
        (*params, limit, offset),
    )
    return cur.fetchall()


def page_visit_rows_since(cur, since):
    """fetchall() of SELECT * FROM page_visits from `since` (ISO string)."""
    cur.execute("SELECT * FROM page_visits WHERE timestamp >= %s ORDER BY timestamp ASC", (since,))
    return cur.fetchall()


def page_visit_rows(cur):
    """fetchall() of SELECT * FROM page_visits."""
    cur.execute("SELECT * FROM page_visits ORDER BY timestamp ASC")
    return cur.fetchall()


# ── todo_jobs (api_todo.py; on the caller's connection) ──────────────────────

def todo_job_row(conn, job_id):
    """fetchone() of SELECT * for one job."""
    return conn.execute("SELECT * FROM todo_jobs WHERE id=%s", (job_id,)).fetchone()


def todo_all_jobs(conn):
    """The cursor of SELECT * over every job."""
    return conn.execute("SELECT * FROM todo_jobs ORDER BY due_date ASC, id ASC")


def todo_jobs_by_status(conn, status):
    """The cursor of SELECT * over the jobs with `status`."""
    return conn.execute(
                "SELECT * FROM todo_jobs WHERE status=%s ORDER BY due_date ASC, id ASC",
                (status,),
            )


def insert_todo_job(conn, subject, details, recipient, due_date, priority, created_at):
    """The cursor (lastrowid); the caller commits."""
    return conn.execute(
            """INSERT INTO todo_jobs
               (subject, details, recipient, due_date, priority, status, created_at)
               VALUES (%s, %s, %s, %s, %s, 'pending', %s)""",
            (subject, details, recipient, due_date,
             priority, created_at),
        )


def update_todo_job(conn, fields, values, job_id):
    """UPDATE todo_jobs SET <fields>; `fields` are the caller's "col = %s"
    fragments. The cursor (rowcount); the caller commits."""
    return conn.execute(
            f"UPDATE todo_jobs SET {', '.join(fields)} WHERE id = %s",
            (*values, job_id),
        )


def complete_todo_job(conn, completed_at, job_id):
    """The cursor (rowcount); the caller commits."""
    return conn.execute(
            "UPDATE todo_jobs SET status='done', completed_at=%s WHERE id=%s",
            (completed_at, job_id),
        )


def reopen_todo_job(conn, job_id):
    """The cursor (rowcount); the caller commits."""
    return conn.execute(
            "UPDATE todo_jobs SET status='pending', completed_at=NULL WHERE id=%s",
            (job_id,),
        )


def delete_todo_job(conn, job_id):
    """The cursor (rowcount); the caller commits."""
    return conn.execute("DELETE FROM todo_jobs WHERE id=%s", (job_id,))


# ── daily_work_log (api_worklog.py; on the caller's connection) ──────────────

def worklog_entry_row(conn, entry_id):
    """fetchone() of SELECT * for one entry."""
    return conn.execute("SELECT * FROM daily_work_log WHERE id=%s", (entry_id,)).fetchone()


def worklog_rows(conn, where_sql, params):
    """The cursor of SELECT * FROM daily_work_log <where_sql>, newest first;
    `where_sql` is the caller's "WHERE ..." (or "") over `params`."""
    return conn.execute(
            f"SELECT * FROM daily_work_log {where_sql} ORDER BY work_date DESC, id DESC",
            params,
        )


def insert_worklog_entry(conn, work_date, description, remarks, created_at):
    """The cursor (lastrowid); the caller commits."""
    return conn.execute(
            """INSERT INTO daily_work_log (work_date, description, remarks, created_at)
               VALUES (%s, %s, %s, %s)""",
            (work_date, description, remarks,
             created_at),
        )


def update_worklog_entry(conn, fields, values, entry_id):
    """UPDATE daily_work_log SET <fields>; `fields` are the caller's
    "col = %s" fragments. The cursor (rowcount); the caller commits."""
    return conn.execute(
            f"UPDATE daily_work_log SET {', '.join(fields)} WHERE id = %s",
            (*values, entry_id),
        )


def delete_worklog_entry(conn, entry_id):
    """The cursor (rowcount); the caller commits."""
    return conn.execute("DELETE FROM daily_work_log WHERE id=%s", (entry_id,))
