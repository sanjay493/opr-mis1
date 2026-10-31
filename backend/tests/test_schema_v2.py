"""Task 5: the v2 schema DDL (backend/scripts/v2/schema_v2.sql + seed_cal_month.sql).

Applied to a throwaway `mis_reports_test_v2_<pid>` schema (conftest
`mysql_v2_db`), then checked through information_schema. Also checks the
v1 -> v2 table map at the top of schema_v2.sql against the exact v1 DDL
(tests/fixtures/schema_v1.sql), which Task 6's migration consumes.
"""
import json
import re
from datetime import date
from pathlib import Path

import pymysql
import pytest

BACKEND = Path(__file__).resolve().parents[1]
SCHEMA_V2_DIR = BACKEND / "scripts" / "v2"

SCHEMA_V2 = SCHEMA_V2_DIR / "schema_v2.sql"
SCHEMA_V1 = Path(__file__).resolve().parent / "fixtures" / "schema_v1.sql"

PLANT_COLUMNS = ("plant_code", "from_plant_code", "to_plant_code")
# v2 tables that are not the target of any v1 table: the new dimensions
# seeded from v1 values (plant from every plant column) or generated.
NEW_DIMENSIONS = {"plant", "cal_month", "unique_activity", "unique_activity_tag", "production_op_monthly",
                  "rmt_month", "rmt_plan_note", "rmt_ipt_row", "rmt_stock_row"}
JSON_ARCHIVES = {"production_data_json", "production_plan_json", "stock_data_json",
                 "ipt_data_json", "special_steel_json"}


def _rows(conn, sql, args=None):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def _v2_tables_in_file():
    return re.findall(r"^CREATE TABLE `?(\w+)`?", SCHEMA_V2.read_text(encoding="utf-8"), re.M)


def _v1_tables():
    return re.findall(r"^CREATE TABLE `(\w+)`", SCHEMA_V1.read_text(encoding="utf-8"), re.M)


def _table_map():
    """{v1 table: [v2 targets] or ['DROPPED']} from the V1-TABLE-MAP block."""
    text = SCHEMA_V2.read_text(encoding="utf-8")
    block = re.search(r"^-- V1-TABLE-MAP BEGIN\n(.*?)^-- V1-TABLE-MAP END", text, re.M | re.S)
    assert block, "schema_v2.sql has no V1-TABLE-MAP block"
    out = {}
    for line in block.group(1).splitlines():
        m = re.match(r"^--\s+(\w+)\s+->\s+([^|]+?)\s*(\|.*)?$", line)
        if not m:
            continue
        v1, targets = m.group(1), [t.strip() for t in m.group(2).split(",")]
        assert v1 not in out, f"{v1} is mapped twice"
        out[v1] = targets
    return out


def _db_tables(conn):
    return {r[0] for r in _rows(conn, "SELECT table_name FROM information_schema.tables "
                                      "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'")}


# ── the DDL applies and is well-formed ───────────────────────────────────────

def test_schema_v2_applies_cleanly(mysql_v2_db):
    in_file = _v2_tables_in_file()
    assert len(in_file) == len(set(in_file)), "a table is created twice"
    assert _db_tables(mysql_v2_db) == set(in_file)
    # every table is InnoDB with the schema's charset / default collation
    bad = _rows(mysql_v2_db, "SELECT table_name, engine, table_collation FROM information_schema.tables "
                             "WHERE table_schema = DATABASE() AND (engine <> 'InnoDB' "
                             "OR table_collation <> 'utf8mb4_0900_ai_ci')")
    assert bad == ()


def test_every_table_has_pk(mysql_v2_db):
    with_pk = {r[0] for r in _rows(mysql_v2_db, "SELECT table_name FROM information_schema.table_constraints "
                                                "WHERE table_schema = DATABASE() AND constraint_type = 'PRIMARY KEY'")}
    assert _db_tables(mysql_v2_db) - with_pk == set()


def _fk_targets(conn):
    """{(table, column): {(referenced_table, referenced_column), ...}} for every
    FK column (a column can be in several FKs, e.g. plant_code in the plant FK
    and in the composite (plant_code, unit_id) unit FK)."""
    out = {}
    for t, c, rt, rc in _rows(conn, "SELECT table_name, column_name, referenced_table_name, referenced_column_name "
                                    "FROM information_schema.key_column_usage "
                                    "WHERE table_schema = DATABASE() AND referenced_table_name IS NOT NULL"):
        out.setdefault((t, c), set()).add((rt, rc))
    return out


def _columns_named(conn, names):
    ph = ",".join(["%s"] * len(names))
    return {(t, c) for t, c in _rows(conn, f"SELECT table_name, column_name FROM information_schema.columns "
                                           f"WHERE table_schema = DATABASE() AND column_name IN ({ph})", names)}


def test_plant_columns_have_fk(mysql_v2_db):
    fks = _fk_targets(mysql_v2_db)
    cols = _columns_named(mysql_v2_db, PLANT_COLUMNS) - {("plant", "plant_code")}
    assert len(cols) >= 25, cols  # sanity: the facts and masters all carry a plant (29 today)
    missing = sorted(col for col in cols if ("plant", "plant_code") not in fks.get(col, ()))
    assert missing == []


def test_item_and_unit_columns_have_fk(mysql_v2_db):
    fks = _fk_targets(mysql_v2_db)
    items = _columns_named(mysql_v2_db, ("item_id",)) - {("item", "item_id")}
    units = _columns_named(mysql_v2_db, ("unit_id",)) - {("plant_unit", "unit_id")}
    assert items and units
    assert sorted(c for c in items if ("item", "item_id") not in fks.get(c, ())) == []
    # unit_id is plant-scoped: every unit_id references plant_unit together with
    # its plant_code (composite FK), so a row cannot pair a plant with another plant's unit
    assert sorted(c for c in units if ("plant_unit", "unit_id") not in fks.get(c, ())) == []
    assert sorted((t, "plant_code") for t, _ in units
                  if ("plant_unit", "plant_code") not in fks.get((t, "plant_code"), ())) == []


def test_no_varchar_timestamps(mysql_v2_db):
    cols = _rows(mysql_v2_db, r"SELECT table_name, column_name, data_type FROM information_schema.columns "
                              r"WHERE table_schema = DATABASE() "
                              r"AND (column_name LIKE '%\_at' OR column_name = 'timestamp')")
    assert len(cols) >= 20
    assert sorted((t, c, d) for t, c, d in cols if d != "datetime") == []


def test_production_indexes_serve_item_month_and_month_plant(mysql_v2_db):
    """CARRY TO T7: production reads by (item, month) and by (month, plant)
    each have an index whose leading columns match."""
    idx = {}
    for name, seq, col in _rows(mysql_v2_db, "SELECT index_name, seq_in_index, column_name FROM information_schema.statistics "
                                             "WHERE table_schema = DATABASE() AND table_name = 'production_monthly' "
                                             "ORDER BY index_name, seq_in_index"):
        idx.setdefault(name, []).append(col)
    leads = {tuple(cols[:2]) for cols in idx.values()}
    assert ("item_id", "report_month") in leads
    assert ("report_month", "plant_code") in leads
    assert idx["PRIMARY"] == ["report_month", "plant_code", "item_id"]


# ── v1 -> v2 table map ───────────────────────────────────────────────────────

def test_every_v1_table_is_mapped():
    v1 = set(_v1_tables()) | {"data_version"}
    assert len(v1) == 72  # the 71 tables of the v1 dump + Task 4's data_version
    mapping = _table_map()
    assert set(mapping) == v1
    v2 = set(_v2_tables_in_file())
    dropped = {t for t, targets in mapping.items() if targets == ["DROPPED"]}
    assert dropped == JSON_ARCHIVES
    targets = {t for ts in mapping.values() for t in ts if ts != ["DROPPED"]}
    assert targets - v2 == set(), "map names a v2 table the DDL does not create"
    assert v2 - targets - NEW_DIMENSIONS == set(), "a v2 table no v1 table maps to"


# ── seed_cal_month.sql ───────────────────────────────────────────────────────

def _expected_cal_row(year, month):
    fy_start = year if month >= 4 else year - 1
    fy_month = (month - 4) % 12 + 1
    return (f"{year:04d}-{month:02d}", date(year, month, 1),
            f"{fy_start}-{(fy_start + 1) % 100:02d}", fy_month, (fy_month - 1) // 3 + 1, (fy_month - 1) // 6 + 1)


def test_cal_month_seed(mysql_v2_db):
    rows = _rows(mysql_v2_db, "SELECT report_month, month_start, fy, fy_month, quarter, half "
                              "FROM cal_month ORDER BY report_month")
    assert len(rows) == 80 * 12
    assert rows[0][0] == "1960-04" and rows[-1][0] == "2040-03"
    expected = [_expected_cal_row(y, m) for y in range(1960, 2041) for m in range(1, 13)
                if "1960-04" <= f"{y:04d}-{m:02d}" <= "2040-03"]
    assert list(rows) == expected
    known = {r[0]: r[2:] for r in rows}
    assert known["2026-08"] == ("2026-27", 5, 2, 1)
    assert known["2027-03"] == ("2026-27", 12, 4, 2)
    assert known["2026-04"] == ("2026-27", 1, 1, 1)
    assert known["2026-10"] == ("2026-27", 7, 3, 2)
    assert known["2000-01"] == ("1999-00", 10, 4, 2)


# ── behaviour the design decisions rely on ──────────────────────────────────

@pytest.fixture
def tx(mysql_v2_db):
    """Run a test's writes in a transaction that is always rolled back."""
    mysql_v2_db.begin()
    try:
        yield mysql_v2_db
    finally:
        mysql_v2_db.rollback()


def _seed_plants(cur, *codes):
    cur.executemany("INSERT INTO plant (plant_code, plant_kind) VALUES (%s, 'integrated')", [(c,) for c in codes])


def test_masters_keep_every_spelling_verbatim(tx):
    """Review Focus #4: the masters record the stored strings, they do not
    clean them. Case variants of an item are distinct items (utf8mb4_0900_bin)."""
    names = ["Crude Steel", "Total Crude Steel", "CC BILLET", "CC Billet", "Billet Caster",
             "BILLET Caster", "BF#1", "BF-1", "Oven Pushing (nos/day)", "Oven Pushing(nos/d)"]
    with tx.cursor() as cur:
        _seed_plants(cur, "SSP", "SSPs", "BSP", "VISL", "VISP")
        cur.executemany("INSERT INTO item (item_name) VALUES (%s)", [(n,) for n in names])
        cur.execute("SELECT item_name FROM item ORDER BY item_id")
        assert [r[0] for r in cur.fetchall()] == names
        cur.execute("SELECT plant_code FROM plant ORDER BY plant_code")
        assert [r[0] for r in cur.fetchall()] == ["BSP", "SSP", "SSPs", "VISL", "VISP"]
        cur.executemany("INSERT INTO plant_unit (plant_code, unit_code) VALUES ('BSP', %s)",
                        [("BF#1",), ("BF-1",), ("Billet Casters (M/c-1 & M/c-2)",)])
        cur.execute("SELECT unit_code FROM plant_unit WHERE plant_code = 'BSP' ORDER BY unit_id")
        assert [r[0] for r in cur.fetchall()] == ["BF#1", "BF-1", "Billet Casters (M/c-1 & M/c-2)"]
        # the same spelling twice is still rejected
        with pytest.raises(pymysql.err.IntegrityError):
            cur.execute("INSERT INTO item (item_name) VALUES ('CC Billet')")


def test_production_value_needs_its_has_flag(tx):
    """has_* keeps "no v1 row" apart from "a v1 row holding NULL"."""
    with tx.cursor() as cur:
        _seed_plants(cur, "BSP")
        cur.execute("INSERT INTO item (item_name) VALUES ('Hot Metal')")
        item_id = cur.lastrowid
        cur.execute("INSERT INTO production_monthly (report_month, plant_code, item_id, actual, has_actual) "
                    "VALUES ('2026-08', 'BSP', %s, NULL, 1)", (item_id,))  # a v1 row holding NULL
        with pytest.raises(pymysql.err.OperationalError):  # CHECK: a value without its flag
            cur.execute("INSERT INTO production_monthly (report_month, plant_code, item_id, abp_plan) "
                        "VALUES ('2026-09', 'BSP', %s, 5)", (item_id,))
        with pytest.raises(pymysql.err.OperationalError):  # CHECK: a row with no source at all
            cur.execute("INSERT INTO production_monthly (report_month, plant_code, item_id) "
                        "VALUES ('2026-10', 'BSP', %s)", (item_id,))
        with pytest.raises(pymysql.err.IntegrityError):  # FK: month outside cal_month
            cur.execute("INSERT INTO production_monthly (report_month, plant_code, item_id, actual, has_actual) "
                        "VALUES ('2099-01', 'BSP', %s, 1, 1)", (item_id,))


def test_techno_value_is_number_or_raw(tx):
    with tx.cursor() as cur:
        _seed_plants(cur, "BSP")
        cur.execute("INSERT INTO plant_unit (plant_code, unit_code) VALUES ('BSP', 'BF-1')")
        unit_id = cur.lastrowid
        cur.execute("INSERT INTO techno_upload (report_month, plant_code, unit_id, has_month, has_till_month) "
                    "VALUES ('2026-08', 'BSP', %s, 1, 0)", (unit_id,))
        ins = ("INSERT INTO techno_value (report_month, plant_code, unit_id, period, param_key, num, is_int, raw) "
               "VALUES ('2026-08', 'BSP', %s, 'month', %s, %s, %s, %s)")
        cur.execute(ins, (unit_id, "coke_rate", 5, 1, None))
        cur.execute(ins, (unit_id, "Coke_Rate", 5.5, 0, None))  # JSON keys are case-sensitive
        cur.execute(ins, (unit_id, "remark", None, 0, '"n/a"'))
        cur.execute(ins, (unit_id, "blank", None, 0, "null"))  # an explicit JSON null
        cur.execute("SELECT param_key, raw IS NULL, raw FROM techno_value ORDER BY param_key")
        # (binary collation: upper case sorts first)
        assert cur.fetchall() == (("Coke_Rate", 1, None), ("blank", 0, "null"), ("coke_rate", 1, None),
                                  ("remark", 0, '"n/a"'))
        for bad in ((unit_id, "both", 1, 0, '"x"'), (unit_id, "neither", None, 0, None),
                    (unit_id, "int_str", None, 1, '"x"')):
            with pytest.raises(pymysql.err.OperationalError):
                cur.execute(ins, bad)
        # values belong to an upload row (FK), and go with it
        cur.execute("DELETE FROM techno_upload WHERE plant_code = 'BSP'")
        cur.execute("SELECT COUNT(*) FROM techno_value")
        assert cur.fetchone()[0] == 0


def test_unit_case_variants_and_upload_seq(tx):
    """Task 7c fix round 1: plant_unit.unit_code is binary (each case variant
    its own unit, as v1 stored per row); techno_upload.seq keeps v1's id and
    continues as AUTO_INCREMENT, unchanged by an upsert."""
    with tx.cursor() as cur:
        _seed_plants(cur, "BSP")
        cur.executemany("INSERT INTO plant_unit (plant_code, unit_code) VALUES ('BSP', %s)",
                        [("BF_Shop",), ("bf_shop",)])
        cur.execute("SELECT unit_code FROM plant_unit WHERE plant_code = 'BSP' "
                    "AND unit_code COLLATE utf8mb4_0900_ai_ci = 'BF_SHOP' ORDER BY unit_id")
        ids_names = cur.fetchall()
        assert [r[0] for r in ids_names] == ["BF_Shop", "bf_shop"]
        with pytest.raises(pymysql.err.IntegrityError):
            cur.execute("INSERT INTO plant_unit (plant_code, unit_code) VALUES ('BSP', 'bf_shop')")
        cur.execute("SELECT unit_id FROM plant_unit WHERE plant_code = 'BSP' ORDER BY unit_id")
        u1, u2 = [r[0] for r in cur.fetchall()]
        up = ("INSERT INTO techno_upload (report_month, plant_code, unit_id{}) VALUES ('2026-08', 'BSP', %s{}) "
              "AS new ON DUPLICATE KEY UPDATE source_file = 'again'")
        cur.execute(up.format(", seq", ", %s"), (u1, 22167))         # the migration: v1's id
        cur.execute(up.format("", ""), (u2,))                       # a new row: the next value
        cur.execute(up.format("", ""), (u1,))                       # an upsert keeps its seq
        cur.execute("SELECT unit_id, seq, source_file FROM techno_upload ORDER BY seq")
        rows = [tuple(r) for r in cur.fetchall()]
        assert rows[0] == (u1, 22167, "again") and rows[1][0] == u2 and rows[1][1] > 22167
        with pytest.raises(pymysql.err.IntegrityError):
            cur.execute("UPDATE techno_upload SET seq = 22167 WHERE unit_id = %s", (u2,))


def test_report_text_key_is_unique_without_plant_or_item(tx):
    """NULL plant_code / item_id must not let the same text block be stored twice."""
    with tx.cursor() as cur:
        ins = ("INSERT INTO report_text (scope, period, block_key, text) "
               "VALUES ('page3_narrative', '2026-08', 'highlights', %s)")
        cur.execute(ins, ("first",))
        with pytest.raises(pymysql.err.IntegrityError):
            cur.execute(ins, ("second",))
        _seed_plants(cur, "BSP", "DSP")
        board = ("INSERT INTO report_text (scope, period, block_key, plant_code, text) "
                 "VALUES ('board_note', '2026-27:Q1', 'why_narrative', %s, 'x')")
        cur.execute(board, ("BSP",))
        cur.execute(board, ("DSP",))
        with pytest.raises(pymysql.err.IntegrityError):
            cur.execute(board, ("BSP",))


def test_report_month_columns_reference_cal_month(mysql_v2_db):
    """Every report_month is an FK to cal_month, except the extraction log
    (a deliberate non-FK: v1 holds '2099-01' there)."""
    fks = _fk_targets(mysql_v2_db)
    cols = _columns_named(mysql_v2_db, ("report_month",)) - {("cal_month", "report_month")}
    assert len(cols) >= 20
    missing = sorted(c for c in cols if ("cal_month", "report_month") not in fks.get(c, ()))
    assert missing == [("extraction_log", "report_month")]


def test_page_config_rejects_invalid_json(tx):
    with tx.cursor() as cur:
        cur.execute("INSERT INTO page_config (report_month, page_number, page_data) "
                    "VALUES ('2026-08', 1, %s)", ('{"b": 1, "a": [1.0, 2]}',))
        cur.execute("SELECT page_data FROM page_config WHERE page_number = 1")
        assert cur.fetchone()[0] == '{"b": 1, "a": [1.0, 2]}'  # text kept as written
        with pytest.raises(pymysql.err.OperationalError):  # CHECK ck_page_config_json
            cur.execute("INSERT INTO page_config (report_month, page_number, page_data) "
                        "VALUES ('2026-08', 2, '{not json')")


def test_deleting_capital_repair_leaves_breakdown_link(tx):
    """breakdown.capital_repair_id is a deliberate non-FK: as in v1, deleting
    the linked capital repair leaves the id in place (no block, no SET NULL)."""
    with tx.cursor() as cur:
        _seed_plants(cur, "BSP")
        cur.execute("INSERT INTO plant_unit (plant_code, unit_code) VALUES ('BSP', 'BF-4')")
        unit_id = cur.lastrowid
        cur.execute("INSERT INTO capital_repair (plant_code, fy, unit_id) VALUES ('BSP', '2026-27', %s)",
                    (unit_id,))
        cr_id = cur.lastrowid
        cur.execute("INSERT INTO breakdown (plant_code, unit_type, unit_id, start_ts, cause, capital_repair_id) "
                    "VALUES ('BSP', 'BF', %s, '2026-08-02', 'relining', %s)", (unit_id, cr_id))
        bd_id = cur.lastrowid
        cur.execute("DELETE FROM capital_repair WHERE id = %s", (cr_id,))
        cur.execute("SELECT capital_repair_id FROM breakdown WHERE id = %s", (bd_id,))
        assert cur.fetchone()[0] == cr_id


def test_techno_key_order_rule_matches_mysql_json(tx):
    """The documented rebuild order (period, LENGTH(param_key), param_key on the
    _bin column) is the key order MySQL's JSON type gave the v1 blobs."""
    keys = ["coke_rate", "Coke_Rate", "a", "B", "zz", "hm_prod", "b", "average_volatile_matter_in_coal_blend"]
    with tx.cursor() as cur:
        cur.execute("SELECT JSON_KEYS(CAST(%s AS JSON))", (json.dumps({k: 1 for k in keys}),))
        mysql_order = json.loads(cur.fetchone()[0])
        _seed_plants(cur, "BSP")
        cur.execute("INSERT INTO plant_unit (plant_code, unit_code) VALUES ('BSP', 'SP-1')")
        unit_id = cur.lastrowid
        cur.execute("INSERT INTO techno_upload (report_month, plant_code, unit_id) VALUES ('2026-08', 'BSP', %s)",
                    (unit_id,))
        cur.executemany("INSERT INTO techno_value (report_month, plant_code, unit_id, period, param_key, num) "
                        "VALUES ('2026-08', 'BSP', %s, %s, %s, 1)",
                        [(unit_id, p, k) for k in keys for p in ("till_month", "month")])
        cur.execute("SELECT period, param_key FROM techno_value "
                    "ORDER BY period, LENGTH(param_key), param_key")
        rows = cur.fetchall()
    assert [k for p, k in rows if p == "month"] == mysql_order
    assert [p for p, _ in rows] == ["month"] * len(keys) + ["till_month"] * len(keys)
