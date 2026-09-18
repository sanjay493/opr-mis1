"""
Steel Sales Performance — report-month and YTD Key Performance Parameter
bullet lists (STEEL_SALES_PAGE_ID in main.py, inserted right after "SAIL
Performance - 1 Page Summary"). Modeled on Report_format/
RMT_0109_partial.pdf's "<Mon>'YY Key Performance Parameters" / "<Apr-Mon>'YY
Key Performance Parameters" pages, with a constant page title ("Steel Sales
Performance") plus two sub-headings naming the two periods — per direct
instruction, 2026-09-18 — rather than the period name doubling as the page
title.

The bullet text itself (Cash Collection, Total Sales, Tier-1/Tier-2 sales,
despatch/dispatch figures, etc.) is a Marketing/Sales analyst's monthly
bulletin, not derivable from any table this app already has — entered via
/data-entry/steel-sales-highlights (editor/admin only — see
api_steel_sales_highlights.py) and read straight from steel_sales_highlights
(db.get_steel_sales_highlights) for report_month. Only the two sub-headings
("Report Month i.e. <Mon YYYY>" / "Apr - <Mon YYYY>") are computed here from
report_month, so the same saved bullets always show under the right
month/YTD label. Sections show empty until an editor has entered something
for that month.
"""
import datetime as _dt

import db


def _month_label(report_month: str) -> str:
    dt = _dt.datetime.strptime(report_month, "%Y-%m")
    return dt.strftime("%b %Y")


def _ytd_label(report_month: str) -> str:
    ytd_months = db.get_ytd_months(report_month)
    end = _month_label(report_month)
    if len(ytd_months) <= 1:
        return f"Apr - {end}"
    start = _dt.datetime.strptime(ytd_months[0], "%Y-%m").strftime("%b")
    return f"{start} - {end}"


def generate_steel_sales_performance(report_month: str) -> dict:
    month_label = _month_label(report_month)
    ytd_label = _ytd_label(report_month)

    saved = db.get_steel_sales_highlights(report_month) or {"month_items": [], "ytd_items": []}

    return {
        "type": "steel_sales_performance",
        "title": "Steel Sales Performance",
        "month_heading": f"Report Month i.e. {month_label}",
        "ytd_heading": ytd_label,
        "month_items": saved["month_items"],
        "ytd_items": saved["ytd_items"],
    }
