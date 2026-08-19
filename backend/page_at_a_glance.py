"""
MIS at a Glance — infographic-style snapshot page, the first numbered page
of the report (see AT_A_GLANCE_PAGE_ID in main.py). Composites headline
numbers already computed elsewhere in the report — production,
techno-economic, value added (special) steel — into one visual dashboard,
plus a short production trend line, so a reader gets the month's story in
one page before diving into the detailed report.

Sentinel page id (not part of the static 1-40 page list) — see main.py's
comment next to AT_A_GLANCE_PAGE_ID for why (also individually browsable
on-screen — see get_data()'s page_number handling and PageRenderer.js's
'at_a_glance' case).
"""
import datetime as _dt
import re as _re

import db
from report_utils import compute_item_row
from page_techno import generate_at_a_glance_te_table
from page_special_steel import generate_special_steel_sail
from page_special_steel_trend import (
    _last_n_fys, _fy_months, _current_fy_rate, _saleable_steel, _sum_actual,
)

_PROD_ITEMS = ["Hot Metal", "Crude Steel", "Finished Steel", "Saleable Steel"]

# compute_item_row/db.get_sail_production_*_actual expect the DB's own item
# names — "Crude Steel" is stored as "Total Crude Steel"; Finished Steel is
# already correct as-is.
_YTD_DB_ITEM = {"Crude Steel": "Total Crude Steel"}

# Rate/consumption metrics are "good" when they go down; productivity is
# "good" when it goes up. Sinter/Pellet in Burden are mix-ratio params with
# no universal "better" direction, so they're left out of this set (default:
# above target reads as good) same as BF Productivity.
_TE_LOWER_IS_BETTER = {
    "Coke Rate", "Fuel Rate", "Specific Energy Consumption", "TMI", "Sp. CO2 Emission",
    "Imported Coking Coal in Blend",
}
_TE_PARAMS = [
   "Imported Coking Coal in Blend","BF Productivity","Coke Rate",  "CDI Rate", "Fuel Rate", "Sinter in Burden", 
    "Pellet in Burden", "TMI","Specific Energy Consumption", "Sp. CO2 Emission",
]

# Tile background groups the tile by what the parameter actually IS (fuel &
# reductants / energy / process efficiency / burden mix / environment /
# import blend), not by whether it's over/under target — that comparison is
# already carried by the delta_pct text color, so the tile fill is free to
# encode identity instead. Keys are colors_config.json entries.
_TE_CATEGORY_BG = {
    "Coke Rate": "techno_cat_fuel_bg",
    "Fuel Rate": "techno_cat_fuel_bg",
    "CDI Rate": "techno_cat_fuel_bg",
    "Specific Energy Consumption": "techno_cat_energy_bg",
    "BF Productivity": "techno_cat_process_bg",
    "Sinter in Burden": "techno_cat_burden_bg",
    "Pellet in Burden": "techno_cat_burden_bg",
    "TMI": "techno_cat_burden_bg",
    "Sp. CO2 Emission": "techno_cat_environment_bg",
    "Imported Coking Coal in Blend": "techno_cat_blend_bg",
}

# techno_data unit='General' keys this page sums across plants (BSP, DSP,
# RSP, BSL, ISP) to compute "Imported Coking Coal in Blend" - a sum-of-
# quantities ratio, not a weighted average, so it doesn't go through
# page_techno.py's SAIL-rollup machinery like the params above.
_COAL_BLEND_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]

# FY bar colors: fixed categorical order (blue / orange / aqua / yellow),
# validated with the dataviz palette script for adjacent-pair CVD + normal-
# vision separation — see scripts/validate_palette.js. The "(YTD)" legend
# suffix (not color) marks the current partial year.
_YTD_BAR_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]

# Two-series trend line colors.
_TREND_SERIES = [("Saleable Steel", "#0284c7"), ("Finished Steel", "#f97316")]


def _num(v):
    try:
        if v in (None, ""):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _fmt(v, dp=1):
    n = _num(v)
    return None if n is None else f"{n:.{dp}f}"


def _contrast_text(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#0f172a" if luminance > 0.6 else "#ffffff"


def _trailing_months(report_month: str, n: int = 6) -> list:
    y, m = int(report_month[:4]), int(report_month[5:7])
    months = []
    for k in range(n - 1, -1, -1):
        mm = m - k
        yy = y
        while mm <= 0:
            mm += 12
            yy -= 1
        months.append(f"{yy}-{mm:02d}")
    return months


def _fy_label(fy_start_year: int) -> str:
    return f"{fy_start_year}-{(fy_start_year + 1) % 100:02d}"


def _last4_fy_starts(report_month: str) -> list:
    """4 FY start years, oldest first, ending with the FY containing
    report_month (the current, partial one)."""
    y, m = int(report_month[:4]), int(report_month[5:7])
    cur_fy_start = y if m >= 4 else y - 1
    return [cur_fy_start - k for k in range(3, -1, -1)]


def _ytd_months_for_fy(fy_start_year: int, n_months: int) -> list:
    """First n_months of the FY starting April fy_start_year — i.e. the same
    Apr..report-month window as the current FY, replayed on an earlier FY,
    so each bar is a like-for-like YTD comparison."""
    months = []
    yy, mm = fy_start_year, 4
    for _ in range(n_months):
        months.append(f"{yy}-{mm:02d}")
        mm += 1
        if mm > 12:
            mm = 1
            yy += 1
    return months


# ── SVG: two-series monthly trend line + semi-finished-by-plant stacked bar ──

# Reuses the page's own validated 4-color categorical order (already used for
# the FY bar chart above) plus one more slot (magenta) for ASP — validated
# together for adjacent-pair CVD/normal-vision separation, see
# scripts/validate_palette.js. RSP has no "Saleable Semis" item at all (see
# page_prod_by_process.py's _semis_ytd) — excluded from the stack rather than
# shown as a zero segment. ASP doesn't track semis directly either, but
# page5_6.py already derives it as Saleable Steel − Finished Steel for ASP —
# the same derivation is reused here for consistency with that page.
_SEMIS_PLANTS = ["BSP", "DSP", "BSL", "ISP", "ASP"]
_SEMIS_COLORS = dict(zip(_SEMIS_PLANTS, _YTD_BAR_COLORS + ["#e87ba4"]))
_SEMIS_INK = "#1e293b"  # legend/annotation text stays neutral ink, never the segment's own hue (identity comes from the adjacent swatch/fill, not colored text — low-contrast hues like yellow/aqua/magenta are illegible as text on a light surface)
_SEMIS_OWN_PCT_LABEL_COLOR = "#6366f1"  # indigo, for the "small % = ..." caption clause specifically
_SEMIS_OWN_PCT_BADGE_FILL = "yellow"    # circle behind each own-% data label
# Kept small: ASP's segment is consistently the thinnest in every month (its
# own % badge sits only ~3-6 units from the neighboring segment's badge) —
# a larger radius reads fine in isolation but overlaps its neighbor there.
_SEMIS_OWN_PCT_BADGE_R = 3.0
_SEMIS_OWN_PCT_BADGE_FS = 5.0


def _semis_breakdown_data(months: list) -> dict:
    """Per trailing month: each reporting plant's semi-finished steel
    quantity, its % share of that month's cross-plant semi-finished total,
    and — a different ratio — that same plant's own semi-finished as a % of
    its own Saleable Steel (own product mix, not comparable across plants,
    so kept as a separate number rather than blended into the share %)."""
    out = {}
    for m in months:
        plants = []
        for p in _SEMIS_PLANTS:
            saleable = db.get_production_actual_value(p, "Saleable Steel", m)
            if p == "ASP":
                finished = db.get_production_actual_value(p, "Finished Steel", m)
                semis = (saleable - finished) if (saleable is not None and finished is not None) else None
            else:
                semis = db.get_production_actual_value(p, "Saleable Semis", m)
            if semis is None:
                continue
            plants.append({
                "plant": p, "qty": semis,
                "own_pct": round(semis / saleable * 100, 1) if saleable else None,
            })
        total = sum(p["qty"] for p in plants)
        for p in plants:
            p["share_pct"] = round(p["qty"] / total * 100, 1) if total else None
        out[m] = {"total": total, "plants": plants}
    return out


def _declutter_1d(values: list, min_gap: float, iterations: int = 6) -> list:
    """Nudge a list of positions (in real spatial adjacency order — each
    entry adjacent to its neighbors in the list) apart so consecutive
    values are at least min_gap apart, symmetrically (each colliding pair
    pushed apart equally rather than cascading everything downward/upward
    from one end) and iterated a few times so a fix for one pair doesn't
    silently reintroduce a collision with its other neighbor. Converges
    quickly for the small counts (<=5) this chart ever deals with."""
    out = list(values)
    n = len(out)
    for _ in range(iterations):
        moved = False
        for i in range(1, n):
            gap = out[i] - out[i - 1]
            if gap < min_gap:
                deficit = min_gap - gap
                out[i - 1] -= deficit / 2
                out[i] += deficit / 2
                moved = True
        if not moved:
            break
    return out


def _trend_line_svg(labels: list, series: dict, colors: dict, semis_by_month: dict,
                     vw: int = 480, vh: int = 180) -> str:
    # No Y-axis (removed along with its value labels — every data point is
    # already labeled directly on its line/bar, so the axis scale was
    # redundant). Left margin is now sized for Zone B's "outside-left" share%
    # labels (thin-segment fallback, positioned left of the first month's
    # bar) rather than a column of axis numbers — those still need clearance
    # or they render off-canvas at month 0. Right margin mirrors this: every
    # segment's "own %" label sits outside-right of its bar (text-anchor
    # "start", growing rightward from x + bar_w/2 + 2.5) — at the LAST
    # month, that bar's x sits right at the canvas edge, so mr must clear
    # bar_w/2 (~9.5) plus the label text itself or it renders off-canvas
    # there too (same failure mode as month 0's left-side labels, mirrored).
    ml, mr = 26, 26
    # Zone A (top): existing Saleable/Finished Steel line trend.
    mt_a, ch_a = 13, 70
    # Zone B (bottom): new semi-finished-by-plant stacked bar — its own Y
    # scale (a different, much smaller magnitude than Zone A), sharing Zone
    # A's x positions so the same month lines up in both zones. "Fits inside
    # the space available for each month" = the bar stays inside its own
    # month's column (bar_w below), never widening the chart itself. The two
    # zones share a SINGLE x-axis line (drawn once, at the very bottom) —
    # Zone A has no baseline of its own.
    mt_b, ch_b = mt_a + ch_a + 16, 64
    mb = 16
    cw = vw - ml - mr

    n = len(labels)
    step = cw / max(n - 1, 1)

    def xs(i):
        return ml + i * step

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']

    # ── Zone A: line trend — no Y-axis, no gridlines, no baseline of its own
    # (the one shared x-axis line lives at the bottom of Zone B); every point
    # already carries its own value label, so the axis scale is redundant ──
    all_vals = [v for vals in series.values() for v in vals if v is not None]
    yhi_a = max(all_vals) * 1.15 if all_vals else 10.0
    yhi_a = max(yhi_a, 5.0)

    def ys_a(v):
        return mt_a + ch_a * (1.0 - v / yhi_a)

    # Each series' data labels sit on a fixed side of its own line (above for
    # the first series, below for the second) rather than both hugging their
    # points — with two lines this close together, labels anchored to the
    # same side collide/overlap wherever the lines cross or run parallel.
    for si, (name, vals) in enumerate(series.items()):
        color = colors.get(name, "#0284c7")
        pts = [(xs(i), ys_a(v)) for i, v in enumerate(vals) if v is not None]
        if len(pts) > 1:
            d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
            lines.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6"/>')
        label_dy = -6 if si == 0 else 12
        for i, v in enumerate(vals):
            if v is None:
                continue
            x, y = xs(i), ys_a(v)
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="{color}"/>')
            # The first point sits exactly on the y-axis, so a centered label
            # extends left into the value labels — start it to the right of
            # the point instead; every other point stays centered.
            anchor, tx = ("start", x + 3) if i == 0 else ("middle", x)
            lines.append(f'<text x="{tx:.1f}" y="{y + label_dy:.1f}" text-anchor="{anchor}" font-size="6.5" '
                         f'font-weight="bold" font-family="Arial,sans-serif" fill="{color}">{v:.0f}</text>')

    lx, ly = ml, 9
    for name in series:
        color = colors.get(name, "#0284c7")
        lines.append(f'<rect x="{lx}" y="{ly - 5}" width="9" height="3" fill="{color}"/>')
        lines.append(f'<text x="{lx + 12}" y="{ly - 2}" font-size="7" font-weight="bold" '
                     f'font-family="Arial,sans-serif" fill="{_SEMIS_INK}">{name}</text>')
        lx += 12 + len(name) * 4.6 + 16

    # ── Zone B: semi-finished steel, stacked by plant ──
    sub_y = mt_b - 9
    lines.append(f'<text x="{ml:.1f}" y="{sub_y:.1f}" font-size="6.8" font-weight="bold" '
                 f'font-family="Arial,sans-serif" fill="{_SEMIS_INK}">Semis by plant (\'000T &amp; %)</text>')
    lines.append(f'<text x="{vw - mr:.1f}" y="{sub_y:.1f}" text-anchor="end" font-size="5.4" '
                 f'font-family="Arial,sans-serif" font-style="italic" fill="#64748b">'
                 f'bold % = share of total · '
                 f'<tspan fill="{_SEMIS_OWN_PCT_LABEL_COLOR}" font-style="italic" text-decoration="underline">'
                 f'right (circle) % = share of plant\'s own Saleable Steel</tspan></text>')

    # Legend (plant colors) — top-right of Zone B's plot area.
    lx = vw - mr
    legend_items = list(reversed(_SEMIS_PLANTS))  # build right-to-left, ending with BSP first on screen
    for p in legend_items:
        lx -= len(p) * 4.2 + 3
        lines.append(f'<text x="{lx:.1f}" y="{mt_b - 1:.1f}" font-size="6.4" font-weight="bold" '
                     f'font-family="Arial,sans-serif" fill="{_SEMIS_INK}">{p}</text>')
        lx -= 10
        lines.append(f'<rect x="{lx:.1f}" y="{mt_b - 6:.1f}" width="7" height="5.5" rx="1" '
                     f'fill="{_SEMIS_COLORS[p]}"/>')
        lx -= 4

    month_totals = [semis_by_month.get(m, {}).get("total", 0) or 0 for m in semis_by_month]
    yhi_b = max(month_totals) * 1.2 if any(month_totals) else 10.0
    yhi_b = max(yhi_b, 5.0)
    base_b = mt_b + ch_b
    bar_w = 19.0
    seg_gap = 1.3  # surface-color ring between stacked segments (mark spec)

    for i, (label, month_key) in enumerate(zip(labels, semis_by_month.keys())):
        month = semis_by_month[month_key]
        x = xs(i)
        plants = month["plants"]
        total = month["total"]
        if total > 0:
            lines.append(f'<text x="{x:.1f}" y="{base_b - ch_b * min(total / yhi_b, 1.0) - 4:.1f}" '
                         f'text-anchor="middle" font-size="6.8" font-weight="bold" '
                         f'font-family="Arial,sans-serif" fill="{_SEMIS_INK}">{total:.0f}</text>')
        # Geometry pass first (no SVG emitted yet) — the own-% badges need
        # every segment's true center before any collision-avoidance can
        # run, so bar/label emission is split into a second pass below.
        geom = []
        y_cursor = base_b
        for seg in plants:
            seg_h = ch_b * seg["qty"] / yhi_b
            if seg_h <= 0:
                continue
            by = y_cursor - seg_h
            geom.append({"seg": seg, "seg_h": seg_h, "by": by, "cy": by + seg_h / 2})
            y_cursor = by

        # Own-% badges all sit at the same x (outside-right of the bar), so
        # the only collision axis is vertical — and `geom`'s order is
        # already real spatial adjacency (each entry touches its stacking
        # neighbors), just bottom-to-top (descending y). _declutter_1d only
        # needs consecutive-pair adjacency, not a particular direction, but
        # working in ascending (top-to-bottom) order reads more naturally.
        badge_r = _SEMIS_OWN_PCT_BADGE_R
        min_gap = badge_r * 2 + 0.8
        badge_idxs = [j for j, g in enumerate(geom) if g["seg"]["own_pct"] is not None]
        ideal_desc = [geom[j]["cy"] for j in badge_idxs]
        adjusted_asc = _declutter_1d(list(reversed(ideal_desc)), min_gap)
        badge_cy = dict(zip(badge_idxs, reversed(adjusted_asc)))

        for j, g in enumerate(geom):
            seg, seg_h, by, cy = g["seg"], g["seg_h"], g["by"], g["cy"]
            color = _SEMIS_COLORS[seg["plant"]]
            lines.append(f'<rect x="{x - bar_w / 2:.1f}" y="{by:.1f}" width="{bar_w:.1f}" '
                         f'height="{max(seg_h - seg_gap, 0.5):.1f}" fill="{color}"/>')
            # Share % must never just disappear on a thin segment (that's
            # what happened before this fix — several months' BSL/ISP
            # segments were too short for the label's 8.5px threshold, so
            # they silently lost their %): tall-enough segments get it
            # centered inside on the fill's own contrast color; a thin
            # segment still gets it, just moved outside to the left (own %
            # already lived outside to the right) instead of dropped.
            if seg["share_pct"] is not None:
                if seg_h >= 7:
                    lines.append(f'<text x="{x:.1f}" y="{cy + 2:.1f}" text-anchor="middle" font-size="6" '
                                 f'font-weight="bold" font-family="Arial,sans-serif" '
                                 f'fill="{_contrast_text(color)}">{seg["share_pct"]:.0f}%</text>')
                else:
                    lines.append(f'<text x="{x - bar_w / 2 - 2.5:.1f}" y="{cy + 1.8:.1f}" text-anchor="end" '
                                 f'font-size="5.4" font-weight="bold" font-family="Arial,sans-serif" '
                                 f'fill="{_SEMIS_INK}">{seg["share_pct"]:.0f}%</text>')
            if seg["own_pct"] is not None:
                bcy = badge_cy[j]
                bcx = x + bar_w / 2 + 2.5 + badge_r
                # Collision-avoidance can shift a badge away from its true
                # segment center — a thin leader line back to the segment's
                # edge keeps it legible which color the % belongs to.
                if abs(bcy - cy) > 0.5:
                    lines.append(f'<line x1="{x + bar_w / 2 + 0.5:.1f}" y1="{cy:.1f}" '
                                 f'x2="{bcx - badge_r:.1f}" y2="{bcy:.1f}" '
                                 f'stroke="{_SEMIS_INK}" stroke-width="0.4"/>')
                lines.append(f'<circle cx="{bcx:.1f}" cy="{bcy:.1f}" r="{badge_r:.1f}" '
                             f'fill="{_SEMIS_OWN_PCT_BADGE_FILL}"/>')
                lines.append(f'<text x="{bcx:.1f}" y="{bcy + 1.3:.1f}" text-anchor="middle" '
                             f'font-size="{_SEMIS_OWN_PCT_BADGE_FS}" font-weight="bold" '
                             f'font-family="Arial,sans-serif" fill="{_SEMIS_INK}">'
                             f'{seg["own_pct"]:.0f}%</text>')

    # The one shared x-axis line for BOTH zones.
    lines.append(f'<line x1="{ml}" y1="{base_b:.1f}" x2="{vw - mr}" y2="{base_b:.1f}" '
                 f'stroke="#374151" stroke-width="0.8"/>')

    for i, label in enumerate(labels):
        lines.append(f'<text x="{xs(i):.1f}" y="{base_b + 12:.1f}" text-anchor="middle" '
                     f'font-size="6.6" font-family="Arial,sans-serif" fill="#64748b">{label}</text>')

    lines.append("</svg>")
    return "\n".join(lines)




# ── SVG: grouped bar chart — one group per production item, one bar per FY ──

def _bar_path(x: float, y: float, w: float, h: float, r: float) -> str:
    """Bar outline with a half-circular top cap (radius r, clamped to fit)
    and a flat bottom — the "capsule top" bar shape."""
    r = max(0.0, min(r, w / 2, h))
    if r <= 0.05:
        return f'M{x:.1f},{y + h:.1f} L{x:.1f},{y:.1f} L{x + w:.1f},{y:.1f} L{x + w:.1f},{y + h:.1f} Z'
    return (f'M{x:.1f},{y + h:.1f} '
            f'L{x:.1f},{y + r:.1f} '
            f'A{r:.1f},{r:.1f} 0 0 1 {x + r:.1f},{y:.1f} '
            f'L{x + w - r:.1f},{y:.1f} '
            f'A{r:.1f},{r:.1f} 0 0 1 {x + w:.1f},{y + r:.1f} '
            f'L{x + w:.1f},{y + h:.1f} Z')


def _ytd_bar_chart_svg(items: list, data: dict, fy_labels: list, growth: dict,
                        vw: int = 980, vh: int = 250) -> str:
    ml, mr, mt, mb = 34, 10, 28, 50
    cw, ch = vw - ml - mr, vh - mt - mb

    all_vals = [v for item in items for (_, v) in data[item] if v is not None]
    yhi = max(all_vals) * 1.25 if all_vals else 10.0
    yhi = max(yhi, 5.0)

    n_groups = len(items)
    n_bars = len(fy_labels)
    group_gap = 26.0          # whitespace between item groups
    side_pad = 6.0            # padding inside a group before/after its bar cluster
    bar_gap = 3.5             # gap between the FY bars within one group
    bar_shrink = 0.6          # slim the bars down from their natural fit width

    group_w = (cw - group_gap * (n_groups - 1)) / n_groups
    raw_w = (group_w - 2 * side_pad - bar_gap * (n_bars - 1)) / n_bars
    bar_w = max(5.0, raw_w * bar_shrink)
    cluster_w = n_bars * bar_w + (n_bars - 1) * bar_gap
    cluster_pad = (group_w - cluster_w) / 2

    fs = 11.0        # item name / growth labels
    data_fs = 14.0   # in-bar data value labels — larger, read against the bar's own fill

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']

    lx, ly = ml, 14
    for j, fy_label in enumerate(fy_labels):
        note = " (YTD)" if j == len(fy_labels) - 1 else ""
        label = f"FY{fy_label}{note}"
        lines.append(f'<rect x="{lx}" y="{ly - 7}" width="10" height="8" rx="2" fill="{_YTD_BAR_COLORS[j]}"/>')
        lines.append(f'<text x="{lx + 13}" y="{ly}" font-size="8" font-family="Arial,sans-serif" '
                     f'fill="#334155">{label}</text>')
        lx += 13 + len(label) * 5.0 + 14

    lines.append(f'<line x1="{ml}" y1="{mt + ch:.1f}" x2="{vw - mr}" y2="{mt + ch:.1f}" '
                 f'stroke="#374151" stroke-width="0.7"/>')

    gx = ml
    for item in items:
        bx = gx + cluster_pad
        for j, (_, v) in enumerate(data[item]):
            color = _YTD_BAR_COLORS[j]
            x = bx + j * (bar_w + bar_gap)
            cx = x + bar_w / 2
            if v is None:
                bh, by = 3, mt + ch - 3
                lines.append(f'<rect x="{x:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh}" '
                             f'fill="none" stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="2,1.5"/>')
                lines.append(f'<text x="{cx:.1f}" y="{by - 3:.1f}" text-anchor="middle" '
                             f'font-size="5.6" font-family="Arial,sans-serif" fill="#94a3b8">N/A</text>')
            else:
                bh = max(2.0, ch * v / yhi)
                by = mt + ch - bh
                lines.append(f'<path d="{_bar_path(x, by, bar_w, bh, bar_w / 2)}" fill="{color}"/>')
                val_str = f"{v:,.0f}"
                # Centered inside the bar when it's tall enough for the label
                # to fully fit; short bars fall back to just above (dark ink,
                # since that sits on the page background, not the fill).
                fits_inside = bh >= data_fs * len(val_str) * 0.62 + 10
                if fits_inside:
                    ty, tfill = by + bh / 2, _contrast_text(color)
                else:
                    ty, tfill = by - 8, "#1e293b"
                lines.append(f'<text x="{cx:.1f}" y="{ty:.1f}" text-anchor="middle" dominant-baseline="middle" '
                             f'transform="rotate(-90 {cx:.1f} {ty:.1f})" '
                             f'font-size="{data_fs:.1f}" font-weight="bold" font-family="Arial,sans-serif" '
                             f'fill="{tfill}">{val_str}</text>')
        lxc = gx + group_w / 2
        lyc = mt + ch + 20
        lines.append(f'<text x="{lxc:.1f}" y="{lyc:.1f}" text-anchor="middle" font-size="{fs:.1f}" '
                     f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{item}</text>')
        g = growth.get(item, {})
        if g.get("pct") is not None:
            arrow = "▲" if g["good"] else "▼"
            gcolor = "#059669" if g["good"] else "#b91c1c"
            lines.append(f'<text x="{lxc:.1f}" y="{lyc + 16:.1f}" text-anchor="middle" font-size="{fs:.1f}" '
                         f'font-weight="bold" font-family="Arial,sans-serif" fill="{gcolor}">'
                         f'{arrow} {abs(g["pct"]):.1f}%</text>')
        gx += group_w + group_gap

    lines.append("</svg>")
    return "\n".join(lines)


# ── data sections ────────────────────────────────────────────────────────────

def _production_section(report_month: str) -> list:
    rows = []
    for item in _PROD_ITEMS:
        v = compute_item_row(report_month, item)
        rows.append({
            "item": item,
            "month_act": v[1], "month_pct_ful": v[3],
            "pct_growth_cply": v[5], "growth_good": None if v[5] == "" else int(v[5]) >= 0,
        })
    return rows


def _ytd_trend_section(report_month: str) -> dict:
    """Last-4-FY grouped bar chart: for each production item, YTD (Apr through
    the report month, replayed on each of the last 4 FYs) side by side, plus
    the growth from the immediately preceding FY to the current one."""
    n_months = len(db.get_ytd_months(report_month))
    fy_starts = _last4_fy_starts(report_month)
    fy_labels = [_fy_label(fs) for fs in fy_starts]

    data, growth = {}, {}
    for item in _PROD_ITEMS:
        db_item = _YTD_DB_ITEM.get(item, item)
        vals = [db.get_sail_production_ytd_actual(_ytd_months_for_fy(fs, n_months), db_item)
                for fs in fy_starts]
        data[item] = list(zip(fy_labels, vals))
        prev, current = vals[-2], vals[-1]
        if prev and current is not None:
            pct = (current - prev) / prev * 100
            growth[item] = {"pct": round(pct, 1), "good": pct >= 0}
        else:
            growth[item] = {"pct": None, "good": None}

    cur_months = _ytd_months_for_fy(fy_starts[-1], n_months)
    period_label = _dt.datetime.strptime(cur_months[0], "%Y-%m").strftime("%b")
    if n_months > 1:
        period_label += "-" + _dt.datetime.strptime(cur_months[-1], "%Y-%m").strftime("%b")

    return {
        "fy_labels": fy_labels,
        "period_label": period_label,
        "svg": _ytd_bar_chart_svg(_PROD_ITEMS, data, fy_labels, growth),
    }


def _imported_coal_blend_pct(report_month: str):
    """SAIL 'Imported Coking Coal in Blend' % for report_month = imported
    (Hard + Soft) / total coking coal (Indigenous PCC + MCC + Imported Hard
    + Soft), summed across the 5 plants - a sum-of-quantities ratio, so
    plant-level quantities are summed first and the % taken once at the
    end (not averaged per-plant), matching how the source EPI report's own
    SAIL blend % is derived."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        ph = ",".join("?" * len(_COAL_BLEND_PLANTS))
        cur.execute(
            f"SELECT plant, techno_json FROM techno_data "
            f"WHERE report_month=? AND unit='General' AND plant IN ({ph})",
            [report_month, *_COAL_BLEND_PLANTS],
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    import json as _json
    indigenous = imported = 0.0
    found = False
    for _plant, tj in rows:
        m = _json.loads(tj).get("month", {})
        pcc, mcc = m.get("indigenous_pcc"), m.get("indigenous_mcc")
        hard, soft = m.get("imported_hard_coal"), m.get("imported_soft_coal")
        if None in (pcc, mcc, hard, soft):
            continue
        found = True
        indigenous += pcc + mcc
        imported += hard + soft
    total = indigenous + imported
    return round(imported / total * 100, 1) if found and total > 0 else None


def _imported_coal_blend_target(report_month: str):
    """SAIL's own Imported Coking Coal in Blend annual target — stored in
    the same techno_plan_fy table every other techno target uses, under
    plant_name='SAIL', unit='Coal_Consumption', key='imported_total_pct'
    (see page_key_parameters.py's _coal_blend_targets / main.py's
    /api/coal-blend-targets, entered via /data-entry/annual-target's "Coal
    Blend %" tab) — a different (plant_name, unit) pair than page 27's own
    SAIL techno target row ('SAIL', 'Shop'), since this concept lives
    outside that table entirely (see page_key_parameters.py's module note)."""
    fy = db.get_fy_for_month(report_month)
    data = db.get_techno_plan("SAIL", fy, unit="Coal_Consumption").get("data", {})
    v = data.get("imported_total_pct")
    return v.get("value") if isinstance(v, dict) else v


def _techno_section(report_month: str) -> list:
    te = {row["parameter"]: row for row in generate_at_a_glance_te_table(report_month)}

    # "Imported Coking Coal in Blend" doesn't come from generate_at_a_glance_
    # te_table (see _COAL_BLEND_PLANTS' module comment) — computed here and
    # merged into `te` in the SAME {"unit", "values": [target, actual]} shape
    # every other row has, so it flows through the one loop below like any
    # other parameter and its tile position follows _TE_PARAMS' own order
    # instead of always landing last. It's already listed in
    # _TE_LOWER_IS_BETTER (lower blend % is "good"), so the loop's existing
    # sign-flip covers it too — no separate delta formula needed.
    blend_pct = _imported_coal_blend_pct(report_month)
    if blend_pct is not None:
        blend_target = _imported_coal_blend_target(report_month)
        te["Imported Coking Coal in Blend"] = {
            "unit": "%",
            "values": [
                f"{blend_target:.1f}" if blend_target is not None else "",
                f"{blend_pct:.1f}",
            ],
        }

    out = []
    for name in _TE_PARAMS:
        row = te.get(name)
        if not row:
            continue
        target, month_actual = row["values"][0], row["values"][1]
        t, m = _num(target), _num(month_actual)
        delta = None
        if t and m is not None:
            delta = (m - t) / t * 100
            if name in _TE_LOWER_IS_BETTER:
                delta = -delta
        out.append({
            "parameter": name, "unit": row["unit"],
            "target": target, "month_actual": month_actual,
            "delta_pct": None if delta is None else round(delta, 1),
            "good": None if delta is None else delta >= 0,
            "bg_key": _TE_CATEGORY_BG.get(name, "highlight_default_row_bg"),
        })
    return out


_VA_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_VA_BAR_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
_VA_ORANGE = "#eb6834"
_VA_LINE_COLOR = "#334155"


def _va_period_saleable_total(cur, months) -> float:
    """SAIL Saleable Steel ('000T) summed across these months — the
    denominator for a Value Added Steel % of Saleable Steel figure over any
    period (FY or quarter), not just a single report month."""
    total, has = 0.0, False
    for m in months:
        for p in _VA_PLANTS:
            v = _saleable_steel(cur, m, p)
            if v is not None:
                total += v
                has = True
    return total if has else None


def _va_period_value(cur, months):
    """(qty_tonnes, pct_of_saleable) for SAIL Value Added (Special) Steel
    over these months, or (None, None) if nothing's been reported yet."""
    qty, has = _sum_actual(cur, months, "SAIL")
    if not has:
        return None, None
    saleable_000T = _va_period_saleable_total(cur, months)
    pct = qty / (saleable_000T * 1000) * 100 if saleable_000T else None
    return qty, pct


def _quarter_bounds(report_month: str):
    """(start_ym, end_ym) of the Apr-Jun/Jul-Sep/Oct-Dec/Jan-Mar quarter
    containing report_month."""
    y, m = int(report_month[:4]), int(report_month[5:7])
    qs = ((m - 1) // 3) * 3 + 1
    return f"{y}-{qs:02d}", f"{y}-{qs + 2:02d}"


def _just_ended_quarter(report_month: str):
    """The most recently CONCLUDED quarter as of report_month: the quarter
    containing report_month itself if report_month is its last month,
    otherwise the quarter before it."""
    start, end = _quarter_bounds(report_month)
    if end == report_month:
        return start, end
    y, m = int(start[:4]), int(start[5:7])
    pm = m - 3
    py = y - 1 if pm <= 0 else y
    pm = pm + 12 if pm <= 0 else pm
    return f"{py}-{pm:02d}", f"{py}-{pm + 2:02d}"


def _quarter_months(start_ym: str, end_ym: str) -> list:
    y, m0 = int(start_ym[:4]), int(start_ym[5:7])
    m1 = int(end_ym[5:7])
    return [f"{y}-{mm:02d}" for mm in range(m0, m1 + 1)]


def _quarter_label(start_ym: str, end_ym: str) -> str:
    s = _dt.datetime.strptime(start_ym, "%Y-%m").strftime("%b")
    e = _dt.datetime.strptime(end_ym, "%Y-%m").strftime("%b'%y")
    return f"{s}-{e}"


def _fmt_int(v) -> str:
    return f"{v:,.0f}"


def _fmt_million(v) -> str:
    """Tonnes -> Million T, 2 decimal places, for the value-added qty line."""
    return f"{v / 1_000_000:.2f}"


def _split_cat_label(cat: str):
    """Category axis labels like 'FY2026-27 (YTD rate)' split into a main
    line and a smaller parenthetical sub-line, so the main label can run at
    the requested 11pt without the annotation forcing it to shrink to fit."""
    if " (" in cat:
        main, rest = cat.split(" (", 1)
        return main, "(" + rest
    return cat, None


def _value_added_combo_svg(categories: list, pct_vals: list, qty_vals: list,
                            bar_colors: list, title: str,
                            vw: int = 470, vh: int = 250) -> str:
    """Grouped bar (% of Saleable Steel) + line (Qty, Million T) combo, on two
    independent scales: the % axis auto-scales with generous headroom so
    bars only ever occupy the lower ~60% of the chart, and the qty line is
    deliberately mapped into a fixed band near the top (~4%-26% of chart
    height) — so on any real data the line draws clear above the bar tops,
    per spec, rather than because the two series happen to be comparable."""
    ml, mr, mt, mb = 10, 10, 42, 40
    cw, ch = vw - ml - mr, vh - mt - mb

    pct_present = [v for v in pct_vals if v is not None]
    pct_yhi = max(5.0, (max(pct_present) if pct_present else 10.0) * 1.6)

    qty_present = [v for v in qty_vals if v is not None]
    qty_lo = min(qty_present) * 0.85 if qty_present else 0.0
    qty_hi = max(qty_present) * 1.08 if qty_present else 1.0
    if qty_hi <= qty_lo:
        qty_hi = qty_lo + 1.0

    line_top, line_bot = mt + ch * 0.04, mt + ch * 0.26

    def line_y(v):
        return line_bot - (line_bot - line_top) * (v - qty_lo) / (qty_hi - qty_lo)

    n = len(categories)
    slot_w = cw / n
    bar_w = max(34.0, slot_w * 0.4)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']
    lines.append(f'<text x="{vw / 2:.0f}" y="12" text-anchor="middle" font-size="8.5" '
                 f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{title}</text>')
    lines.append(f'<line x1="{ml}" y1="{mt + ch:.1f}" x2="{vw - mr}" y2="{mt + ch:.1f}" '
                 f'stroke="#374151" stroke-width="0.7"/>')

    pts = []
    x = ml
    for i, cat in enumerate(categories):
        color = bar_colors[i % len(bar_colors)]
        cx = x + slot_w / 2
        pv = pct_vals[i]
        if pv is None:
            by = mt + ch - 3
            lines.append(f'<rect x="{cx - bar_w / 2:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="3" '
                         f'fill="none" stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="2,1.5"/>')
        else:
            bh = max(2.0, ch * pv / pct_yhi)
            by = mt + ch - bh
            lines.append(f'<path d="{_bar_path(cx - bar_w / 2, by, bar_w, bh, bar_w / 2)}" fill="{color}"/>')
            val_str = f"{pv:.1f}%"
            ty = by + bh / 2
            lines.append(f'<text x="{cx:.1f}" y="{ty:.1f}" text-anchor="middle" dominant-baseline="middle" '
                         f'font-size="12" font-weight="bold" font-family="Arial,sans-serif" '
                         f'fill="#000000">{val_str}</text>')
        main_cat, sub_cat = _split_cat_label(cat)
        lines.append(f'<text x="{cx:.1f}" y="{mt + ch + 16:.1f}" text-anchor="middle" font-size="11" '
                     f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{main_cat}</text>')
        if sub_cat:
            lines.append(f'<text x="{cx:.1f}" y="{mt + ch + 27:.1f}" text-anchor="middle" font-size="7.5" '
                         f'font-family="Arial,sans-serif" fill="#64748b">{sub_cat}</text>')
        qv = qty_vals[i]
        if qv is not None:
            pts.append((cx, line_y(qv), qv))
        x += slot_w

    if len(pts) >= 2:
        d = "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py, _ in pts)
        lines.append(f'<path d="{d}" fill="none" stroke="{_VA_LINE_COLOR}" stroke-width="1.6"/>')
    for px, py, qv in pts:
        lines.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.4" fill="{_VA_LINE_COLOR}"/>')
        lines.append(f'<text x="{px:.1f}" y="{py - 8:.1f}" text-anchor="middle" font-size="12" '
                     f'font-weight="bold" font-family="Arial,sans-serif" fill="{_VA_LINE_COLOR}">{_fmt_million(qv)}</text>')

    # legend — stacked two rows (rather than side-by-side) so the 11pt
    # labels never overlap on the narrower vw=300 quarter chart.
    ly1 = 24
    lines.append(f'<rect x="{ml}" y="{ly1 - 7}" width="10" height="8" fill="{bar_colors[0]}"/>')
    lines.append(f'<text x="{ml + 14}" y="{ly1}" font-size="11" font-family="Arial,sans-serif" '
                 f'fill="#334155">% of Saleable Steel</text>')
    ly2 = ly1 + 13
    lines.append(f'<line x1="{ml}" y1="{ly2 - 3}" x2="{ml + 14}" y2="{ly2 - 3}" stroke="{_VA_LINE_COLOR}" stroke-width="1.8"/>')
    lines.append(f'<text x="{ml + 18}" y="{ly2}" font-size="11" font-family="Arial,sans-serif" '
                 f'fill="#334155">Qty (Million T)</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def _special_steel_section(report_month: str, month_label: str) -> dict:
    sail = generate_special_steel_sail(report_month)
    total = next((r for r in sail.get("rows", []) if r.get("type") == "sail-total"), {})
    pct_growth = total.get("pct_growth", "")
    month_qty_raw = total.get("actual", "")
    month_qty = _fmt_int(float(month_qty_raw)) if month_qty_raw not in ("", None) else ""

    conn = db.connect()
    cur = conn.cursor()
    try:
        fys = _last_n_fys(report_month, 5)
        fy_cats, fy_pct, fy_qty = [], [], []
        for j, fy in enumerate(fys):
            is_current = j == len(fys) - 1
            months = db.get_ytd_months(report_month) if is_current else _fy_months(fy)
            qty, pct = _va_period_value(cur, months)
            if is_current:
                qty = _current_fy_rate(cur, report_month, "SAIL")
                qty = qty * 1000 if qty is not None else None  # '000T -> T
            fy_cats.append(f"{fy[2:]}" + (" (YTD rate)" if is_current else ""))
            fy_pct.append(pct)
            fy_qty.append(qty)

        q_start, q_end = _just_ended_quarter(report_month)
        cply_start = f"{int(q_start[:4]) - 1}-{q_start[5:7]}"
        cply_end = f"{int(q_end[:4]) - 1}-{q_end[5:7]}"
        q_cats, q_pct, q_qty = [], [], []
        for start, end in [(cply_start, cply_end), (q_start, q_end)]:
            qty, pct = _va_period_value(cur, _quarter_months(start, end))
            q_cats.append(_quarter_label(start, end))
            q_pct.append(pct)
            q_qty.append(qty)
    finally:
        conn.close()

    return {
        "pct_ful": total.get("pct_ful", ""),
        "pct_growth": pct_growth, "growth_good": None if pct_growth == "" else int(pct_growth) >= 0,
        "abp_fy": total.get("abp_fy", ""),
        "special_pct": sail.get("special_pct", {}).get("current", ""),
        "month_title": f"For the Month ({month_label})",
        "month_qty": month_qty,
        "five_year_svg": _value_added_combo_svg(
            fy_cats, fy_pct, fy_qty, [_VA_ORANGE] * len(fy_cats),
            "Last 5 Years", vw=560, vh=222),
        "quarter_svg": _value_added_combo_svg(
            q_cats, q_pct, q_qty, [_VA_BAR_COLORS[0], _VA_BAR_COLORS[3]],
            "Quarter Just Ended vs CPLY", vw=300, vh=222),
    }


def _trend_section(report_month: str) -> dict:
    months = _trailing_months(report_month, 6)
    labels = [_dt.datetime.strptime(m, "%Y-%m").strftime("%b'%y") for m in months]
    series, colors = {}, {}
    for name, color in _TREND_SERIES:
        series[name] = [db.get_sail_production_actual(m, name) for m in months]
        colors[name] = color
    semis_by_month = _semis_breakdown_data(months)
    return {
        "months": labels,
        "svg": _trend_line_svg(labels, series, colors, semis_by_month),
    }


# ── public API ────────────────────────────────────────────────────────────────

def generate_at_a_glance(report_month: str) -> dict:
    dt = _dt.datetime.strptime(report_month, "%Y-%m")
    month_label = dt.strftime("%B %Y")
    month_short = dt.strftime("%b'%y")

    return {
        "type": "at_a_glance",
        "title": "SAIL Performance - At a Glance",
        "month_label": month_label,
        "production": _production_section(report_month),
        "ytd_trend": _ytd_trend_section(report_month),
        "techno": _techno_section(report_month),
        "special_steel": _special_steel_section(report_month, month_short),
        "trend": _trend_section(report_month),
    }
