"""ABP production projection (abp_projection.py), on a fake repo (no DB)."""

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

import abp_projection as t
import api_abp_projection as api

FIVE = ["BSP", "DSP", "RSP", "BSL", "ISP"]
FY_2026_ACT = dict(zip(["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"],
                       [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0]))
PAST_MONTHLY = {2023: 50.0, 2024: 60.0, 2025: 40.0}


def _fy_of(month):
    return int(month[:4]) - (int(month[5:7]) < 4)


def fake_values(months, plants, items, measure):
    """Five plants: FY 2026 actual per FY_2026_ACT, APP 150 and MoU 200 a
    month. Others: actual 10, APP 20, MoU 25, except VISL Hot Metal (APP 0, no
    actual). Past FYs: actual only, 600 / 720 / 480 a year at the five plants.
    Plans exist only for FY 2026, as in the live DB."""
    out = {}
    for m in months:
        fy = _fy_of(m)
        for p in plants:
            for i in items:
                five = p in FIVE
                if measure == "actual":
                    if fy == 2026 and m in FY_2026_ACT:
                        if five:
                            out[(m, p, i)] = FY_2026_ACT[m]
                        elif not (p == "VISL" and i == "Hot Metal"):
                            out[(m, p, i)] = 10.0
                    elif fy in PAST_MONTHLY and five:
                        out[(m, p, i)] = PAST_MONTHLY[fy]
                elif fy == 2026:
                    if p == "VISL" and i == "Hot Metal":
                        out[(m, p, i)] = 0.0
                    elif measure == "abp":
                        out[(m, p, i)] = 150.0 if five else 20.0
                    else:
                        out[(m, p, i)] = 200.0 if five else 25.0
    return out


def fake_op(months, plants):
    """Only BSP Hot Metal has an OP for Nov-26; Oct-26's must never be used."""
    rows = [("2026-10", "BSP", "Hot Metal", 999.0), ("2026-11", "BSP", "Hot Metal", 300.0)]
    return [r for r in rows if r[0] in months and r[1] in plants]


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(t.rp, "values", fake_values)
    monkeypatch.setattr(t.rp, "op_plan_month_rows", fake_op)
    monkeypatch.setattr(t, "get_effective_capacity",
                        lambda p, i, m: 1000.0 if p in FIVE and m >= "2026-04" else None)


def _row(rep, item, plant):
    sec = next(s for s in rep["sections"] if s["item"] == item)
    return next(r for r in sec["rows"] if r["plant"] == plant)


def test_rows_follow_the_format_and_finished_steel_stops_at_five_plants(fake):
    rep = t.build(2026)
    assert {s["item"]: [r["plant"] for r in s["rows"]] for s in rep["sections"]} == {
        "Hot Metal": FIVE + ["SAIL-5 PL", "VISL", "SAIL"],
        "Crude Steel": FIVE + ["SAIL-5 PL", "ASP", "SSP", "VISL", "SAIL"],
        "Saleable Steel": FIVE + ["SAIL-5 PL", "ASP", "SSP", "VISL", "SAIL"],
        "Finished Steel": FIVE + ["SAIL-5 PL"],
    }


def test_mid_fy_projection_is_actual_then_running_month_op_then_app(fake):
    r = _row(t.build(2026), "Hot Metal", "BSP")
    assert r["ytd"] == 910.0
    assert r["projection"] == 910.0 + 300.0 + 4 * 150.0
    assert r["proj_app"] == pytest.approx(1810 / 1800 * 100)
    assert r["proj_mou"] == pytest.approx(1810 / 2400 * 100)


def test_plant_without_op_uses_app_for_the_running_month_and_is_listed(fake):
    rep = t.build(2026)
    assert _row(rep, "Hot Metal", "DSP")["projection"] == 910.0 + 5 * 150.0
    assert "Hot Metal: DSP" in rep["op_missing"]
    assert not any("BSP" in x and x.startswith("Hot Metal") for x in rep["op_missing"])


def test_zero_app_plant_without_op_is_not_listed_as_missing(fake):
    assert not any("VISL" in x for x in t.build(2026)["op_missing"] if x.startswith("Hot Metal"))


def test_prorated_scales_actual_by_calendar_days(fake):
    r = _row(t.build(2026), "Hot Metal", "BSP")
    # Apr-Oct = 214 days of a 365-day FY
    assert r["prorated"] == pytest.approx(910 * 365 / 214)
    assert r["pro_app"] == pytest.approx(910 * 365 / 214 / 1800 * 100)


def test_prorated_counts_the_leap_february(monkeypatch):
    # FY 2027-28: 366 days. Apr-27 alone is 30 days.
    def values(months, plants, items, measure):
        return {("2027-04", "BSP", "Hot Metal"): 30.0} if measure == "actual" and "2027-04" in months else {}
    monkeypatch.setattr(t.rp, "values", values)
    monkeypatch.setattr(t.rp, "op_plan_month_rows", lambda m, p: [])
    monkeypatch.setattr(t, "get_effective_capacity", lambda p, i, m: None)
    assert _row(t.build(2027), "Hot Metal", "BSP")["prorated"] == pytest.approx(366.0)


def test_best_month_and_avg_of_three_come_from_the_selected_fy_only(fake):
    r = _row(t.build(2026), "Hot Metal", "BSP")
    assert (r["best"], r["avg3"]) == (160.0, 150.0)


def test_totals_add_the_plants(fake):
    rep = t.build(2026)
    pl5 = _row(rep, "Crude Steel", "SAIL-5 PL")
    sail = _row(rep, "Crude Steel", "SAIL")
    assert pl5["app"] == 5 * 1800.0
    assert pl5["best"] == 5 * 160.0           # the sum of plant bests, not a joint month
    assert pl5["avg3"] == 5 * 150.0
    assert sail["ytd"] == 5 * 910.0 + 3 * 70.0
    assert sail["projection"] == 5 * (910.0 + 5 * 150.0) + 3 * (70.0 + 5 * 20.0)
    assert sail["proj_app"] == pytest.approx(sail["projection"] / (5 * 1800 + 3 * 240) * 100)


def test_past_years_are_the_three_before_the_selected_fy_with_max_flagged(fake):
    rep = t.build(2026)
    assert rep["past_labels"] == ["23-24", "24-25", "25-26"]
    r = _row(rep, "Hot Metal", "BSP")
    assert r["past"] == [600.0, 720.0, 480.0]
    assert r["past_max"] == [False, True, False]


def test_past_max_flags_ties_but_not_an_all_zero_or_empty_row(monkeypatch, fake):
    assert t._past_max([5.0, 5.0, 1.0]) == [True, True, False]
    assert t._past_max([0.0, 0.0, 0.0]) == [False, False, False]
    assert t._past_max([None, None, None]) == [False, False, False]
    assert t._past_max([None, 3.0, None]) == [False, True, False]


def test_labels_describe_the_mid_fy_basis(fake):
    rep = t.build(2026)
    assert rep["ytd_label"] == "Apr-Oct'26"
    assert rep["projection_label"] == "Apr-Oct'26 act + Nov'26 OP + Dec'26-Mar'27 APP"
    assert rep["title"] == "SAIL Production Projection for FY 2026-27"


def test_a_completed_fy_projects_its_actual_and_has_no_plan_percentages(fake):
    rep = t.build(2025)
    r = _row(rep, "Hot Metal", "BSP")
    assert r["ytd"] == r["projection"] == 480.0
    assert r["prorated"] == pytest.approx(480.0)
    assert r["app"] is None and r["mou"] is None
    assert r["proj_app"] is None and r["pro_mou"] is None
    assert rep["has_plan"] is False
    assert rep["projection_label"] == "Apr-Mar'26 act"


def test_an_fy_with_no_actuals_projects_its_plan_and_has_no_prorated(monkeypatch, fake):
    def only_plan(months, plants, items, measure):
        return {} if measure == "actual" else fake_values(months, plants, items, measure)
    monkeypatch.setattr(t.rp, "values", only_plan)
    r_rep = t.build(2026)
    r = _row(r_rep, "Hot Metal", "BSP")
    assert r["ytd"] is None and r["best"] is None and r["prorated"] is None
    assert r["projection"] == 1800.0
    assert r_rep["ytd_label"] == ""
    assert r_rep["projection_label"] == "Apr'26-Mar'27 APP"


def test_running_month_without_any_op_is_labelled_app(monkeypatch, fake):
    monkeypatch.setattr(t.rp, "op_plan_month_rows", lambda m, p: [])
    assert t.build(2026)["projection_label"] == "Apr-Oct'26 act + Nov'26-Mar'27 APP"


def test_capacities_installed_from_config_operating_from_db(fake):
    rep = t.build(2026)
    r = _row(rep, "Hot Metal", "BSP")
    assert (r["installed"], r["operating"]) == (7220.0, 1000.0)
    assert _row(rep, "Crude Steel", "SAIL")["installed"] == 20442.0
    assert _row(rep, "Saleable Steel", "SAIL")["installed"] == 19978.0
    assert _row(rep, "Finished Steel", "BSP")["installed"] is None
    assert _row(rep, "Finished Steel", "SAIL-5 PL")["installed"] is None
    assert _row(rep, "Hot Metal", "SAIL-5 PL")["operating"] == 5000.0


def test_xlsx_writes_values_at_the_chosen_decimals_and_marks_the_best_year(fake):
    rep = t.build(2026)
    ws = load_workbook(io.BytesIO(t.build_xlsx(rep, {}, 2))).active
    cells = {(c.row, c.column): c for row in ws.iter_rows() for c in row}
    bsp = next(k[0] for k, c in cells.items() if c.value == "BSP")
    assert ws.cell(bsp, 3).value == 7220.0
    assert ws.cell(bsp, 5).number_format == "0.00"
    assert ws.cell(bsp, 6).fill.fgColor.rgb[-6:] == "92D050"     # 24-25, the max
    assert ws.cell(bsp, 5).fill.fgColor.rgb[-6:] != "92D050"
    assert ws.cell(bsp, 13).value == 1810.0                      # Projection


def test_html_prints_figures_at_the_chosen_decimals(fake):
    rep = t.build(2026)
    assert ">1810.00<" in t.build_html(rep, {}, 2)
    assert ">1810<" in t.build_html(rep, {}, 0)
    assert "Apr-Oct&#x27;26" in t.build_html(rep, {}, 0)


@pytest.fixture
def client(fake):
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_api_serves_json_and_xlsx(client):
    assert client.get("/api/abp-projection?fy=2026").json()["fy_label"] == "2026-27"
    res = client.get("/api/abp-projection/xlsx?fy=2026&decimals=3")
    assert res.status_code == 200
    assert 'filename="ABP_Production_Projection_2026-27.xlsx"' in res.headers["content-disposition"]


@pytest.mark.parametrize("url", [
    "/api/abp-projection/xlsx?fy=2026&decimals=4",
    "/api/abp-projection/xlsx?fy=2026&decimals=-1",
    "/api/abp-projection?fy=20",
])
def test_api_rejects_out_of_range_inputs(client, url):
    assert client.get(url).status_code == 400
