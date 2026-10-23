"""api_mou_plan insert: 409 on existing values, upsert on confirm."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api_mou_plan
from v2dual import production_rows


@pytest.fixture
def client(mysql_db, monkeypatch):
    monkeypatch.setattr(api_mou_plan.rop, "log_extraction", lambda **kw: None)
    app = FastAPI()
    app.include_router(api_mou_plan.router)
    return TestClient(app), None


REC = [{"report_month": "2026-04", "plant_name": "BSP", "item_name": "Hot Metal", "value": 565.45}]


def test_insert_then_conflict_then_replace(client):
    tc, dbfile = client
    assert tc.post("/api/mou-plan/insert", json={"records": REC}).json()["saved"] == 1
    r = tc.post("/api/mou-plan/insert", json={"records": [dict(REC[0], value=600.0)]})
    assert r.status_code == 409
    r = tc.post("/api/mou-plan/insert", json={"records": [dict(REC[0], value=600.0)], "confirm_replace": True})
    assert r.status_code == 200
    assert production_rows("mou_plan_table") == [("2026-04", "BSP", "Hot Metal", 600.0)]


def test_insert_without_records_is_400(client):
    tc, _ = client
    assert tc.post("/api/mou-plan/insert", json={"records": []}).status_code == 400


def test_plant_outside_page4_sail_set_is_warned():
    recs = [{"report_month": "2026-04", "plant_name": "VISL", "item_name": "Pig Iron", "value": 2.0},
            {"report_month": "2026-04", "plant_name": "VISL", "item_name": "Total Crude Steel", "value": 0.0},
            {"report_month": "2026-04", "plant_name": "ASP", "item_name": "Total Crude Steel", "value": 1.0}]
    w = api_mou_plan.sail_set_warnings(recs)
    assert len(w) == 1 and "VISL" in w[0] and "Pig Iron" in w[0]
