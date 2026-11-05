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
        ("2026-04", "ISP", "BF-5"): {"month": {"coke_rate": 360, "hot_blast_temp": 1200, "bf_productivity": 4.0}},
        ("2025-03", "DSP", "BF-3"): {"till_month": {"coke_rate": 470}},
    }
    actual = {("2026-04", "BSP", "BF#8"): 100.0, ("2026-05", "BSP", "BF#8"): 300.0, ("2026-06", "BSP", "BF#8"): 100.0,
              ("2026-04", "BSP", "BF#4"): 100.0, ("2026-04", "ISP", "Hot Metal"): 200.0,
              ("2026-04", "BSL", "BF#3"): 50.0, ("2026-04", "BSP", "BF#1"): 0.0}
    abp = {("2026-04", "BSP", "BF#8"): 80.0, ("2026-05", "BSP", "BF#8"): 400.0, ("2026-06", "BSP", "BF#8"): 20.0,
           ("2026-07", "BSP", "BF#8"): 500.0, ("2026-04", "BSP", "Hot Metal"): 300.0,
           ("2026-04", "ISP", "Hot Metal"): 100.0}
    plans = {"BSP": {"BF-8": {"data": {"coke_rate": {"value": 366}, "cdi": {"value": 150},
                                       "hot_blast_temp": {"value": 1000}}}}}
    monkeypatch.setattr(bf_report.rt, "blobs", lambda months, plants, units: blobs)
    monkeypatch.setattr(bf_report.rp, "values",
                        lambda months, plants, items, measure: actual if measure == "actual" else abp)
    monkeypatch.setattr(bf_report.rt, "get_techno_plan", lambda plant, fy: plans.get(plant, {}))
    return bf_report.build(2026)


def _row(rep, plant, bf):
    return next(r for r in rep["rows"] if r["plant"] == plant and r["bf"] == bf)


def _cell(rep, row, section, **match):
    sec = next(s for s in rep["sections"] if s["key"] == section)
    i = next(i for i, c in enumerate(sec["columns"]) if all(c.get(k) == v for k, v in match.items()))
    return row["sections"][section]["cells"][i]


def test_column_layout_matches_the_format_sheet(db):
    ws = openpyxl.load_workbook(io.BytesIO(bf_report.build_xlsx(db))).active
    # Each section starts in the format sheet's column; the last one ends at JU.
    starts = [c.column_letter for c in ws[5] if c.value]
    assert starts == ["J", "AI", "BG", "CE", "DC", "DZ", "EW", "FU", "GR", "HO", "IK", "JE"]
    assert col_letter(ws.max_column) == "JU"
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
    assert _cell(db, _row(db, "BSP", "Shop"), "production", month="2026-04") == 200    # sum of furnaces


def test_missing_values_stay_blank_not_zero(db):
    bf8 = _row(db, "BSP", "8")
    assert _cell(db, bf8, "slag", month="2026-04") is None
    assert _cell(db, bf8, "pellet_kg", kind="cum") is None


def test_cum_uses_till_month_else_production_weighted_else_hbt_average(db):
    bf8 = _row(db, "BSP", "8")
    assert _cell(db, bf8, "coke", kind="cum") == 401
    assert _cell(db, bf8, "slag", kind="cum") == pytest.approx((300 * 300 + 600 * 100) / 400)
    assert _cell(db, bf8, "hbt", kind="cum") == 1150
    assert bf8["sections"]["hbt"]["pct"] == pytest.approx(115)
    assert _cell(db, _row(db, "DSP", "3"), "coke", fy=2024) == 470
    assert _cell(db, bf8, "fuel", kind="app") == 516       # coke + CDI, as the sheet


def test_sail_row_follows_the_sheet_formulas(db):
    sail = _row(db, "SAIL", "")
    assert _cell(db, sail, "production", month="2026-04") == 450     # BSP 200, ISP 200, BSL 50
    assert _cell(db, sail, "coke", month="2026-04") == pytest.approx((420 * 200 + 360 * 200) / 400)
    assert _cell(db, sail, "productivity", month="2026-04") == pytest.approx(400 / (200 / 2 + 200 / 4))
    assert _cell(db, sail, "hbt", month="2026-04") == 1100
