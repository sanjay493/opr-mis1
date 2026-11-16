"""Mining leases API: the editor login on save, validation errors as 422, the read for the report."""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import api_mining_leases as api


def _row(**kw):
    base = {"s_no": "1", "mine": "K", "state": "", "lease": "L", "mineral": "", "area": "", "reserves": "",
            "status": "", "mine_span": 1, "state_span": 1, "lease_span": 1, "mineral_span": 1, "area_span": 1,
            "reserves_span": 1, "status_span": 1}
    base.update(kw)
    return base


@pytest.fixture
def store(monkeypatch):
    data = {"rows": [], "user": None}
    monkeypatch.setattr(api.mining_leases.rmines, "mining_leases_rows", lambda: list(data["rows"]))
    monkeypatch.setattr(api.mining_leases.rmines, "save_mining_leases",
                        lambda rows, u: data.update(rows=list(rows), user=u) or len(rows))
    return data


def test_save_needs_editor_login():
    app = FastAPI()
    app.include_router(api.router)
    assert TestClient(app).post("/api/mining-leases", json={"rows": []}).status_code == 401


def test_get_returns_rows(store):
    store["rows"] = [_row()]
    assert api.mining_leases_list()["rows"][0]["mine"] == "K"


def test_bad_span_422(store):
    with pytest.raises(HTTPException) as e:
        api.mining_leases_save({"rows": [_row(mine_span=3)]}, {"email": "e@sail.in"})
    assert e.value.status_code == 422 and "row 1" in e.value.detail and store["rows"] == []


def test_non_list_rows_422(store):
    with pytest.raises(HTTPException) as e:
        api.mining_leases_save({"rows": "x"}, {"email": "e@sail.in"})
    assert e.value.status_code == 422


def test_save_round_trip(store):
    out = api.mining_leases_save({"rows": [_row(mine_span=2), _row(s_no="2", mine="", mine_span=0)]},
                                 {"email": "e@sail.in"})
    assert out["status"] == "ok" and out["saved"] == 2 and store["user"] == "e@sail.in"
    assert [r["mine_span"] for r in out["rows"]] == [2, 0]
