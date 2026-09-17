"""
Rail Production & Dispatch from BSP (Report_format/"Rail Prod & Despatch
Report for OMI.pdf") — a genuine A4-landscape report page (spliced in by
pdf.py's _LANDSCAPE_TYPES handling), inserted right after Segment Wise
Production (page 18), before the Special Steel plant pages (page 19).

One column per financial year (Apr-Mar) from RAIL_HISTORY_START_FY_YEAR
through the report month's own FY; the report month's own (open) FY holds a
running Apr-<report month> cumulative in the same row, not auto-summed from
anything (same "typed in directly" convention as Cost Trend's till_month) —
its column is simply labelled "Till <Mon>'YY" instead of a closed "YYYY-YY".

9 metrics are entered directly (rail_prod_despatch, one row per
financial_year x metric, via /data-entry/rail-report); 4 are computed here
at read time from those 9, per the source PDF:
  - % LR in RSM Prime Prod        = LR Prod at RSM / Total Prime Rail Prod. at RSM
  - Total Prime Rail Prod.        = Prod. at RSM + Prod. at URM (None only if both missing)
  - % Fulfillment of Bulk Indent  = Total Despatch to IR / Total Bulk Indent Qty
  - % LR in Total supply          = Qty. of Long Rails in Total supply / Total Despatch to IR
R350HT Rails supplied carries an optional free-text note alongside its
value (e.g. "9 Rakes" in the source PDF), shown under the figure.

Footer remarks (rail_prod_despatch_note) are standing footnotes, not scoped
to a FY — see db.py's table comment.
"""
import db

RAIL_HISTORY_START_FY_YEAR = 2015  # first column (2015-16), per the source PDF

_MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Raw metrics, in the row order they're entered/displayed. Unit is baked
# into the label, matching the source PDF (lac = lakh = 100,000).
_RAW_METRICS = [
    ("bulk_indent",        "Total Bulk Indent Qty (lac T)"),
    ("rsm_prod",           "Total Prime Rail Prod. at RSM (lac T)"),
    ("lr_rsm",             "LR Prod at RSM (lac T)"),
    ("urm_prod",           "Prime Rail Prod. at URM (lac T)"),
    ("despatch_ir",        "Total Despatch to IR (lac T)"),
    ("lr_total_supply",    "Qty. of Long Rails in Total supply (lac T)"),
    ("twa_supplied",       "TWA Rails supplied (T)"),
    ("r350ht_supplied",    "R350HT Rails supplied (T)"),
    ("lr_rakes_sabarmati", "No. of LR Rakes supplied from Sabarmati FBW Plant"),
]
RAW_METRIC_CODES = [m for m, _ in _RAW_METRICS]
RAW_METRIC_LABEL = dict(_RAW_METRICS)

_LAC_T_METRICS = {"bulk_indent", "rsm_prod", "lr_rsm", "urm_prod", "despatch_ir", "lr_total_supply"}
_INT_METRICS = {"twa_supplied", "r350ht_supplied", "lr_rakes_sabarmati"}


def _fy_label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def _fmt_raw(metric: str, v):
    if v is None:
        return ""
    if metric in _LAC_T_METRICS:
        return f"{v:.2f}"
    if metric in _INT_METRICS:
        return f"{v:.0f}"
    return f"{v:g}"


def _fmt_sum(v):
    return "" if v is None else f"{v:.2f}"


def _fmt_pct(v):
    return "" if v is None else f"{v:.1f}"


def _sum_or_none(a, b):
    """a + b, treating a missing side as 0 — None only when BOTH are missing
    (same convention as Cost Trend's TOTAL = VARIABLE + FIXED)."""
    vals = [x for x in (a, b) if x is not None]
    return round(sum(vals), 2) if vals else None


def _pct(numer, denom):
    if numer is None or not denom:
        return None
    return round(numer / denom * 100, 1)


def _row(label, cells, band=None, bold=False, notes=None):
    return {"label": label, "cells": cells, "band": band, "bold": bold, "notes": notes or {}}


def generate_rail_report(report_month: str) -> dict:
    cur_fy = db.get_fy_for_month(report_month)
    cur_start = int(cur_fy[:4])
    fys = [_fy_label(y) for y in range(RAIL_HISTORY_START_FY_YEAR, cur_start + 1)]

    data = db.get_rail_report_data(fys)

    def v(fy, metric):
        cell = data.get(fy, {}).get(metric)
        return cell["value"] if cell else None

    def note(fy, metric):
        cell = data.get(fy, {}).get(metric)
        return (cell.get("note") if cell else None) or None

    mon, yr = int(report_month[5:7]), int(report_month[:4])
    till_label = f"Till {_MON[mon]}'{yr % 100:02d}"
    columns = [{"key": fy, "label": (till_label if fy == cur_fy else fy)} for fy in fys]

    bulk = {fy: v(fy, "bulk_indent") for fy in fys}
    rsm = {fy: v(fy, "rsm_prod") for fy in fys}
    lr_rsm = {fy: v(fy, "lr_rsm") for fy in fys}
    urm = {fy: v(fy, "urm_prod") for fy in fys}
    total_prime = {fy: _sum_or_none(rsm[fy], urm[fy]) for fy in fys}
    despatch = {fy: v(fy, "despatch_ir") for fy in fys}
    lr_total = {fy: v(fy, "lr_total_supply") for fy in fys}
    twa = {fy: v(fy, "twa_supplied") for fy in fys}
    r350 = {fy: v(fy, "r350ht_supplied") for fy in fys}
    r350_note = {fy: note(fy, "r350ht_supplied") for fy in fys}
    rakes = {fy: v(fy, "lr_rakes_sabarmati") for fy in fys}

    rows = [
        _row(RAW_METRIC_LABEL["bulk_indent"],
             {fy: _fmt_raw("bulk_indent", bulk[fy]) for fy in fys}, band="green"),
        _row(RAW_METRIC_LABEL["rsm_prod"],
             {fy: _fmt_raw("rsm_prod", rsm[fy]) for fy in fys}),
        _row(RAW_METRIC_LABEL["lr_rsm"],
             {fy: _fmt_raw("lr_rsm", lr_rsm[fy]) for fy in fys}),
        _row("% LR in RSM Prime Prod",
             {fy: _fmt_pct(_pct(lr_rsm[fy], rsm[fy])) for fy in fys}, band="orange", bold=True),
        _row(RAW_METRIC_LABEL["urm_prod"],
             {fy: _fmt_raw("urm_prod", urm[fy]) for fy in fys}),
        _row("Total Prime Rail Prod. (lac T)",
             {fy: _fmt_sum(total_prime[fy]) for fy in fys}, band="yellow", bold=True),
        _row(RAW_METRIC_LABEL["despatch_ir"],
             {fy: _fmt_raw("despatch_ir", despatch[fy]) for fy in fys}, band="blue"),
        _row("% Fulfillment of Bulk Indent",
             {fy: _fmt_pct(_pct(despatch[fy], bulk[fy])) for fy in fys}, band="yellow", bold=True),
        _row(RAW_METRIC_LABEL["lr_total_supply"],
             {fy: _fmt_raw("lr_total_supply", lr_total[fy]) for fy in fys}, band="blue"),
        _row("% LR in Total supply",
             {fy: _fmt_pct(_pct(lr_total[fy], despatch[fy])) for fy in fys}, band="blue", bold=True),
        _row(RAW_METRIC_LABEL["twa_supplied"],
             {fy: _fmt_raw("twa_supplied", twa[fy]) for fy in fys}, band="blue"),
        _row(RAW_METRIC_LABEL["r350ht_supplied"],
             {fy: _fmt_raw("r350ht_supplied", r350[fy]) for fy in fys}, band="blue", notes=r350_note),
        _row(RAW_METRIC_LABEL["lr_rakes_sabarmati"],
             {fy: _fmt_raw("lr_rakes_sabarmati", rakes[fy]) for fy in fys}, band="blue"),
    ]

    notes = [t for _so, t in db.get_rail_report_notes()]

    return {
        "type": "rail_report",
        "title": "Rail Production & Dispatch from BSP",
        "columns": columns,
        "rows": rows,
        "notes": notes,
    }
