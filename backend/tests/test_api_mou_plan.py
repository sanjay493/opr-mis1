"""api_mou_plan insert: 409 on existing values, upsert on confirm."""
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api_mou_plan


@pytest.fixture
def client(tmp_path, monkeypatch):
    dbfile = tmp_path / "mou.db"
    c = sqlite3.connect(dbfile)
    c.execute("CREATE TABLE mou_plan_table (report_month TEXT, plant_name TEXT, item_name TEXT, "
              "month_actual REAL, PRIMARY KEY (report_month, plant_name, item_name))")
    c.commit()
    c.close()

    class _Conn:
        def __init__(self):
            self._c = sqlite3.connect(dbfile)

        def cursor(self):
            return self._c.cursor()

        def commit(self):
            self._c.commit()

        def close(self):
            self._c.close()

    monkeypatch.setattr(api_mou_plan.db, "connect", _Conn)
    monkeypatch.setattr(api_mou_plan.db, "log_extraction", lambda **kw: None)
    app = FastAPI()
    app.include_router(api_mou_plan.router)
    return TestClient(app), dbfile


REC = [{"report_month": "2026-04", "plant_name": "BSP", "item_name": "Hot Metal", "value": 565.45}]


def test_insert_then_conflict_then_replace(client):
    tc, dbfile = client
    assert tc.post("/api/mou-plan/insert", json={"records": REC}).json()["saved"] == 1
    r = tc.post("/api/mou-plan/insert", json={"records": [dict(REC[0], value=600.0)]})
    assert r.status_code == 409
    r = tc.post("/api/mou-plan/insert", json={"records": [dict(REC[0], value=600.0)], "confirm_replace": True})
    assert r.status_code == 200
    rows = sqlite3.connect(dbfile).execute("SELECT month_actual FROM mou_plan_table").fetchall()
    assert rows == [(600.0,)]


def test_insert_without_records_is_400(client):
    tc, _ = client
    assert tc.post("/api/mou-plan/insert", json={"records": []}).status_code == 400
