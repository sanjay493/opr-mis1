"""
Cost Trend — "TREND IN COST OF PRODUCTION OF HOT METAL / CRUDE STEEL /
SALEABLE STEEL" (Report_format/COST TREND.xlsx, sheets HM/CS/SS) — 3 pages
inserted right after "SAIL Large BFs - Performance Snapshot" (page 3.6):
3.61 (Hot Metal), 3.62 (Crude Steel), 3.63 (Saleable Steel).

Each page reproduces its sheet's 3 blocks (Total/Variable/Fixed Cost), one
row per plant (BSP/DSP/RSP/BSL/ISP, plus the workbook's own "SAIL 5 ISPs"
aggregate row — entered directly like every other row, not computed, since
the source doesn't state whether it's a simple average or a weighted one),
with dynamic columns per direct instruction:
  - N closed FYs immediately before the report month's own FY (6, matching
    the source workbook's Apr'20-Mar'26 span for a Jul'26 report month —
    recalculated from report_month every time, never hardcoded to those
    specific years).
  - One column per current-FY month, April through the report month.
  - A final Apr-<report month> "till month" cumulative column (not in the
    source workbook, added per direct instruction alongside the monthly
    columns).

Data is 100% DB-sourced (db.cost_trend_annual / db.cost_trend_monthly),
entered via the Cost Trend Entry data-entry page (frontend/src/app/
data-entry/cost-trend) — nothing computed or hardcoded here; a period/
plant/cost-type with no entry shows "—". till_month is entered directly
(same convention as techno_data / Demurrage elsewhere in this app), not
auto-summed from the monthly columns, since a plant's own reported
cumulative doesn't always tie out to a clean sum of its monthly figures.
"""
import db

_PRODUCT_TITLE = {
    "HM": "TREND IN COST OF PRODUCTION OF HOT METAL",
    "CS": "TREND IN COST OF PRODUCTION OF CRUDE STEEL",
    "SS": "TREND IN COST OF PRODUCTION OF SALEABLE STEEL",
}
_COST_TYPE_LABEL = {"TOTAL": "TOTAL COST", "VARIABLE": "VARIABLE COST", "FIXED": "FIXED COST"}
_PLANT_LABEL = {"BSP": "BSP", "DSP": "DSP", "RSP": "RSP", "BSL": "BSL", "ISP": "ISP", "SAIL": "SAIL 5 ISPs"}

_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fmt(v):
    if v is None:
        return None
    return f"{v:,.0f}"


def _month_col_label(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    return f"{_MON_ABBR[mo]}-{y % 100:02d}"


def _ytd_col_label(ytd_months: list) -> str:
    y0, m0 = int(ytd_months[0][:4]), int(ytd_months[0][5:7])
    y1, m1 = int(ytd_months[-1][:4]), int(ytd_months[-1][5:7])
    if len(ytd_months) == 1:
        return f"{_MON_ABBR[m0]}'{y0 % 100:02d}"
    return f"{_MON_ABBR[m0]}-{_MON_ABBR[m1]}'{y1 % 100:02d}"


def _annual_fys(report_month: str, n: int = 6) -> list:
    """N full FY labels (e.g. "2020-21") for the N closed FYs immediately
    before report_month's own FY."""
    fy_start_year = int(db.get_fy_months(report_month)[0][:4])
    return [f"{y}-{(y + 1) % 100:02d}" for y in range(fy_start_year - n, fy_start_year)]


def generate_cost_trend(report_month: str, product: str) -> dict:
    fy_months = db.get_fy_months(report_month)
    ytd_months = [m for m in fy_months if m <= report_month]
    annual_fys = _annual_fys(report_month, 6)

    annual_data = db.get_cost_trend_annual(product, annual_fys)
    monthly_data = db.get_cost_trend_monthly(product, ytd_months)

    periods = (
        [{"key": f"annual:{fy}", "label": fy[2:], "kind": "annual"} for fy in annual_fys]
        + [{"key": f"month:{m}", "label": _month_col_label(m), "kind": "month"} for m in ytd_months]
        + [{"key": "till_month", "label": _ytd_col_label(ytd_months), "kind": "till"}]
    )

    blocks = []
    for cost_type in db.COST_TREND_COST_TYPES:
        rows = []
        for plant in db.COST_TREND_PLANTS:
            cells = {}
            for fy in annual_fys:
                cells[f"annual:{fy}"] = _fmt(annual_data.get(fy, {}).get(cost_type, {}).get(plant))
            for m in ytd_months:
                v = monthly_data.get(m, {}).get(cost_type, {}).get(plant, {}).get("month")
                cells[f"month:{m}"] = _fmt(v)
            tv = monthly_data.get(report_month, {}).get(cost_type, {}).get(plant, {}).get("till_month")
            cells["till_month"] = _fmt(tv)
            rows.append({"plant": _PLANT_LABEL[plant], "cells": cells})
        blocks.append({"label": _COST_TYPE_LABEL[cost_type], "rows": rows})

    return {
        "title": _PRODUCT_TITLE[product],
        "variant": "cost_trend",
        "unit": "Rs/T",
        "periods": periods,
        "blocks": blocks,
    }
