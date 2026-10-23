"""Task 6b: tools/verify_v2.py.

The 6a v1 fixture is loaded into the session's v1 test schema and migrated
once into the session's v2 test schema. verify() must return [] on that
clean pair, and each injected corruption of the v2 side (applied with
FOREIGN_KEY_CHECKS=0, as a careless load could, then undone) must produce a
specific message. The v2 schema is emptied again at the end of the module.
"""
import re
from contextlib import contextmanager

import pytest

import test_migrate_v1_to_v2 as m6a
from repo import v2codec as vc
from tools import migrate_v1_to_v2 as mig
from tools import verify_v2 as ver

pytestmark = pytest.mark.filterwarnings("ignore::Warning")


@pytest.fixture(scope="module")
def dbs(_mysql_v1_schema, mysql_v2_db):
    v1 = _mysql_v1_schema
    with mysql_v2_db.cursor() as cur:
        cur.execute("SELECT DATABASE()")
        v2 = cur.fetchone()[0]
    assert v1.startswith("mis_reports_test_") and v2.startswith("mis_reports_test_v2_")
    m6a._load_v1(v1)
    mig.migrate(v1, v2, src_cfg=m6a._cfg(), dst_cfg=m6a._cfg())
    try:
        yield v1, v2
    finally:
        mig.clear_dst(v2, dst_cfg=m6a._cfg())


def _verify(dbs):
    v1, v2 = dbs
    return ver.verify(v1, v2, src_cfg=m6a._cfg(), dst_cfg=m6a._cfg())


@contextmanager
def _corrupt(db, do, undo):
    """Run `do` on db with FK checks off (as a careless load might), yield,
    then run `undo`."""
    conn = m6a._connect(db)
    try:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            for sql in do:
                cur.execute(sql)
                assert cur.rowcount == 1, sql
        yield
    finally:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            for sql in undo:
                cur.execute(sql)
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.close()


def _has(problems, pattern):
    rx = re.compile(pattern)
    assert any(rx.search(p) for p in problems), f"no problem matching {pattern!r} in:\n" + "\n".join(problems)


# ── clean ───────────────────────────────────────────────────────────────────

def test_clean_migration_verifies(dbs):
    report = {}
    v1, v2 = dbs
    assert ver.verify(v1, v2, src_cfg=m6a._cfg(), dst_cfg=m6a._cfg(), report=report) == []
    # it really looked: counts for the merged / split tables
    counts = report["counts"]
    assert counts["production_monthly"] == (10, 10)     # union of 7 + 3 + 2 keys
    assert counts["techno_upload"] == (4, 4)
    assert counts["report_text"][0] == counts["report_text"][1] > 0
    assert report["fk_checked"] > 40
    assert report["json_checked"] >= 7


# ── corruptions: each gives a specific message ─────────────────────────────

_PROD_BSP_CS = ("report_month = '2026-04' AND plant_code = 'BSP' AND item_id = "
                "(SELECT item_id FROM item WHERE item_name = 'Crude Steel')")


def test_changed_value(dbs):
    v1, v2 = dbs
    with _corrupt(v2, [f"UPDATE production_monthly SET actual = 100.75 WHERE {_PROD_BSP_CS}"],
                  [f"UPDATE production_monthly SET actual = 100.5 WHERE {_PROD_BSP_CS}"]):
        problems = _verify(dbs)
    _has(problems, r"production_table: row \('2026-04', 'BSP', 'Crude Steel'\) month_actual: "
                   r"v1 100\.5 != v2 100\.75")
    _has(problems, r"SUM production_monthly\.actual .*\('2026-04', 'BSP'\)")
    assert _verify(dbs) == []


def test_deleted_row(dbs):
    v1, v2 = dbs
    row = m6a._rows(v2, "SELECT * FROM activity_log WHERE id = 2")[0]
    cols = ", ".join(f"`{c}`" for c in row)
    with _corrupt(v2, ["DELETE FROM activity_log WHERE id = 2"], []):
        problems = _verify(dbs)
        conn = m6a._connect(v2)
        with conn.cursor() as cur:
            cur.execute(f"INSERT INTO activity_log ({cols}) VALUES ({', '.join(['%s'] * len(row))})",
                        list(row.values()))
        conn.close()
    _has(problems, r"activity_log -> activity_log: row \(2,\) missing in v2")
    _has(problems, r"row count activity_log: v1 2 != v2 1")
    assert _verify(dbs) == []


def test_flipped_has_flag(dbs):
    """has_mou 0 -> 1 on a row whose mou_plan is NULL: a v1 'no row' turns
    into a v1 'row holding NULL' (Review Focus #2)."""
    v1, v2 = dbs
    where = ("report_month = '2026-04' AND plant_code = 'BSP' AND item_id = "
             "(SELECT item_id FROM item WHERE item_name = 'Hot Metal')")
    with _corrupt(v2, [f"UPDATE production_monthly SET has_mou = 1 WHERE {where}"],
                  [f"UPDATE production_monthly SET has_mou = 0 WHERE {where}"]):
        problems = _verify(dbs)
    _has(problems, r"mou_plan_table: row \('2026-04', 'BSP', 'Hot Metal'\) in v2 has no v1 row")
    assert _verify(dbs) == []


def test_techno_leaf_type(dbs):
    v1, v2 = dbs
    where = "param_key = 'Coke Rate' AND period = 'month'"
    with _corrupt(v2, [f"UPDATE techno_value SET is_int = 0 WHERE {where}"],
                  [f"UPDATE techno_value SET is_int = 1 WHERE {where}"]):
        problems = _verify(dbs)
    _has(problems, r"techno_data \('BSP', '2026-04', 'BF-1'\): \$\.month\.Coke Rate: type v1 int != v2 float")
    assert _verify(dbs) == []


def test_techno_seq_is_the_v1_id(dbs):
    """techno_upload.seq carries v1 techno_data.id (insertion order, MAX(id))."""
    v1, v2 = dbs
    where = "plant_code = 'BSP' AND report_month = '2026-04'"
    with _corrupt(v2, [f"UPDATE techno_upload SET seq = seq + 1000 WHERE {where}"],
                  [f"UPDATE techno_upload SET seq = seq - 1000 WHERE {where}"]):
        problems = _verify(dbs)
    _has(problems, r"techno_data \('BSP', '2026-04', 'BF-1'\): id v1 \d+ != v2 seq \d+")
    assert _verify(dbs) == []


def test_techno_ai_ci_duplicate_unit(dbs):
    """plant_unit.unit_code is binary; v1's uq_techno was ai_ci, so a (month,
    plant) holding 'BF-1' and 'bf-1' is reported."""
    v1, v2 = dbs
    with _corrupt(v2, ["INSERT INTO plant_unit (plant_code, unit_code) VALUES ('BSP', 'bf-1')",
                       "INSERT INTO techno_upload (report_month, plant_code, unit_id) SELECT '2026-04', 'BSP', "
                       "unit_id FROM plant_unit WHERE plant_code = 'BSP' AND unit_code = 'bf-1'"],
                  ["DELETE u FROM techno_upload u JOIN plant_unit pu USING (unit_id) WHERE pu.unit_code = 'bf-1'",
                   "DELETE FROM plant_unit WHERE unit_code = 'bf-1'"]):
        problems = _verify(dbs)
    _has(problems, r"techno_upload \('BSP', '2026-04'\): ai_ci-duplicate units BF-1 \| bf-1")
    assert _verify(dbs) == []


def test_techno_leaf_value_hidden_by_decode(dbs):
    """is_int=1 with a fractional num decodes as int(num), equal to v1's 450:
    the decode cannot see it, the canonical-form and SUM checks do. (A raw
    leaf with a num is already refused by ck_techno_value_one_form.)"""
    v1, v2 = dbs
    where = "param_key = 'Coke Rate' AND period = 'month'"
    with _corrupt(v2, [f"UPDATE techno_value SET num = 450.5 WHERE {where}"],
                  [f"UPDATE techno_value SET num = 450 WHERE {where}"]):
        problems = _verify(dbs)
    assert not any("$.month.Coke Rate" in p for p in problems)
    _has(problems, r"techno_value \('BSP', '2026-04', 'BF-1'\) month\.'Coke Rate': is_int=1 but num 450\.5")
    _has(problems, r"SUM techno_value\.num at \('2026-04', 'BSP'\)")
    assert _verify(dbs) == []


def test_orphan(dbs):
    v1, v2 = dbs
    where = "plant_code = 'DSP' AND pdf_label = 'Billet caster (t)'"
    item = m6a._rows(v2, f"SELECT item_id FROM pdf_item_alias WHERE {where}")[0]["item_id"]
    with _corrupt(v2, [f"UPDATE pdf_item_alias SET item_id = 9999 WHERE {where}"],
                  [f"UPDATE pdf_item_alias SET item_id = {item} WHERE {where}"]):
        problems = _verify(dbs)
    _has(problems, r"FK fk_pdf_item_alias_item: 1 orphan row\(s\) in pdf_item_alias\(item_id\) -> item\(item_id\)")
    assert _verify(dbs) == []


def test_timestamp_off_by_one_second(dbs):
    v1, v2 = dbs
    with _corrupt(v2, ["UPDATE activity_log SET created_at = created_at + INTERVAL 1 SECOND WHERE id = 1"],
                  ["UPDATE activity_log SET created_at = created_at - INTERVAL 1 SECOND WHERE id = 1"]):
        problems = _verify(dbs)
    _has(problems, r"activity_log -> activity_log: row \(1,\) timestamp: "
                   r"v1 '2026-09-09T05:58:59\.243471\+00:00' != v2 '2026-09-09T05:59:00\.243471\+00:00'")
    assert _verify(dbs) == []


def test_text_and_page_data(dbs):
    v1, v2 = dbs
    with _corrupt(v2, ["UPDATE report_text SET text = 'n2!' WHERE scope = 'rail_note' AND seq = 2",
                       "UPDATE page_config SET page_data = CONCAT(page_data, ' ') "
                       "WHERE report_month = '2026-04' AND page_number = 3"],
                  ["UPDATE report_text SET text = 'n2' WHERE scope = 'rail_note' AND seq = 2",
                   "UPDATE page_config SET page_data = LEFT(page_data, CHAR_LENGTH(page_data) - 1) "
                   "WHERE report_month = '2026-04' AND page_number = 3"]):
        problems = _verify(dbs)
    _has(problems, r"rail_prod_despatch_note: row \(2,\) note_text: v1 'n2' != v2 'n2!'")
    _has(problems, r"page_configs -> page_config: row \('2026-04', 3\) page_data")
    assert _verify(dbs) == []


def test_wide_text_stamp_split(dbs):
    """A wide v1 row is several report_text rows that must share one stamp;
    the decoder reads only one of them, so a split stamp is checked apart."""
    v1, v2 = dbs
    where = "scope = 'key_highlights' AND block_key = 'shortfalls'"
    with _corrupt(v2, [f"UPDATE report_text SET updated_at = updated_at + INTERVAL 1 SECOND WHERE {where}"],
                  [f"UPDATE report_text SET updated_at = updated_at - INTERVAL 1 SECOND WHERE {where}"]):
        problems = _verify(dbs)
    _has(problems, r"report_text key_highlights")
    assert _verify(dbs) == []


# ── independence from migrate's own maps (fix round 1) ─────────────────────

_KEYWORDS = {"PRIMARY", "CONSTRAINT", "KEY", "UNIQUE", "INDEX", "FOREIGN", "CHECK", "FULLTEXT"}


def _ddl_columns(path):
    """{table: {column}} parsed from a CREATE TABLE dump (v1 or v2)."""
    from pathlib import Path
    text = Path(path).read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"CREATE TABLE `?(\w+)`? \((.*?)\n\)", text, re.S):
        cols = set()
        for line in m.group(2).splitlines():
            c = re.match(r"\s+`?(\w+)`?\s+[A-Za-z]", line)
            if c and c.group(1).upper() not in _KEYWORDS:
                cols.add(c.group(1))
        out[m.group(1)] = cols
    return out


def test_map_matches_hand_written_oracle():
    from pathlib import Path
    tests = Path(__file__).resolve().parent
    v1 = _ddl_columns(tests / "fixtures" / "schema_v1.sql")
    v2 = _ddl_columns(tests.parent / "scripts" / "v2" / "schema_v2.sql")
    assert len(ver.EXPECTED_RENAMES) == 46
    # the oracle names real columns of both schemas
    v2_of = {v1t: v2t for v1t, v2t, _ in mig.SIMPLE}
    for (v1t, c1), c2 in ver.EXPECTED_RENAMES.items():
        assert c1 in v1[v1t], (v1t, c1)
        assert c2 in v2[v2_of[v1t]], (v2_of[v1t], c2)
    # every SIMPLE column is same-named or an expected rename; both directions
    seen = set()
    for v1t, v2t, spec in mig.SIMPLE:
        for c2, c1, _ in spec:
            assert c1 in v1[v1t] and c2 in v2[v2t], (v1t, c1, v2t, c2)
            if c1 != c2:
                assert ver.EXPECTED_RENAMES.get((v1t, c1)) == c2, (v1t, c1, c2)
                seen.add((v1t, c1))
    assert seen == set(ver.EXPECTED_RENAMES)
    assert ver.map_problems() == []
    # literal production and text maps
    assert vc.PRODUCTION_SOURCES == {"production_table": ("actual", "has_actual"),
                                     "production_plan_table": ("abp_plan", "has_abp"),
                                     "mou_plan_table": ("mou_plan", "has_mou")}
    assert {s: spec["table"] for s, spec in vc.TEXT_SCOPES.items()} == {
        "page3_narrative": "page3_narrative", "key_highlights": "key_highlights_narrative",
        "steel_sales": "steel_sales_highlights", "secretary_review": "secretary_review_text",
        "board_note": "board_note_manual_text", "do_letter": "do_letter_remark_table",
        "sail_sales_note": "sail_sales_note_table", "rail_note": "rail_prod_despatch_note",
        "ss_phys_note": "special_steel_phys_note"}


def test_map_drift_reported(monkeypatch):
    oracle = dict(ver.EXPECTED_RENAMES)
    oracle[("stock_table", "stock_month")] = "month"
    oracle[("users", "email")] = "user_email"
    monkeypatch.setattr(ver, "EXPECTED_RENAMES", oracle)
    problems = ver.map_problems()
    _has(problems, r"map: stock_table\.stock_month -> stock_monthly\.report_month is not an expected rename")
    _has(problems, r"map: expected rename users\.email -> user_email is not in migrate's map")


def test_uncovered_v2_column(dbs):
    v1, v2 = dbs
    with _corrupt(v2, [], ["ALTER TABLE mine_group DROP COLUMN extra_col"]):
        conn = m6a._connect(v2)
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE mine_group ADD COLUMN extra_col INT NULL")
        conn.close()
        problems = _verify(dbs)
    _has(problems, r"v2 column mine_group\.extra_col is not covered by the v1 -> v2 map")
    assert _verify(dbs) == []


def test_unparseable_v1_timestamp(dbs):
    v1, v2 = dbs
    with _corrupt(v1, ["UPDATE todo_jobs SET created_at = '2026-07-10 07:17:33.5' WHERE id = 2"],
                  ["UPDATE todo_jobs SET created_at = '2026-07-10T07:17:33' WHERE id = 2"]):
        problems = _verify(dbs)
    _has(problems, r"todo_jobs -> todo_job: row \(2,\) created_at: unparseable v1 timestamp")
    assert _verify(dbs) == []


# ── CLI and guards ──────────────────────────────────────────────────────────

def test_cli_refusal_is_one_line(monkeypatch, capsys):
    def boom(*a, **k):
        raise ver.VerifyError("'x' is not a v2 schema")
    monkeypatch.setattr(ver, "verify", boom)
    assert ver.main(["--src", "a", "--dst", "b"]) == 1
    assert capsys.readouterr().out == "verify refused: 'x' is not a v2 schema\n"


def test_cli_exit_code(monkeypatch, capsys):
    for problems, code in (([], 0), (["row count x: v1 1 != v2 0"], 1)):
        monkeypatch.setattr(ver, "verify", lambda *a, _p=problems, **k: list(_p))
        assert ver.main(["--src", "a", "--dst", "b"]) == code
    assert "PROBLEM: row count x" in capsys.readouterr().out


def test_guards(dbs):
    v1, v2 = dbs
    with pytest.raises(ver.VerifyError, match="same database"):
        ver.verify(v1, v1.upper(), src_cfg=m6a._cfg(), dst_cfg=m6a._cfg())
    with pytest.raises(ver.VerifyError, match="not a v2 schema"):
        ver.verify(v2, v1, src_cfg=m6a._cfg(), dst_cfg=m6a._cfg())
