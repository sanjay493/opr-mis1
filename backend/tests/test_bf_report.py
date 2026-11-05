"""BF Parameters report: layout against the format sheet, and its figures."""
import io

import openpyxl
import pytest
from openpyxl.utils import get_column_letter as col_letter

import bf_report


@pytest.fixture
def db(monkeypatch):
    blobs = {
        ("2026-04", "BSP", "BF-8"): {"month": {"coke_rate": 400, "hot_blast_temp": 1100, "bf_productivity": 2.0},
                                     "till_month": {"coke_rate": 401}},
        ("2026-05", "BSP", "BF-8"): {"month": {"coke_rate": 500, "hot_blast_temp": 1200, "slag_rate": 300}},
        ("2026-06", "BSP", "BF-8"): {"month": {"slag_rate": 600}},
        ("2026-04", "BSP", "BF_Shop"): {"month": {"coke_rate": 420, "hot_blast_temp": 1000, "bf_productivity": 2.0}},
        ("2026-04", "ISP", "BF-5"): {"month": {"coke_rate": 360, "hot_blast_temp": 1200, "bf_productivity": 4.0,
                                               "silicon_in_hm": 0.8}},
        ("2026-04", "RSP", "BF_Shop"): {"month": {"pellet_in_burden": 20, "silicon_in_hm": 0.6}},
        ("2026-05", "SAIL", "BF_Shop"): {"month": {"coke_rate": 999}},
        ("2025-03", "DSP", "BF-3"): {"till_month": {"coke_rate": 470}},
    }
    actual = {("2026-04", "BSP", "BF#8"): 100.0, ("2026-05", "BSP", "BF#8"): 300.0, ("2026-06", "BSP", "BF#8"): 100.0,
              ("2026-04", "BSP", "BF#4"): 100.0, ("2026-04", "ISP", "Hot Metal"): 200.0,
              ("2026-04", "BSL", "BF#3"): 50.0, ("2026-04", "BSP", "BF#1"): 0.0,
              ("2026-04", "BSP", "Hot Metal"): 210.0, ("2026-04", "RSP", "Hot Metal"): 100.0,
              ("2026-04", "DSP", "Hot Metal"): 100.0}
    abp = {("2026-04", "BSP", "BF#8"): 80.0, ("2026-05", "BSP", "BF#8"): 400.0, ("2026-06", "BSP", "BF#8"): 20.0,
           ("2026-07", "BSP", "BF#8"): 500.0, ("2026-04", "BSP", "Hot Metal"): 300.0,
           ("2026-04", "ISP", "Hot Metal"): 100.0}
    plans = {"BSP": {"BF-8": {"data": {"coke_rate": {"value": 366}, "cdi": {"value": 150},
                                       "hot_blast_temp": {"value": 1000}}}}}
    monkeypatch.setattr(bf_report.rt, "blobs", lambda months, plants, units: blobs)
    monkeypatch.setattr(bf_report.rp, "values",
                        lambda months, plants, items, measure: actual if measure == "actual" else abp)
    monkeypatch.setattr(bf_report.rt, "get_techno_plan", lambda plant, fy: plans.get(plant, {}))
    monkeypatch.setattr(bf_report.rt, "get_sail_techno_plan", lambda fy: {"data": {
        "Coke Rate": 400, "Nut Coke Rate": 16, "CDI Rate": 119, "BF Productivity": 2.24}})
    return bf_report.build(2026)


def _row(rep, plant, bf):
    return next(r for r in rep["rows"] if r["plant"] == plant and r["bf"] == bf)


def _cell(rep, row, section, **match):
    sec = next(s for s in rep["sections"] if s["key"] == section)
    i = next(i for i, c in enumerate(sec["columns"]) if all(c.get(k) == v for k, v in match.items()))
    return row["sections"][section]["cells"][i]


def test_column_layout_matches_the_format_sheet(db):
    ws = openpyxl.load_workbook(io.BytesIO(bf_report.build_xlsx(db))).active
    # Each section starts in the format sheet's column, up to the removed
    # Pellet (Kg/THM) block (IK:JD); Pellet(%) takes its place and ends at JA.
    starts = [c.column_letter for c in ws[5] if c.value]
    assert starts == ["J", "AI", "BG", "CE", "DC", "DZ", "EW", "FU", "GR", "HO", "IK"]
    assert col_letter(ws.max_column) == "JA"
    assert ws["S6"].value == " APP\n26-27" and ws["R6"].value == "25-26" and ws["J6"].value == "17-18"
    assert ws["T6"].number_format == "mmm\\'yy" and ws["AF6"].value == "Cum"
    assert ws["DB6"].value == "% \nefficiency"
    assert ws.freeze_panes == "D8"


def test_static_data_comes_from_the_json(db):
    bf8 = _row(db, "BSP", "8")
    assert bf8["static"]["working_volume"] == 3445 and bf8["static"]["tuyeres"] == 36
    assert bf8["static"]["cast_houses"] == "Circular"


def test_rows_hidden_on_the_format_appear_only_with_data(db):
    assert "3" in [r["bf"] for r in db["rows"] if r["plant"] == "BSL"]      # has production in the FY
    assert "1" not in [r["bf"] for r in db["rows"] if r["plant"] == "BSP"]


def test_production_sums_and_percent_of_app_to_date(db):
    bf8 = _row(db, "BSP", "8")
    assert _cell(db, bf8, "production", kind="cum") == 500
    assert _cell(db, bf8, "production", kind="app") == 1000
    assert bf8["sections"]["production"]["pct"] == pytest.approx(500 / 500 * 100)
    assert _cell(db, _row(db, "BSP", "Shop"), "production", month="2026-04") == 210    # the plant's Hot Metal


def test_missing_values_stay_blank_not_zero(db):
    bf8 = _row(db, "BSP", "8")
    assert _cell(db, bf8, "slag", month="2026-04") is None
    assert _cell(db, bf8, "pellet_pct", kind="cum") is None


def test_cum_uses_till_month_else_production_weighted_else_hbt_average(db):
    bf8 = _row(db, "BSP", "8")
    assert _cell(db, bf8, "coke", kind="cum") == 401
    assert _cell(db, bf8, "slag", kind="cum") == pytest.approx((300 * 300 + 600 * 100) / 400)
    assert _cell(db, bf8, "hbt", kind="cum") == 1150
    assert bf8["sections"]["hbt"]["pct"] == pytest.approx(115)
    assert _cell(db, _row(db, "DSP", "3"), "coke", fy=2024) == 470
    assert _cell(db, bf8, "fuel", kind="app") == 516       # coke + CDI, as the sheet


def test_narrow_drops_chosen_rows_and_columns_and_keeps_the_rest_aligned(db):
    full_cum = _cell(db, _row(db, "BSP", "8"), "production", kind="cum")
    rep = bf_report.narrow(db, hide_rows=["BSP:BF-4", "BSP:BF-8"], hide_fys=[2025], hide_months=["04"])
    assert not [r for r in rep["rows"] if r["id"] in ("BSP:BF-4", "BSP:BF-8")]
    for sec in rep["sections"]:
        labels = [c["label"] for c in sec["columns"]]
        assert "25-26" not in labels and "Apr'26" not in labels and "May'26" in labels and "Cum" in labels
        for row in rep["rows"]:
            assert len(row["sections"][sec["key"]]["cells"]) == len(labels)
    shop = _row(rep, "BSP", "Shop")
    assert _cell(rep, shop, "production", month="2026-05") == 300     # still covers the hidden furnace
    assert _cell(rep, _row(rep, "SAIL", ""), "production", kind="cum") == _cell(db, _row(db, "SAIL", ""), "production", kind="cum")
    assert full_cum == 500 and _cell(db, _row(db, "BSP", "8"), "production", month="2026-04") == 100    # db untouched


def test_narrow_recounts_the_merged_plant_cell(db):
    rep = bf_report.narrow(db, hide_rows=["BSP:BF-4"])
    bsp = [r for r in rep["rows"] if r["plant"] == "BSP"]
    assert bsp[0]["plant_span"] == len(bsp) and all(r["plant_span"] == 0 for r in bsp[1:])


def test_narrowed_excel_builds_with_only_the_chosen_section(db):
    rep = bf_report.narrow(db, hide_rows=["BSP:BF-4"], hide_fys=range(2017, 2026), sections=["coke"])
    ws = openpyxl.load_workbook(io.BytesIO(bf_report.build_xlsx(rep))).active
    assert [c.value for c in ws[5] if c.value] == ["Coke Rate(Kg/THM)"]
    assert ws["J6"].value == " APP\n26-27" and ws["K6"].number_format == "mmm\\'yy"


def test_a_shop_without_hot_metal_falls_back_to_its_furnaces(db):
    assert _cell(db, _row(db, "BSL", "Shop"), "production", month="2026-04") == 50


def test_sail_follows_page_27(db):
    sail = _row(db, "SAIL", "")
    # BSP 210, DSP 100, RSP 100, BSL 50 (its furnaces), ISP 200
    assert _cell(db, sail, "production", month="2026-04") == 660
    assert _cell(db, sail, "coke", month="2026-04") == pytest.approx((420 * 210 + 360 * 200) / 410, abs=1e-3)
    assert _cell(db, sail, "productivity", month="2026-04") == pytest.approx(410 / (210 / 2 + 200 / 4), abs=1e-3)
    assert _cell(db, sail, "hbt", month="2026-04") == 1100          # plain average
    assert _cell(db, sail, "si", month="2026-04") == pytest.approx(0.7)     # rule: plain average


def test_stored_sail_value_wins(db):
    assert _cell(db, _row(db, "SAIL", ""), "coke", month="2026-05") == 999


def test_dsp_pellet_counts_as_zero_in_sail(db):
    # RSP 20 at weight 100 and DSP's blank as 0 at weight 100
    assert _cell(db, _row(db, "SAIL", ""), "pellet_pct", month="2026-04") == pytest.approx(10)
    assert _cell(db, _row(db, "SAIL", ""), "pellet_pct", month="2026-11") is None    # nobody reported


def test_sail_app_is_the_stored_plan(db):
    sail = _row(db, "SAIL", "")
    assert _cell(db, sail, "coke", kind="app") == 400
    assert _cell(db, sail, "productivity", kind="app") == 2.24
    assert _cell(db, sail, "fuel", kind="app") == 535       # coke + nut coke + CDI
