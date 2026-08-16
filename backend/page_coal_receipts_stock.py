"""
"Receipt, Consumption and Stocks of Coking Coal at Plants" — landscape page
reproducing Report_format/Coal_co2/Coal Format.pdf's OIS-2 table (SAIL-level
only, no plant breakdown — the source workbook doesn't carry one). Sourced
from techno_data (plant="SAIL", unit="Coal_Receipt_Stock"), populated by
api_coal_omi_techno.py — see techno_project/coal_omi_extractor.py's
extract_ois2 for the source workbook layout. Pure lookup/display: (A)/(B)
read the report month's own stored row verbatim; (C)'s month-wise stock
history is assembled by reading every one of the report month's FY's 13
month-start snapshots' OWN stored data (each month's Excel upload captures
that month's stock as of the column the extractor matched — see
extract_ois2's docstring on why the workbook's own multi-column stock
history is NOT trustworthy enough to read directly: stale/mismatched-year
leftover columns are common) rather than trusting the current file's own
(often incomplete or stale) historical columns — a month with no stored
snapshot yet (including any not-yet-reached this FY) is OMITTED from table
(C) entirely rather than shown as a blank column, so the table only ever
grows out to whatever's actually been reported.
"""
import db

_UNIT = "Coal_Receipt_Stock"


def _stock_col(month: str) -> dict:
    ym = db.get_techno_data("SAIL", month, unit=_UNIT).get(_UNIT, {}).get("month") or {}
    as_of = ym.get("stock_as_of_month")
    date_label = None
    if as_of:
        y, mo, *_ = as_of.split("-")
        date_label = f"01-{mo}-{y[-2:]}"
    else:
        # Nothing stored for this month yet — still needed as a fallback
        # label for the has_data check below to key off of, even though a
        # column with no data at all never actually renders (see
        # generate_coal_receipts_sail's filtering).
        y, mo = month.split("-")
        date_label = f"01-{mo}-{y[-2:]}"
    indigenous, imported, total = ym.get("stock_indigenous"), ym.get("stock_imported"), ym.get("stock_total")
    return {
        "date_label": date_label,
        "indigenous": indigenous,
        "imported": imported,
        "total": total,
        "has_data": indigenous is not None or imported is not None or total is not None,
    }


def _fy_stock_months(report_month: str) -> list:
    """The 13 month-start snapshots Report_format/Coal_co2/Coal Format.pdf's
    table (C) shows for report_month's FY: April of that FY through April of
    the NEXT FY (13, not 12 — the last column is next FY's opening stock,
    equivalently this FY's own March closing stock, shown as its own
    column rather than folded into a 12-wide grid). Static per FY, not
    per report_month within it — switching the report month to a
    different month in the SAME FY shows the same 13 columns; switching to
    a month in a DIFFERENT FY shows that FY's own 13."""
    fy_months = db.get_fy_months(report_month)  # 12 months, Apr..Mar
    # fy_months[-1] is always March (get_fy_months always ends the FY
    # there) — the following April falls in that SAME calendar year, no
    # year rollover needed.
    next_year = fy_months[-1].split("-")[0]
    return fy_months + [f"{next_year}-04"]


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

    # Split into the same two blocks the reference PDF prints as two
    # separate stacked mini-tables — first 6 FY months (Apr-Sep), then the
    # remaining 7 (Oct through next FY's Apr) — per direct instruction,
    # matching the reference's layout. Within each block, a column only
    # renders if that month actually has stock data — no more padding out
    # to a fixed 13-column calendar grid with blank placeholders for
    # months nobody's reported yet: an April report_month, whose own file
    # is the only one on record, shows only the 1-2 columns that are
    # actually populated (see _stock_col's has_data), not all 6.
    fy_stock_months = _fy_stock_months(report_month)
    row1_raw = [_stock_col(mo) for mo in fy_stock_months[:6]]
    row2_raw = [_stock_col(mo) for mo in fy_stock_months[6:]]

    stock_cols_1 = [c for c in row1_raw if c["has_data"]]
    stock_cols_2 = [c for c in row2_raw if c["has_data"]]

    # Where row 1's own gap (splitting Apr-Jun from Jul-Sep) belongs among
    # the now-filtered columns — only shown when there's at least one real
    # column on BOTH sides of that split; an all-empty second half (the
    # ordinary case for most of the year) means no gap at all, just the
    # populated columns with nothing following them.
    n_before_gap = sum(1 for c in row1_raw[:3] if c["has_data"])
    stock_gap_after = n_before_gap if 0 < n_before_gap < len(stock_cols_1) else None

    return {
        "type": "coal_receipt_stock",
        "title": f"Receipt, Consumption and Stocks of Coking Coal at Plants during {_month_label(report_month)}",
        "receipt_rows": receipt_rows,
        "consumption_rows": consumption_rows,
        "stock_cols_1": stock_cols_1,
        "stock_cols_2": stock_cols_2,
        "stock_gap_after": stock_gap_after,
    }


_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_label(report_month: str) -> str:
    y, m = report_month.split("-")
    return f"{_MON_ABBR[int(m)]}'{y[-2:]}"
