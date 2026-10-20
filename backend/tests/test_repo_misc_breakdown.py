"""repo.breakdown / repo.misc (batch 3e2): the moved write paths still persist
the right values on the same connection with the same commit point.

Write sites are exercised through their routes where the route holds the
connection (main.py, api_breakdown, api_bf_benchmark, api_power_omi), so the
caller-side wiring (connection, cursor, commit) is covered as well as the
repo function itself. "Spy" = connect() wrapped to count commits and record,
after each write statement, how many rows another connection sees."""
import io

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

import db
import dbengine
from repo import breakdown as rbd
from repo import conn as rc
from repo import misc as rmisc


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


_WRITES = ("INSERT", "DELETE", "UPDATE", "REPLACE")


class _CommitSpy:
    """Wraps a connect(): counts connections and commit() calls and, after
    every write statement, records how many `table` rows another connection
    sees."""

    def __init__(self, real_connect, table):
        self.real_connect = real_connect
        self.table = table
        self.conns = 0
        self.commits = 0
        self.visible_mid_call = []

    def __call__(self, *a, **kw):
        spy = self
        spy.conns += 1
        conn = self.real_connect(*a, **kw)

        class _Cur:
            def __init__(self, cur):
                self._cur = cur

            def execute(self, sql, params=()):
                self._cur.execute(sql, params)
                if sql.lstrip().upper().startswith(_WRITES):
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


def _spy(mp, module, table):
    spy = _CommitSpy(module.connect, table)
    mp.setattr(module, "connect", spy)
    return spy


# ── repo.breakdown: breakdown_table through /api/breakdown ──────────────────

def test_breakdown_create_patch_delete_through_api(tc):
    body = {"plant": "BSP", "unit_type": "BF", "unit_name": "BF-4", "start_ts": "2026-08-01 10:00",
            "end_ts": "2026-08-01 14:00", "cause": "tuyere leak"}
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rbd, "breakdown_table")
        r = tc.post("/api/breakdown", json=body)
    assert r.status_code == 200, r.text
    bid = r.json()["id"]
    assert (spy.conns, spy.commits, spy.visible_mid_call) == (1, 1, [0])
    assert _rows("SELECT plant, unit_type, unit_name, start_ts, end_ts, is_ongoing, cause, created_by "
                 "FROM breakdown_table") == [
        ("BSP", "BF", "BF-4", "2026-08-01 10:00", "2026-08-01 14:00", 0, "tuyere leak", "unknown")]

    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rbd, "breakdown_table")
        r = tc.patch(f"/api/breakdown/{bid}", json={"cause": "tuyere leak, replaced", "end_ts": "2026-08-01 16:00"})
    assert r.status_code == 200, r.text
    # list_breakdown_entries (route's existence check) + update: 2 conns, 1 commit
    assert (spy.conns, spy.commits) == (2, 1)
    assert _rows("SELECT cause, end_ts, updated_by FROM breakdown_table") == [
        ("tuyere leak, replaced", "2026-08-01 16:00", "unknown")]

    got = tc.get("/api/breakdown", params={"plant": "BSP", "fy": "2026-27"}).json()["rows"]
    assert [(g["id"], g["unit_name"]) for g in got] == [(bid, "BF-4")]
    assert tc.get("/api/breakdown", params={"fy": "2025-26"}).json()["rows"] == []

    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rbd, "breakdown_table")
        r = tc.delete(f"/api/breakdown/{bid}")
    assert r.status_code == 200, r.text
    assert (spy.conns, spy.commits, spy.visible_mid_call) == (1, 1, [1])
    assert _rows("SELECT * FROM breakdown_table") == []
    assert tc.delete(f"/api/breakdown/{bid}").status_code == 404
    # db.py re-exports the moved functions
    assert db.list_breakdown_entries is rbd.list_breakdown_entries
    assert db.save_breakdown_entry is rbd.save_breakdown_entry
    assert db.update_breakdown_entry is rbd.update_breakdown_entry
    assert db.delete_breakdown_entry is rbd.delete_breakdown_entry


# ── repo.breakdown: capital_repair_table through main.py's routes ───────────

def test_capital_repair_rows_entry_reorder_delete(tc):
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "capital_repair_table")
        r1 = tc.post("/api/capital-repair-row", json={"plant": "BSP", "fy": "2026-27"})
    assert r1.status_code == 200, r1.text
    assert (spy.conns, spy.commits, spy.visible_mid_call) == (1, 1, [0, 0])   # INSERT, renumber UPDATE
    id1 = r1.json()["row"]["id"]

    r = tc.post("/api/capital-repair-entry", json={
        "id": id1, "shop": "BF", "equipment": "BF-4", "activity": "Reline",
        "unit_type": "BF", "unit_name": "BF-4"})
    assert r.status_code == 200, r.text
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "capital_repair_table")
        r2 = tc.post("/api/capital-repair-row", json={"plant": "BSP", "fy": "2026-27", "copy_from_id": id1})
    assert r2.status_code == 200, r2.text
    assert (spy.conns, spy.commits, spy.visible_mid_call) == (1, 1, [1, 1, 1])  # INSERT + 2 renumbers
    id2 = r2.json()["row"]["id"]
    assert r2.json()["row"]["equipment"] == "BF-4"

    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "capital_repair_table")
        r = tc.post("/api/capital-repair-entry", json={
            "id": id2, "unit_type": "BF", "unit_name": "BF-4", "actual_start": "2026-08-01",
            "actual_end": "2026-08-05", "planned_days": "10", "period": "Aug'26"})
    assert r.status_code == 200, r.text
    assert (spy.conns, spy.commits) == (1, 1)
    assert _rows("SELECT unit_type, unit_name, actual_start, actual_end, actual_ongoing, planned_days, period, "
                 "actual FROM capital_repair_table WHERE id=%s", (id2,)) == [
        ("BF", "BF-4", "2026-08-01", "2026-08-05", 0, 10.0, "Aug'26", r.json()["actual"])]
    assert tc.post("/api/capital-repair-entry", json={"id": 999999}).status_code == 404

    got = tc.get("/api/capital-repair", params={"plant": "BSP", "fy": "2026-27"}).json()["rows"]
    assert [g["id"] for g in got] == [id1, id2]

    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "capital_repair_table")
        r = tc.post("/api/capital-repair-reorder", json={"plant": "BSP", "fy": "2026-27", "ids": [id2, id1]})
    assert r.status_code == 200, r.text
    assert (spy.conns, spy.commits) == (1, 1)
    got = tc.get("/api/capital-repair", params={"plant": "BSP", "fy": "2026-27"}).json()["rows"]
    assert [g["id"] for g in got] == [id2, id1]
    assert tc.post("/api/capital-repair-reorder",
                   json={"plant": "BSP", "fy": "2026-27", "ids": [id1]}).status_code == 409

    # The CR with actual dates is a link candidate for a breakdown; link is validated.
    cands = tc.get("/api/breakdown/cr-candidates", params={"plant": "BSP", "start_ts": "2026-08-02 00:00"}).json()
    assert [c["id"] for c in cands["candidates"]] == [id2]
    bad = tc.post("/api/breakdown", json={"plant": "DSP", "unit_type": "BF", "unit_name": "BF-2",
                                          "start_ts": "2026-08-01 10:00", "end_ts": "2026-08-01 11:00",
                                          "cause": "x", "capital_repair_id": id2})
    assert bad.status_code == 400 and "BSP" in bad.json()["detail"]

    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "capital_repair_table")
        r = tc.delete(f"/api/capital-repair-row/{id1}")
    assert r.status_code == 200, r.text
    assert (spy.conns, spy.commits, spy.visible_mid_call) == (1, 1, [2, 2])   # DELETE, renumber
    assert [r[0] for r in _rows("SELECT id FROM capital_repair_table")] == [id2]
    assert tc.delete(f"/api/capital-repair-row/{id1}").status_code == 404


def test_production_loss_and_secretary_review_reads(tc):
    import api_production_loss as apl
    import page_secretary_review_texts as psrt
    import datetime as dt
    cr = tc.post("/api/capital-repair-row", json={"plant": "BSP", "fy": "2026-27"}).json()["row"]["id"]
    tc.post("/api/capital-repair-entry", json={"id": cr, "shop": "BF", "equipment": "BF-4",
                                               "unit_type": "BF", "unit_name": "BF-4",
                                               "actual_start": "2026-08-01", "actual_end": "2026-08-03"})
    rbd.save_breakdown_entry("BSP", "BF", "BF-6", None, "2026-08-10 10:00", None, True,
                             "cooling", None, "t@x")
    assert [r["equipment"] for r in apl._cr_rows_for_plant("BSP")] == ["BF-4"]
    assert [(r["unit_name"], r["is_ongoing"]) for r in apl._bd_rows_for_plant("BSP")] == [("BF-6", 1)]
    rmisc.save_major_unit_daily_record("BSP", "BF-4", 9000.0, "T", "2024-01-02", None, 0)
    assert apl._unit_weights("BSP")["BF"] == {"BF-4": 9000.0}
    with rc.cursor() as cur:
        assert [b["unit_name"] for b in psrt._fetch_breakdowns(cur, "2026-08")] == ["BF-6"]
        assert [c["equipment"] for c in psrt._fetch_cr(cur, "BSP", "2026-27", dt.date(2026, 8, 31))] == ["BF-4"]


# ── repo.misc: pdf_item_alias ────────────────────────────────────────────────

def test_pdf_item_alias_learn_and_lookup(tc):
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rmisc, "pdf_item_alias")
        r = tc.post("/api/save-item-alias", json={"plant": "DSP", "pdf_label": "1 nos total",
                                                  "item_name": "Oven Pushing(nos/d)", "convert_t": 1})
    assert r.status_code == 200, r.text
    assert (spy.conns, spy.commits, spy.visible_mid_call) == (1, 1, [0])
    db.save_pdf_item_alias("DSP", "HM prodn", "Hot Metal")
    db.save_pdf_item_alias("DSP", "HM prodn", "Hot Metal ", 0)        # re-learn overwrites
    db.save_pdf_item_alias("BSP", "HM prodn", "Hot Metal")
    # count-type items are forced to convert_t=0
    assert db.get_pdf_item_aliases("DSP") == {"1 nos total": ("Oven Pushing(nos/d)", 0),
                                              "HM prodn": ("Hot Metal ", 0)}
    assert db.get_pdf_item_aliases("BSP") == {"HM prodn": ("Hot Metal", 1)}
    assert db.get_pdf_item_aliases is rmisc.get_pdf_item_aliases
    assert db.save_pdf_item_alias is rmisc.save_pdf_item_alias


# ── repo.misc: cover_photos / report_cover_settings ─────────────────────────

def _jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (10, 20, 30)).save(buf, "JPEG")
    return buf.getvalue()


def test_cover_photo_upload_settings_save_and_remove(mysql_db, tmp_path, monkeypatch):
    import cover_store
    monkeypatch.setattr(cover_store, "PHOTO_DIR", str(tmp_path / "photos"))
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rmisc, "cover_photos")
        p = cover_store.add_photo(_jpeg(), "a.jpg", "u@x")
    assert spy.commits == 1 and spy.visible_mid_call == [0]
    design = [d for d in cover_store.cover_designs.DESIGN_IDS if d != "classic"][0]
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rmisc, "report_cover_settings")
        s = cover_store.save_setting("2026-08", design, "library", p["id"], "u@x")
    assert spy.commits == 1 and spy.visible_mid_call == [0]
    assert (s["design"], s["photo_mode"], s["photo_id"], s["updated_by"]) == (design, "library", p["id"], "u@x")
    cover_store.save_setting("2026-08", design, "random", None, "v@x")          # REPLACE overwrites
    assert _rows("SELECT report_month, photo_mode, photo_id, updated_by FROM report_cover_settings") == [
        ("2026-08", "random", p["id"], "v@x")]
    assert [(x["id"], x["used_by"]) for x in cover_store.list_photos()] == [(p["id"], 1)]
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rmisc, "cover_photos")
        assert cover_store.deactivate_photo(p["id"]) is True
    assert spy.commits == 1
    assert cover_store.list_photos() == [] and cover_store.get_photo(p["id"])["is_active"] == 0
    assert cover_store.deactivate_photo(999999) is False


# ── repo.misc: power_data_table ──────────────────────────────────────────────

def test_power_omi_insert_route_and_conflict(tc):
    recs = [{"report_month": "2026-08", "plant_name": "BSP", "item_name": "purchased_power", "value": 1.5},
            {"report_month": "2026-08", "plant_name": "DSP", "item_name": "purchased_power", "value": 2.5}]
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "power_data_table")
        r = tc.post("/api/power-omi/insert", json={"records": recs, "source_file": "p.xlsx"})
    assert r.status_code == 200, r.text
    # conflict check + insert: 2 conns, one commit after both rows
    assert (spy.conns, spy.commits, spy.visible_mid_call) == (2, 1, [0, 0])
    assert tc.post("/api/power-omi/insert", json={"records": recs[:1]}).status_code == 409
    recs[0]["value"] = 9.0
    assert tc.post("/api/power-omi/insert", json={"records": recs[:1], "confirm_replace": True}).status_code == 200
    assert _rows("SELECT plant_name, value FROM power_data_table ORDER BY plant_name") == [("BSP", 9.0), ("DSP", 2.5)]


# ── repo.misc: bf_benchmark_* ────────────────────────────────────────────────

def test_bf_benchmark_crud_routes(tc):
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "bf_benchmark_external_bf")
        r = tc.post("/api/bf-benchmark/external-bfs", json={"name": " JSW BF-3 ", "company": "JSW", "location": "VJN"})
    assert r.status_code == 200, r.text
    assert (spy.conns, spy.commits, spy.visible_mid_call) == (1, 1, [0])
    bf = r.json()["id"]
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "bf_benchmark_external_bf")
        assert tc.patch(f"/api/bf-benchmark/external-bfs/{bf}", json={"working_volume_m3": 4000}).status_code == 200
    assert (spy.conns, spy.commits) == (1, 1)
    assert tc.patch("/api/bf-benchmark/external-bfs/999999", json={"name": "x"}).status_code == 404

    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "bf_benchmark_external_data")
        r = tc.post(f"/api/bf-benchmark/external-bfs/{bf}/entry", json={"fy": "2025-26", "param_data": {"coke_rate": 380}})
    assert r.status_code == 200, r.text
    assert (spy.conns, spy.commits, spy.visible_mid_call) == (1, 1, [0])
    r = tc.post(f"/api/bf-benchmark/external-bfs/{bf}/entry",
                json={"fy": "2025-26", "param_data": {"coke_rate": None, "pci_rate": 150}})
    assert r.json()["param_data"] == {"coke_rate": 380, "pci_rate": 150}
    got = tc.get(f"/api/bf-benchmark/external-bfs/{bf}/entry", params={"fy": "2025-26"}).json()
    assert got["param_data"] == {"coke_rate": 380, "pci_rate": 150}
    lst = tc.get("/api/bf-benchmark/external-bfs").json()["external_bfs"]
    assert [(b["name"], b["working_volume_m3"], b["latest_fy"]) for b in lst] == [("JSW BF-3", 4000.0, "2025-26")]

    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "bf_benchmark_sail_meta")
        r = tc.patch("/api/bf-benchmark/sail-meta", json={"plant": "bsp", "unit": "BF-8", "working_volume_m3": 4060})
    assert r.status_code == 200, r.text
    assert (spy.conns, spy.commits, spy.visible_mid_call) == (1, 1, [0])
    tc.patch("/api/bf-benchmark/sail-meta", json={"plant": "BSP", "unit": "BF-8", "working_volume_m3": 4100})
    meta = tc.get("/api/bf-benchmark/sail-meta").json()["sail_meta"]
    assert [(m["plant"], m["unit"], m["working_volume_m3"]) for m in meta] == [("BSP", "BF-8", 4100.0)]
    params = tc.get("/api/bf-benchmark/params").json()
    assert {b["label"]: b["working_volume_m3"] for b in params["sail_bfs_all"]}["BSP BF-8"] == 4100.0
    import page_bf_large_annexure as pbl
    assert pbl._sail_static_working_volume("BSP", "BF-8") == 4100.0
    assert pbl._sail_static_working_volume("BSP", "BF-1") is None


# ── repo.misc: steel_sector_performance_table ───────────────────────────────

def test_steel_sector_performance_confirm_and_read(tc):
    import page_steel_sector_performance as pssp
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, db, "steel_sector_performance_table")
        r = tc.post("/api/steel-sector-performance/confirm",
                    json={"report_month": "2026-07", "source_file": "jpc.pdf", "tables": {}})
    assert r.status_code == 200, r.text
    assert (spy.conns, spy.commits, spy.visible_mid_call) == (1, 1, [0])
    tc.post("/api/steel-sector-performance/confirm", json={"report_month": "2026-07", "source_file": "v2.pdf", "tables": {}})
    data_month, _data, source_file = pssp._load_row("2026-09")[:3]
    assert (data_month, source_file) == ("2026-07", "v2.pdf")
    assert _rows("SELECT COUNT(*) FROM steel_sector_performance_table") == [(1,)]


# ── repo.misc: major_unit_daily_record / ready_reckoner_pages / rail ────────

def test_major_unit_ready_reckoner_and_rail_saves(tc):
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rmisc, "major_unit_daily_record")
        rmisc.save_major_unit_daily_record("BSP", "BF-8", 9100.0, "T", "2025-03-01", "rec", 2, "u@x")
    assert (spy.conns, spy.commits, spy.visible_mid_call) == (1, 1, [0])
    rmisc.save_major_unit_daily_record("BSP", "BF-8", 9200.0, "T", "2025-04-01", None, 2, "u@x")
    assert [(r["unit_label"], r["value"]) for r in db.get_major_unit_daily_records("BSP")] == [("BF-8", 9200.0)]
    assert db.get_major_unit_daily_records_all()["BSP"]["BF-8"]["record_date"] == "2025-04-01"

    db.upsert_ready_reckoner_master({"plant_code": "BSP", "plant_name": "Bhilai", "plant_group": "ISP", "sort_order": 1})
    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rmisc, "ready_reckoner_pages")
        db.save_ready_reckoner_content("BSP", capacity_rows=[{"item": "HM", "details": "", "capacity": "7.5",
                                                              "is_total": False}], updated_by="u@x")
    assert (spy.conns, spy.commits) == (1, 1)
    db.save_ready_reckoner_image("BSP", "x.png", "u@x")
    page = db.get_ready_reckoner_page("BSP")
    assert (page["capacity_rows"][0]["capacity"], page["product_mix_rows"], page["process_flow_image_path"]) == (
        "7.5", [], "x.png")
    assert [p["plant_code"] for p in db.get_ready_reckoner_pages()] == ["BSP"]
    assert tc.get("/api/ready-reckoner").json()["rows"][0]["plant_name"] == "Bhilai"

    with pytest.MonkeyPatch.context() as mp:
        spy = _spy(mp, rmisc, "rail_prod_despatch")
        r = tc.post("/api/rail-report/grid", json={"financial_year": "2025-26",
                                                    "rows": [{"metric": "prod", "value": "1.5", "note": " n "},
                                                             {"metric": "desp", "value": "-"}]})
    assert r.status_code == 200, r.text
    assert (spy.conns, spy.commits, spy.visible_mid_call) == (1, 1, [0, 0])
    assert db.get_rail_report_data(["2025-26", "2024-25"]) == {
        "2025-26": {"prod": {"value": 1.5, "note": "n"}, "desp": {"value": None, "note": None}}, "2024-25": {}}
    for name in ("get_rail_report_data", "save_rail_report_data", "get_ready_reckoner_pages",
                 "save_major_unit_daily_record", "upsert_ready_reckoner_master"):
        assert getattr(db, name) is getattr(rmisc, name)


# ── repo.ops: admin backup lock and table counts (never the real endpoints) ─

def test_admin_backup_lock_and_live_counts(mysql_db):
    import api_admin_backup as aab
    rbd.save_breakdown_entry("BSP", "BF", "BF-4", None, "2026-08-01 10:00", None, True, "x", None, "t@x")
    counts = aab._live_table_counts()
    assert counts["breakdown_table"] == 1 and counts["capital_repair_table"] == 0
    lock = aab._acquire_admin_lock()
    try:
        with pytest.raises(HTTPException) as e:
            aab._acquire_admin_lock()
        assert e.value.status_code == 409
    finally:
        aab._release_admin_lock(lock)
    again = aab._acquire_admin_lock()
    aab._release_admin_lock(again)
