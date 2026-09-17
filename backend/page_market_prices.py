"""
"Movement of Key Prices - International" (MARKET_PRICES_PAGE_ID = 2.41) —
a genuine A4-landscape report page (see pdf.py's _LANDSCAPE_TYPES), inserted
right before "SAIL Performance - At a Glance" (AT_A_GLANCE_PAGE_ID = 2.5).

Two line charts, Raw Materials vs Finished Steel input/output prices
(USD/T, source: BigMint) — scraped once from Report_format/work/
"DC-2 pages.pdf" (see scripts/backfill_market_intel.py for the initial
values), then extended one month at a time via /data-entry/market-intel.

Trailing 12-calendar-month window ending at the report month (db.
get_trailing_months — a plain rolling window, not April-aligned like the
rest of the report, since the source itself is a rolling BigMint snapshot).
A series with no data at all in that window is dropped rather than drawn as
a flat zero line; a series with SOME missing months (e.g. Raw Materials
only goes back to Jan'26) simply has gaps — line charts break across a
missing point rather than interpolating through it.
"""
from typing import Dict, List, Optional

import db

WINDOW_MONTHS = 12

# Same validated 4-hue categorical set page_sail_mines.py already uses
# (pdf.py's _BADGE_COLORS / globals.css's .dept-badge.grp-N — passed the
# dataviz skill's six-check gate there) — reused here rather than
# introducing/re-validating a second palette. Raw Materials draws the first
# 3, Finished Steel all 4, in fixed series order (never re-cycled per the
# dataviz skill's categorical rule).
_SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]

# (series_code, label, category). category drives which of the 2 charts a
# series is drawn on. Order is display order within its chart (also the
# fixed categorical color order — see page_market_prices_svg._SERIES_COLORS).
_SERIES = [
    ("premium_hcc_aus_cnf_paradip",          "Premium HCC, Australia Origin, CNF Paradip, India",        "raw_materials"),
    ("iron_ore_fines_aus_cfr_china_fe61",    "Iron Ore Fines, Australia Origin, CFR China, Fe 61%",      "raw_materials"),
    ("iron_ore_fines_india_fob_paradip_fe57", "Iron Ore Fines, India Origin, FOB Paradip, India, Fe 57%", "raw_materials"),
    ("hrc_fob_rizhao_china",       "HRC, FOB Rizhao, China SS400",              "finished_steel"),
    ("hrc_cfr_antwerp_europe",     "HRC, CFR Antwerp, Europe S275",             "finished_steel"),
    ("hrc_cfr_west_coast_india",   "HRC, CFR West Coast India, China origin SS400", "finished_steel"),
    ("rebars_exw_donghua_china",   "Re-bars, Exw-Donghua, China HRB400E",       "finished_steel"),
]
SERIES_CODES = [s for s, _, _ in _SERIES]
SERIES_LABEL = {s: lbl for s, lbl, _ in _SERIES}
SERIES_CATEGORY = {s: cat for s, _, cat in _SERIES}

_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _mon_label(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{_MON_ABBR[m]}'{y % 100:02d}"


def _series_points(monthly: Dict[str, Dict[str, float]], months: List[str], code: str) -> List[Optional[float]]:
    return [monthly.get(m, {}).get(code) for m in months]


def _num(v: float) -> str:
    return f"{int(round(v))}" if v == round(v) else f"{v:.1f}"


# Both charts share the same total VH (full page width, and — since
# width:100%/height:auto preserves the aspect ratio uniformly, no x/y
# distortion — an equal, tall height too, splitting the page into
# upper/lower halves, per direct instruction 2026-09-17). Sized against
# this page's real rendered content width (~253mm — A4 landscape 297mm,
# minus the @page's 10mm+10mm print margin and this page's own 8mm+8mm
# layout_config padding): at 1200 viewBox units across that width, 1 unit
# ≈ 0.211mm, so _DATA_FONT_SIZE (19.2 units) ≈ 11.5pt (4.06mm) as
# requested.
#
# The legend's own row budget is sized to each chart's ACTUAL series count
# (3 for Raw Materials, 4 for Finished Steel) rather than a fixed worst-case
# 4 rows — the reclaimed space goes straight into _CH (plot height), giving
# every point more vertical room to spread into and reducing value-label
# overlap where series sit close together on the shared Y-scale (per direct
# instruction, 2026-09-17 — Raw Materials' Iron Ore Fines pair overlapped
# most, compressed near the bottom of a scale shared with the ~3x-larger
# Premium HCC series). Both charts still land at the SAME total _VH (so
# they stay visually equal height) since generate_market_prices always
# passes VH_TOTAL through unchanged — only each chart's own CH/legend_h
# split of that total differs. _VH_TOTAL was walked down from an initial
# estimate against an actual 1-vs-2-page PDF render (Playwright + pypdf
# page count) until it fit a single page, rather than trusted from the mm
# math alone — margins/padding elsewhere on the page make that math only
# approximate.
_VW = 1200
_ML, _MR, _MT = 46, 45, 26
_XAXIS_H = 32
_LEGEND_ROW_H = 24
_LEGEND_PAD = 10
_VH_TOTAL = 354   # verified to keep the page single-sheet
_TITLE_FONT_SIZE = 26
_DATA_FONT_SIZE = 19.2  # legend / axis / point-value text — ≈ 11.5pt, see above


def _line_chart_svg(title: str, chart: dict) -> str:
    """One multi-series line chart, full page width and half page height:
    2px-scaled lines, circular markers, a direct value label at every
    point (mirrors the source PDF's own style — print-only, no hover, so
    direct labels replace a tooltip rather than supplementing one) and a
    vertical legend (one row per series) sized to this chart's own series
    count, with every unclaimed row going to plot height instead (see
    module docstring). Returns "" when the chart has no series at all
    (every series in this category came back empty)."""
    labels, series = chart["labels"], chart["series"]
    if not series:
        return ""
    n = len(labels)
    cw = _VW - _ML - _MR
    legend_h = len(series) * _LEGEND_ROW_H + _LEGEND_PAD
    ch = _VH_TOTAL - _MT - _XAXIS_H - legend_h

    vals = [v for s in series for v in s["values"] if v is not None]
    vmin, vmax = min(vals), max(vals)
    pad = (vmax - vmin) * 0.18 or max(vmax * 0.1, 1.0)
    vlo, vhi = vmin - pad, vmax + pad

    def x(i):
        return _ML + (cw * i / (n - 1) if n > 1 else cw / 2)

    def y(v):
        return _MT + ch - ch * (v - vlo) / (vhi - vlo)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_VW} {_VH_TOTAL}" '
           f'style="width:100%;height:auto;display:block;">']
    out.append(f'<text x="{_VW / 2:.0f}" y="20" text-anchor="middle" font-size="{_TITLE_FONT_SIZE}" '
               f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{title}</text>')
    out.append(f'<line x1="{_ML}" y1="{_MT + ch:.1f}" x2="{_ML + cw}" y2="{_MT + ch:.1f}" '
               f'stroke="#94a3b8" stroke-width="1"/>')
    for i, lab in enumerate(labels):
        out.append(f'<text x="{x(i):.1f}" y="{_MT + ch + 26:.1f}" text-anchor="middle" '
                   f'font-size="{_DATA_FONT_SIZE}" font-family="Arial,sans-serif" fill="#475569">{lab}</text>')

    for si, s in enumerate(series):
        color = _SERIES_COLORS[si % len(_SERIES_COLORS)]
        pts = [(x(i), y(v)) if v is not None else None for i, v in enumerate(s["values"])]
        seg: list = []
        for p in pts + [None]:  # trailing None flushes the final segment
            if p is None:
                if len(seg) > 1:
                    d = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in seg)
                    out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="3.5"/>')
                seg = []
            else:
                seg.append(p)
        for i, v in enumerate(s["values"]):
            if v is None:
                continue
            px, py = x(i), y(v)
            out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{color}"/>')
            out.append(f'<text x="{px:.1f}" y="{py - 10:.1f}" text-anchor="middle" font-size="{_DATA_FONT_SIZE}" '
                       f'font-weight="700" font-family="Arial,sans-serif" fill="{color}">{_num(v)}</text>')

    # Vertical legend, one row per series, left-aligned under the axis —
    # at this font size a horizontal row no longer fits the longest labels
    # (e.g. "Iron Ore Fines, India Origin, FOB Paradip, India, Fe 57%") side
    # by side within the page width, so each series gets its own full-width
    # row instead. legend_h above is sized to THIS chart's own series
    # count (see module docstring) rather than padded to a worst case.
    ly = _MT + ch + _XAXIS_H + 22
    for si, s in enumerate(series):
        color = _SERIES_COLORS[si % len(_SERIES_COLORS)]
        out.append(f'<line x1="{_ML:.1f}" y1="{ly - 6:.1f}" x2="{_ML + 36:.1f}" y2="{ly - 6:.1f}" '
                   f'stroke="{color}" stroke-width="5"/>')
        out.append(f'<text x="{_ML + 46:.1f}" y="{ly:.1f}" font-size="{_DATA_FONT_SIZE}" '
                   f'font-family="Arial,sans-serif" fill="#334155">{s["label"]}</text>')
        ly += _LEGEND_ROW_H

    out.append("</svg>")
    return "".join(out)


def generate_market_prices(report_month: str) -> dict:
    months = db.get_trailing_months(report_month, WINDOW_MONTHS)
    monthly = db.get_market_price_trend(months)
    labels = [_mon_label(m) for m in months]

    def chart(category: str) -> dict:
        codes = [s for s in SERIES_CODES if SERIES_CATEGORY[s] == category]
        series = []
        for code in codes:
            pts = _series_points(monthly, months, code)
            if all(v is None for v in pts):
                continue
            series.append({"code": code, "label": SERIES_LABEL[code], "values": pts})
        return {"labels": labels, "series": series}

    raw_materials = chart("raw_materials")
    finished_steel = chart("finished_steel")

    return {
        "type": "market_prices",
        "title": "Movement of Key Prices - International",
        "unit": "USD/T",
        "source": "Source: BigMint",
        "period_label": f"{labels[0]} - {labels[-1]}",
        "raw_materials_svg": _line_chart_svg("Raw Materials", raw_materials),
        "finished_steel_svg": _line_chart_svg("Finished Steel", finished_steel),
    }
