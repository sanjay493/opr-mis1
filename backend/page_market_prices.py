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
# The legend now sits ABOVE the plot area (between the title and the chart)
# in a 2-column grid — 2 entries per row, with a trailing odd entry alone
# and centered on its own row — instead of one full-width row per series
# below the chart (per direct instruction, 2026-09-17). Since a chart never
# has more than 4 series, this caps the legend at 2 rows regardless of
# series count, which reclaims rows straight into _CH (plot height) versus
# the old up-to-4-rows bottom legend — Finished Steel (4 series) gains the
# most. Both charts still land at the SAME total _VH (so they stay visually
# equal height) since generate_market_prices always passes VH_TOTAL through
# unchanged — only each chart's own CH/legend_h split of that total differs.
# _VH_TOTAL was walked down from an initial estimate against an actual
# 1-vs-2-page PDF render (Playwright + pypdf page count) until it fit a
# single page, rather than trusted from the mm math alone — margins/padding
# elsewhere on the page make that math only approximate.
_VW = 1200
_ML, _MR, _MT = 46, 45, 26
_XAXIS_H = 32
_LEGEND_ROW_H = 24
_LEGEND_GAP_TOP = 14     # title baseline -> first legend row
_LEGEND_GAP_BOTTOM = 16  # last legend row -> plot area top
_VH_TOTAL = 354   # verified to keep the page single-sheet
_TITLE_FONT_SIZE = 26
_DATA_FONT_SIZE = 19.2  # x-axis month-label text — ≈ 11.5pt, see above
# Point-value numbers, 0.5pt smaller than _DATA_FONT_SIZE (≈11.5pt -> 11pt;
# at the ~1.67 units/pt scale derived above that's 19.2 - 0.5*1.67 ≈ 18.4
# units) for a bit more breathing room around the value labels on the
# 4-series Finished Steel chart (per direct instruction, 2026-09-17).
_POINT_VALUE_FONT_SIZE = 18.4
# Smaller than _DATA_FONT_SIZE so the two longest labels (the Raw Materials
# Iron Ore Fines pair, ~50-56 chars each) fit side by side within half the
# chart width without overlapping the other column.
_LEGEND_FONT_SIZE = 16


def _text_w(s: str, font_size: float) -> float:
    """Rough Arial-text width estimate (avg glyph ≈ 0.55×font-size) — only
    used to center/space legend entries, not for exact layout."""
    return len(s) * font_size * 0.55


def _line_chart_svg(title: str, chart: dict, label_below_lowest: bool = False) -> str:
    """One multi-series line chart, full page width and half page height:
    2px-scaled lines, circular markers, a direct value label at every
    point (mirrors the source PDF's own style — print-only, no hover, so
    direct labels replace a tooltip rather than supplementing one) and a
    2-column legend grid above the plot area, capped at 2 rows regardless
    of series count, with every unclaimed row going to plot height instead
    (see module docstring). Returns "" when the chart has no series at all
    (every series in this category came back empty).

    label_below_lowest: draw the whole lowest-average series' value labels
    BELOW its points instead of above — the space below the bottom-most
    line is clear (nothing but the axis), while placing it above would
    crowd the line(s) running just above it. The bottom series is fixed
    for the whole chart (by overall average, not re-decided at each x),
    so the two middle series always keep the ordinary above-point style
    throughout, even where a crossover briefly puts one of them lowest —
    a per-x decision made them flicker between styles, which read as
    inconsistent rather than legible (per direct instruction, 2026-09-17).
    Used for Finished Steel (4 close-running series) where labels above
    every point get cluttered."""
    labels, series = chart["labels"], chart["series"]
    if not series:
        return ""
    n = len(labels)
    cw = _VW - _ML - _MR

    # Legend rows: 2 entries per row, in series order; an odd series count
    # leaves one entry alone on the last row (centered — see below). Each
    # entry keeps its original series index so its color stays correct.
    indexed = list(enumerate(series))
    legend_rows = [indexed[i:i + 2] for i in range(0, len(indexed), 2)]
    legend_h = len(legend_rows) * _LEGEND_ROW_H
    plot_top = _MT + _LEGEND_GAP_TOP + legend_h + _LEGEND_GAP_BOTTOM
    ch = _VH_TOTAL - plot_top - _XAXIS_H

    vals = [v for s in series for v in s["values"] if v is not None]
    vmin, vmax = min(vals), max(vals)
    pad = (vmax - vmin) * 0.18 or max(vmax * 0.1, 1.0)
    vlo, vhi = vmin - pad, vmax + pad

    def x(i):
        return _ML + (cw * i / (n - 1) if n > 1 else cw / 2)

    def y(v):
        return plot_top + ch - ch * (v - vlo) / (vhi - vlo)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_VW} {_VH_TOTAL}" '
           f'style="width:100%;height:auto;display:block;">']
    out.append(f'<text x="{_VW / 2:.0f}" y="20" text-anchor="middle" font-size="{_TITLE_FONT_SIZE}" '
               f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{title}</text>')

    # Legend, above the plot area: each row holds up to 2 entries split into
    # left/right halves of the chart width; a lone trailing entry (odd
    # series count) is centered across the full width instead.
    ly = _MT + _LEGEND_GAP_TOP
    for row in legend_rows:
        if len(row) == 2:
            col_x = [_ML, _ML + cw / 2]
        else:
            item_w = 46 + _text_w(row[0][1]["label"], _LEGEND_FONT_SIZE)
            col_x = [_ML + (cw - item_w) / 2]
        for (si, s), lx in zip(row, col_x):
            color = _SERIES_COLORS[si % len(_SERIES_COLORS)]
            out.append(f'<line x1="{lx:.1f}" y1="{ly - 6:.1f}" x2="{lx + 36:.1f}" y2="{ly - 6:.1f}" '
                       f'stroke="{color}" stroke-width="5"/>')
            out.append(f'<text x="{lx + 46:.1f}" y="{ly:.1f}" font-size="{_LEGEND_FONT_SIZE}" '
                       f'font-family="Arial,sans-serif" fill="#334155">{s["label"]}</text>')
        ly += _LEGEND_ROW_H

    out.append(f'<line x1="{_ML}" y1="{plot_top + ch:.1f}" x2="{_ML + cw}" y2="{plot_top + ch:.1f}" '
               f'stroke="#94a3b8" stroke-width="1"/>')
    for i, lab in enumerate(labels):
        out.append(f'<text x="{x(i):.1f}" y="{plot_top + ch + 26:.1f}" text-anchor="middle" '
                   f'font-size="{_DATA_FONT_SIZE}" font-family="Arial,sans-serif" fill="#475569">{lab}</text>')

    # The single lowest-average series (fixed for the whole chart — see
    # docstring), only computed when actually used.
    avgs = []
    for si, s in enumerate(series):
        pts_ = [v for v in s["values"] if v is not None]
        if pts_:
            avgs.append((sum(pts_) / len(pts_), si))
    bottom_idx: Optional[int] = min(avgs)[1] if (label_below_lowest and avgs) else None

    # (px, py) for every series/point, computed once and reused by the line
    # paths (pass 1), the label-stacking pass below, and the marker pass.
    pts_all = [[(x(i), y(v)) if v is not None else None for i, v in enumerate(s["values"])]
               for s in series]

    # Pass 1: every series' line, all drawn before any marker/label — so a
    # later series' line never gets drawn on top of an earlier series'
    # value label (see the opaque backdrop rect in pass 2 below, which
    # then also cuts a clean gap through whichever line runs behind it).
    for si, s in enumerate(series):
        color = _SERIES_COLORS[si % len(_SERIES_COLORS)]
        seg: list = []
        for p in pts_all[si] + [None]:  # trailing None flushes the final segment
            if p is None:
                if len(seg) > 1:
                    d = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in seg)
                    out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="3.5"/>')
                seg = []
            else:
                seg.append(p)

    # Per-series label offset (a single fixed px-above-own-point distance,
    # applied at every x for that series) rather than a per-point/per-column
    # decision. A per-column version was tried first (push whichever label
    # collides at THIS x away from its neighbour) but that let a label drift
    # an arbitrary, month-dependent distance from its own point — on the
    # month where two close-running series (e.g. Finished Steel's HRC FOB
    # Rizhao vs HRC CFR West Coast India, within single-digit USD/T of each
    # other most months) happened to be closest, the pushed label ended up
    # sitting right on/next to the OTHER series' point, reading as if it
    # belonged to that line instead (reported directly, 2026-09-17). Fixing
    # the offset per series instead means a label always sits the same
    # distance above its own point, month to month — it visually travels
    # WITH its own line rather than occasionally jumping onto a neighbour.
    # The offset itself is still decided from the data (each series' own
    # average value, not a hardcoded per-series constant), the same way
    # bottom_idx already is: series are walked from the lowest average
    # upward, and a series only gets pushed further above its own point
    # than the default 10 when its average would otherwise sit within one
    # label-height of the series just below it's assigned label. The single
    # lowest-average series is excluded, keeping its own fixed "always
    # below" placement (see label_below_lowest above) instead.
    label_h = _POINT_VALUE_FONT_SIZE * 0.9 + 4
    offset = {si: -10.0 for si in range(len(series))}
    group = sorted((v, si) for v, si in avgs if si != bottom_idx)
    prev_label_py = None
    for avg_v, si in group:
        avg_py = y(avg_v)
        ly = avg_py - 10
        if prev_label_py is not None and ly > prev_label_py - label_h:
            ly = prev_label_py - label_h
        offset[si] = ly - avg_py
        prev_label_py = ly

    label_ys = [[None] * n for _ in series]
    for si in range(len(series)):
        off = 24 if si == bottom_idx else offset[si]
        for i, p in enumerate(pts_all[si]):
            if p is not None:
                label_ys[si][i] = p[1] + off

    # Pass 2: every series' markers, all drawn before any label (pass 3) —
    # so on a close-running chart where two series' points sit only a few
    # px apart, a later series' marker never lands on top of (and eats a
    # bite out of) an earlier series' already-drawn label. Each marker sits
    # on a white halo a couple px wider than the dot, cutting a clean gap
    # in the line right at the data point instead of the line running
    # straight up to (and visually fusing with) the marker's edge.
    for si, s in enumerate(series):
        color = _SERIES_COLORS[si % len(_SERIES_COLORS)]
        for i, v in enumerate(s["values"]):
            if v is None:
                continue
            px, py = pts_all[si][i]
            out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="8" fill="#ffffff"/>')
            out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{color}"/>')

    # Pass 3: value labels, on top of every marker and every line. Each
    # label sits on an opaque white backdrop sized to the number's text, so
    # wherever a line or a neighbouring point's marker (its halo included —
    # see the stacking above, which can still leave a label close to
    # another series' point on a genuinely tight chart) runs behind the
    # label, that area is visually cut rather than crossing through/eating
    # into the digits.
    for si, s in enumerate(series):
        color = _SERIES_COLORS[si % len(_SERIES_COLORS)]
        for i, v in enumerate(s["values"]):
            if v is None:
                continue
            px, _ = pts_all[si][i]
            label_y = label_ys[si][i]
            num = _num(v)
            w = len(num) * _POINT_VALUE_FONT_SIZE * 0.62 + 6
            h = _POINT_VALUE_FONT_SIZE * 0.9
            out.append(f'<rect x="{px - w / 2:.1f}" y="{label_y - h * 0.8:.1f}" width="{w:.1f}" '
                       f'height="{h:.1f}" fill="#ffffff"/>')
            out.append(f'<text x="{px:.1f}" y="{label_y:.1f}" text-anchor="middle" font-size="{_POINT_VALUE_FONT_SIZE}" '
                       f'font-weight="700" font-family="Arial,sans-serif" fill="{color}">{num}</text>')

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
        "finished_steel_svg": _line_chart_svg("Finished Steel", finished_steel, label_below_lowest=True),
    }
