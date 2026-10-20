"""repo.text / repo.pages / repo.ops: the moved read and write paths keep their
connection, statement and commit point.

Write sites are driven through their routes where they live in main.py /
api_*.py, so the caller-side wiring (connection, cursor, commit) is covered as
well as the repo function. The auth test runs with the editor gate ON:
allow-list -> register (OTP) -> login (password + OTP) -> gated write ->
activity_log row, plus the barred / allowed_pages / can_delete decisions."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import auth
import db
import dbengine
from repo import conn as rc
from repo import ops as rop
from repo import pages as rpg
from repo import text as rtx


@pytest.fixture
def tc(mysql_db, monkeypatch):
    import main
    monkeypatch.setattr(main, "_is_gated", lambda method, path: False)
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture
def gated(mysql_db):
    """TestClient with the editor/admin gate middleware active."""
    import main
    return TestClient(main.app, raise_server_exceptions=False)


def _rows(sql, params=()):
    with rc.cursor() as cur:
        cur.execute(sql, params)
        return [tuple(r) for r in cur.fetchall()]


def _exec(sql, params=()):
    with rc.tx() as cur:
        cur.execute(sql, params)


def _other_conn_count(table):
    """Row count of `table` seen from a separate, fresh connection (only
    committed rows are visible there)."""
    raw = dbengine._open_raw()
    try:
        with raw.cursor() as c:
            c.execute(f"SELECT COUNT(*) FROM {table}")
            return c.fetchone()[0]
    finally:
        raw.close()


class _CommitSpy:
    """Wraps a connect(): counts connections and commit() calls and, after
    every INSERT/DELETE/UPDATE, records how many `table` rows another
    connection sees (0 = not yet committed)."""

    def __init__(self, real_connect, table):
        self.real_connect = real_connect
        self.table = table
        self.connects = 0
        self.commits = 0
        self.visible_mid_call = []

    def __call__(self, *a, **kw):
        spy = self
        spy.connects += 1
        conn = self.real_connect(*a, **kw)

        class _Cur:
            def __init__(self, cur):
                self._cur = cur

            def execute(self, sql, params=()):
                self._cur.execute(sql, params)
                if sql.lstrip().upper().startswith(("INSERT", "DELETE", "UPDATE")):
                    spy.visible_mid_call.append(_other_conn_count(spy.table))
                return self

            def fetchone(self):
                return self._cur.fetchone()

            def fetchall(self):
                return self._cur.fetchall()

            def __getattr__(self, name):
                return getattr(self._cur, name)

        class _Conn:
            def cursor(self):
                return _Cur(conn.cursor())

            def execute(self, sql, params=()):
                return self.cursor().execute(sql, params)

            def commit(self):
                spy.commits += 1
                conn.commit()

            def __getattr__(self, name):
                return getattr(conn, name)

            def __setattr__(self, name, value):
                setattr(conn, name, value)

        return _Conn()


def _spy(monkeypatch, module, table):
    spy = _CommitSpy(module.connect, table)
    monkeypatch.setattr(module, "connect", spy)
    return spy


# ── repo.pages ────────────────────────────────────────────────────────────────

def test_page_configs_save_load_round_trip_commit_once(mysql_db, monkeypatch):
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rpg, "page_configs")
        rpg.save_page_config("2026-08", 5, {"page": 5, "title": "five"})
        assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [0])
    rpg.save_page_config("2026-08", 2, {"page": 2, "title": "two"})
    rpg.save_page_config("2026-08", 5, {"page": 5, "title": "five v2"})
    rpg.save_page_config("2026-09", 1, {"page": 1})
    assert rpg.get_page_config("2026-08", 5) == {"page": 5, "title": "five v2"}
    assert rpg.get_page_config("2026-08", 7) is None
    assert rpg.get_all_page_configs("2026-08") == [{"page": 2, "title": "two"}, {"page": 5, "title": "five v2"}]
    assert db.save_page_config is rpg.save_page_config
    assert db.get_all_page_configs is rpg.get_all_page_configs
    assert db.get_page_config is rpg.get_page_config


# ── repo.text: narratives through their routes ───────────────────────────────

def test_page3_narrative_route_commit_once_and_missing_data(tc, monkeypatch):
    import page_missing_data
    assert rtx.page3_narrative_any_row("2026-08") is False
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rtx, "page3_narrative")
        r = tc.post("/api/page3-narrative", json={"month": "2026-08", "production_narrative": "Steady.",
                                                    "highlights": ["a", "b"]})
        assert r.status_code == 200, r.text
        assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [0])
    assert rtx.get_page3_narrative("2026-08") == {"production_narrative": "Steady.", "highlights": ["a", "b"]}
    assert db.get_page3_narrative("2026-09") is None
    assert rtx.page3_narrative_any_row("2026-08") is True
    sec = [s for s in page_missing_data.generate_missing_data("2026-08")["sections"] if s["id"] == "page3_narrative"]
    assert sec[0]["checks"][0]["present"] is True
    # a blank narrative does not count as present
    rtx.save_page3_narrative("2026-07", "", [])
    assert rtx.page3_narrative_any_row("2026-07") is False


def test_do_letter_remarks_routes_commit_once(tc, monkeypatch):
    import page_do_letter
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "do_letter_remark_table")
        r = tc.post("/api/do-letter/remarks", json={"report_month": "2026-08", "remarks": [
            {"item_name": "Crude Steel", "plant_name": "RSP", "remark": "BF-5 down"},
            {"item_name": "Finished Steel", "plant_name": "BSP", "remark": "mill reline"}]})
        assert r.json() == {"saved": 2}
        assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [0, 0])
    assert tc.get("/api/do-letter/remarks", params={"month": "2026-08"}).json() == {
        "Crude Steel": {"RSP": "BF-5 down"}, "Finished Steel": {"BSP": "mill reline"}}
    # an empty remark deletes the row
    tc.post("/api/do-letter/remarks", json={"report_month": "2026-08", "remarks": [
        {"item_name": "Finished Steel", "plant_name": "BSP", "remark": ""}]})
    conn = db.connect()
    try:
        assert page_do_letter._fetch_remarks(conn.cursor(), "2026-08", "Crude Steel") == {"RSP": "BF-5 down"}
        assert page_do_letter._fetch_remarks(conn.cursor(), "2026-08", "Finished Steel") == {}
    finally:
        conn.close()


def test_sail_sales_note_confirm_route_and_one_page_read(tc, monkeypatch):
    import page_one_page_report
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "sail_sales_note_table")
        r = tc.post("/api/sail-1page/confirm", json={"report_month": "2026-08", "sales_rows": [],
                                                       "stock_rows": [], "sales_note": "* incl. NSL"})
        assert r.status_code == 200, r.text
        assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [0])
    conn = db.connect()
    try:
        assert page_one_page_report._sales_note(conn.cursor(), "2026-08") == "* incl. NSL"
        assert page_one_page_report._sales_note(conn.cursor(), "2026-09") is None
    finally:
        conn.close()


def test_board_note_and_secretary_review_text_commit_once(tc, monkeypatch):
    import board_note_manual_text as bnm
    import secretary_review_text as srt
    assert bnm.get_manual_text is rtx.get_manual_text and srt.save_texts is rtx.save_texts
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rtx, "board_note_manual_text")
        r = tc.post("/api/board-note/manual-text", json={"report_fy": "2026-27", "quarter": 2, "entries": [
            {"plant": "BSP", "field": "why_narrative", "text": "shutdown"},
            {"plant": "DSP", "field": "additional_highlights", "text": "record"}]})
        assert r.json() == {"saved": 2}
        assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [0, 0])
    assert tc.get("/api/board-note/manual-text", params={"fy": "2026-27", "quarter": 2}).json() == {
        "BSP": {"why_narrative": "shutdown"}, "DSP": {"additional_highlights": "record"}}
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rtx, "secretary_review_text")
        r = tc.post("/api/secretary-review/texts", json={"month": "2026-09", "texts": {"hl_SAIL": "x", "hl_BSP": ""}})
        assert r.status_code == 200, r.text
        assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [0, 0])
    assert srt.get_texts("2026-09") == {"hl_SAIL": "x", "hl_BSP": ""}
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rtx, "secretary_review_text")
        assert srt.delete_texts("2026-09", ["hl_BSP"]) == 1
        assert (spy.connects, spy.commits) == (1, 1)


def test_phys_and_rail_notes_replace_commit_once(tc, monkeypatch):
    rtx.save_ss_phys_notes("2026-27", [{"sort_order": 1, "note_text": "old"}])
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rtx, "special_steel_phys_note")
        assert rtx.save_ss_phys_notes("2026-27", [{"sort_order": 2, "note_text": " b "},
                                                  {"sort_order": 1, "note_text": "a"},
                                                  {"sort_order": 3, "note_text": "  "}]) == 3
        # DELETE + 2 INSERTs on one connection, all invisible until the one commit
        assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [1, 1, 1])
    assert db.get_ss_phys_notes("2026-27") == [(1, "a"), (2, "b")]
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rtx, "rail_prod_despatch_note")
        r = tc.post("/api/rail-report/grid", json={"financial_year": "2026-27",
                                                   "notes": [{"sort_order": 1, "note_text": "n1"}]})
        assert r.json() == {"status": "ok"}
        assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [0, 0])
    assert db.get_rail_report_notes() == [(1, "n1")]


def test_steel_sales_and_key_highlights_db_reexports(mysql_db):
    db.save_steel_sales_highlights("2026-08", ["m1"], ["y1"], updated_by="e@x")
    got = rtx.get_steel_sales_highlights("2026-08")
    assert (got["month_items"], got["ytd_items"], got["updated_by"]) == (["m1"], ["y1"], "e@x")
    db.save_key_highlights_narrative("2026-08", [{"text": "a", "subs": []}], ["s"], [], updated_by="e@x")
    got = rtx.get_key_highlights_narrative("2026-08")
    assert (got["achievements"], got["shortfalls"], got["focus_areas"]) == ([{"text": "a", "subs": []}], ["s"], [])
    assert db.get_steel_sales_highlights is rtx.get_steel_sales_highlights
    assert db.save_key_highlights_narrative is rtx.save_key_highlights_narrative


# ── repo.text get/put: one test per scope ────────────────────────────────────

def test_text_get_put_page3(mysql_db):
    assert rtx.get("page3_narrative", "2026-08", "production_narrative") is None
    rtx.put("page3_narrative", "2026-08", "production_narrative", "Steady.", "e@x")
    rtx.put("page3_narrative", "2026-08", "highlights", "a\nb", "e@x")
    assert rtx.get("page3_narrative", "2026-08", "production_narrative") == "Steady."
    assert rtx.get("page3_narrative", "2026-08", "highlights") == "a\nb"
    assert rtx.get_page3_narrative("2026-08") == {"production_narrative": "Steady.", "highlights": ["a", "b"]}


def test_text_get_put_key_highlights(mysql_db):
    assert rtx.get("key_highlights", "2026-08", "shortfalls") is None
    rtx.put("key_highlights", "2026-08", "shortfalls", "s1\ns2", "e@x")
    rtx.put("key_highlights", "2026-08", "focus_areas",
            json.dumps([{"title": "t", "description": "d"}]), "e@x")
    assert rtx.get("key_highlights", "2026-08", "shortfalls") == json.dumps(["s1", "s2"])
    got = rtx.get_key_highlights_narrative("2026-08")
    assert got["shortfalls"] == ["s1", "s2"] and got["focus_areas"] == [{"title": "t", "description": "d"}]
    assert got["achievements"] == [] and got["updated_by"] == "e@x"


def test_text_get_put_steel_sales(mysql_db):
    rtx.put("steel_sales", "2026-08", "month_items", "m1\nm2", "e@x")
    rtx.put("steel_sales", "2026-08", "ytd_items", "y1", "f@x")
    got = rtx.get_steel_sales_highlights("2026-08")
    assert (got["month_items"], got["ytd_items"], got["updated_by"]) == (["m1", "m2"], ["y1"], "f@x")
    assert rtx.get("steel_sales", "2026-08", "ytd_items") == json.dumps(["y1"])


def test_text_get_put_secretary_review(mysql_db):
    assert rtx.get("secretary_review", "2026-09", "hl_SAIL") is None
    rtx.put("secretary_review", "2026-09", "hl_SAIL", "x", "e@x")
    rtx.put("secretary_review", "2026-09", "hl_BSP", "", "e@x")
    assert rtx.get("secretary_review", "2026-09", "hl_SAIL") == "x"
    assert rtx.get("secretary_review", "2026-09", "hl_BSP") == ""
    assert rtx.get_texts("2026-09") == {"hl_SAIL": "x", "hl_BSP": ""}


def test_text_get_put_board_note(mysql_db):
    assert rtx.get("board_note", "2026-27:Q2", "why_narrative", plant="BSP") is None
    rtx.put("board_note", "2026-27:Q2", "why_narrative", "shutdown", "e@x", plant="BSP")
    assert rtx.get("board_note", "2026-27:Q2", "why_narrative", plant="BSP") == "shutdown"
    assert rtx.get_manual_text("2026-27", 2) == {("BSP", "why_narrative"): "shutdown"}
    rtx.put("board_note", "2026-27:Q2", "why_narrative", "", "e@x", plant="BSP")
    assert rtx.get_manual_text("2026-27", 2) == {}


def test_text_get_put_do_letter(mysql_db):
    assert rtx.get("do_letter", "2026-08", "remark", plant="RSP", item="Crude Steel") is None
    rtx.put("do_letter", "2026-08", "remark", "BF-5", "e@x", plant="RSP", item="Crude Steel")
    assert rtx.get("do_letter", "2026-08", "remark", plant="RSP", item="Crude Steel") == "BF-5"
    assert _rows("SELECT item_name, plant_name, remark FROM do_letter_remark_table") == [("Crude Steel", "RSP", "BF-5")]
    rtx.put("do_letter", "2026-08", "remark", "", "e@x", plant="RSP", item="Crude Steel")
    assert _rows("SELECT * FROM do_letter_remark_table") == []


def test_text_get_put_sail_sales_note(mysql_db):
    assert rtx.get("sail_sales_note", "2026-08", "note") is None
    rtx.put("sail_sales_note", "2026-08", "note", "* incl. NSL", "e@x")
    rtx.put("sail_sales_note", "2026-08", "note", "* v2", "e@x")
    assert rtx.get("sail_sales_note", "2026-08", "note") == "* v2"


def test_text_get_put_rail_note(mysql_db):
    rtx.save_rail_report_notes([{"sort_order": 1, "note_text": "one"}])
    assert rtx.get("rail_note", None, "2") is None
    rtx.put("rail_note", None, "2", "two", "e@x")
    rtx.put("rail_note", None, "1", "ONE", "e@x")
    assert rtx.get("rail_note", None, "2") == "two"
    assert rtx.get_rail_report_notes() == [(1, "ONE"), (2, "two")]
    rtx.put("rail_note", None, "1", "", "e@x")
    assert rtx.get_rail_report_notes() == [(2, "two")]


def test_text_get_put_ss_phys_note(mysql_db):
    rtx.put("ss_phys_note", "2026-27", "1", "first", "e@x")
    rtx.put("ss_phys_note", "2026-27", "2", "second", "e@x")
    rtx.put("ss_phys_note", "2025-26", "1", "other fy", "e@x")
    assert rtx.get("ss_phys_note", "2026-27", "2") == "second"
    assert rtx.get_ss_phys_notes("2026-27") == [(1, "first"), (2, "second")]
    assert rtx.get_ss_phys_notes("2025-26") == [(1, "other fy")]


def test_text_scope_map_and_unknown_scope(mysql_db):
    assert set(rtx.SCOPES) == {"page3_narrative", "key_highlights", "steel_sales", "secretary_review",
                               "board_note", "do_letter", "sail_sales_note", "rail_note", "ss_phys_note"}
    with pytest.raises(ValueError):
        rtx.get("nope", "2026-08", "x")
    with pytest.raises(ValueError):
        rtx.put("page3_narrative", "2026-08", "nope", "x", "e@x")


def test_text_put_requires_plant_and_item(mysql_db):
    """board_note needs `plant`; do_letter needs `plant` and `item`. A
    missing one raises before anything is written."""
    with pytest.raises(ValueError):
        rtx.put("board_note", "2026-27:Q2", "why_narrative", "x", "e@x")
    with pytest.raises(ValueError):
        rtx.put("do_letter", "2026-08", "remark", "x", "e@x", item="Crude Steel")
    with pytest.raises(ValueError):
        rtx.put("do_letter", "2026-08", "remark", "x", "e@x", plant="RSP")
    assert _rows("SELECT * FROM board_note_manual_text") == []
    assert _rows("SELECT * FROM do_letter_remark_table") == []


def test_text_get_sail_sales_note_blank_is_none(mysql_db):
    """A blank stored note reads as None, as page_one_page_report._sales_note
    does."""
    import page_one_page_report as p1
    rtx.put("sail_sales_note", "2026-08", "note", "", "e@x")
    assert _rows("SELECT report_month, note FROM sail_sales_note_table") == [("2026-08", "")]
    assert rtx.get("sail_sales_note", "2026-08", "note") is None
    with rc.cursor() as cur:
        assert p1._sales_note(cur, "2026-08") is None


def test_text_block_keys_validated_for_secretary_review_and_board_note(mysql_db):
    from secretary_review_layout import BLOCKS
    import board_note_manual_text as bnm
    assert rtx.SCOPES["secretary_review"][1] == tuple(k for k, _, _ in BLOCKS)
    assert rtx.SCOPES["board_note"][1] == bnm.FIELDS
    for call in (lambda: rtx.get("secretary_review", "2026-09", "nope"),
                 lambda: rtx.put("secretary_review", "2026-09", "nope", "x", "e@x"),
                 lambda: rtx.get("board_note", "2026-27:Q2", "nope", plant="BSP"),
                 lambda: rtx.put("board_note", "2026-27:Q2", "nope", "x", "e@x", plant="BSP")):
        with pytest.raises(ValueError):
            call()
    assert _rows("SELECT * FROM secretary_review_text") == []
    assert _rows("SELECT * FROM board_note_manual_text") == []


# ── repo.ops: auth flow through the gate ─────────────────────────────────────

def _cookie(resp):
    tok = resp.cookies.get(auth.COOKIE_NAME)
    assert tok, resp.text
    return {auth.COOKIE_NAME: tok}


def _make_admin(email="admin@x.in"):
    now = datetime.now(timezone.utc).isoformat()
    _exec("INSERT INTO users (email, password_hash, name, role, profile_pic, created_at, updated_at) "
          "VALUES (%s, %s, 'Admin', 'admin', '', %s, %s)", (email, auth.hash_password("adminpass1"), now, now))
    uid = _rows("SELECT id FROM users WHERE email=%s", (email,))[0][0]
    return {auth.COOKIE_NAME: auth.create_session_token(uid, email, "admin")}


def test_auth_register_login_gated_write_activity_log(gated, monkeypatch):
    sent = []
    monkeypatch.setattr(auth, "send_otp_email", lambda to, code, purpose: sent.append((to, code, purpose)))
    monkeypatch.setattr(auth, "LOGIN_2FA_ENABLED", True)
    admin = _make_admin()
    email = "ed@x.in"

    # not on the allow-list yet
    assert gated.post("/api/auth/register/request-otp", json={"email": email}).status_code == 403
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "allowed_emails")
        r = gated.post("/api/admin/allowed-emails", json={"email": email}, cookies=admin)
        assert r.status_code == 200, r.text
        # the allow-list insert, then log_activity's own connection + commit
        assert (spy.connects, spy.commits) == (1, 1) and spy.visible_mid_call == [0]
    assert _rows("SELECT action, entity, details FROM activity_log") == [
        ("insert", "allowed_emails", f"added/unbarred {email}")]
    assert [e["email"] for e in gated.get("/api/admin/allowed-emails", cookies=admin).json()["emails"]] == [email]

    # register: request OTP, wrong code refused, right code creates the account
    assert gated.post("/api/auth/register/request-otp", json={"email": email}).json() == {"status": "sent"}
    code = sent[-1][1]
    bad = gated.post("/api/auth/register/verify", json={"email": email, "otp": "000000" if code != "000000" else "111111",
                                                        "password": "secret123", "name": "Ed"})
    assert bad.status_code == 400
    r = gated.post("/api/auth/register/verify", json={"email": email, "otp": code, "password": "secret123", "name": "Ed"})
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    assert r.json()["user"]["role"] is None
    assert _rows("SELECT used FROM otp_codes WHERE email=%s", (email,)) == [(1,)]
    # the code can't be replayed
    assert not auth.verify_otp(email, "register", code)

    # a role-less user can't write
    me = _cookie(r)
    assert gated.post("/api/page3-narrative", json={"month": "2026-08", "production_narrative": "x", "highlights": []},
                      cookies=me).status_code == 403
    assert gated.patch(f"/api/admin/users/{uid}/role", json={"role": "editor"}, cookies=admin).status_code == 200

    # login: password, then the emailed code
    assert gated.post("/api/auth/login", json={"email": email, "password": "wrong-pass"}).status_code == 401
    r = gated.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert r.json()["status"] == "code_required", r.text
    challenge, code = r.json()["challenge"], sent[-1][1]
    assert sent[-1][2] == "login"
    assert r.json()["resend_after_seconds"] > 0
    r = gated.post("/api/auth/login/verify", json={"challenge": challenge, "code": code})
    assert r.status_code == 200, r.text
    me = _cookie(r)
    assert _rows("SELECT kind, user_email FROM admin_notifications") == [("sign_in", email)]

    # gated write: the narrative is saved and the middleware logs it
    before = _rows("SELECT COUNT(*) FROM activity_log")[0][0]
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rop, "activity_log")
        r = gated.post("/api/page3-narrative", json={"month": "2026-08", "production_narrative": "Steady.",
                                                     "highlights": ["h"]}, cookies=me)
        assert r.status_code == 200, r.text
        # the gate's three connections, as before the move: get_user_by_id,
        # _is_barred, then log_activity's INSERT + its one commit
        assert (spy.connects, spy.commits, spy.visible_mid_call) == (3, 1, [before])
    assert rtx.get_page3_narrative("2026-08")["production_narrative"] == "Steady."
    last = _rows("SELECT user_email, user_name, action, entity FROM activity_log ORDER BY id DESC LIMIT 1")
    assert last == [(email, "Ed", "insert/update/delete", "POST /api/page3-narrative")]

    # the key-highlights save route (Depends(require_editor_or_admin)) logs its own row
    r = gated.post("/api/key-highlights/save", json={"report_month": "2026-08", "shortfalls": ["s"]}, cookies=me)
    assert r.status_code == 200, r.text
    assert rtx.get_key_highlights_narrative("2026-08")["updated_by"] == email
    assert _rows("SELECT action, entity, details FROM activity_log WHERE entity='key_highlights_narrative'") == [
        ("update", "key_highlights_narrative", "2026-08")]

    # allowed_pages / can_delete
    r = gated.patch(f"/api/admin/users/{uid}/permissions", json={"allowed_pages": ["todo"], "can_delete": False},
                    cookies=admin)
    assert r.status_code == 200, r.text
    users = {u["email"]: u for u in gated.get("/api/admin/users", cookies=admin).json()["users"]}
    assert users[email]["allowed_pages"] == ["todo"] and users[email]["can_delete"] is False
    assert gated.post("/api/page3-narrative", json={"month": "2026-08", "production_narrative": "y", "highlights": []},
                      cookies=me).status_code == 403
    r = gated.post("/api/todo/add", json={"subject": "s", "due_date": "2026-10-30"}, cookies=me)
    assert r.status_code == 200, r.text
    job = r.json()["id"]
    assert gated.post(f"/api/todo/{job}/delete", cookies=me).status_code == 403

    # barred: the session stops working for gated writes and /me
    assert gated.patch(f"/api/admin/allowed-emails/{email}/bar", json={"barred": True}, cookies=admin).status_code == 200
    assert _rows("SELECT barred, barred_by FROM allowed_emails WHERE email=%s", (email,)) == [(1, "admin@x.in")]
    assert gated.post("/api/todo/add", json={"subject": "t", "due_date": "2026-10-30"}, cookies=me).status_code == 403
    assert gated.get("/api/auth/me", cookies=me).status_code == 403
    assert not auth.is_email_allowed(email)
    assert gated.post("/api/auth/login", json={"email": email, "password": "secret123"}).status_code == 403

    # admin activity log views
    flt = gated.get("/api/admin/activity-log/filters", cookies=admin).json()
    assert email in flt["users"] and "insert/update/delete" in flt["actions"]
    ent = gated.get("/api/admin/activity-log", params={"user_email": email, "action": "update"}, cookies=admin).json()
    assert [e["entity"] for e in ent["entries"]] == ["key_highlights_narrative"]

    # admin deletes the account
    assert gated.delete(f"/api/admin/users/{uid}", cookies=admin).status_code == 200
    assert auth.get_user_by_email(email) is None
    assert gated.delete(f"/api/admin/allowed-emails/{email}", cookies=admin).status_code == 200
    assert _rows("SELECT * FROM allowed_emails") == []


def test_otp_expiry_burn_and_reset_password(gated, monkeypatch):
    sent = []
    monkeypatch.setattr(auth, "send_otp_email", lambda to, code, purpose: sent.append(code))
    now = datetime.now(timezone.utc).isoformat()
    _exec("INSERT INTO users (email, password_hash, name, role, profile_pic, created_at, updated_at) "
          "VALUES ('u@x.in', %s, 'U', NULL, '', %s, %s)", (auth.hash_password("oldpass12"), now, now))
    # an expired code (VARCHAR ISO timestamp in the past) is refused
    code = auth.generate_and_store_otp("u@x.in", "reset_password")
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    _exec("UPDATE otp_codes SET expires_at=%s", (past,))
    assert not auth.verify_otp("u@x.in", "reset_password", code)
    # a new code invalidates the earlier unused ones
    code1 = auth.generate_and_store_otp("u@x.in", "reset_password")
    code2 = auth.generate_and_store_otp("u@x.in", "reset_password")
    assert _rows("SELECT used FROM otp_codes ORDER BY id") == [(1,), (1,), (0,)]
    assert auth.otp_resend_wait_seconds("u@x.in", "reset_password") > 0
    assert auth.otp_resend_wait_seconds("u@x.in", "login") == 0
    # OTP_MAX_ATTEMPTS wrong guesses burn the code
    wrong = "000000" if code2 != "000000" else "111111"
    for _ in range(auth.OTP_MAX_ATTEMPTS):
        assert not auth.verify_otp("u@x.in", "reset_password", wrong)
    assert _rows("SELECT used FROM otp_codes ORDER BY id DESC LIMIT 1") == [(1,)]
    assert not auth.verify_otp("u@x.in", "reset_password", code2)
    assert code1  # (unused: it was invalidated by code2)
    # password reset through the routes
    assert gated.post("/api/auth/password/request-otp", json={"email": "u@x.in"}).status_code == 200
    r = gated.post("/api/auth/password/verify", json={"email": "u@x.in", "otp": sent[-1], "new_password": "newpass12"})
    assert r.status_code == 200, r.text
    user = auth.get_user_by_email("u@x.in")
    assert auth.verify_password("newpass12", user["password_hash"])
    # profile update (dynamic UPDATE users SET ...) and re-read
    tok = {auth.COOKIE_NAME: auth.create_session_token(user["id"], "u@x.in", None)}
    r = gated.put("/api/auth/profile", data={"name": " New Name "}, cookies=tok)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["name"] == "New Name"
    assert auth.get_user_by_id(user["id"])["name"] == "New Name"


# ── repo.ops: per-request writes (visits / notifications) ────────────────────

def test_log_visit_and_admin_notifications(gated, monkeypatch):
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rop, "page_visits")
        r = gated.post("/api/log-visit", json={"path": "/report"}, headers={"x-forwarded-for": "10.0.0.9"})
        assert r.status_code == 200, r.text
        # one connection for the visit, one for the anon-visit notification
        assert (spy.connects, spy.commits) == (2, 2)
        assert spy.visible_mid_call == [0, 1]
    gated.post("/api/log-visit", json={"path": "/upload"}, headers={"x-forwarded-for": "10.0.0.9"})
    assert _rows("SELECT ip_address, user_email, path FROM page_visits ORDER BY id") == [
        ("10.0.0.9", None, "/report"), ("10.0.0.9", None, "/upload")]
    # the second anonymous visit inside the window is not notified again
    assert _rows("SELECT kind, ip_address, path FROM admin_notifications") == [("anon_visit", "10.0.0.9", "/report")]
    admin = _make_admin()
    notes = gated.get("/api/admin/notifications", cookies=admin).json()["notifications"]
    assert [(n["kind"], n["path"]) for n in notes] == [("anon_visit", "/report")]
    visits = gated.get("/api/admin/site-visits", cookies=admin).json()
    assert visits and json.dumps(visits).count("/upload") >= 1
    assert gated.get("/api/admin/site-visits", params={"days": 0}, cookies=admin).status_code == 200
    # a failing notification insert is swallowed
    monkeypatch.setattr(rop, "_add_admin_notification", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    db.add_admin_notification("sign_in", "1.2.3.4")
    assert db.log_page_visit is rop.log_page_visit and db.list_admin_notifications is rop.list_admin_notifications


# ── repo.ops: extraction_log ─────────────────────────────────────────────────

def test_extraction_log_own_and_caller_connection(tc, monkeypatch):
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rop, "extraction_log")
        db.log_extraction("RSP", "2026-08", "Final Monthly Report Aug.xlsx", "s", "Final Monthly Report", 5)
        assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [0])
    # with the caller's connection it neither commits nor closes
    conn = db.connect()
    try:
        rop.log_extraction("ISP", "2026-08", "f.pdf", "s", "Final Monthly Report", 3, conn=conn)
        assert _other_conn_count("extraction_log") == 1
        conn.commit()
    finally:
        conn.close()
    assert _other_conn_count("extraction_log") == 2
    logs = tc.get("/api/extraction-log", params={"plant": "RSP"}).json()["logs"]
    assert [(l["plant_name"], l["items_extracted"]) for l in logs] == [("RSP", 5)]
    assert [l["plant_name"] for l in db.get_extraction_logs()] == ["ISP", "RSP"]
    st = db.production_month_status("2026-08")
    assert st == {"tentative": True, "missing": ["BSL", "DSP"]}
    assert db._production_month_status is rop._production_month_status


# ── repo.ops: to-do and work log routes ──────────────────────────────────────

def test_todo_routes_commit_once(tc, monkeypatch):
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "todo_jobs")
        r = tc.post("/api/todo/add", json={"subject": " Send note ", "due_date": "2026-10-30", "priority": "high"})
        assert r.status_code == 200, r.text
        assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [0])
    job = r.json()["id"]
    assert tc.post(f"/api/todo/{job}/update", json={"remark": "r1"}).status_code == 200
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "todo_jobs")
        assert tc.post(f"/api/todo/{job}/complete").status_code == 200
        assert (spy.connects, spy.commits) == (1, 1)
    jobs = tc.get("/api/todo/list", params={"status": "done"}).json()["jobs"]
    assert [(j["subject"], j["status"], j["remark"], j["priority"]) for j in jobs] == [("Send note", "done", "r1", "high")]
    assert jobs[0]["completed_at"]
    assert tc.post(f"/api/todo/{job}/reopen").status_code == 200
    assert tc.get("/api/todo/list").json()["count"] == 1
    assert tc.get("/api/todo/list", params={"status": "all"}).json()["count"] == 1
    assert tc.post("/api/todo/999/complete").status_code == 404
    assert tc.post(f"/api/todo/{job}/delete").status_code == 200
    assert tc.post(f"/api/todo/{job}/delete").status_code == 404
    assert _rows("SELECT * FROM todo_jobs") == []


def test_worklog_routes_commit_once(tc, monkeypatch):
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "daily_work_log")
        r = tc.post("/api/worklog/add", json={"work_date": "2026-10-19", "description": " did x ", "remarks": "r"})
        assert r.status_code == 200, r.text
        assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [0])
    eid = r.json()["id"]
    tc.post("/api/worklog/add", json={"work_date": "2026-09-01", "description": "older"})
    assert tc.post(f"/api/worklog/{eid}/update", json={"remarks": "r2"}).status_code == 200
    got = tc.get("/api/worklog/list", params={"month": "2026-10"}).json()
    assert [(e["description"], e["remarks"]) for e in got["entries"]] == [("did x", "r2")]
    got = tc.get("/api/worklog/list", params={"from": "2026-08-01", "to": "2026-09-30"}).json()
    assert [e["description"] for e in got["entries"]] == ["older"]
    assert tc.get("/api/worklog/list").json()["count"] == 2
    assert tc.post(f"/api/worklog/{eid}/delete").status_code == 200
    assert tc.post(f"/api/worklog/{eid}/update", json={"remarks": "x"}).status_code == 404
    assert _rows("SELECT description FROM daily_work_log") == [("older",)]
