"""Plant performance API: basis/decimals validation and the two-sheet xlsx."""
import io

import openpyxl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api_plant_performance as app_mod

ROW = {"item": "HOT METAL", "plant": "BSP", "capacity": 7000.0,
       "values": [6688.1476, 565.4525, 500.12345, -65.33, 88.4, 520.0, -3.8, 85.0,
                  2800.0, 2700.5, -99.5, 96.4, 2600.0, 3.9, 90.0],
       "is_conversion": False, "is_sail_incl_conv": False}


@pytest.fixture
def tc(monkeypatch):
    monkeypatch.setattr(app_mod, "_rows", lambda month, basis: [dict(ROW)])
    monkeypatch.setattr(app_mod.db, "init_db", lambda: None)
    app = FastAPI()
    app.include_router(app_mod.router)
    return TestClient(app)


def test_json_basis(tc):
    d = tc.get("/api/plant-performance-main-items?month=2026-08&basis=mou").json()
    assert d["labels"]["basis"] == "MoU" and d["has_plan"] is True


@pytest.mark.parametrize("q", ["basis=abp", "decimals=4", "decimals=x", "decimals=-1"])
def test_bad_params_400(tc, q):
    path = "" if q.startswith("basis") else "/xlsx"
    assert tc.get(f"/api/plant-performance-main-items{path}?month=2026-08&{q}").status_code in (400, 422)


def test_xlsx_two_sheets_with_decimals(tc):
    r = tc.get("/api/plant-performance-main-items/xlsx?month=2026-08&decimals=1")
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["w.r.t APP", "w.r.t MoU"]
    ws = wb["w.r.t MoU"]
    assert ws.cell(3, 4).value.startswith("MoU")
    assert ws.cell(5, 6).number_format == "#,##0.0"
    assert ws.cell(5, 8).number_format == "0"


def test_pdf_html_has_both_pages():
    import plant_performance_pdf as ppdf
    sec = {"labels": {**app_mod._labels("2026-08", "app")}, "pct_idx": sorted(app_mod.PCT_IDX),
           "rows": [dict(ROW)], "has_plan": True}
    sec2 = {**sec, "labels": app_mod._labels("2026-08", "mou")}
    html = ppdf.build_html([sec, sec2], 2, {"perf_app_bg": "#111111"})
    assert html.count('class="sheet"') == 2 and "w.r.t MoU" in html and "500.12" in html and "#111111" in html


def test_pdf_small_negative_pct_is_zero():
    import plant_performance_pdf as ppdf
    assert ppdf._p(-0.3) == "0" and ppdf._p(-0.6) == "-1"
