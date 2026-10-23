"""repo.mines / repo.rake / repo.cost_trend / repo.misc: the moved write paths
still persist the right values on the same connection with the same commit
point, and the moved reads return the same shapes.

Write sites are driven through their main.py routes where they have one, so
the caller-side wiring is covered as well as the repo function itself.
Multi-row saves are checked for commit-once: a spy around the module's
connect() counts commit() calls and, after every INSERT/UPDATE, records how
many rows a separate connection can see (0 until the single commit)."""
import pytest
from fastapi.testclient import TestClient

import dbengine
from repo import conn as rc
from repo import cost_trend as rct
from repo import mines as rmn
from repo import misc as rmisc
from repo import rake as rrk


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
    """Wraps a module's connect(): counts commit() calls and, after every
    write statement, records how many `table` rows another connection sees."""

    def __init__(self, real_connect, table):
        self.real_connect = real_connect
        self.table = table
        self.commits = 0
        self.connects = 0
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
                if sql.lstrip().upper().startswith(("INSERT", "DELETE", "UPDATE")) and "data_version" not in sql:  # not the bump
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


# ── repo.cost_trend ───────────────────────────────────────────────────────────

def test_cost_trend_monthly_route_commits_once(tc):
    spy = _CommitSpy(rct.connect, "cost_trend_monthly")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(rct, "connect", spy)
        r = tc.post("/api/cost-trend/monthly", json={"report_month": "2026-08", "product": "HM", "entries": [
            {"cost_type": "VARIABLE", "plant": "BSP", "month_value": 101.5, "till_month_value": 99.0},
            {"cost_type": "FIXED", "plant": "BSP", "month_value": None, "till_month_value": 7.0},
            {"cost_type": "VARIABLE", "plant": "SAIL", "month_value": 88.0}]})
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "success", "saved": 3}
    assert (spy.connects, spy.commits) == (1, 1)
    assert spy.visible_mid_call == [0, 0, 0]
    assert _rows("SELECT report_month, product, cost_type, plant_code, month_value, till_month_value "
                 "FROM cost_trend_monthly ORDER BY plant_code, cost_type") == [
        ("2026-08", "HM", "FIXED", "BSP", None, 7.0),
        ("2026-08", "HM", "VARIABLE", "BSP", 101.5, 99.0),
        ("2026-08", "HM", "VARIABLE", "SAIL", 88.0, None)]
    got = tc.get("/api/cost-trend/monthly", params={"product": "HM", "report_month": "2026-08"}).json()
    assert got["entries"]["VARIABLE"]["BSP"] == {"month": 101.5, "till_month": 99.0}
    assert got["entries"]["TOTAL"] == {}


def test_cost_trend_annual_and_field_update(tc):
    spy = _CommitSpy(rct.connect, "cost_trend_annual")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(rct, "connect", spy)
        r = tc.post("/api/cost-trend/annual", json={"fy": "2025-26", "product": "CS", "entries": [
            {"cost_type": "VARIABLE", "plant": "DSP", "value": 1.25},
            {"cost_type": "FIXED", "plant": "DSP", "value": None}]})
    assert r.status_code == 200, r.text
    assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [0, 0])
    assert rct.get_cost_trend_annual("CS", ["2025-26", "2024-25"]) == {
        "2025-26": {"TOTAL": {}, "VARIABLE": {"DSP": 1.25}, "FIXED": {"DSP": None}},
        "2024-25": {"TOTAL": {}, "VARIABLE": {}, "FIXED": {}}}

    # Field-only upsert (cost trend Excel extractor): the other column is kept.
    rct.save_cost_trend_monthly("2026-07", "COKE", [
        {"cost_type": "FIXED", "plant": "RSP", "month_value": 5.0, "till_month_value": 6.0}])
    assert rct.save_cost_trend_monthly_field("2026-07", "COKE", [
        {"cost_type": "FIXED", "plant": "RSP", "value": 60.0},
        {"cost_type": "VARIABLE", "plant": "RSP", "value": 70.0}], "till_month_value") == 2
    assert _rows("SELECT cost_type, month_value, till_month_value FROM cost_trend_monthly "
                 "WHERE product='COKE' ORDER BY cost_type") == [("FIXED", 5.0, 60.0), ("VARIABLE", None, 70.0)]
    with pytest.raises(ValueError):
        rct.save_cost_trend_monthly_field("2026-07", "COKE", [], "value")
    assert rct.monthly_any_row("2026-07") is True
    assert rct.monthly_any_row("2026-06") is False


def test_cost_trend_extract_field_save_commits_once(mysql_db):
    spy = _CommitSpy(rct.connect, "cost_trend_monthly")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(rct, "connect", spy)
        rct.save_cost_trend_monthly_field("2026-08", "SS", [
            {"cost_type": "FIXED", "plant": "BSP", "value": 1.0},
            {"cost_type": "FIXED", "plant": "DSP", "value": 2.0}], "month_value")
    assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [0, 0])


# ── repo.mines ────────────────────────────────────────────────────────────────

def _seed_mine_masters():
    with rc.tx() as cur:
        cur.execute("INSERT INTO mine_group (group_code, group_name, sort_order) VALUES "
                    "('JG','J Group',1), ('OG','O Group',2)")
        cur.execute("INSERT INTO mine (mine_code, mine_name, group_code, is_active, sort_order) VALUES "
                    "('A','Alpha','JG',1,1), ('B','Beta','OG',0,2)")
        cur.execute("INSERT INTO mine_material (material_code, material_name, material_category, "
                    "has_production, counts_in_total_production, sort_order) VALUES "
                    "('LUMP','Lump','FRESH',1,1,1), ('FINES','Fines','FRESH',1,1,2), "
                    "('PELLETS','Pellets','LEGACY',0,1,3)")
        cur.execute("INSERT INTO mine_end_use (end_use_code, end_use_name, sort_order, tracks_actual) "
                    "VALUES ('CAPTIVE','Captive',1,1), ('SALES','Sales',2,1), ('UNALLOCATED','Unalloc',3,0)")


def test_mines_production_despatch_route_commits_once(tc):
    _seed_mine_masters()
    spy = _CommitSpy(rmn.connect, "mine_production_monthly")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(rmn, "connect", spy)
        r = tc.post("/api/mines-production-despatch/monthly", json={
            "report_month": "2026-08", "mine_code": "A",
            "production": [{"material_code": "LUMP", "actual": 10.0, "plan": 12.0},
                           {"material_code": "FINES", "actual": 5.0}],
            "despatch": [{"material_code": "LUMP", "transport_mode": "RAIL", "end_use_code": "CAPTIVE",
                          "actual": 8.0},
                         {"material_code": "PELLETS", "transport_mode": "ROAD", "end_use_code": "SALES",
                          "actual": 3.0}],
            "despatch_plan": [{"material_code": "LUMP", "end_use_code": "CAPTIVE", "plan": 9.0}],
            "booked_qty": [{"material_code": "FINES", "transport_mode": "RAIL", "actual": 2.5}],
            "booked_qty_plan": [{"material_code": "FINES", "plan": 4.0}]})
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "success", "saved": 7}
    assert (spy.connects, spy.commits) == (1, 1)
    assert spy.visible_mid_call == [0] * 7
    assert _rows("SELECT report_month, mine_code, material_code, qty_actual, qty_plan "
                 "FROM mine_production_monthly ORDER BY material_code") == [
        ("2026-08", "A", "FINES", 5.0, None), ("2026-08", "A", "LUMP", 10.0, 12.0)]
    assert _rows("SELECT material_code, transport_mode, end_use_code, qty_actual "
                 "FROM mine_despatch_actual_monthly ORDER BY material_code") == [
        ("LUMP", "RAIL", "CAPTIVE", 8.0), ("PELLETS", "ROAD", "SALES", 3.0)]
    assert _rows("SELECT material_code, end_use_code, qty_plan FROM mine_despatch_plan_monthly") == [
        ("LUMP", "CAPTIVE", 9.0)]
    assert _rows("SELECT material_code, transport_mode, qty_actual FROM mine_booked_qty_actual_monthly") == [
        ("FINES", "RAIL", 2.5)]
    assert _rows("SELECT material_code, qty_plan FROM mine_booked_qty_plan_monthly") == [("FINES", 4.0)]

    got = tc.get("/api/mines-production-despatch/monthly",
                 params={"report_month": "2026-08", "mine_code": "A"}).json()
    assert got["production"] == {"LUMP": {"actual": 10.0, "plan": 12.0}, "FINES": {"actual": 5.0, "plan": None}}
    assert got["despatch"]["LUMP"] == {"RAIL": {"CAPTIVE": {"actual": 8.0}}}
    assert got["despatch_plan"] == {"LUMP": {"CAPTIVE": 9.0}}
    assert got["booked_qty"] == {"FINES": {"RAIL": {"actual": 2.5}}}
    assert got["booked_qty_plan"] == {"FINES": 4.0}

    m = tc.get("/api/mines-master").json()
    assert [g["group_code"] for g in m["groups"]] == ["JG", "OG"]
    assert m["mines"][1] == {"mine_code": "B", "mine_name": "Beta", "group_code": "OG", "is_active": False}
    assert [x["material_code"] for x in m["materials"]] == ["LUMP", "FINES", "PELLETS"]
    assert m["end_uses"][2] == {"end_use_code": "UNALLOCATED", "end_use_name": "Unalloc", "tracks_actual": False}

    # Group roll-ups (JOIN mine) and the flat series.
    roll = rmn.get_iron_ore_group_rollup_monthly(["2026-08"])
    assert roll["2026-08"]["iron_ore_prod"] == {"JG": {"actual": 18.0, "plan": 12.0}}
    assert roll["2026-08"]["iron_ore_despatch"] == {"JG": {"actual": 11.0, "plan": 9.0}}
    assert rmn.get_iron_ore_despatch_mix(["2026-08"]) == {"CAPTIVE": 8.0, "SALES": 3.0}
    sales = rmn.get_iron_ore_sales_group_rollup_monthly(["2026-08"])
    assert sales["2026-08"]["iron_ore_sales"] == {"JG": {"actual": 2.5, "plan": 4.0}}
    assert sales["2026-08"]["iron_ore_sales_despatch"] == {"JG": {"actual": 3.0, "plan": None}}
    series = rmn.get_iron_ore_mines_series(["2026-08"])
    assert len(series["production"]) == 2 and len(series["despatch"]) == 2
    assert series["despatch_plan"] == [{"report_month": "2026-08", "mine_code": "A", "group_code": "JG",
                                        "material_code": "LUMP", "end_use_code": "CAPTIVE", "plan": 9.0}]


def test_sail_mines_route_commits_once_and_performance_load(tc):
    _seed_mine_masters()
    spy = _CommitSpy(rmn.connect, "sail_mines_monthly")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(rmn, "connect", spy)
        r = tc.post("/api/sail-mines/monthly", json={"report_month": "2026-08", "entries": [
            {"section": "coal_prod", "item": "Tasra", "actual": 1.5, "plan": 2.0},
            {"section": "washery", "item": "Chasnalla", "actual": 0.75}]})
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "success", "saved": 2}
    assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [0, 0])
    assert _rows("SELECT report_month, section, item, month_actual, month_plan FROM sail_mines_monthly "
                 "ORDER BY section") == [("2026-08", "coal_prod", "Tasra", 1.5, 2.0),
                                         ("2026-08", "washery", "Chasnalla", 0.75, None)]
    got = tc.get("/api/sail-mines/monthly", params={"report_month": "2026-08"}).json()
    assert got["entries"]["coal_prod"]["Tasra"] == {"actual": 1.5, "plan": 2.0}
    assert rmn.sail_mines_any_row("2026-08") is True
    assert rmn.sail_mines_any_row("2026-07") is False

    # mines_performance._load reads every series via the repo.mines cursor helpers.
    rmn.save_mines_production_despatch_monthly(
        "2026-08", "A", [{"material_code": "LUMP", "actual": 10.0, "plan": 12.0}],
        [{"material_code": "LUMP", "transport_mode": "RAIL", "end_use_code": "SALES", "actual": 4.0},
         {"material_code": "LUMP", "transport_mode": "ROAD", "end_use_code": "SALES", "actual": 1.0}],
        [{"material_code": "LUMP", "end_use_code": "SALES", "plan": 6.0}],
        [{"material_code": "LUMP", "transport_mode": "RAIL", "actual": 2.0}],
        [{"material_code": "LUMP", "plan": 3.0}])
    import mines_performance as mperf
    data = mperf._load(["2026-08"])
    assert [tuple(g) for g in data["groups"]] == [("JG", "J Group"), ("OG", "O Group")]
    assert [tuple(m) for m in data["mines"]] == [("A", "Alpha", "JG", 1), ("B", "Beta", "OG", 0)]
    assert [m[0] for m in data["materials"]] == ["LUMP", "FINES", "PELLETS"]
    assert data["prod"] == {("A", "LUMP"): {"2026-08": (10.0, 12.0)}}
    assert data["desp"] == {("A", "LUMP", "SALES"): {"2026-08": (5.0, 6.0)}}
    assert data["booked"] == {("A", "LUMP"): {"2026-08": (2.0, 3.0)}}
    assert data["sail"][("coal_prod", "Tasra")] == {"2026-08": (1.5, 2.0)}


# ── repo.rake ─────────────────────────────────────────────────────────────────

def test_rake_detention_master_and_grid_routes(tc):
    r = tc.post("/api/rake-detention/master", json={
        "plant": "BSP", "section": "INWARD", "commodity": "Coal", "wagon_type": "BOXN",
        "row_label": "BOXN", "freetime_hours": 5.0, "sort_order": 1})
    assert r.status_code == 200, r.text
    mid = r.json()["id"]
    r2 = tc.post("/api/rake-detention/master", json={
        "plant": "BSP", "section": "INWARD", "row_label": "Total Inward", "is_total": True, "sort_order": 9})
    tot = r2.json()["id"]
    # update by id
    assert tc.post("/api/rake-detention/master", json={
        "id": mid, "plant": "BSP", "section": "INWARD", "commodity": "Coal", "wagon_type": "BOXN",
        "row_label": "BOXN-HL", "freetime_hours": 6.5, "sort_order": 1}).status_code == 200
    assert _rows("SELECT id, row_label, freetime_hours, is_total, is_active FROM rake_detention_master "
                 "ORDER BY id") == [(mid, "BOXN-HL", 6.5, 0, 1), (tot, "Total Inward", None, 1, 1)]

    spy = _CommitSpy(rrk.connect, "rake_detention_monthly")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(rrk, "connect", spy)
        r = tc.post("/api/rake-detention/grid", json={
            "report_month": "2026-08",
            "monthly": [{"master_id": mid, "value_hours": "7.5"}, {"master_id": tot, "value_hours": "-"}],
            "summary": [{"period_row": "YTD_TY", "plant": "BSP", "value": 4.25},
                        {"period_row": "YTD_LY", "plant": "BSP", "value": ""}]})
    assert r.status_code == 200, r.text
    # one connection + one commit per save function (monthly, then summary)
    assert (spy.connects, spy.commits) == (2, 2)
    assert spy.visible_mid_call == [0, 0, 2, 2]
    assert rrk.get_rake_detention_monthly("2026-08") == {mid: 7.5, tot: None}
    assert rrk.get_rake_detention_monthly("2026-08", master_ids=[mid]) == {mid: 7.5}
    assert rrk.get_rake_detention_summary("2026-08") == {"YTD_TY": {"BSP": 4.25}, "YTD_LY": {"BSP": None}}
    assert rrk.get_rake_detention_trend([mid, 999]) == {mid: {"2026-08": 7.5}, 999: {}}

    grid = tc.get("/api/rake-detention/grid", params={"report_month": "2026-08"}).json()
    assert [(x["id"], x["value_hours"]) for x in grid["rows"]] == [(mid, 7.5), (tot, None)]

    assert tc.post("/api/rake-detention/master/deactivate", json={"id": mid}).status_code == 200
    assert [x["id"] for x in rrk.get_rake_detention_master()] == [tot]
    assert [x["id"] for x in rrk.get_rake_detention_master(plants=["BSP"], active_only=False)] == [mid, tot]
    assert rrk.get_rake_detention_master(plants=["DSP"]) == []

    spy = _CommitSpy(rrk.connect, "rake_detention_annual")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(rrk, "connect", spy)
        assert rrk.save_rake_detention_annual([
            {"plant": "BSP", "financial_year": "2024-25", "avg_hours": 6.0},
            {"plant": "DSP", "financial_year": "2024-25"}]) == 2
    assert (spy.connects, spy.commits, spy.visible_mid_call) == (1, 1, [0, 0])
    assert rrk.get_rake_detention_annual(["BSP", "DSP", "RSP"], ["2024-25"]) == {
        "BSP": {"2024-25": 6.0}, "DSP": {"2024-25": None}, "RSP": {}}


# ── repo.misc ─────────────────────────────────────────────────────────────────

def test_market_intel_route_commits_once(tc):
    spy = _CommitSpy(rmisc.connect, "market_price_monthly")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(rmisc, "connect", spy)
        r = tc.post("/api/market-intel/grid", json={
            "report_month": "2026-08",
            "market_price_rows": [{"series_code": "HRC_CHINA", "value": "512.5"},
                                  {"series_code": "COKING_COAL", "value": ""}],
            "macro_rows": [{"metric_code": "GDP", "value": 7.1}, {"metric_code": "IIP", "value": None}]})
    assert r.status_code == 200, r.text
    assert (spy.connects, spy.commits) == (2, 2)
    # market prices visible to the other connection only after their commit
    assert spy.visible_mid_call == [0, 0, 2, 2]
    assert rmisc.get_market_price_trend(["2026-08", "2026-07"]) == {
        "2026-08": {"HRC_CHINA": 512.5, "COKING_COAL": None}, "2026-07": {}}
    assert rmisc.get_macro_indicators(["2026-08"]) == {"2026-08": {"GDP": 7.1, "IIP": None}}
    assert _rows("SELECT report_month, metric_code, value FROM macro_indicator_monthly ORDER BY metric_code") == [
        ("2026-08", "GDP", 7.1), ("2026-08", "IIP", None)]
