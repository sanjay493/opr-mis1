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

Cell shading is a per-row SEQUENTIAL heatmap (one hue, light->dark, by that
row's own min-max across the displayed window) rather than the source PDF's
red/yellow/green per-row shading — the source's colouring implies a
"good/bad" direction (e.g. lower Coal Imports shaded green, lower Automobile
Sales shaded red — opposite polarities), but that "better direction" isn't
stated anywhere in the source for any of the 14 rows, so asserting one here
per metric would be an editorial guess this page has no basis for. A plain
magnitude heatmap (dataviz skill: sequential = magnitude, diverging =
polarity) shows the same at-a-glance shape — which months in a row ran high
or low — without asserting which end is "better."
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

# Sequential ramp endpoints — reuses colors_config.json's already-validated
# highlight_actual_bg (light) / highlight_actual_border (dark) pair rather
# than introducing a new hue.
_RAMP_LIGHT = (0xdb, 0xea, 0xfe)  # highlight_actual_bg  #dbeafe
_RAMP_DARK = (0x1d, 0x4e, 0xd8)   # highlight_actual_border #1d4ed8


def _mon_label(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{_MON_ABBR[m]}'{y % 100:02d}"


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return ""
    r = round(v, 2)
    return str(int(r)) if r == int(r) else f"{r:.2f}".rstrip("0").rstrip(".")


def _ramp_color(frac: float) -> tuple:
    """Linear-interpolate _RAMP_LIGHT -> _RAMP_DARK at frac in [0, 1] ->
    (hex, text_color) — text flips to white once the fill's relative
    luminance drops low enough that black text would be hard to read (the
    darker 2/3 of the ramp, roughly _RAMP_DARK-ward of the midpoint)."""
    r, g, b = (round(lo + (hi - lo) * frac) for lo, hi in zip(_RAMP_LIGHT, _RAMP_DARK))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    text = "#ffffff" if luminance < 0.55 else None  # None = default dark text
    return f"#{r:02x}{g:02x}{b:02x}", text


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
