"""Task 6a: v1 -> v2 migration (tools/migrate_v1_to_v2.py) round-trips.

A small v1 fixture (FIXTURE below: the edge cases of Review Focus #1, #2,
#4, #5) is loaded into the session's v1 test schema, migrated ONCE into the
session's v2 test schema, and read back with plain SQL + repo.v2codec (ruling
R5: no Task 7 repository functions exist yet). The v2 schema is emptied
again at the end of the module, so test_schema_v2 still sees empty tables.
"""
import json
import os

import pymysql
import pytest
from pymysql.constants import FIELD_TYPE

from repo import v2codec as vc
from tools import migrate_v1_to_v2 as mig

pytestmark = pytest.mark.filterwarnings("ignore::Warning")


def _cfg():
    return {
        "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ["MYSQL_TEST_USER"],
        "password": os.environ["MYSQL_TEST_PASSWORD"],
    }


def _connect(db):
    """A connection that reads DATETIME / DATE as strings, like dbengine."""
    conv = pymysql.converters.conversions.copy()
    for ft in (FIELD_TYPE.DATETIME, FIELD_TYPE.DATE, FIELD_TYPE.TIMESTAMP):
        conv[ft] = str
    cfg = _cfg()
    return pymysql.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"],
                           password=cfg["password"], database=db, charset="utf8mb4",
                           autocommit=True, ssl_disabled=True, conv=conv)


def _rows(db, sql, params=()):
    conn = _connect(db)
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())
    finally:
        conn.close()


# ── the v1 fixture ──────────────────────────────────────────────────────────

TECHNO_BLOBS = {
    # types, explicit null, nested object, bool, mixed-length / mixed-case keys
    ("BSP", "2026-04", "BF-1"): {
        "month": {"Coke Rate": 450, "CDI": 5.0, "Productivity": 2.137, "remark": "ok",
                  "nullkey": None, "obj": {"b": 1, "a": [1, 2.5]}, "AA": 1, "a": 2,
                  "Zz": True, "B": -0.25},
        "till_month": {},
    },
    # no till_month key at all (SAIL Coal_Receipt_Stock in v1)
    ("SAIL", "2026-04", "Coal_Receipt_Stock"): {"month": {"x": 1.5}},
    # empty month, '#' unit spelling
    ("BSP", "2026-05", "BF#1"): {"month": {}, "till_month": {"Coke Rate": 451}},
    # large int, int vs float of the same number, exponents
    ("DSP", "2011-03", "SMS"): {"month": {"Heat": 1420711, "neg": -0.5, "big": 1e20, "tiny": 1e-7},
                                "till_month": {"Heat": 1420711.0, "s": "1.50"}},
}

FIXTURE = {
    "production_table": (
        ("report_month", "plant_name", "item_name", "month_actual"),
        [("2026-04", "BSP", "Crude Steel", 100.5),
         ("2026-04", "BSP", "CC BILLET", 10.0),
         ("2026-04", "DSP", "CC Billet", 11.0),
         ("2026-04", "SAIL", "Total Crude Steel", 500.25),
         ("2026-04", "BSP", "Hot Metal", None),           # a row holding NULL
         ("2016-03", "RSP", "Crude Steel", 3.0),
         ("1964-11", "BSP", "Hot Metal", 1.0)],
    ),
    "production_plan_table": (
        ("report_month", "plant_name", "item_name", "month_actual"),
        [("2026-04", "BSP", "Crude Steel", 110.0),
         ("2026-04", "BSP", "Pig Iron", None),
         ("2026-05", "CFP", "Crude Steel", 2.0)],
    ),
    "mou_plan_table": (
        ("report_month", "plant_name", "item_name", "month_actual"),
        [("2026-04", "BSP", "Crude Steel", 120.0),
         ("2026-04", "VISL", "Saleable Steel", 5.5)],
    ),
    "pdf_item_alias": (
        ("plant_name", "pdf_label", "item_name", "convert_t"),
        [("DSP", "Billet Caster Prod", "BILLET Caster", 1),
         ("DSP", "Billet caster (t)", "Billet Caster", 0)],
    ),
    "item_capacity_table": (
        ("id", "plant_name", "item_name", "effective_month", "annual_capacity", "reason",
         "created_by", "created_at", "updated_by", "updated_at"),
        [(7, "BSP", "Crude Steel", "2026-04", 7000.0, "", "a@x", "2026-08-19T11:02:50.043984",
          "b@x", "2026-08-19T11:02:50")],                     # microsecond 0: no fraction
    ),
    "do_letter_remark_table": (
        ("report_month", "item_name", "plant_name", "remark"),
        [("2026-08", "Crude Steel", "BSP", "remark text"),
         ("2026-08", "CC BILLET", "DSP", None)],
    ),
    "techno_data": (
        ("id", "plant", "report_month", "unit", "techno_json", "source_file", "created_at"),
        [(i + 1, p, m, u, json.dumps(b), f"src{i}.xlsx", f"2026-07-25 07:56:1{i}")
         for i, ((p, m, u), b) in enumerate(TECHNO_BLOBS.items())],
    ),
    "techno_plan_fy": (
        ("plant_name", "unit", "fy", "techno_json", "is_user_supplied", "created_at", "updated_at",
         "created_by"),
        [("BSP", "BF-1", "2026-27", '{"b": 1, "a": 2.0}', 1, "2026-07-01 10:00:00",
          "2026-07-02 11:00:00", "u@x")],
    ),
    "breakdown_table": (
        ("id", "plant", "unit_type", "unit_name", "start_ts", "end_ts", "is_ongoing", "cause",
         "capital_repair_id", "created_by", "created_at", "updated_by", "updated_at"),
        [(1, "BSP", "BF", "BF-1", "2026-08-02 10:00", None, 1, "cause", 999,      # dangling id
          "u", "2026-08-23T09:41:58.078837", "u", "2026-08-23T09:41:58"),
         (2, "BSP", "GENERAL", "Shop", "2026-08-02", "2026-08-03", 0, "c2", 5,
          "u", "2026-08-24T10:00:00.000001", None, None)],
    ),
    "capital_repair_table": (
        ("id", "plant", "fy", "shop", "equipment", "unit_type", "unit_name", "activity",
         "schedule_days", "actual_start", "actual_end", "actual_ongoing", "planned_days", "sort_order"),
        [(5, "BSP", "2026-27", "Shop", "Eq", "BF", "Shop", "act", "10", "2026-07-28",
          "2026-08-05", 0, 10.0, 1),
         (6, "DSP", "2026-27", None, None, None, None, None, None, None, None, 1, None, 2)],
    ),
    "bf_benchmark_sail_meta": (
        ("plant", "unit", "working_volume_m3", "updated_at"),
        [("BSP", "BF-8", 4060.0, "2026-09-04T02:12:01.869162+00:00")],
    ),
    "bf_benchmark_external_bf": (
        ("id", "name", "company", "location", "working_volume_m3", "active", "created_at", "created_by"),
        [(1, "POSCO 1", "POSCO", "KR", 6000.0, 1, "2026-08-12T19:52:34.519063+00:00", "a"),
         (2, "JSW 3", "JSW", "IN", 4000.0, 1, "2026-08-16 18:18:13", ""),
         (3, "Tata G", "Tata", "IN", None, 0, "2026-08-12T19:52:34+00:00", "a")],
    ),
    "bf_benchmark_external_data": (
        ("id", "external_bf_id", "report_month", "param_json", "created_at", "updated_at"),
        [(1, 1, "2023-24", '{"p": 1}', "2026-08-13T00:08:41.444667+00:00", "2026-08-16 18:18:53"),
         (2, 2, "2024-25", '{"q": 2.5}', "2026-08-16 18:18:53", "2026-08-16 18:18:53"),
         (3, 3, "2024-25", '{}', None, None)],
    ),
    "major_unit_daily_record": (
        ("plant_code", "unit_label", "unit_of_measure", "value", "record_date", "remarks",
         "sort_order", "updated_by", "updated_at"),
        [("BSP", "Blast Furnace-8", "THM", 123.0, "2026-03-04", None, 1, "u", "2026-09-23T13:41:31"),
         ("RSP", "SMS-2", None, None, None, None, 0, None, None)],
    ),
    "users": (
        ("id", "email", "password_hash", "name", "role", "created_at", "updated_at", "can_delete"),
        [(1, "a@x", "h", "A", "admin", "2026-07-19T05:44:35.845751+00:00",
          "2026-09-11T15:07:55.429501+00:00", 0)],
    ),
    "allowed_emails": (
        ("email", "added_by", "added_at", "barred", "barred_by", "barred_at"),
        [("a@x", "root", "2026-08-05T06:27:22.367981+00:00", 0, None, None),
         ("b@x", "root", "2026-08-05T06:27:22+00:00", 1, "a@x", "2026-08-06T01:02:03.000004+00:00")],
    ),
    "otp_codes": (
        ("id", "email", "purpose", "code_hash", "expires_at", "used", "created_at"),
        [(1, "a@x", "login", "h", "2026-07-19T05:39:34.844765+00:00", 1,
          "2026-07-19T05:29:34.844765+00:00")],
    ),
    "activity_log": (
        ("id", "user_email", "user_name", "action", "entity", "details", "timestamp"),
        [(1, "a@x", "A", "login", None, None, "2026-09-09T05:58:59.243471+00:00"),
         (2, None, None, "save", "page", "d", "2026-09-09T05:59:00+00:00")],
    ),
    "page_visits": (
        ("id", "timestamp", "ip_address", "user_email", "user_name", "path"),
        [(1, "2026-09-02T01:16:50.901683+00:00", "1.2.3.4", None, None, "/report")],
    ),
    "admin_notifications": (
        ("id", "created_at", "kind", "user_email", "user_name", "ip_address", "path"),
        [(1, "2026-10-03T22:12:42.954813+00:00", "anon_visit", None, None, "1.2.3.4", "/")],
    ),
    "todo_jobs": (
        ("id", "subject", "details", "recipient", "due_date", "priority", "status", "created_at",
         "completed_at", "remark"),
        [(1, "s", "d", "r", "2026-07-22", "medium", "done", "2026-07-10T07:17:32.769191",
          "2026-08-02T15:44:53.501850", None),
         (2, "t", None, None, "2026-08-01", "high", "pending", "2026-07-10T07:17:33", None, "x")],
    ),
    "daily_work_log": (
        ("id", "work_date", "description", "remarks", "created_at"),
        [(1, "2026-07-10", "work", None, "2026-07-11T13:45:28.568951")],
    ),
    "special_steel_grade_clubs": (
        ("plant_name", "product", "quality_grade", "club_label", "created_at"),
        [("DSP", "Wheel", "R7", "Club A", "2026-08-07T04:30:54.292973")],
    ),
    "steel_sector_performance_table": (
        ("report_month", "data_json", "source_file", "created_at"),
        [("2026-08", '{"a": 1}', "f.pdf", "2026-08-22T16:45:57.847952")],
    ),
    "cover_photos": (
        ("id", "filename", "thumb_filename", "original_name", "width", "height", "uploaded_by",
         "uploaded_at", "is_active"),
        [(6, "a.jpg", "a_t.jpg", "orig.jpg", 100, 50, "admin", "2026-10-03 21:05:15", 1)],
    ),
    "report_cover_settings": (
        ("report_month", "design", "photo_mode", "photo_id", "updated_by", "updated_at"),
        [("2026-08", "classic", "fixed", 6, "admin", "2026-10-04 05:44:13")],
    ),
    "extraction_log": (
        ("id", "logged_at", "plant_name", "report_month", "file_name", "items_extracted"),
        [(1, "2026-06-07 22:15:11", "TESTPLANT", "2099-01", "f.xlsx", 0),
         (2, "2026-06-07 22:15:12", "BSP_BF", "2026-04", "g.xlsx", 5)],
    ),
    "sail_stock_snapshot_table": (
        ("snapshot_date", "item_name", "value"),
        [("2021-01-04", "Plants", 1.0)],
    ),
    "page_configs": (
        ("report_month", "page_number", "page_data"),
        [("2026-04", 3, '{"z": 1, "a": [1, 2.50], "u": "é \\u00e9"}  \n')],
    ),
    # the 9 narrative tables
    "page3_narrative": (
        ("report_month", "production_narrative", "highlights", "updated_at"),
        [("2026-04", "narr", "h1\nh2", "2026-07-21 07:09:24"),
         ("2026-05", None, "", None)],
    ),
    "key_highlights_narrative": (
        ("report_month", "achievements", "shortfalls", "focus_areas", "updated_by", "updated_at"),
        [("2026-08", '["a"]', "[]", None, "u@x", "2026-09-18 13:30:55")],
    ),
    "steel_sales_highlights": (
        ("report_month", "month_items", "ytd_items", "updated_by", "updated_at"),
        [("2026-09", '["m"]', '["y"]', None, "2026-09-18 13:30:56")],
    ),
    "secretary_review_text": (
        ("report_month", "block_key", "text", "updated_at"),
        [("2026-09", "intro", "text – 1", "2026-10-07T17:26:15"),
         ("2026-09", "outro", None, None)],
    ),
    "board_note_manual_text": (
        ("report_fy", "quarter", "plant", "field", "text"),
        [("2026-27", 1, "BSP", "why_narrative", "w"),
         ("2026-27", 2, "VISL", "additional_highlights", "")],
    ),
    "sail_sales_note_table": (
        ("report_month", "note"),
        [("2026-07", "note"), ("2026-08", None)],
    ),
    "rail_prod_despatch_note": (
        ("sort_order", "note_text"),
        [(1, "n1"), (2, "n2")],
    ),
    "special_steel_phys_note": (
        ("financial_year", "sort_order", "note_text"),
        [("2025-26", 1, "p1"), ("2026-27", 1, "p2")],
    ),
}


def _load_v1(db):
    conn = _connect(db)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE()")
            assert cur.fetchone()[0].startswith("mis_reports_test_")
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            cur.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
            for t, _ in cur.fetchall():
                if t == "data_version":
                    continue
                cur.execute(f"SELECT EXISTS(SELECT 1 FROM `{t}`)")
                if cur.fetchone()[0]:
                    cur.execute(f"DELETE FROM `{t}`")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            for table, (cols, rows) in FIXTURE.items():
                sql = (f"INSERT INTO `{table}` ({', '.join(f'`{c}`' for c in cols)}) "
                       f"VALUES ({', '.join(['%s'] * len(cols))})")
                cur.executemany(sql, rows)
            cur.execute("INSERT INTO data_version (id, n) VALUES (1, 7) "
                        "ON DUPLICATE KEY UPDATE n = 7")
    finally:
        conn.close()


@pytest.fixture(scope="module")
def dbs(_mysql_test_schema, mysql_v2_db):
    v1 = _mysql_test_schema
    with mysql_v2_db.cursor() as cur:
        cur.execute("SELECT DATABASE()")
        v2 = cur.fetchone()[0]
    assert v1.startswith("mis_reports_test_") and v2.startswith("mis_reports_test_v2_")
    _load_v1(v1)
    mig.migrate(v1, v2, src_cfg=_cfg(), dst_cfg=_cfg())
    try:
        yield v1, v2
    finally:
        mig.clear_dst(v2, dst_cfg=_cfg())


# ── Review Focus #4: exact strings ──────────────────────────────────────────

def test_migration_preserves_every_distinct_string(dbs):
    v1, v2 = dbs
    plants = {r["plant_code"] for r in _rows(v2, "SELECT plant_code FROM plant")}
    items = {r["item_name"]: r["item_id"] for r in _rows(v2, "SELECT item_id, item_name FROM item")}
    units = {(r["plant_code"], r["unit_code"]) for r in
             _rows(v2, "SELECT plant_code, unit_code FROM plant_unit")}

    seen_plants = set()
    for table, col in mig.PLANT_COLUMNS:
        for r in _rows(v1, f"SELECT DISTINCT CAST(`{col}` AS BINARY) AS v FROM `{table}`"):
            seen_plants.add(r["v"].decode())
    assert seen_plants and seen_plants == plants
    assert {"SAIL", "CFP", "VISL", "BSP"} <= plants

    seen_items = set()
    for table, col in mig.ITEM_COLUMNS:
        for r in _rows(v1, f"SELECT DISTINCT CAST(`{col}` AS BINARY) AS v FROM `{table}`"):
            seen_items.add(r["v"].decode())
    assert seen_items == set(items)
    # case variants are separate items, and each name resolves exactly to itself
    for a, b in (("CC BILLET", "CC Billet"), ("BILLET Caster", "Billet Caster"),
                 ("Crude Steel", "Total Crude Steel")):
        assert a in items and b in items and items[a] != items[b]
    for name, item_id in items.items():
        got = _rows(v2, "SELECT item_id FROM item WHERE item_name = %s", (name,))
        assert [r["item_id"] for r in got] == [item_id], name

    seen_units = set()
    for table, pcol, ucol in mig.UNIT_COLUMNS:
        for r in _rows(v1, f"SELECT DISTINCT CAST(`{pcol}` AS BINARY) AS p, CAST(`{ucol}` AS BINARY) AS u "
                           f"FROM `{table}` WHERE `{ucol}` IS NOT NULL"):
            seen_units.add((r["p"].decode(), r["u"].decode()))
    assert seen_units == units
    assert ("BSP", "BF#1") in units and ("BSP", "BF-1") in units

    # every fact row points at the exact v1 spelling
    got = _rows(v2, "SELECT p.report_month, p.plant_code, i.item_name FROM production_monthly p "
                    "JOIN item i ON i.item_id = p.item_id")
    assert ("2026-04", "BSP", "CC BILLET") in {tuple(r.values()) for r in got}
    assert ("2026-04", "DSP", "CC Billet") in {tuple(r.values()) for r in got}


# ── Review Focus #2: production has_* flags ─────────────────────────────────

def test_production_roundtrip(dbs):
    v1, v2 = dbs
    v2rows = _rows(v2, "SELECT p.report_month, p.plant_code, i.item_name, p.actual, p.abp_plan, "
                       "p.mou_plan, p.has_actual, p.has_abp, p.has_mou FROM production_monthly p "
                       "JOIN item i ON i.item_id = p.item_id")
    union = set()
    for table, (col, flag) in vc.PRODUCTION_SOURCES.items():
        src = {(r["report_month"], r["plant_name"], r["item_name"]): r["month_actual"]
               for r in _rows(v1, f"SELECT report_month, plant_name, item_name, month_actual FROM `{table}`")}
        assert src, table
        union |= set(src)
        back = {(r["report_month"], r["plant_code"], r["item_name"]): r[col]
                for r in v2rows if r[flag]}
        assert back == src, table
        for k, v in src.items():
            assert type(back[k]) is type(v)
        for r in v2rows:
            if not r[flag]:
                assert r[col] is None
                assert (r["report_month"], r["plant_code"], r["item_name"]) not in src
    assert len(v2rows) == len(union)


# ── Review Focus #1 / #2: techno ────────────────────────────────────────────

def _same(a, b, path="$"):
    assert type(a) is type(b), f"{path}: {type(a).__name__} != {type(b).__name__}"
    if isinstance(a, dict):
        assert list(a) == list(b), f"{path}: key order {list(a)} != {list(b)}"
        for k in a:
            _same(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _same(x, y, f"{path}[{i}]")
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"


def _v2_techno(v2):
    uploads = {(r["plant_code"], r["report_month"], r["unit_code"]): r for r in _rows(
        v2, "SELECT t.plant_code, t.report_month, u.unit_code, t.has_month, t.has_till_month, "
            "t.source_file, t.created_at FROM techno_upload t JOIN plant_unit u ON u.unit_id = t.unit_id")}
    leaves = {}
    for r in _rows(v2, "SELECT t.plant_code, t.report_month, u.unit_code, t.period, t.param_key, "
                       "t.num, t.is_int, t.raw FROM techno_value t JOIN plant_unit u ON u.unit_id = t.unit_id "
                       f"ORDER BY t.plant_code, t.report_month, u.unit_code, {vc.TECHNO_LEAF_ORDER_BY}"):
        leaves.setdefault((r["plant_code"], r["report_month"], r["unit_code"]), []).append(
            (r["period"], r["param_key"], r["num"], r["is_int"], r["raw"]))
    return uploads, leaves


def test_techno_roundtrip_preserves_types(dbs):
    v1, v2 = dbs
    uploads, leaves = _v2_techno(v2)
    src = _rows(v1, "SELECT plant, report_month, unit, techno_json, source_file, created_at FROM techno_data")
    assert len(src) == len(TECHNO_BLOBS) == len(uploads)
    for r in src:
        key = (r["plant"], r["report_month"], r["unit"])
        up = uploads[key]
        rows = leaves.get(key, [])
        # SQL order rule == the codec's order == MySQL JSON's normalised order
        assert rows == sorted(rows, key=lambda x: vc.techno_key_order(x[0], x[1]))
        got = vc.decode_techno(up["has_month"], up["has_till_month"], rows)
        want = json.loads(r["techno_json"])
        assert got == want
        _same(got, want)
        assert up["source_file"] == r["source_file"]
        assert vc.render_ts(vc.SQL_SECONDS, up["created_at"]) == r["created_at"]
    # the fixture really has both number types for the same value
    dsp = vc.decode_techno(*[uploads[("DSP", "2011-03", "SMS")][k] for k in ("has_month", "has_till_month")],
                           leaves[("DSP", "2011-03", "SMS")])
    assert type(dsp["month"]["Heat"]) is int and type(dsp["till_month"]["Heat"]) is float
    assert dsp["till_month"]["s"] == "1.50"


def test_absent_vs_null_distinct(dbs):
    v1, v2 = dbs
    uploads, leaves = _v2_techno(v2)
    bsp = vc.decode_techno(uploads[("BSP", "2026-04", "BF-1")]["has_month"],
                           uploads[("BSP", "2026-04", "BF-1")]["has_till_month"],
                           leaves[("BSP", "2026-04", "BF-1")])
    assert "nullkey" in bsp["month"] and bsp["month"]["nullkey"] is None
    assert "missing" not in bsp["month"]
    assert bsp["till_month"] == {}                         # empty period kept
    raw_null = _rows(v2, "SELECT raw, num, raw IS NULL AS sql_null FROM techno_value "
                         "WHERE param_key = 'nullkey'")
    assert raw_null == [{"raw": "null", "num": None, "sql_null": 0}]   # JSON null, not SQL NULL
    sail = uploads[("SAIL", "2026-04", "Coal_Receipt_Stock")]
    assert (sail["has_month"], sail["has_till_month"]) == (1, 0)
    assert "till_month" not in vc.decode_techno(sail["has_month"], sail["has_till_month"],
                                                leaves[("SAIL", "2026-04", "Coal_Receipt_Stock")])
    bf1 = uploads[("BSP", "2026-05", "BF#1")]
    assert vc.decode_techno(bf1["has_month"], bf1["has_till_month"], leaves[("BSP", "2026-05", "BF#1")]) \
        == {"month": {}, "till_month": {"Coke Rate": 451}}

    # production: a v1 row holding NULL vs no v1 row
    prod = {(r["plant_code"], r["item_name"]): r for r in _rows(
        v2, "SELECT p.plant_code, i.item_name, p.actual, p.has_actual, p.abp_plan, p.has_abp "
            "FROM production_monthly p JOIN item i ON i.item_id = p.item_id WHERE p.report_month = '2026-04'")}
    assert prod[("BSP", "Hot Metal")]["has_actual"] == 1 and prod[("BSP", "Hot Metal")]["actual"] is None
    assert prod[("BSP", "Hot Metal")]["has_abp"] == 0
    assert prod[("BSP", "Pig Iron")]["has_actual"] == 0 and prod[("BSP", "Pig Iron")]["has_abp"] == 1
    assert prod[("BSP", "Pig Iron")]["abp_plan"] is None


# ── narrative text ──────────────────────────────────────────────────────────

def _sort_key(d):
    return tuple((v is None, str(v)) for v in d.values())


def test_text_roundtrip(dbs):
    v1, v2 = dbs
    assert len(vc.TEXT_SCOPES) == 9
    for scope, spec in vc.TEXT_SCOPES.items():
        cols = vc.v1_text_columns(scope)
        src = _rows(v1, f"SELECT {', '.join(f'`{c}`' for c in cols)} FROM `{spec['table']}`")
        assert src, scope
        v2rows = _rows(v2, "SELECT t.period, t.block_key, t.plant_code, i.item_name, t.seq, t.text, "
                           "t.updated_by, t.updated_at FROM report_text t "
                           "LEFT JOIN item i ON i.item_id = t.item_id WHERE t.scope = %s", (scope,))
        got = vc.decode_text_rows(scope, v2rows)
        assert sorted(got, key=_sort_key) == sorted(src, key=_sort_key), scope
        for g in got:
            assert list(g) == list(cols), scope
    # a wide v1 row becomes one row per column, each with the row's stamp
    kh = _rows(v2, "SELECT block_key, text, updated_by, updated_at FROM report_text "
                   "WHERE scope = 'key_highlights' ORDER BY block_key")
    assert [r["block_key"] for r in kh] == ["achievements", "focus_areas", "shortfalls"]
    assert {(r["updated_by"], r["updated_at"]) for r in kh} == {("u@x", "2026-09-18 13:30:55")}


# ── Review Focus #5: timestamps ─────────────────────────────────────────────

# v2 table -> (v1 key columns, v2 key expressions over alias t, v2 FROM)
_TS_KEYS = {
    "activity_log": (["id"], ["t.id"], "activity_log t"),
    "admin_notification": (["id"], ["t.id"], "admin_notification t"),
    "allowed_email": (["email"], ["t.email"], "allowed_email t"),
    "app_user": (["id"], ["t.id"], "app_user t"),
    "otp_code": (["id"], ["t.id"], "otp_code t"),
    "page_visit": (["id"], ["t.id"], "page_visit t"),
    "bf_benchmark_sail_meta": (["plant", "unit"], ["t.plant_code", "u.unit_code"],
                               "bf_benchmark_sail_meta t JOIN plant_unit u ON u.unit_id = t.unit_id"),
    "bf_benchmark_external_bf": (["id"], ["t.id"], "bf_benchmark_external_bf t"),
    "bf_benchmark_external_data": (["id"], ["t.id"], "bf_benchmark_external_data t"),
    "breakdown": (["id"], ["t.id"], "breakdown t"),
    "item_capacity": (["id"], ["t.id"], "item_capacity t"),
    "special_steel_grade_club": (["plant_name", "product", "quality_grade"],
                                 ["t.plant_code", "t.product", "t.quality_grade"], "special_steel_grade_club t"),
    "steel_sector_performance": (["report_month"], ["t.report_month"], "steel_sector_performance t"),
    "todo_job": (["id"], ["t.id"], "todo_job t"),
    "daily_work_log": (["id"], ["t.id"], "daily_work_log t"),
    "major_unit_daily_record": (["plant_code", "unit_label"], ["t.plant_code", "u.unit_code"],
                                "major_unit_daily_record t JOIN plant_unit u ON u.unit_id = t.unit_id"),
    "cover_photo": (["id"], ["t.id"], "cover_photo t"),
    "report_cover_setting": (["report_month"], ["t.report_month"], "report_cover_setting t"),
    "extraction_log": (["id"], ["t.id"], "extraction_log t"),
    "techno_upload": (["plant", "report_month", "unit"], ["t.plant_code", "t.report_month", "u.unit_code"],
                      "techno_upload t JOIN plant_unit u ON u.unit_id = t.unit_id"),
    "capital_repair": (["id"], ["t.id"], "capital_repair t"),
    "sail_stock_snapshot": (["item_name"], ["t.item_name"], "sail_stock_snapshot t"),
}


def _pairs(rows):
    return sorted((tuple(r.values()) for r in rows), key=lambda t: tuple(str(x) for x in t))


def test_timestamp_render_unchanged(dbs):
    v1, v2 = dbs
    checked = 0
    for v2col, (v1col, fmt) in list(vc.TS_COLUMNS.items()) + \
            [(k, (v, vc.DATE)) for k, v in vc.DATE_COLUMNS.items()]:
        v2t, c2 = v2col.split(".")
        v1t, c1 = v1col.split(".")
        k1, k2, frm = _TS_KEYS[v2t]
        src = _rows(v1, f"SELECT {', '.join(f'`{k}`' for k in k1)}, `{c1}` AS v FROM `{v1t}`")
        assert src, v1col
        flag = vc.TS_PLAIN_FLAGS.get(v2col)
        sel = f"SELECT {', '.join(f'{k} AS k{i}' for i, k in enumerate(k2))}, t.`{c2}` AS v" \
              + (f", t.`{flag}` AS plain" if flag else "") + f" FROM {frm}"
        back = []
        for r in _rows(v2, sel):
            plain = r.pop("plain", 0)
            r["v"] = vc.render_ts_mixed(r["v"], plain) if flag else vc.render_ts(fmt, r["v"])
            back.append(r)
        assert _pairs(back) == _pairs(src), v2col
        checked += 1
    assert checked == len(vc.TS_COLUMNS) + len(vc.DATE_COLUMNS)

    # no UTC / IST shift: the stored DATETIME is the wall time the v1 string spelled
    assert _rows(v2, "SELECT created_at FROM page_visit WHERE id = 1") == \
        [{"created_at": "2026-09-02 01:16:50.901683"}]
    assert _rows(v2, "SELECT created_at FROM extraction_log WHERE id = 1") == \
        [{"created_at": "2026-06-07 22:15:11.000000"}]
    # the plain flags of the mixed columns
    assert [(r["id"], r["created_at_plain"]) for r in
            _rows(v2, "SELECT id, created_at_plain FROM bf_benchmark_external_bf ORDER BY id")] == \
        [(1, 0), (2, 1), (3, 0)]
    for col in vc.TS_COLUMNS:
        assert vc.tz_was_utc(col) == (vc.TS_COLUMNS[col][1] == vc.ISO_UTC)


def test_timestamp_codec_rules():
    # isoformat() drops '.ffffff' at microsecond 0, and render_ts does the same
    for fmt, s in ((vc.ISO_LOCAL, "2026-08-23T09:41:58"), (vc.ISO_LOCAL, "2026-08-23T09:41:58.000001"),
                   (vc.ISO_UTC, "2026-08-23T09:41:58+00:00"), (vc.ISO_UTC, "2026-08-23T09:41:58.500000+00:00"),
                   (vc.ISO_SECONDS, "2026-09-23T13:41:31"), (vc.SQL_SECONDS, "2026-06-07 22:15:11")):
        dt = vc.parse_ts(fmt, s)
        assert vc.render_ts(fmt, dt) == s
        assert vc.render_ts(fmt, str(dt)) == s                # MySQL text form
    # strings no writer produces are refused, never silently changed
    for fmt, s in ((vc.ISO_LOCAL, "2026-08-23T09:41:58.000000"), (vc.ISO_UTC, "2026-08-23T09:41:58+05:30"),
                   (vc.ISO_UTC, "2026-08-23T09:41:58"), (vc.SQL_SECONDS, "2026-08-23T09:41:58"),
                   (vc.ISO_SECONDS, "2026-08-23T09:41:58.1"), (vc.DATE, ""), (vc.DATE, "20260801")):
        with pytest.raises(vc.CodecError):
            vc.parse_ts(fmt, s)


# ── loud failures and verbatim copies ───────────────────────────────────────

def test_month_outside_cal_month_fails_loudly(dbs):
    v1, v2 = dbs
    before = _rows(v2, "SELECT COUNT(*) AS n FROM production_monthly")
    conn = _connect(v1)
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO production_table VALUES ('2041-01', 'BSP', 'Crude Steel', 1)")
        with pytest.raises(mig.MigrationError) as e:
            mig.migrate(v1, v2, src_cfg=_cfg(), dst_cfg=_cfg())
        assert "production_table" in str(e.value) and "2041-01" in str(e.value)
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM production_table WHERE report_month = '2041-01'")
        conn.close()
    # validation runs before anything is written: dst is untouched
    assert _rows(v2, "SELECT COUNT(*) AS n FROM production_monthly") == before


def test_verbatim_copies(dbs):
    v1, v2 = dbs
    # page_data byte for byte
    assert _rows(v2, "SELECT report_month, page_number, page_data FROM page_config") == \
        _rows(v1, "SELECT report_month, page_number, page_data FROM page_configs")
    # dangling capital_repair_id kept
    assert _rows(v2, "SELECT id, capital_repair_id FROM breakdown ORDER BY id") == \
        [{"id": 1, "capital_repair_id": 999}, {"id": 2, "capital_repair_id": 5}]
    # extraction_log keeps its free plant / month labels
    assert {(r["plant_name"], r["report_month"]) for r in
            _rows(v2, "SELECT plant_name, report_month FROM extraction_log")} == \
        {("TESTPLANT", "2099-01"), ("BSP_BF", "2026-04")}
    # capital repair without a unit -> unit_id NULL; unit_type kept per row
    assert _rows(v2, "SELECT id, unit_id IS NULL AS no_unit, unit_type FROM capital_repair ORDER BY id") == \
        [{"id": 5, "no_unit": 0, "unit_type": "BF"}, {"id": 6, "no_unit": 1, "unit_type": None}]
    assert _rows(v2, "SELECT n FROM data_version") == [{"n": 7}]
