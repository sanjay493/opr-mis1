"""
"India Macro Economic Indicators" (MACRO_INDICATORS_PAGE_ID = 2.42) — a
genuine A4-landscape report page (see pdf.py's _LANDSCAPE_TYPES), inserted
right after "Movement of Key Prices - International" (2.41), right before
"SAIL Performance - At a Glance" (AT_A_GLANCE_PAGE_ID = 2.5).

A 13-column monthly matrix (Key Parameters x months), scraped once from
Report_format/work/"DC-2 pages.pdf" (see scripts/backfill_market_intel.py
for the initial values), then extended one month at a time via
/data-entry/market-intel. Source: Various Ministries (Government of India) |
SIAM | BigMint. Steel data excludes Stainless Steel & Alloy steel.

Window: trailing 13 calendar months ending at report_month MINUS ONE MONTH
(db.get_trailing_months(db.shift_month(report_month, -1), 13)) — the source
PDF itself shows Jul'25-Jul'26 for an Aug'26 report (a 1-month lag), since
government/industry macro stats are published with that lag; matched here
exactly rather than showing the report month's own (not-yet-published) figure.

Cell shading is a per-row red/yellow/green 3-color scale (low->mid->high by
that row's own min-max across the displayed window), copied inline from the
source PDF's own colouring (Excel's default 3-Color Scale palette: #f8696b
low, #ffeb84 mid, #63be7b high) per direct instruction, 2026-09-17 — an
earlier version here used a single-hue sequential ramp instead, reasoning
that red/yellow/green implies a "good/bad" direction the source never
states per metric, but the source's own look takes precedence now.
"""
from typing import Dict, List, Optional

import db

WINDOW_MONTHS = 13

# (metric_code, label, unit). Order is display (row) order, matching the
# source PDF's own row order.
_METRICS = [
    ("crude_steel_prod",    "Crude steel production",              "million tonnes"),
    ("pig_iron_prod",       "Pig iron production",                 "million tonnes"),
    ("steel_exports",       "Steel Exports",                       "million tonnes"),
    ("steel_imports",       "Steel Imports",                       "million tonnes"),
    ("iron_ore_imports",    "Iron ore Imports",                    "million tonnes"),
    ("coal_prod",           "Coal Production",                     "million tonnes"),
    ("coal_imports",        "Coal Imports",                        "million tonnes"),
    ("auto_prod",           "Automobile Production",               "million units"),
    ("auto_sales",          "Automobile Sales",                    "million units"),
    ("power_consumption",   "Daily Average Power Consumption",     "'000 MUs"),
    ("merchandise_exports", "Merchandize exports",                 "Billion USD ($)"),
    ("ev_registrations",    "EV Registrations",                    "Lakh Units"),
    ("gst_collections",     "GST Collections",                     "Trillion INR (₹)"),
    ("manufacturing_pmi",   "Manufacturing PMI Index",             ""),
]
METRIC_CODES = [m for m, _, _ in _METRICS]
METRIC_LABEL = {m: lbl for m, lbl, _ in _METRICS}
METRIC_UNIT = {m: u for m, _, u in _METRICS}

_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Excel's default 3-Color Scale (Red-Yellow-Green) preset — matches the
# source PDF's own per-row heatmap colours exactly.
_RAMP_LOW = (0xf8, 0x69, 0x6b)   # #f8696b
_RAMP_MID = (0xff, 0xeb, 0x84)   # #ffeb84
_RAMP_HIGH = (0x63, 0xbe, 0x7b)  # #63be7b


def _mon_label(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{_MON_ABBR[m]}'{y % 100:02d}"


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return ""
    r = round(v, 2)
    return str(int(r)) if r == int(r) else f"{r:.2f}".rstrip("0").rstrip(".")


def _ramp_color(frac: float) -> tuple:
    """Piecewise-interpolate _RAMP_LOW -> _RAMP_MID -> _RAMP_HIGH at frac in
    [0, 1] -> (hex, text_color). All 3 stops are pale enough that default
    dark text stays readable throughout (matches the source, which never
    flips to white text either), so text_color is always None."""
    lo, hi, t = (_RAMP_LOW, _RAMP_MID, frac / 0.5) if frac <= 0.5 else (_RAMP_MID, _RAMP_HIGH, (frac - 0.5) / 0.5)
    r, g, b = (round(a + (b - a) * t) for a, b in zip(lo, hi))
    return f"#{r:02x}{g:02x}{b:02x}", None


def _row_colors(values: List[Optional[float]]) -> List[Optional[tuple]]:
    present = [v for v in values if v is not None]
    if len(present) < 2:
        return [None] * len(values)
    vmin, vmax = min(present), max(present)
    if vmax == vmin:
        return [None] * len(values)
    return [None if v is None else _ramp_color((v - vmin) / (vmax - vmin)) for v in values]


def generate_macro_indicators(report_month: str) -> dict:
    end_month = db.shift_month(report_month, -1)
    months = db.get_trailing_months(end_month, WINDOW_MONTHS)
    monthly = db.get_macro_indicators(months)
    labels = [_mon_label(m) for m in months]

    rows = []
    for code in METRIC_CODES:
        values = [monthly.get(m, {}).get(code) for m in months]
        colors = _row_colors(values)
        cells = []
        for v, c in zip(values, colors):
            bg, fg = c if c else (None, None)
            cells.append({"value": _fmt(v), "bg": bg, "fg": fg})
        rows.append({"label": METRIC_LABEL[code], "unit": METRIC_UNIT[code], "cells": cells})

    return {
        "type": "macro_indicators",
        "title": "India Macro Economic Indicators",
        "period_label": f"({labels[0]}-{labels[-1]})",
        "column_labels": labels,
        "rows": rows,
        "source": "Source: Various Ministries (Government of India) | SIAM | BigMint",
        "footnote": "Steel data excl. Stainless Steel & Alloy steel",
    }
