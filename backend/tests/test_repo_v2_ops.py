"""v1 vs v2 equivalence of repo.ops (Task 7f).

The same rows are seeded into v1's users / allowed_emails / otp_codes /
activity_log / page_visits / admin_notifications / extraction_log /
todo_jobs / daily_work_log and v2's tables (timestamps through repo.v2codec).
datetime.now() is frozen in both ops modules. After each step both sides
must agree on the outcome (result, or exception type and args), every read
(canonical form: row types, column names, the exact timestamp strings) and
the stored rows (v2 rendered back to v1's columns and strings).
"""
import datetime as dt

import pytest

import dbengine
from dbengine import Row
from repo import conn as rc
from _v1_frozen import ops as o1
from repo import ops as o2
from repo._keys import OutOfModelError
from v2dual import FrozenNow, assert_same_reads, on_cursor, run_step

NOW = dt.datetime(2026, 10, 23, 9, 0, 5, 250000)
U = lambda minutes: (NOW - dt.timedelta(minutes=minutes)).replace(tzinfo=dt.timezone.utc).isoformat()  # noqa: E731
NOW_UTC = NOW.replace(tzinfo=dt.timezone.utc).isoformat()
NOW_LOCAL = NOW.isoformat()

TABLES = ("users", "allowed_emails", "otp_codes", "activity_log", "page_visits", "admin_notifications",
          "extraction_log", "todo_jobs", "daily_work_log")

USERS = [
    {"id": 1, "email": "Admin@x.com", "password_hash": "h1", "name": "Admin", "role": "admin",
     "profile_pic": "a.png", "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-02-01T10:00:00.123456+00:00",
     "allowed_pages": '["a"]', "can_delete": 1},
    {"id": 2, "email": "ed@x.com", "password_hash": "h2", "name": "", "role": None, "profile_pic": "",
     "created_at": "2026-03-01T08:30:00.5+00:00".replace(".5", ".500000"), "updated_at": None, "allowed_pages": None,
     "can_delete": 0},
    {"id": 3, "email": "z@x.com", "password_hash": "h3", "name": None, "role": "editor", "profile_pic": None,
     "created_at": "2026-03-01T08:30:00.500000+00:00", "updated_at": None, "allowed_pages": "[]", "can_delete": 1},
]
ALLOWED = [
    {"email": "ok@x.com", "added_by": "admin", "added_at": "2026-01-02T00:00:00+00:00", "barred": 0, "barred_by": None,
     "barred_at": None},
    {"email": "bad@x.com", "added_by": None, "added_at": "2026-02-02T00:00:00.000001+00:00", "barred": 1,
     "barred_by": "admin", "barred_at": "2026-03-03T03:03:03.030303+00:00"},
]
OTP = [{"id": i, "email": e, "purpose": p, "code_hash": c, "expires_at": ex, "used": u, "created_at": cr}
       for i, e, p, c, ex, u, cr in [
    (1, "ok@x.com", "register", "c1", "2026-10-23T08:50:00+00:00", 1, "2026-10-23T08:40:00+00:00"),
    (2, "ok@x.com", "register", "c2", "2026-10-23T09:10:00.500000+00:00", 0, "2026-10-23T08:59:00.250000+00:00"),
    (3, "ok@x.com", "reset", "c3", "2026-10-23T09:10:00+00:00", 0, "2026-10-23T08:58:00+00:00")]]
ACTIVITY = [{"id": i, "user_email": e, "user_name": n, "action": a, "entity": en, "details": d, "timestamp": t}
            for i, e, n, a, en, d, t in [
    (1, "admin@x.com", "Admin", "insert", "e1", "d", "2026-10-01T10:00:00.100000+00:00"),
    (2, None, None, "update", None, None, "2026-10-02T10:00:00+00:00"),
    (3, "ed@x.com", "Ed", "insert", "e3", "", "2026-10-03T10:00:00.999999+00:00")]]
VISITS = [{"id": i, "timestamp": t, "ip_address": ip, "user_email": e, "user_name": n, "path": p}
          for i, t, ip, e, n, p in [
    (1, "2026-10-20T10:00:00+00:00", "1.1.1.1", None, None, "/a"),
    (2, "2026-10-22T10:00:00.5+00:00".replace(".5", ".500000"), "2.2.2.2", "ed@x.com", "Ed", "/b"),
    (3, "2026-10-22T10:00:00+00:00", None, "ed@x.com", "Ed", "/c"),
    (4, "2026-10-23T08:00:00.000100+00:00", "1.1.1.1", None, None, "/a")]]
NOTES = [{"id": i, "created_at": c, "kind": k, "user_email": e, "user_name": n, "ip_address": ip, "path": p}
         for i, c, k, e, n, ip, p in [
    (1, U(10), "anon_visit", None, None, "9.9.9.9", "/x"),
    (2, U(40), "anon_visit", None, None, "8.8.8.8", "/y"),
    (3, "2026-10-01T00:00:00+00:00", "sign_in", "ed@x.com", "Ed", "1.1.1.1", None)]]
EXTRACT = [{"id": i, "logged_at": t, "plant_name": p, "report_month": m, "file_name": f, "sheet_name": s,
            "source_type": st, "items_extracted": n} for i, t, p, m, f, s, st, n in [
    (1, "2026-10-01 10:00:00", "RSP", "2026-10", "r.xlsx", "S1", "Final Monthly Report", 10),
    (2, "2026-10-02 10:00:00", "ISP", "2026-10", "i.xlsx", None, "Summarized Monthly Report x", None),
    (3, "2026-10-03 10:00:00", "DSP", "2026-08", "mis0826.pdf", "p", "DSP OMI PDF Report", 5),
    (4, "2026-10-04 10:00:00", "TESTPLANT", "2099-01", "t.xlsx", "t", "Techno Data", 1),
    (5, "2026-10-05 10:00:00", "BSL", "2026-10", "b.pdf", "", "BSL Production of Main Products (PDF)", 3)]]
TODO = [{"id": i, "subject": s, "details": d, "recipient": r, "due_date": dd, "priority": p, "status": st,
         "created_at": c, "completed_at": ca, "remark": rm} for i, s, d, r, dd, p, st, c, ca, rm in [
    (1, "Call", "x", "bob", "2026-11-01", "high", "pending", "2026-10-01T09:00:00.123456", None, None),
    (2, "Done", None, None, "2026-10-15", "medium", "done", "2026-10-02T09:00:00", "2026-10-10T12:00:00.5".replace(".5", ".500000"), "ok"),
    (3, "Late", "", "", "2026-10-15", "low", "pending", "2026-10-03T09:00:00", None, "")]]
WORKLOG = [{"id": i, "work_date": d, "description": ds, "remarks": r, "created_at": c} for i, d, ds, r, c in [
    (1, "2026-10-01", "did a", None, "2026-10-01T18:00:00.250000"),
    (2, "2026-10-02", "did b", "", "2026-10-02T18:00:00"),
    (3, "2026-09-30", "did c", "r", "2026-09-30T18:00:00.000001")]]


@pytest.fixture
def seeded(dual, monkeypatch):
    for t, rows in (("users", USERS), ("allowed_emails", ALLOWED), ("otp_codes", OTP), ("activity_log", ACTIVITY),
                    ("page_visits", VISITS), ("admin_notifications", NOTES), ("extraction_log", EXTRACT),
                    ("todo_jobs", TODO), ("daily_work_log", WORKLOG)):
        dual.seed_simple(t, rows)
    FrozenNow(monkeypatch, o1, o2, value=NOW)
    return dual


def _cur(fn, rf=None, commit=False):
    return on_cursor(fn, row_factory=rf, commit=commit)


def _conn_run(fn, commit=False):
    def run(mod):
        conn = dbengine.connect()
        conn.row_factory = Row
        try:
            out = fn(mod, conn)
            if commit:
                conn.commit()
            return out
        finally:
            conn.close()
    return run


def _rows(cur):
    return [dict(r) if isinstance(r, Row) else r for r in cur.fetchall()]


def _reads(m):
    out = {}
    for e in ("Admin@x.com", "admin@x.com", "ED@x.com", "z@x.com", "nobody@x.com"):
        out[("by_email", e)] = m.get_user_by_email(e)
    for i in (1, 2, 3, 99):
        out[("by_id", i)] = m.get_user_by_id(i)
        out[("user_row", i)] = _cur(lambda mod, cur: (mod.user_row(cur, i), [d[0] for d in cur.description]))(m)
        out[("user_email", i)] = _cur(lambda mod, cur: mod.user_email_row(cur, i))(m)
    out["user_list"] = _cur(lambda mod, cur: mod.user_list_rows(cur))(m)
    out["user_list_row"] = _cur(lambda mod, cur: mod.user_list_rows(cur), rf=Row)(m)
    for e in ("ok@x.com", "OK@x.com", "bad@x.com", "none@x.com"):
        out[("allowed", e)] = (m.is_email_allowed(e), m._is_barred(e),
                               _cur(lambda mod, cur: mod.allowed_email_exists_row(cur, e))(m))
    out["allowed_rows"] = _cur(lambda mod, cur: mod.allowed_email_rows(cur), rf=Row)(m)
    out["allowed_rows_t"] = _cur(lambda mod, cur: mod.allowed_email_rows(cur))(m)
    for e, p in (("ok@x.com", "register"), ("ok@x.com", "reset"), ("ok@x.com", "other"), ("bad@x.com", "register")):
        out[("otp_created", e, p)] = _cur(lambda mod, cur: mod.otp_latest_created_row(cur, e, p))(m)
        out[("otp_unused", e, p)] = _cur(lambda mod, cur: mod.otp_latest_unused_row(cur, e, p))(m)
    out["act_users"] = _cur(lambda mod, cur: mod.activity_log_user_rows(cur))(m)
    out["act_actions"] = _cur(lambda mod, cur: mod.activity_log_action_rows(cur))(m)
    for clause, params in (("", []), ("WHERE user_email=%s", ["admin@x.com"]), ("WHERE action=%s", ["update"]),
                           ("WHERE user_email=%s AND action=%s", ["ed@x.com", "insert"])):
        for limit, offset in ((200, 0), (1, 1)):
            out[("act", clause, limit, offset)] = _cur(
                lambda mod, cur: _rows(_after(cur, mod.activity_log_rows(cur, clause, params, limit, offset))),
                rf=Row)(m)
    for since in ("2026-10-20T10:00:00+00:00", "2026-10-22T10:00:00.250000+00:00", "2027-01-01T00:00:00+00:00"):
        out[("visits_since", since)] = _cur(lambda mod, cur: mod.page_visit_rows_since(cur, since))(m)
    out["visits"] = _cur(lambda mod, cur: mod.page_visit_rows(cur), rf=Row)(m)
    out["visits_t"] = _cur(lambda mod, cur: mod.page_visit_rows(cur))(m)
    for n in (1, 2, 100):
        out[("notes", n)] = m.list_admin_notifications(n)
    for kw in ({}, {"limit": 2}, {"plant": "rsp"}, {"source_type": "Techno Data"}, {"plant": "ISP", "source_type": "x"}):
        out[("extlogs", repr(kw))] = m.get_extraction_logs(**kw)
    for mo in ("2026-10", "2026-08", "2026-03", "2099-01"):
        out[("status", mo)] = m.production_month_status(mo)
    out["todo_all"] = _conn_run(lambda mod, c: _rows(mod.todo_all_jobs(c)))(m)
    for st in ("pending", "done", "x"):
        out[("todo_status", st)] = _conn_run(lambda mod, c: _rows(mod.todo_jobs_by_status(c, st)))(m)
    for i in (1, 2, 99):
        out[("todo_row", i)] = _conn_run(lambda mod, c: mod.todo_job_row(c, i))(m)
        out[("work_row", i)] = _conn_run(lambda mod, c: mod.worklog_entry_row(c, i))(m)
    for where, params in (("", []), ("WHERE work_date LIKE %s", ["2026-10-%"]),
                          ("WHERE work_date >= %s AND work_date <= %s", ["2026-10-01", "2026-10-01"])):
        out[("work", where)] = _conn_run(lambda mod, c: _rows(mod.worklog_rows(c, where, params)))(m)
    return out


def _after(cur, rows):
    class R:
        def fetchall(self_):
            return rows
    return R()


@pytest.fixture
def step(seeded):
    def go(fn):
        return run_step(seeded, o1, o2, fn, reads=_reads, tables=TABLES)
    return go


def test_seeded_reads_agree(seeded):
    r = assert_same_reads(seeded, o1, o2, _reads)
    assert "2026-02-01T10:00:00.123456+00:00" in r[("by_email", "admin@x.com")]
    assert "2026-10-10T12:00:00.500000" in r["todo_all"]


def test_users(step):
    def ins(**k):
        a = dict(email="new@x.com", password_hash="hh", name="New", created_at=NOW_UTC, updated_at=NOW_UTC)
        a.update(k)
        return _cur(lambda m, c: (m.insert_user(c, **a), c.lastrowid)[1], commit=True)
    for fn in (ins(), ins(email="NEW@x.com"),                                   # ai_ci clash on users.email
               ins(email="n2@x.com", updated_at=None), ins(email="n3@x.com", created_at="2026-10-23T09:00:05+00:00"),
               ins(email="e" * 191), ins(email=None), ins(password_hash="p" * 256), ins(name="n" * 191),
               ins(email="n4@x.com", created_at=None), ins(email="n5@x.com", created_at="c" * 41),
               _cur(lambda m, c: m.update_password(c, "newhash", NOW_UTC, "ED@x.com"), commit=True),
               _cur(lambda m, c: m.update_password(c, "newhash", NOW_UTC, "none@x.com"), commit=True),
               _cur(lambda m, c: m.update_password(c, "p" * 256, NOW_UTC, "ed@x.com"), commit=True),
               _cur(lambda m, c: m.update_user_fields(c, ["name=%s", "updated_at=%s"], ["Renamed", NOW_UTC, 1]),
                    commit=True),
               _cur(lambda m, c: m.update_user_fields(c, ["profile_pic=%s", "name=%s", "updated_at=%s"],
                                                      ["p.png", "N", NOW_UTC, 2]), commit=True),
               _cur(lambda m, c: m.update_user_fields(c, ["email=%s"], ["Z@x.com", 2]), commit=True),   # 1062
               _cur(lambda m, c: m.update_user_fields(c, ["name=%s"], ["x" * 191, 1]), commit=True),
               _cur(lambda m, c: m.set_user_permissions(c, '["x"]', 0, NOW_UTC, 1), commit=True),
               _cur(lambda m, c: m.set_user_permissions(c, None, 1, NOW_UTC, 99), commit=True),
               _cur(lambda m, c: m.set_user_role(c, "editor", NOW_UTC, 2), commit=True),
               _cur(lambda m, c: m.set_user_role(c, None, "2026-10-23T09:00:05+00:00", 2), commit=True),
               _cur(lambda m, c: m.set_user_role(c, "r" * 33, NOW_UTC, 2), commit=True),
               _cur(lambda m, c: m.delete_user(c, 3), commit=True),
               _cur(lambda m, c: m.delete_user(c, 3), commit=True)):
        step(fn)


def test_allowed_emails(step):
    for fn in (_cur(lambda m, c: m.upsert_allowed_email(c, "new@x.com", "admin", NOW_UTC), commit=True),
               _cur(lambda m, c: m.upsert_allowed_email(c, "BAD@x.com", "boss", NOW_UTC), commit=True),   # un-bar
               _cur(lambda m, c: m.upsert_allowed_email(c, "ok@x.com", None, "2026-10-23T09:00:05+00:00"), commit=True),
               _cur(lambda m, c: m.upsert_allowed_email(c, "e" * 191, "a", NOW_UTC), commit=True),
               _cur(lambda m, c: m.upsert_allowed_email(c, "x@x.com", "a", None), commit=True),
               _cur(lambda m, c: m.set_allowed_email_barred(c, 1, "admin", NOW_UTC, "ok@x.com"), commit=True),
               _cur(lambda m, c: m.set_allowed_email_barred(c, 0, None, None, "bad@x.com"), commit=True),
               _cur(lambda m, c: m.set_allowed_email_barred(c, 1, "a", NOW_UTC, "nobody@x.com"), commit=True),
               _cur(lambda m, c: m.delete_allowed_email(c, "OK@x.com"), commit=True),
               _cur(lambda m, c: m.delete_allowed_email(c, "ok@x.com"), commit=True)):
        step(fn)


def test_otp(step):
    exp = (NOW + dt.timedelta(minutes=10)).replace(tzinfo=dt.timezone.utc).isoformat()
    for fn in (_cur(lambda m, c: m.otp_invalidate_unused(c, "ok@x.com", "register"), commit=True),
               _cur(lambda m, c: m.otp_invalidate_unused(c, "none@x.com", "register"), commit=True),
               _cur(lambda m, c: (m.otp_insert(c, "ok@x.com", "register", "hash", exp, NOW_UTC), c.lastrowid)[1],
                    commit=True),
               _cur(lambda m, c: m.otp_insert(c, "n@x.com", "reset", "hash", "2026-10-23T09:10:00+00:00", NOW_UTC),
                    commit=True),
               _cur(lambda m, c: m.otp_insert(c, "e" * 191, "reset", "hash", exp, NOW_UTC), commit=True),
               _cur(lambda m, c: m.otp_insert(c, "n@x.com", "p" * 33, "hash", exp, NOW_UTC), commit=True),
               _cur(lambda m, c: m.otp_insert(c, "n@x.com", "reset", "h" * 256, exp, NOW_UTC), commit=True),
               _cur(lambda m, c: m.otp_insert(c, "n@x.com", "reset", "hash", None, NOW_UTC), commit=True),
               _cur(lambda m, c: m.otp_mark_used(c, 2), commit=True), _cur(lambda m, c: m.otp_mark_used(c, 99),
                                                                           commit=True)):
        step(fn)


def test_logs(step):
    user = {"email": "ed@x.com", "name": "Ed"}
    for fn in (lambda m: m.log_activity(user, "insert", "entity", "details"),
               lambda m: m.log_activity(None, "update", "entity"),
               lambda m: m.log_activity(user, "a" * 65, "entity"),
               lambda m: m.log_activity(user, None, "entity"),
               lambda m: m.log_activity(user, "x", "e" * 161),
               lambda m: m.log_page_visit("3.3.3.3", user, "/p"),
               lambda m: m.log_page_visit("", None, "/q"),
               lambda m: m.log_page_visit("3.3.3.3", user, "p" * 256),
               lambda m: m.log_page_visit("i" * 65, user, "/p"),
               lambda m: m.add_admin_notification("sign_in", "5.5.5.5", user, "/login"),
               lambda m: m.add_admin_notification("anon_visit", "9.9.9.9", None, "/x"),    # inside the window: skipped
               lambda m: m.add_admin_notification("anon_visit", "8.8.8.8", None, "/y"),    # outside: recorded
               lambda m: m.add_admin_notification("anon_visit", "", None, "/z"),
               lambda m: m.add_admin_notification("anon_visit", "", None, "/z"),
               lambda m: m.add_admin_notification("k" * 21, "6.6.6.6", user, None),         # swallowed error
               lambda m: m.log_extraction("RSP", "2026-10", "f.xlsx", "S", "Final Monthly Report", 3),
               lambda m: m.log_extraction("TESTPLANT", "2099-01", "f", "s", "t", 0),
               lambda m: m.log_extraction("BSL", "2026-10 ", "f", None, None, None),        # cut
               lambda m: m.log_extraction("BSL", "2026-1055", "f", "s", "t", 1),
               lambda m: m.log_extraction("BSL", "abc", "f", "s", "t", 1),                  # any text <= 7
               lambda m: m.log_extraction("P" * 33, "2026-10", "f", "s", "t", 1),
               lambda m: m.log_extraction(None, "2026-10", "f", "s", "t", 1),
               lambda m: m.log_extraction("BSL", None, "f", "s", "t", 1),
               lambda m: m.log_extraction("BSL", "2026-10", "f" * 256, "s", "t", 1),
               lambda m: m.log_extraction("BSL", "2026-10", "f", "s" * 161, "t", 1),
               lambda m: m.log_extraction("BSL", "2026-10", "f", "s", "t", "x")):
        step(fn)


def test_todo_and_worklog(step):
    def todo(fn, commit=True):
        return _conn_run(lambda m, c: (lambda cur: (cur.lastrowid, cur.rowcount))(fn(m, c)), commit=commit)
    for fn in (
            todo(lambda m, c: m.insert_todo_job(c, "New", "d", "bob", "2026-12-01", "high", NOW_LOCAL)),
            todo(lambda m, c: m.insert_todo_job(c, "New2", None, None, "2026-12-02", "low", "2026-10-23T09:00:05")),
            todo(lambda m, c: m.insert_todo_job(c, "s" * 256, "", "", "2026-12-01", "low", NOW_LOCAL)),
            todo(lambda m, c: m.insert_todo_job(c, None, "", "", "2026-12-01", "low", NOW_LOCAL)),
            todo(lambda m, c: m.insert_todo_job(c, "s", "", "", "2026-12-011", "low", NOW_LOCAL)),   # 1406
            todo(lambda m, c: m.insert_todo_job(c, "s", "", "", None, "low", NOW_LOCAL)),
            todo(lambda m, c: m.insert_todo_job(c, "s", "", "", "2026-12-01", "p" * 17, NOW_LOCAL)),
            todo(lambda m, c: m.update_todo_job(c, ["subject = %s", "due_date = %s"], ["Changed", "2027-01-01"], 1)),
            todo(lambda m, c: m.update_todo_job(c, ["details = %s", "remark = %s", "priority = %s"],
                                                [None, "r", "low"], 3)),
            todo(lambda m, c: m.update_todo_job(c, ["subject = %s"], ["same"], 99)),
            todo(lambda m, c: m.update_todo_job(c, ["subject = %s"], ["same"], 1)),
            todo(lambda m, c: m.update_todo_job(c, ["subject = %s"], ["s" * 256], 1)),
            todo(lambda m, c: m.update_todo_job(c, ["due_date = %s"], ["2027-01-011"], 1)),
            todo(lambda m, c: m.complete_todo_job(c, NOW_LOCAL, 1)),
            todo(lambda m, c: m.complete_todo_job(c, NOW_LOCAL, 1)),
            todo(lambda m, c: m.complete_todo_job(c, "2026-10-23T09:00:05", 99)),
            todo(lambda m, c: m.reopen_todo_job(c, 2)), todo(lambda m, c: m.reopen_todo_job(c, 2)),
            todo(lambda m, c: m.delete_todo_job(c, 3)), todo(lambda m, c: m.delete_todo_job(c, 3)),
            todo(lambda m, c: m.insert_worklog_entry(c, "2026-10-23", "did", "r", NOW_LOCAL)),
            todo(lambda m, c: m.insert_worklog_entry(c, "2026-10-23", "did2", None, NOW_LOCAL)),
            todo(lambda m, c: m.insert_worklog_entry(c, "2026-10-23", None, None, NOW_LOCAL)),
            todo(lambda m, c: m.insert_worklog_entry(c, "2026-10-2399", "d", None, NOW_LOCAL)),
            todo(lambda m, c: m.insert_worklog_entry(c, None, "d", None, NOW_LOCAL)),
            todo(lambda m, c: m.update_worklog_entry(c, ["work_date = %s", "description = %s"], ["2026-10-24", "e"], 1)),
            todo(lambda m, c: m.update_worklog_entry(c, ["remarks = %s"], [None], 2)),
            todo(lambda m, c: m.update_worklog_entry(c, ["remarks = %s"], ["r"], 99)),
            todo(lambda m, c: m.update_worklog_entry(c, ["work_date = %s"], ["2026-10-2499"], 1)),
            todo(lambda m, c: m.delete_worklog_entry(c, 3)), todo(lambda m, c: m.delete_worklog_entry(c, 3))):
        step(fn)


def test_since_filters_use_the_stored_utc_wall_clock_not_the_session_time_zone(seeded):
    """page_visit_rows_since / the anon-visit window must give v1's rows
    whatever the MySQL session time zone is."""
    for tz in ("+00:00", "+05:30", "-08:00"):
        with seeded.v2():
            conn = dbengine.connect()
            try:
                cur = conn.cursor()
                cur.execute("SET time_zone = %s", (tz,))
                got = o2.page_visit_rows_since(cur, "2026-10-22T10:00:00+00:00")
            finally:
                conn.close()
        with seeded.v1():
            conn = dbengine.connect()
            try:
                want = o1.page_visit_rows_since(conn.cursor(), "2026-10-22T10:00:00+00:00")
            finally:
                conn.close()
        assert [tuple(r) for r in got] == [tuple(r) for r in want]


def test_counts_locks_and_table_names(seeded):
    with seeded.v1():
        a = _cur(lambda m, c: m.table_count_row(c, "users"))(o1)
    with seeded.v2():
        b = _cur(lambda m, c: m.table_count_row(c, "app_user"))(o2)
        names = [r[0] for r in _cur(lambda m, c: m.table_name_rows(c))(o2)]
    assert tuple(a) == tuple(b) == (3,) and "app_user" in names and "extraction_log" in names
    with seeded.v2():
        c1 = dbengine.connect()
        c2 = dbengine.connect()
        try:
            assert tuple(o2.get_lock_row(c1.cursor(), "mis_test_lock_7f")) == (1,)
            assert tuple(o2.get_lock_row(c2.cursor(), "mis_test_lock_7f")) == (0,)
            assert tuple(o2.release_lock(c1.cursor(), "mis_test_lock_7f") or (1,)) in ((1,), ())
        finally:
            c1.close()
            c2.close()


def test_timestamps_not_in_the_column_form_are_refused(seeded):
    with seeded.v2():
        for call in (lambda c: o2.insert_user(c, "q@x.com", "h", "n", "2026-10-23T09:00:05", None),
                     lambda c: o2.insert_user(c, "q@x.com", "h", "n", "2026-10-23 09:00:05+00:00", None),
                     lambda c: o2.otp_insert(c, "q@x.com", "reset", "h", "tomorrow", NOW_UTC),
                     lambda c: o2.page_visit_rows_since(c, "2026-10-22"),
                     lambda c: o2.set_user_role(c, "x", "2026-10-23T09:00:05+05:30", 1)):
            with pytest.raises(OutOfModelError):
                _cur(lambda m, c: call(c), commit=True)(o2)
        conn = dbengine.connect()
        try:
            for call in (lambda: o2.insert_todo_job(conn, "s", "", "", "2026-02-30", "low", NOW_LOCAL),
                         lambda: o2.insert_todo_job(conn, "s", "", "", "2026-12-01", "low", NOW_UTC),
                         lambda: o2.insert_worklog_entry(conn, "2026-4-1", "d", None, NOW_LOCAL),
                         lambda: o2.complete_todo_job(conn, "2026-10-23 09:00:05", 1)):
                with pytest.raises(OutOfModelError):
                    call()
        finally:
            conn.close()


def test_extraction_log_keeps_free_plants_and_months(seeded):
    with seeded.v2():
        o2.log_extraction("TESTPLANT", "2099-01", "f", "s", "t", 1)
        assert any(r["plant_name"] == "TESTPLANT" and r["report_month"] == "2099-01"
                   for r in o2.get_extraction_logs(limit=50))
    assert seeded.sql(2, "SELECT COUNT(*) FROM plant WHERE plant_code = 'TESTPLANT'")[0][0] == 0
    assert seeded.sql(2, "SELECT COUNT(*) FROM cal_month WHERE report_month = '2099-01'")[0][0] == 0


def test_bump_exemptions_and_dry_run(seeded):
    """Only log_extraction bumps (page 4 reads it); every other ops write
    leaves data_version alone, as in v1. Nothing persists in a dry run."""
    with seeded.v2():
        n = seeded.data_version(2)
        o2.log_activity(None, "x", "y")
        o2.log_page_visit("1.2.3.4", None, "/z")
        o2.add_admin_notification("sign_in", "1.2.3.4", None, None)
        _cur(lambda m, c: m.otp_mark_used(c, 2), commit=True)(o2)
        _cur(lambda m, c: m.delete_user(c, 3), commit=True)(o2)
        assert seeded.data_version(2) == n
        o2.log_extraction("RSP", "2026-10", "f", "s", "t", 1)
        assert seeded.data_version(2) > n
        before = {k: repr(v) for k, v in _reads(o2).items()}
        n = seeded.data_version(2)
        with rc.rollback_tx():
            o2.log_extraction("RSP", "2026-11", "dry", "s", "t", 1)
            o2.log_activity(None, "dry", "dry")
        assert seeded.data_version(2) == n
        assert {k: repr(v) for k, v in _reads(o2).items()} == before
