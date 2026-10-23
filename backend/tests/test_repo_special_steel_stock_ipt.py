"""repo.special_steel / repo.stock / repo.ipt: the moved write paths still
persist the right values on the same connection with the same commit point.

Write sites are exercised through their routes where they live in main.py /
api_special_steel_clubs.py, so the caller-side wiring (connection, cursor,
commit) is covered as well as the repo function itself."""
import json

import pytest
from fastapi.testclient import TestClient

import dbengine
from repo import conn as rc
from repo import ipt as ript
from repo import special_steel as rss
from repo import stock as rst


@pytest.fixture
def tc(mysql_db, monkeypatch):
    import main
    monkeypatch.setattr(main, "_is_gated", lambda method, path: False)
    return TestClient(main.app, raise_server_exceptions=False)


def _rows(sql, params=()):
    with rc.cursor() as cur:
        cur.execute(sql, params)
        return [tuple(r) for r in cur.fetchall()]


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
    """Wraps db.connect()/dbengine.connect(): counts commit() calls and, after
    every statement, records how many `table` rows another connection sees."""

    def __init__(self, real_connect, table):
        self.real_connect = real_connect
        self.table = table
        self.commits = 0
        self.visible_mid_call = []

    def __call__(self, *a, **kw):
        spy = self
        conn = self.real_connect(*a, **kw)

        class _Cur:
            def __init__(self, cur):
                self._cur = cur

            def execute(self, sql, params=()):
                self._cur.execute(sql, params)
                if sql.lstrip().upper().startswith(("INSERT", "DELETE")) and "data_version" not in sql:  # not the bump
                    spy.visible_mid_call.append(_other_conn_count(spy.table))
                return self

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


# ── repo.special_steel ────────────────────────────────────────────────────────

def test_special_steel_entry_save_and_clear(mysql_db):
    rss.save_special_steel_entry("2026-08", "BSP", "PLATE", "IS 2062", 2, 10.5, 9.25, section="")
    rss.save_special_steel_entry("2026-08", "BSP", "PLATE", "IS 2062", 3, 11.0, None, section="")
    rss.save_special_steel_entry("2026-08", "DSP", "WHEEL", "TOTAL", 0, None, 4.0, section="S1")
    assert _rows("SELECT report_month, plant_name, product, quality_grade, section, sort_order, "
                 "order_qty, actual_despatch FROM special_steel_orders ORDER BY plant_name") == [
        ("2026-08", "BSP", "PLATE", "IS 2062", "", 3, 11.0, None),
        ("2026-08", "DSP", "WHEEL", "TOTAL", "S1", 0, None, 4.0),
    ]
    assert rss.clear_special_steel_orders("2026-08", "BSP") == 1
    assert _rows("SELECT plant_name FROM special_steel_orders") == [("DSP",)]
    # db.py re-exports the moved functions


def test_special_steel_manual_save_route(tc):
    rss.save_special_steel_entry("2026-08", "BSL", "OLD", "X", 0, 1.0, 1.0)
    r = tc.post("/api/special-steel-manual/save", json={
        "plant": "BSL", "month": "2026-08",
        "rows": [{"product": "HR COIL", "quality_grade": "API", "order_qty": 5, "actual_despatch": 4},
                 {"product": "HR COIL", "quality_grade": "BQ", "section": "A", "actual_despatch": 2}]})
    assert r.status_code == 200, r.text
    assert _rows("SELECT product, quality_grade, section, sort_order, order_qty, actual_despatch "
                 "FROM special_steel_orders WHERE plant_name='BSL' ORDER BY sort_order") == [
        ("HR COIL", "API", "", 0, 5.0, 4.0), ("HR COIL", "BQ", "A", 1, None, 2.0)]
    got = tc.get("/api/special-steel-manual", params={"plant": "BSL", "month": "2026-08"}).json()
    assert [x["quality_grade"] for x in got["rows"]] == ["API", "BQ"]


def test_special_steel_abp_save_commits_once(tc):
    spy = _CommitSpy(dbengine.connect, "special_steel_abp_table")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(dbengine, "connect", spy)
        r = tc.post("/api/special-steel-abp", json={"financial_year": "2026-27", "entries": [
            {"plant_name": "BSP", "report_month": "2026-04", "abp_qty": 12.5},
            {"plant_name": "DSP", "report_month": "2026-05", "abp_qty": None},
            {"plant_name": "SSPs", "report_month": "2026-06", "abp_qty": 3.0}]})
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "success", "saved": 3}
    assert spy.commits == 1
    assert spy.visible_mid_call == [0, 0, 0]        # nothing committed mid-call
    assert _rows("SELECT report_month, plant_name, abp_qty FROM special_steel_abp_table "
                 "ORDER BY report_month") == [
        ("2026-04", "BSP", 12.5), ("2026-05", "DSP", None), ("2026-06", "SSPs", 3.0)]
    got = tc.get("/api/special-steel-abp", params={"financial_year": "2026-27"}).json()
    assert got["entries"]["BSP"] == {"2026-04": 12.5}


def test_grade_clubs_crud(tc):
    rss.save_special_steel_entry("2026-08", "BSP", "PLATE", "A1", 0, 1, 1)
    rss.save_special_steel_entry("2026-08", "BSP", "PLATE", "A2", 1, 1, 1)
    rss.save_special_steel_entry("2026-08", "BSP", "PLATE", "B", 2, 1, 1)
    r = tc.post("/api/special-steel/grade-clubs",
                json={"plant": "bsp", "product": "PLATE", "grades": ["A1", "A2", "B"], "label": "ALL"})
    assert r.status_code == 200, r.text
    assert _rows("SELECT plant_name, product, quality_grade, club_label FROM special_steel_grade_clubs "
                 "ORDER BY quality_grade") == [
        ("BSP", "PLATE", "A1", "ALL"), ("BSP", "PLATE", "A2", "ALL"), ("BSP", "PLATE", "B", "ALL")]
    g = tc.get("/api/special-steel/grades", params={"plant": "BSP", "product": "PLATE"}).json()
    assert g["ungrouped"] == [] and g["clubs"] == [{"label": "ALL", "members": ["A1", "A2", "B"]}]
    assert tc.get("/api/special-steel/products", params={"plant": "BSP"}).json()["products"] == ["PLATE"]

    # remove one grade: two remain clubbed
    r = tc.request("DELETE", "/api/special-steel/grade-clubs",
                   json={"plant": "BSP", "product": "PLATE", "grade": "B"})
    assert r.status_code == 200, r.text
    assert _rows("SELECT quality_grade FROM special_steel_grade_clubs ORDER BY quality_grade") == [
        ("A1",), ("A2",)]
    # remove another: the last member auto-dissolves
    r = tc.request("DELETE", "/api/special-steel/grade-clubs",
                   json={"plant": "BSP", "product": "PLATE", "grade": "A1"})
    assert r.status_code == 200, r.text
    assert _rows("SELECT quality_grade FROM special_steel_grade_clubs") == []
    # dissolve by label
    tc.post("/api/special-steel/grade-clubs",
            json={"plant": "BSP", "product": "PLATE", "grades": ["A1", "A2"], "label": "L"})
    r = tc.request("DELETE", "/api/special-steel/grade-clubs",
                   json={"plant": "BSP", "product": "PLATE", "label": "L"})
    assert r.json()["ungrouped"] == ["A1", "A2"]
    assert _rows("SELECT quality_grade FROM special_steel_grade_clubs") == []


def test_ss_phys_perf_and_meta_save(mysql_db):
    spy = _CommitSpy(rss.connect, "special_steel_phys_perf")
    mp = pytest.MonkeyPatch()
    mp.setattr(rss, "connect", spy)
    assert rss.save_ss_phys_perf([
        {"financial_year": "2025-26", "plant": "ASP", "series": "liquid", "metric": "actual", "value_kt": 1.5},
        {"financial_year": "2025-26", "plant": "SSP", "series": "liquid", "metric": "actual", "value_kt": 2.0},
        {"financial_year": "2025-26", "plant": "VISL", "series": "liquid", "metric": "abp", "value_kt": 3.0},
    ]) == 3
    assert spy.commits == 1
    assert spy.visible_mid_call == [0, 0, 0]
    assert rss.save_ss_phys_perf([
        {"financial_year": "2025-26", "plant": "SSP", "series": "liquid", "metric": "actual", "value_kt": None},
        {"financial_year": "2025-26", "plant": "ASP", "series": "liquid", "metric": "actual", "value_kt": 9.0},
    ]) == 2
    assert spy.commits == 2
    rss.save_ss_phys_meta([{"plant": "ASP", "series": "liquid", "capacity_kt": 100,
                            "best_actual_kt": 90, "best_year": "2019-20", "remark": "r", "sort_order": "2"}])
    mp.undo()
    meta, perf = rss.get_ss_phys_perf()
    assert perf == {("2025-26", "ASP", "liquid", "actual"): 9.0,
                    ("2025-26", "VISL", "liquid", "abp"): 3.0}
    assert meta == {("ASP", "liquid"): {"capacity_kt": 100.0, "best_actual_kt": 90.0,
                                        "best_year": "2019-20", "remark": "r", "sort_order": 2}}


def test_ss_ipt_requirement_save_rename_delete(mysql_db):
    assert rss.save_ss_ipt_requirement("2026-27", [
        {"item": "Slabs", "from_plant": "BSP", "to_plant": "SSP", "plan_kt": 5, "sort_order": 1},
        {"item": "Bad", "from_plant": "BSP", "to_plant": "BSP", "plan_kt": 1},       # skipped
    ]) == 1
    assert rss.save_ss_ipt_requirement("2026-27", [
        {"item": "Slab", "from_plant": "BSP", "to_plant": "SSP", "plan_kt": 6, "sort_order": 1,
         "orig_item": "Slabs", "orig_from_plant": "BSP", "orig_to_plant": "SSP"}]) == 1
    assert rss.get_ss_ipt_requirement("2026-27") == [
        {"item": "Slab", "from_plant": "BSP", "to_plant": "SSP", "plan_kt": 6.0, "sort_order": 1}]
    assert rss.list_ss_ipt_requirement_fys() == ["2026-27"]
    rss.delete_ss_ipt_requirement("2026-27", "Slab", "BSP", "SSP")
    assert _rows("SELECT * FROM special_steel_ipt_requirement") == []


# ── repo.stock ────────────────────────────────────────────────────────────────

def test_stock_entry_route(tc):
    r = tc.post("/api/stock-entry", json={"entries": [
        {"plant": "BSP", "stock_month": "2026-09", "item_type": "SLABS", "stock_type": "FOR SALE", "stock": "12.5"},
        {"plant": "BSP", "stock_month": "2026-09", "item_type": "", "stock": 1}]})
    assert r.json()["saved"] == 1
    rst.save_stock_entry("2026-09", "BSP", "SLABS", "FOR SALE", 13.0)
    assert _rows("SELECT stock_month, plant_name, item_type, stock_type, stock FROM stock_table") == [
        ("2026-09", "BSP", "SLABS", "FOR SALE", 13.0)]
    got = tc.get("/api/stock-data", params={"plant": "BSP", "stock_month": "2026-09"}).json()
    assert got["data"] == [{"item_type": "SLABS", "stock_type": "FOR SALE", "stock": 13.0}]


def test_sail_1page_confirm_commits_once(tc):
    spy = _CommitSpy(dbengine.connect, "sail_sales_table")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(dbengine, "connect", spy)
        r = tc.post("/api/sail-1page/confirm", json={
        "report_month": "2026-08",
        "sales_rows": [{"item_name": "Total Sales", "data": {"month": 10.5, "ytd": None}},
                       {"item_name": "Exports", "data": {"month": None}}],          # all None: skipped
        "stock_rows": [{"item_name": "BSP", "snapshot_date": "2026-09-01", "value": 7.5},
                       {"item_name": "DSP", "snapshot_date": "2026-09-01", "value": None}]})
    assert r.status_code == 200, r.text
    assert r.json() == {"saved_sales": 1, "saved_stock": 1}
    assert spy.commits == 1
    assert spy.visible_mid_call == [0, 0]
    sales = _rows("SELECT report_month, item_name, data_json FROM sail_sales_table")
    assert [(m, i, json.loads(d)) for m, i, d in sales] == [
        ("2026-08", "Total Sales", {"month": 10.5, "ytd": None})]
    assert _rows("SELECT snapshot_date, item_name, value FROM sail_stock_snapshot_table") == [
        ("2026-09-01", "BSP", 7.5)]


# ── repo.ipt ──────────────────────────────────────────────────────────────────

def test_ipt_entry_save_delete(mysql_db):
    ript.save_ipt_entry("2026-08", "CC Slabs", "BSP", "ASP", unit="T", sort_order=1,
                        plan=100.0, actual=90.0)
    ript.save_ipt_entry("2026-08", "CC Slabs", "BSP", "ASP", unit="Rake", sort_order=2,
                        plan=3, actual=2, plan_tonnage=300.0, actual_tonnage=200.0)
    assert _rows("SELECT report_month, item, from_plant, to_plant, unit, sort_order, plan, actual, "
                 "plan_tonnage, actual_tonnage FROM ipt_table") == [
        ("2026-08", "CC Slabs", "BSP", "ASP", "Rake", 2, 3.0, 2.0, 300.0, 200.0)]
    assert ript.delete_ipt_entry("2026-08", "CC Slabs", "BSP", "ASP") == 1
    assert _rows("SELECT * FROM ipt_table") == []


def test_ipt_bulk_route_renames_key(tc):
    ript.save_ipt_entry("2026-08", "CC Slabs", "BSP", "ASP", plan=1.0, actual=1.0)
    r = tc.post("/api/ipt-entries/bulk", json={"month": "2026-08", "entries": [
        {"item": "CC Blooms", "from_plant": "BSP", "to_plant": "ASP", "plan": "5", "actual": "",
         "orig_item": "CC Slabs", "orig_from_plant": "BSP", "orig_to_plant": "ASP"},
        {"item": "X", "from_plant": "DSP", "to_plant": "DSP"}]})
    assert r.json() == {"status": "ok", "saved": 1, "skipped": 1}
    assert _rows("SELECT item, plan, actual FROM ipt_table") == [("CC Blooms", 5.0, None)]
    got = tc.get("/api/ipt-entries", params={"month": "2026-08"}).json()
    assert [x["item"] for x in got["rows"]] == ["CC Blooms"]
    assert tc.get("/api/ipt-items").json() == {"items": ["CC Blooms"]}
    r = tc.post("/api/ipt-delete", json={"month": "2026-08", "item": "CC Blooms",
                                         "from_plant": "BSP", "to_plant": "ASP"})
    assert r.status_code == 200
    assert _rows("SELECT * FROM ipt_table") == []
