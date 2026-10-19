"""Routes whose techno tables (techno_param, techno_param_group, techno_actuals)
no longer exist. Their responses are pinned to what they returned on MySQL
before the dead code paths were deleted (MySQL-only, Task 2)."""
import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def tc(mysql_db, monkeypatch):
    # Skip the editor/admin session gate on write routes.
    monkeypatch.setattr(main, "_is_gated", lambda method, path: False)
    return TestClient(main.app, raise_server_exceptions=False)


def _prod_rows():
    conn = main.db.connect()
    rows = conn.execute("SELECT report_month, plant_name, item_name, month_actual "
                        "FROM production_table").fetchall()
    conn.close()
    return [tuple(r) for r in rows]


def test_techno_groups_is_500(tc):
    r = tc.get("/api/techno-groups")
    assert r.status_code == 500
    assert r.text == "Internal Server Error"


def test_techno_monthly_data_is_empty(tc):
    r = tc.get("/api/techno-monthly-data", params={"group_code": "MAJOR", "month": "2026-04"})
    assert r.status_code == 200
    assert r.json() == {"group_code": "MAJOR", "month": "2026-04", "sections": []}


def test_sail_sms_params_is_empty(tc):
    r = tc.get("/api/sail-sms-params", params={"month": "2026-04"})
    assert r.status_code == 200
    assert r.json() == {"month": "2026-04", "sail_params": {}}
    assert tc.get("/api/sail-sms-params", params={"month": "April"}).status_code == 500


def test_techno_manual_save_counts_but_stores_nothing(tc):
    rows = [
        {"param_id": 1, "actual": "5.5"},
        {"param_id": 2, "till_month_actual": 3},
        {"param_id": 3, "clear": True},
        {"param_id": None, "actual": 1},
        {"param_id": 4, "actual": "-"},
    ]
    r = tc.post("/api/techno-manual-save", json={"month": "2026-04", "rows": rows})
    assert r.status_code == 200
    assert r.json() == {"status": "success", "saved": 2, "cleared": 0,
                        "message": "Saved 2 value(s), cleared 0 value(s) for 2026-04."}
    assert tc.post("/api/techno-manual-save", json={"month": "2026-04", "rows": []}).status_code == 400


PROD = [{"item_name": "Hot Metal", "value": 123.5}]


def test_confirm_extraction_ignores_legacy_techno_rows(tc):
    r = tc.post("/api/confirm-extraction", json={
        "month": "2026-04", "plant": "BSP", "production_rows": PROD,
        "techno_rows": [{"parameter": "Coke Rate", "month_actual": 400}],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["saved_production"] == 1 and body["saved_techno"] == 0
    assert _prod_rows() == [("2026-04", "BSP", "Hot Metal", 123.5)]


def test_confirm_extraction_techno_param_rows_fail_after_production_commit(tc, mysql_db):
    r = tc.post("/api/confirm-extraction", json={
        "month": "2026-04", "plant": "BSP", "production_rows": PROD,
        "techno_param_rows": [{"group_code": "MAJOR", "section": "Coke Rate",
                               "parameter": "BSP", "actual": 400}],
    })
    assert r.status_code == 500
    assert r.json() == {"detail": "Insertion failed: OperationalError: "
                                  f"(1146, \"Table '{mysql_db}.techno_param' doesn't exist\")"}
    # The production rows were committed before the failure, as before.
    assert _prod_rows() == [("2026-04", "BSP", "Hot Metal", 123.5)]


def test_confirm_extraction_techno_param_rows_without_values_are_skipped(tc):
    r = tc.post("/api/confirm-extraction", json={
        "month": "2026-04", "plant": "BSP", "production_rows": PROD,
        "techno_param_rows": [{"group_code": "MAJOR", "section": "Coke Rate", "parameter": "BSP"}],
    })
    assert r.status_code == 200
    assert r.json()["saved_mill_techno"] == 0
