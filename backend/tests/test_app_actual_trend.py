"""APP / MoU vs Actual performance trend (app_actual_trend.py), on a fake
repo.production.values (no DB)."""

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

import api_app_actual_trend as api
import app_actual_trend as t

FY = 2026
LABELS = ["Apr-26", "May-26", "Jun-26", "Q1", "Jul-26", "Aug-26", "Sep-26", "Q2", "H1",
          "Oct-26", "Nov-26", "Dec-26", "Q3", "Jan-27", "Feb-27", "Mar-27", "Q4", "H2", "2026-27"]


def fake_values(months, plants, items, measure):
    """Plan 100 for every plant/item/month (VISL Hot Metal 0); actual 90 for
    Apr-Oct only, none for VISL Hot Metal; Pig Iron actual 10 at BSP only;
    no MoU at all."""
    out = {}
    if measure == "mou":
        return out
    for m in months:
        for p in plants:
            for i in items:
                if measure == "abp":
                    out[(m, p, i)] = 0.0 if (p == "VISL" and i == "Hot Metal") else 100.0
                elif "2026-04" <= m <= "2026-10" and not (p == "VISL" and i == "Hot Metal"):
                    if i != "Pig Iron":
                        out[(m, p, i)] = 90.0
                    elif p == "BSP":
                        out[(m, p, i)] = 10.0
    return out


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(t.rp, "values", fake_values)


def _row(rep, item, plant):
    sec = next(s for s in rep["sections"] if s["item"] == item)
    return next(r for r in sec["rows"] if r["plant"] == plant)


def test_columns_include_quarters_and_halves():
    assert [c["label"] for c in t.columns(FY)] == LABELS
    cols = t.columns(FY)
    assert cols[8]["months"] == t.fy_months(FY)[:6] and cols[17]["months"] == t.fy_months(FY)[6:]


def test_rows_per_section(fake):
    rep = t.build(FY, "app")
    plants = {s["item"]: [r["plant"] for r in s["rows"]] for s in rep["sections"]}
    assert plants["Hot Metal"] == ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL-5 PL", "VISL", "SAIL"]
    for item in ("Crude Steel", "Saleable Steel", "Saleable production"):
        assert plants[item] == ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL-5 PL", "ASP", "SSP", "VISL", "SAIL"]
    assert plants["Finished Steel"] == ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL-5 PL", "ASP", "SSP", "VISL",
                                        "SAIL", "Conversion", "SAIL incl. Conv."]


def test_finished_steel_conversion(fake):
    rep = t.build(FY, "app")
    conv = _row(rep, "Finished Steel", "Conversion")
    assert conv["plan"][0] is None and conv["act"][0] == 90 and conv["pct"][0] is None
    incl = _row(rep, "Finished Steel", "SAIL incl. Conv.")
    assert incl["plan"][0] == 800 and incl["act"][0] == 8 * 90 + 90
    assert _row(rep, "Finished Steel", "SAIL")["act"][0] == 8 * 90


def test_values_totals_and_blanks(fake):
    rep = t.build(FY, "app")
    bsp = _row(rep, "Hot Metal", "BSP")
    i = {lab: k for k, lab in enumerate(LABELS)}
    assert bsp["plan"][i["Apr-26"]] == 100 and bsp["plan"][i["Q1"]] == 300
    assert bsp["plan"][i["H1"]] == 600 and bsp["plan"][i["2026-27"]] == 1200
    assert bsp["act"][i["Oct-26"]] == 90 and bsp["act"][i["Nov-26"]] is None    # no data: blank
    assert bsp["act"][i["Q3"]] == 90 and bsp["act"][i["Q4"]] is None
    assert bsp["act"][i["H2"]] == 90 and bsp["act"][i["2026-27"]] == 630
    assert bsp["pct"][i["Apr-26"]] == 90 and bsp["pct"][i["Nov-26"]] is None
    assert bsp["pct"][i["Q3"]] == pytest.approx(30)
    assert _row(rep, "Hot Metal", "SAIL-5 PL")["plan"][0] == 500
    assert _row(rep, "Hot Metal", "SAIL")["plan"][0] == 500           # + VISL's 0
    visl = _row(rep, "Hot Metal", "VISL")
    assert visl["plan"][0] == 0 and visl["act"][0] is None and visl["pct"][0] is None
    assert _row(rep, "Crude Steel", "SAIL")["plan"][0] == 800          # 5 PL + ASP, SSP, VISL


def test_saleable_production_adds_pig_iron(fake):
    rep = t.build(FY, "app")
    assert _row(rep, "Saleable production", "BSP")["act"][0] == 100     # 90 SS + 10 PI
    assert _row(rep, "Saleable production", "BSP")["plan"][0] == 200    # 100 SS + 100 PI
    assert _row(rep, "Saleable production", "DSP")["act"][0] == 90
    assert _row(rep, "Saleable Steel", "BSP")["act"][0] == 90


def test_mou_without_data_is_blank(fake):
    rep = t.build(FY, "mou")
    assert rep["plan_label"] == "MoU" and not rep["has_plan"]
    assert all(v is None for s in rep["sections"] for r in s["rows"] for v in r["plan"] + r["pct"])


def test_html_and_xlsx(fake):
    rep = t.build(FY, "app")
    html = t.build_html(rep, {})
    assert html.count('class="sheet"') == 3 and "Finished Steel" in html and ">H2<" in html
    wb = load_workbook(io.BytesIO(t.build_xlsx(rep, {})))
    ws = wb.active
    assert [ws.cell(3, 4 + k).value for k in range(len(LABELS))] == LABELS
    assert ws.cell(4, 2).value == "BSP" and ws.cell(4, 3).value == "APP" and ws.cell(4, 4).value == 100
    assert ws.cell(5, 4 + LABELS.index("Nov-26")).value is None


def test_api(fake, monkeypatch):
    app = FastAPI()
    app.include_router(api.router)
    tc = TestClient(app)
    assert tc.get("/api/app-actual-trend?fy=2026&basis=x").status_code == 400
    assert tc.get("/api/app-actual-trend?fy=26").status_code == 400
    d = tc.get("/api/app-actual-trend?fy=2026&basis=mou").json()
    assert d["plan_label"] == "MoU" and len(d["sections"]) == 5
    r = tc.get("/api/app-actual-trend/xlsx?fy=2026")
    assert r.status_code == 200
    assert 'filename="APP_Vs_Actual_Performance_Trend_2026-27.xlsx"' in r.headers["content-disposition"]
    monkeypatch.setattr(t, "render_pdf", lambda html: b"%PDF")
    r = tc.get("/api/app-actual-trend/pdf?fy=2026&basis=mou")
    assert r.content == b"%PDF" and "MoU_Vs_Actual" in r.headers["content-disposition"]
