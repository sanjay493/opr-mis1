"""
"Receipt, Consumption and Stocks of Coking Coal at Plants" — landscape page
reproducing Report_format/Coal_co2/Coal Format.pdf's OIS-2 table (SAIL-level
only, no plant breakdown — the source workbook doesn't carry one). Sourced
from techno_data (plant="SAIL", unit="Coal_Receipt_Stock"), populated by
api_coal_omi_techno.py — see techno_project/coal_omi_extractor.py's
extract_ois2 for the source workbook layout. Pure lookup/display: (A)/(B)
read the report month's own stored row verbatim; (C)'s month-wise stock
history is assembled by reading every FY-to-date month's OWN stored
snapshot (each month's Excel upload captures that month's stock as of the
column the extractor matched — see extract_ois2's docstring on why the
workbook's own multi-column stock history is NOT trustworthy enough to
read directly: stale/mismatched-year leftover columns are common) rather
than trusting the current file's own (often incomplete or stale) historical
columns — a month with no stored snapshot yet just renders blank in that
column instead of guessing.
"""
import db

_UNIT = "Coal_Receipt_Stock"


def generate_coal_receipts_sail(report_month: str) -> dict:
    stored = db.get_techno_data("SAIL", report_month, unit=_UNIT).get(_UNIT, {})
    m = stored.get("month") or {}

    receipt_rows = [
        {"label": "Indigenous Coal", "plan": m.get("receipt_plan_indigenous"), "actual": m.get("receipt_actual_indigenous")},
        {"label": "Imported Coal", "plan": m.get("receipt_plan_imported"), "actual": m.get("receipt_actual_imported")},
        {"label": "Total Coal", "plan": m.get("receipt_plan_total"), "actual": m.get("receipt_actual_total")},
    ]
    consumption_rows = [
        {"label": "Indigenous Coal", "actual": m.get("consumption_actual_indigenous"), "avg": m.get("consumption_avg_indigenous")},
        {"label": "Imported Coal", "actual": m.get("consumption_actual_imported"), "avg": m.get("consumption_avg_imported")},
        {"label": "Total Coal", "actual": m.get("consumption_actual_total"), "avg": m.get("consumption_avg_total")},
    ]

    stock_cols = []
    for ytd_month in db.get_ytd_months(report_month):
        ym = db.get_techno_data("SAIL", ytd_month, unit=_UNIT).get(_UNIT, {}).get("month") or {}
        as_of = ym.get("stock_as_of_month")
        date_label = None
        if as_of:
            y, mo, *_ = as_of.split("-")
            date_label = f"01-{mo}-{y[-2:]}"
        stock_cols.append({
            "date_label": date_label or "—",
            "indigenous": ym.get("stock_indigenous"),
            "imported": ym.get("stock_imported"),
            "total": ym.get("stock_total"),
        })

    return {
        "type": "coal_receipt_stock",
        "title": f"Receipt, Consumption and Stocks of Coking Coal at Plants during {_month_label(report_month)}",
        "receipt_rows": receipt_rows,
        "consumption_rows": consumption_rows,
        "stock_cols": stock_cols,
    }


_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_label(report_month: str) -> str:
    y, m = report_month.split("-")
    return f"{_MON_ABBR[int(m)]}'{y[-2:]}"
