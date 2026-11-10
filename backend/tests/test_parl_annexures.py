"""Parliament annexures: periods, display rules, the deviation tolerance,
the history JSON and the API (validation, xlsx sheets) without the DB."""
import io

import openpyxl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api_parl_annexures as api
import parl_annexures as pa
import parl_annexures_export as px


def test_periods():
    assert pa.fy_of("2026-06") == "2026-27" and pa.fy_of("2027-02") == "2026-27"
    assert pa.period_months("2026-06") == ["2026-04", "2026-05", "2026-06"]
    assert len(pa.period_months("2027-03")) == 12 and pa.fy_months("2025-26")[-1] == "2026-03"
    L = pa.labels("2026-09")
    assert (L["span"], L["period"], L["cply_fy"]) == ("Apr-Sep", "2026-27(Apr-Sep'26)", "2025-26")


def test_pp_cells_mou_dash():
    v = {"cap": 1, "app": 2, "mou": None, "actual": 3, "ful_app": 4, "ful_mou": None, "gr": 5, "cu": 6}
    assert px.pp_cells("period", v) == [1, 2, "-", 3, 4, "-", 5, 6]
    assert px.pp_cells("period", dict.fromkeys(v)) == [None] * 8          # no data: blank
    assert px.fmt(-0.2) == "0" and px.fmt(2.456, 2) == "2.46"


def test_deviation_tolerance():
    assert not pa._differs(1579.0, 1578.904, 0.01)       # integer workbook figure: rounding only
    assert pa._differs(1578.729, 1578.904, 0.01)
    assert not pa._differs(20483.3324, 20483.333, 0.01)  # 3-decimal DB noise
    assert not pa._differs(None, 5.0, 0.01)


def test_source_by_fy(monkeypatch):
    monkeypatch.setattr(pa, "history", lambda: {"db_from_fy": "2022-23"})
    assert pa._pick("2021-22", 2.0, 1.0) == (1.0, "history")
    assert pa._pick("2022-23", 2.0, 1.0) == (2.0, "db")
    assert pa._pick("2022-23", None, 1.0) == (1.0, "history")   # DB lacks it: workbook
    assert pa._pick("2021-22", 2.0, None) == (2.0, "db")


def test_history_json_shape():
    h = pa.history()
    pp = h["production_performance"]["plants"]
    assert set(pa.PP_PLANTS) <= set(pp) and "2025-26" in pp["SAIL"]
    assert set(pp["SAIL"]["2025-26"]) == {"hm", "cs", "ss"}
    assert set(h["production_history"]) == {"hm", "cs", "ss", "pig_iron"}
    assert set(h["techno_history"]) == {"bf_productivity", "coke_rate", "energy"}


FAKE = {
    "production_history": {
        "report": "production_history", "years": 2, "deviations": [],
        "labels": {**pa.labels("2026-06"), "title": "PRODUCTION", "unit": "u", "org": "o", "company": "c"},
        "fys": ["2024-25", "2025-26"],
        "items": [{"key": "hm", "label": "HOT METAL", "rows": [
            {"plant": "BSP", "fys": [1.0, 2.0], "cy": 3.0, "cply": 2.0, "gr": 50.0, "total": False}]}],
    },
}


@pytest.fixture
def tc(monkeypatch):
    monkeypatch.setattr(api.pa, "build", lambda r, m, y=None: FAKE["production_history"])
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


@pytest.mark.parametrize("url", [
    "/api/parl-annexures/production-history?month=2026-13",
    "/api/parl-annexures/production-history?month=2026-06&years=0",
    "/api/parl-annexures/nope?month=2026-06",
    "/api/parl-annexures/all?month=2026-06",          # "all" is downloads only
])
def test_bad_params(tc, url):
    assert tc.get(url).status_code in (400, 404, 422)


def test_xlsx_sheet_and_data_check(tc):
    r = tc.get("/api/parl-annexures/production-history/xlsx?month=2026-06&years=2")
    assert r.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["ProdHIS", "Data check"]
    vals = [c.value for row in wb["ProdHIS"].iter_rows() for c in row]
    assert "Apr-Jun" in vals and "SAIL" not in vals and 50.0 in vals
