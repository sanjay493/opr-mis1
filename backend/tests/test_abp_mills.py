"""ABP Saleable Steel & Mills performance (abp_mills.py), on a fake repo (no DB)."""

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

import abp_mills as t
import api_abp_mills as api

FIVE = ["BSP", "DSP", "RSP", "BSL", "ISP"]
ACT_MONTHS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]


def _fy_of(month):
    return int(month[:4]) - (int(month[5:7]) < 4)


def _actual(m, p, i):
    """FY 2026 runs Apr-Oct. Finished 80 and Saleable 100 a month in past FYs
    from 2022 (70 / 100 in FY 2026). BSP WIRERODS: 30 a month, 40 in FY 2024,
    50 in FY 2010, rising 10..70 in FY 2026. BSP MM: 20 a month in FY 2023, 3
    months only in FY 2024. RSP HSM-2 sale all of FY 2025, plate none till 2026."""
    fy = _fy_of(m)
    if fy == 2026 and m not in ACT_MONTHS:
        return None
    if i == "Finished Steel":
        return 70.0 if fy == 2026 else 80.0 if fy >= 2022 else None
    if i == "Saleable Steel":
        return 100.0 if fy >= 2022 else None
    if p == "BSP" and i == "WIRERODS":
        if fy == 2026:
            return 10.0 * (ACT_MONTHS.index(m) + 1)
        return {2010: 50.0, 2024: 40.0}.get(fy, 30.0 if fy >= 2022 else None)
    if p == "BSP" and i == "MM":
        if fy == 2023:
            return 20.0
        return 500.0 if m in ("2024-04", "2024-05", "2024-06") else None
    if p == "RSP" and i == "HSM-2 HR Coil (Sale)":
        return 90.0 if fy in (2025, 2026) else None
    if p == "RSP" and i == "HSM-2 HR Plate":
        return 10.0 if fy == 2026 else None
    return None


def fake_values(months, plants, items, measure):
    out = {}
    for m in months:
        for p in plants:
            for i in items:
                if measure == "actual":
                    v = _actual(m, p, i)
                    if v is not None:
                        out[(m, p, i)] = v
                elif measure == "abp" and _fy_of(m) == 2026:
                    v = {"Finished Steel": 90.0, "Saleable Steel": 120.0}.get(i)
                    if p == "BSP" and i == "WIRERODS":
                        v = 50.0
                    if v is not None:
                        out[(m, p, i)] = v
    return out


def fake_op(months, plants):
    rows = [("2026-11", "BSP", "WIRERODS", 70.0)]
    return [r for r in rows if r[0] in months and r[1] in plants]


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(t.rp, "values", fake_values)
    monkeypatch.setattr(t.rp, "op_plan_month_rows", fake_op)
    monkeypatch.setattr(t, "get_effective_capacity",
                        lambda p, i, m: {"BSP": 4900.0, "DSP": 1392.0, "RSP": 4306.0, "BSL": 4200.0, "ISP": 2300.0}[p]
                        if m >= "2026-04" else None)


def _plant(rep, name):
    return next(p for p in rep["plants"] if p["plant"] == name)


def _row(rep, plant, label):
    return next(r for r in _plant(rep, plant)["rows"] if r["label"] == label)


def test_rows_follow_the_format_including_rows_with_no_db_item(fake):
    rep = t.build(2026)
    assert [p["plant"] for p in rep["plants"]] == FIVE + ["5 Plants"]
    assert [r["label"] for r in _plant(rep, "DSP")["rows"]] == [
        "MM", "SM(150)", "MSM", "WAP", "SPU Kandrori", "SPU Jagdishpur",
        "Finished Steel", "Semis", "Saleable Steel", "% Finished Steel"]
    assert [r["label"] for r in _plant(rep, "BSL")["rows"]][-4:] == [
        "Finished Steel", "Slabs", "Saleable Steel", "% Finished Steel"]
    assert "GP/GC Sheets(120)" in [r["label"] for r in _plant(rep, "RSP")["rows"]]
    assert [r["label"] for r in _plant(rep, "5 Plants")["rows"]] == [
        "Finished Steel", "Semis for sale", "Saleable Steel", "% Finished Steel"]


def test_a_row_with_no_db_item_is_blank_but_present(fake):
    r = _row(t.build(2026), "DSP", "SPU Kandrori")
    assert r["past"] == [None, None, None, None]
    assert r["abp"] is None and r["likely"] is None and r["best_month"] is None


def test_past_columns_are_the_four_fys_before_the_selected_one(fake):
    rep = t.build(2026)
    assert rep["past_labels"] == ["22-23", "23-24", "24-25", "25-26"]
    assert _row(rep, "BSP", "WRM")["past"] == [360.0, 360.0, 480.0, 360.0]


def test_likely_is_actual_then_running_month_op_then_app(fake):
    rep = t.build(2026)
    r = _row(rep, "BSP", "WRM")
    assert r["abp"] == 600.0
    assert r["likely"] == 280.0 + 70.0 + 4 * 50.0
    assert rep["likely_label"] == "Apr-Oct'26 act + Nov'26 OP + Dec'26-Mar'27 APP"


def test_item_without_op_uses_app_for_the_running_month_and_is_listed(fake):
    rep = t.build(2026)
    assert _row(rep, "BSP", "Finished Steel")["likely"] == 490.0 + 5 * 90.0
    assert "BSP: Finished Steel" in rep["op_missing"]
    assert "BSP: WRM" not in rep["op_missing"]


def test_best_month_is_from_the_selected_fy_for_mills_only(fake):
    rep = t.build(2026)
    assert _row(rep, "BSP", "WRM")["best_month"] == 70.0
    assert _row(rep, "BSP", "Finished Steel")["best_month"] is None


def test_best_achieved_is_the_highest_full_fy_before_the_selected_one(fake):
    r = _row(t.build(2026), "BSP", "WRM")
    assert (r["best_act"], r["best_period"]) == (600.0, "10-11")
    # Selecting FY 2010 itself must not count it, or anything after it.
    r = _row(t.build(2010), "BSP", "WRM")
    assert (r["best_act"], r["best_period"]) == (None, "")


def test_a_part_year_is_hidden_and_never_the_best(fake):
    r = _row(t.build(2026), "BSP", "MM")
    assert r["past"] == [None, 240.0, None, None]   # 3 months of 500 in FY 2024
    assert (r["best_act"], r["best_period"]) == (240.0, "23-24")


def test_a_summed_row_is_hidden_unless_every_item_has_the_full_year(fake):
    r = _row(t.build(2026), "RSP", "HSM-2(Coils/Plts/shts)")
    assert r["past"][3] is None                     # FY 2025: coil full, plate none
    assert r["best_month"] == 100.0                 # the items add up within a month


def test_semis_and_percent_finished_derive_from_finished_and_saleable(fake):
    rep = t.build(2026)
    assert _row(rep, "BSP", "Semis")["past"][0] == 240.0
    assert _row(rep, "BSP", "Semis")["abp"] == 1440.0 - 1080.0
    assert _row(rep, "BSP", "Semis")["likely"] == 1300.0 - 940.0
    pct = _row(rep, "BSP", "% Finished Steel")
    assert pct["past"][0] == pytest.approx(960 / 1200 * 100)
    assert pct["likely"] == pytest.approx(940 / 1300 * 100)


def test_five_plants_add_up_and_their_best_is_a_common_full_fy(fake):
    rep = t.build(2026)
    fs = _row(rep, "5 Plants", "Finished Steel")
    assert fs["capacity"] == 17098.0
    assert fs["past"] == [4800.0] * 4
    assert fs["abp"] == 5 * 1080.0
    assert fs["likely"] == 5 * 940.0
    assert (fs["best_act"], fs["best_period"]) == (4800.0, "25-26")   # ties go to the latest
    assert _row(rep, "5 Plants", "Semis for sale")["likely"] == 5 * 360.0


def test_capacity_comes_from_the_format_for_mills_and_the_db_for_finished_steel(fake):
    rep = t.build(2026)
    assert _row(rep, "BSP", "PM")["capacity"] == 1000.0
    assert _row(rep, "BSP", "Finished Steel")["capacity"] == 4900.0
    assert _row(t.build(2025), "BSP", "Finished Steel")["capacity"] is None
    assert _row(t.build(2025), "BSP", "PM")["capacity"] == 1000.0


def test_a_completed_fy_is_likely_its_actual_with_no_plan(fake):
    rep = t.build(2025)
    r = _row(rep, "BSP", "Saleable Steel")
    assert r["likely"] == 1200.0 and r["abp"] is None
    assert rep["has_plan"] is False


def test_xlsx_writes_values_at_the_chosen_decimals_and_colours_the_saleable_row(fake):
    ws = load_workbook(io.BytesIO(t.build_xlsx(t.build(2026), {}, 2))).active
    row = next(c.row for r in ws.iter_rows() for c in r if c.value == "WRM")
    assert ws.cell(row, 3).value == 550.0
    assert ws.cell(row, 4).number_format == "0.00"
    assert ws.cell(row, 11).value == 550.0                     # Likely
    sale = next(c.row for r in ws.iter_rows() for c in r if c.value == "Saleable Steel")
    assert ws.cell(sale, 2).fill.fgColor.rgb[-6:] == "FFFF00"


def test_html_prints_figures_at_the_chosen_decimals(fake):
    rep = t.build(2026)
    assert ">550.00<" in t.build_html(rep, {}, 2)
    assert ">550<" in t.build_html(rep, {}, 0)


@pytest.fixture
def client(fake):
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_api_serves_json_and_xlsx(client):
    assert client.get("/api/abp-mills?fy=2026").json()["fy_label"] == "2026-27"
    res = client.get("/api/abp-mills/xlsx?fy=2026&decimals=3")
    assert res.status_code == 200
    assert 'filename="Saleable_Steel_Mills_Performance_2026-27.xlsx"' in res.headers["content-disposition"]


@pytest.mark.parametrize("url", ["/api/abp-mills/xlsx?fy=2026&decimals=4", "/api/abp-mills?fy=20"])
def test_api_rejects_out_of_range_inputs(client, url):
    assert client.get(url).status_code == 400
