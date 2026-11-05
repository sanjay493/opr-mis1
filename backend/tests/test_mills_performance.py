"""SAIL Mill Production Performance (mills_performance.py), on a fake
repo.production.values and capacity lookup (no DB)."""

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

import api_mills_performance as api
import mills_performance as mp

FY = 2026
LABELS = ["Apr'26", "May'26", "Jun'26", "Q-1", "Jul'26", "Aug'26", "Sep'26", "Q-2", "H-1",
          "Oct'26", "Nov'26", "Dec'26", "Q-3", "Jan'27", "Feb'27", "Mar'27", "Q-4", "H-2", "2026-27",
          "Apr-Oct'26"]


def fake_values(months, plants, items, measure):
    """APP 100 for every mill and month except DSP SM (no rows); actual 4.25
    for Apr-Oct, none at DSP SM."""
    out = {}
    for m in months:
        for p in plants:
            for i in items:
                if p == "DSP" and i == "SM":
                    continue
                if measure == "abp":
                    out[(m, p, i)] = 100.0
                elif measure == "actual" and "2026-04" <= m <= "2026-10":
                    out[(m, p, i)] = 4.25
    return out


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(mp.rp, "values", fake_values)
    caps = {("BSP", "Finished Steel"): 4900.0, ("BSP", "WIRERODS"): 600.0}
    monkeypatch.setattr(mp.rcap, "get_effective_capacity", lambda p, i, m: caps.get((p, i)))


def _mill(rep, plant, mill):
    return next(r for p in rep["plants"] if p["plant"] == plant for r in p["mills"] if r["mill"] == mill)


def test_columns_and_mills(fake):
    rep = mp.build(FY)
    assert [c["label"] for c in rep["columns"]] == LABELS
    assert all("days" not in c for c in rep["columns"])
    assert [p["plant"] for p in rep["plants"]] == ["BSP", "DSP", "RSP", "BSL", "ISP"]
    assert sum(len(p["mills"]) for p in rep["plants"]) == 21
    assert [m["mill"] for m in rep["plants"][1]["mills"]] == ["MSM", "MM", "W&A"]   # Section Mill: no data
    assert rep["plants"][0]["capacity"] == "4900" and rep["plants"][1]["capacity"] is None


def test_capacity_db_over_sheet(fake):
    rep = mp.build(FY)
    assert _mill(rep, "BSP", "WRM")["capacity"] == "600"
    assert _mill(rep, "BSP", "PM")["capacity"] == "1300 (1000)"


def test_values_totals_and_blanks(fake):
    rep = mp.build(FY)
    i = {lab: k for k, lab in enumerate(LABELS)}
    wrm = _mill(rep, "BSP", "WRM")
    assert wrm["plan"][i["Q-1"]] == 300 and wrm["plan"][i["2026-27"]] == 1200
    assert wrm["plan"][i["Apr-Oct'26"]] == 700 and wrm["act"][i["Apr-Oct'26"]] == pytest.approx(7 * 4.25)
    assert wrm["act"][i["Nov'26"]] is None and wrm["pct"][i["Nov'26"]] is None
    assert wrm["act"][i["Q-4"]] is None and wrm["act"][i["H-2"]] == 4.25
    assert wrm["pct"][0] == pytest.approx(4.25)


def test_fmt():
    assert mp.fmt(4.25, "m", "act") == "4.2" and mp.fmt(4.25, "q", "act") == "4"
    assert mp.fmt(95.6, "m", "pct") == "96" and mp.fmt(None, "m", "plan") == ""
    assert mp.fmt(-0.01, "m", "act") == "0.0"
    assert mp.cap_lines("1300 (1000)") == ["1300", "(1000)"] and mp.cap_lines("550") == ["550"]
    assert mp.cap_lines(None) == []


def test_no_actuals_no_cum_column(monkeypatch):
    monkeypatch.setattr(mp.rp, "values", lambda months, plants, items, measure: {})
    monkeypatch.setattr(mp.rcap, "get_effective_capacity", lambda p, i, m: None)
    rep = mp.build(FY)
    assert rep["columns"][-1]["label"] == "2026-27" and not rep["has_plan"] and rep["plants"] == []


def test_html_and_xlsx(fake):
    rep = mp.build(FY)
    html = mp.build_html(rep, {})
    assert "SAIL Mill Production Performance for FY 2026-27" in html and "(excluding SM)" in html
    ws = load_workbook(io.BytesIO(mp.build_xlsx(rep, {}))).active
    assert [ws.cell(3, 5 + k).value for k in range(len(LABELS))] == LABELS
    assert ws.cell(4, 2).value == "WRM" and ws.cell(4, 4).value == "Plan" and ws.cell(4, 5).value == 100
    assert ws.cell(5, 5).value == 4.2 and ws.cell(5, 5 + LABELS.index("Nov'26")).value is None


def test_api(fake, monkeypatch):
    app = FastAPI()
    app.include_router(api.router)
    tc = TestClient(app)
    assert tc.get("/api/mills-performance?fy=26").status_code == 400
    assert len(tc.get("/api/mills-performance?fy=2026").json()["plants"]) == 5
    r = tc.get("/api/mills-performance/xlsx?fy=2026")
    assert r.status_code == 200 and 'filename="Mills_Performance_2026-27.xlsx"' in r.headers["content-disposition"]
    monkeypatch.setattr(mp, "render_pdf", lambda html: b"%PDF")
    assert tc.get("/api/mills-performance/pdf?fy=2026").content == b"%PDF"
