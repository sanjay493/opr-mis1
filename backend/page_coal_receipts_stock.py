"""
"Receipt, Consumption and Stocks of Coking Coal at Plants" — landscape page
reproducing Report_format/Coal_co2/Coal Format.pdf's OIS-2 table (SAIL-level
only, no plant breakdown — the source workbook doesn't carry one). Sourced
from techno_data (plant="SAIL", unit="Coal_Receipt_Stock"), populated by
api_coal_omi_techno.py — see techno_project/coal_omi_extractor.py's
extract_ois2 for the source workbook layout. Pure lookup/display: (A)/(B)
read the report month's own stored row verbatim.

There used to be a (C) "Month-wise stocks at plants" table here too (the
current FY's own 13 month-start snapshots), but it was removed per direct
instruction as redundant — the 3 tables below (Indigenous/Imported/Total
Coking Coal, one FY per row x Apr-Mar columns, see _stock_history_tables)
already show that same current-FY row as their own top row, alongside the
3 FYs before it. Each of those 3 tables' whole month-wise opening-stock
history (current FY included) is assembled from EVERY SAIL
Coal_Receipt_Stock upload on record, not just the target month's own —
each upload's OIS-2 sheet is a rolling multi-month view (extract_ois2's
own "stock_history", covering several months, not just the one matching
that upload's report_month), so one upload can backfill several FY
months' stock at once (see _all_stock_snapshots). A month with nothing on
record yet just shows "—" rather than being dropped, since these tables
are meant to visibly grow as older months get backfilled rather than
reflow column-by-column as they fill in.
"""
import json as _json

import db

_UNIT = "Coal_Receipt_Stock"


def _all_stock_snapshots() -> dict:
    """{"YYYY-MM": {"indigenous","imported","total"}, ...} merged from
    every SAIL Coal_Receipt_Stock upload on record — each upload's own
    report_month point plus whatever else its stock_history also covers.
    Rows are read oldest-report_month-first and later entries simply
    overwrite earlier ones for the same target month, so a more recent
    upload's figure for a given month always wins over an older one's."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT report_month, techno_json FROM techno_data "
            "WHERE plant='SAIL' AND unit=? ORDER BY report_month ASC",
            [_UNIT],
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    merged = {}
    for rm, tj in rows:
        m = _json.loads(tj).get("month", {})
        indigenous, imported, total = m.get("stock_indigenous"), m.get("stock_imported"), m.get("stock_total")
        if indigenous is not None or imported is not None or total is not None:
            merged[rm] = {"indigenous": indigenous, "imported": imported, "total": total}
        for hist_month, vals in (m.get("stock_history") or {}).items():
            merged[hist_month] = vals
    return merged


_STOCK_HISTORY_MONTH_NAMES = ["Apr", "May", "Jun", "Jul", "Aug", "Sep",
                              "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]


def _stock_history_fy_starts(report_month: str, n: int = 4) -> list:
    """N FY start years ending with report_month's own FY, oldest first —
    default 4 (report_month's FY + the 3 before it), per direct instruction
    ("last 3 years" i.e. FY2023-24 through FY2026-27 for a report_month
    inside FY2026-27). Recalculated from report_month every time, same
    convention as page_cost_trend.py's _annual_fys — never hardcoded to
    specific years, so this keeps sliding forward on its own in future
    report months."""
    fy_start_year = int(db.get_fy_months(report_month)[0][:4])
    return list(range(fy_start_year - (n - 1), fy_start_year + 1))


def _stock_history_tables(report_month: str) -> list:
    """Month-wise opening stock, one row per FY x one column per month
    (Apr-Mar), for the last 4 FYs (see _stock_history_fy_starts) — a
    separate table per coal category (Indigenous/Imported/Total) per
    direct instruction. Filled with whatever's already in
    _all_stock_snapshots() (merged from every upload on record — see its
    own docstring); a month with nothing on record yet just shows "—"
    until that history is backfilled."""
    snapshots = _all_stock_snapshots()
    # Reversed for display — most recent/current FY on top, oldest at the
    # bottom, per direct instruction (_stock_history_fy_starts itself stays
    # oldest-first, since that's the natural order to compute it in).
    fy_starts = list(reversed(_stock_history_fy_starts(report_month)))

    tables = []
    for label, key in [("Indigenous Coking Coal", "indigenous"),
                        ("Imported Coking Coal", "imported"),
                        ("Total Coking Coal", "total")]:
        rows = []
        for fy_start in fy_starts:
            fy_label = f"{fy_start}-{(fy_start + 1) % 100:02d}"
            fy_months = db.get_fy_months(f"{fy_start}-04")  # April always falls in FY fy_start
            values = [snapshots.get(mo, {}).get(key) for mo in fy_months]
            rows.append({"fy": fy_label, "values": values})
        tables.append({"label": label, "key": key, "rows": rows})
    return tables


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

    return {
        "type": "coal_receipt_stock",
        "title": f"Details of Coking Coal Consumption, Blend and Stocks - Receipts & Stocks ({_month_label(report_month)})",
        "receipt_rows": receipt_rows,
        "consumption_rows": consumption_rows,
        "stock_history_month_names": _STOCK_HISTORY_MONTH_NAMES,
        "stock_history_tables": _stock_history_tables(report_month),
    }


_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_label(report_month: str) -> str:
    y, m = report_month.split("-")
    return f"{_MON_ABBR[int(m)]}'{y[-2:]}"
