"""
MIS at a Glance — infographic-style snapshot page inserted right after the
Cover page (see AT_A_GLANCE_PAGE_ID in main.py). Composites headline numbers
already computed elsewhere in the report — production, techno-economic,
special steel, capital repair — into one visual dashboard, plus a short
production trend line, so a reader gets the month's story in one page before
diving into the detailed 40-page report.

Not part of the fixed 1-40 page numbering — see main.py's comment next to
AT_A_GLANCE_PAGE_ID for why (also individually browsable on-screen — see
get_data()'s page_number handling and PageRenderer.js's 'at_a_glance' case).
"""
import datetime as _dt
import re as _re

import db
from report_utils import compute_item_row
from page_techno import generate_at_a_glance_te_table
from page_special_steel import generate_special_steel_sail
from page_capital_repair import generate_capital_repair, fy_from_month, CR_PAGES

_PROD_ITEMS = ["Hot Metal", "Crude Steel", "Finished Steel", "Saleable Steel"]

# compute_item_row/db.get_sail_production_*_actual expect the DB's own item
# names — "Crude Steel" is stored as "Total Crude Steel"; Finished Steel is
# already correct as-is.
_YTD_DB_ITEM = {"Crude Steel": "Total Crude Steel"}

# Rate/consumption metrics are "good" when they go down; productivity is
# "good" when it goes up. Sinter/Pellet in Burden are mix-ratio params with
# no universal "better" direction, so they're left out of this set (default:
# above target reads as good) same as BF Productivity.
_TE_LOWER_IS_BETTER = {"Coke Rate", "Fuel Rate", "Specific Energy Consumption", "TMI", "Sp. CO2 Emission"}
_TE_PARAMS = [
    "Coke Rate", "Fuel Rate", "BF Productivity", "Specific Energy Consumption",
    "CDI Rate", "Sinter in Burden", "Pellet in Burden", "TMI", "Sp. CO2 Emission",
]

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


# ── SVG: two-series monthly trend line ───────────────────────────────────────

def _trend_line_svg(labels: list, series: dict, colors: dict, vw: int = 480, vh: int = 160) -> str:
    ml, mr, mt, mb = 34, 10, 16, 20
    cw, ch = vw - ml - mr, vh - mt - mb

    all_vals = [v for vals in series.values() for v in vals if v is not None]
    yhi = max(all_vals) * 1.15 if all_vals else 10.0
    yhi = max(yhi, 5.0)

    n = len(labels)
    step = cw / max(n - 1, 1)

    def xs(i):
        return ml + i * step

    def ys(v):
        return mt + ch * (1.0 - v / yhi)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']

    for k in range(4):
        v = yhi * k / 3
        gy = ys(v)
        lines.append(f'<line x1="{ml}" y1="{gy:.1f}" x2="{vw - mr}" y2="{gy:.1f}" '
                     f'stroke="#e2e8f0" stroke-width="0.6"/>')
        lines.append(f'<text x="{ml - 4:.1f}" y="{gy + 2.5:.1f}" text-anchor="end" font-size="6.5" '
                     f'font-family="Arial,sans-serif" fill="#64748b">{v:.0f}</text>')
    lines.append(f'<line x1="{ml}" y1="{mt + ch:.1f}" x2="{vw - mr}" y2="{mt + ch:.1f}" '
                 f'stroke="#374151" stroke-width="0.8"/>')

    for name, vals in series.items():
        color = colors.get(name, "#0284c7")
        pts = [(xs(i), ys(v)) for i, v in enumerate(vals) if v is not None]
        if len(pts) > 1:
            d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
            lines.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6"/>')
        for i, v in enumerate(vals):
            if v is None:
                continue
            x, y = xs(i), ys(v)
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="{color}"/>')
        last = next(((i, v) for i, v in reversed(list(enumerate(vals))) if v is not None), None)
        if last:
            i, v = last
            x, y = xs(i), ys(v)
            lines.append(f'<text x="{x:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-size="7" '
                         f'font-weight="bold" font-family="Arial,sans-serif" fill="{color}">{v:.0f}</text>')

    for i, label in enumerate(labels):
        lines.append(f'<text x="{xs(i):.1f}" y="{mt + ch + 13:.1f}" text-anchor="middle" '
                     f'font-size="7" font-family="Arial,sans-serif" fill="#64748b">{label}</text>')

    lx, ly = ml, 10
    for name in series:
        color = colors.get(name, "#0284c7")
        lines.append(f'<rect x="{lx}" y="{ly - 5}" width="9" height="3" fill="{color}"/>')
        lines.append(f'<text x="{lx + 12}" y="{ly - 2}" font-size="7" font-weight="bold" '
                     f'font-family="Arial,sans-serif" fill="#1e293b">{name}</text>')
        lx += 12 + len(name) * 4.6 + 16

    lines.append("</svg>")
    return "\n".join(lines)


# ── SVG: two-bar comparison (Orders vs Actual) ───────────────────────────────

def _two_bar_svg(label_a: str, val_a, label_b: str, val_b, title: str = "",
                  vw: int = 220, vh: int = 150) -> str:
    ml, mr, mt, mb = 14, 14, 20, 22
    cw, ch = vw - ml - mr, vh - mt - mb

    vals = [v for v in (val_a, val_b) if v is not None]
    yhi = max(vals) * 1.2 if vals else 10.0
    yhi = max(yhi, 5.0)

    slot = cw / 2
    bar_w = slot * 0.55
    colors = ["#94a3b8", "#0284c7"]

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']
    if title:
        lines.append(f'<text x="{vw / 2:.0f}" y="11" text-anchor="middle" font-size="8" '
                     f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{title}</text>')
    lines.append(f'<line x1="{ml}" y1="{mt + ch:.1f}" x2="{vw - mr}" y2="{mt + ch:.1f}" '
                 f'stroke="#374151" stroke-width="0.7"/>')

    for i, (label, v) in enumerate([(label_a, val_a), (label_b, val_b)]):
        x = ml + i * slot + (slot - bar_w) / 2
        color = colors[i]
        if v is None:
            by, bh = mt + ch - 3, 3
            lines.append(f'<rect x="{x:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh}" '
                         f'fill="none" stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="2,1.5"/>')
        else:
            bh = max(2.0, ch * v / yhi)
            by = mt + ch - bh
            lines.append(f'<rect x="{x:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                         f'fill="{color}" rx="1.5"/>')
            if bh >= 16:
                ty, fill = by + bh / 2 + 3, _contrast_text(color)
            else:
                ty, fill = by - 4, color
            lines.append(f'<text x="{x + bar_w / 2:.1f}" y="{ty:.1f}" text-anchor="middle" '
                         f'font-size="7.5" font-weight="bold" font-family="Arial,sans-serif" '
                         f'fill="{fill}">{v:,.0f}</text>')
        lines.append(f'<text x="{x + bar_w / 2:.1f}" y="{mt + ch + 12:.1f}" text-anchor="middle" '
                     f'font-size="7.5" font-weight="bold" font-family="Arial,sans-serif" '
                     f'fill="#1e293b">{label}</text>')

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
    the overall growth from the oldest FY shown to the current one."""
    n_months = len(db.get_ytd_months(report_month))
    fy_starts = _last4_fy_starts(report_month)
    fy_labels = [_fy_label(fs) for fs in fy_starts]

    data, growth = {}, {}
    for item in _PROD_ITEMS:
        db_item = _YTD_DB_ITEM.get(item, item)
        vals = [db.get_sail_production_ytd_actual(_ytd_months_for_fy(fs, n_months), db_item)
                for fs in fy_starts]
        data[item] = list(zip(fy_labels, vals))
        oldest, current = vals[0], vals[-1]
        if oldest and current is not None:
            pct = (current - oldest) / oldest * 100
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


def _techno_section(report_month: str) -> list:
    te = {row["parameter"]: row for row in generate_at_a_glance_te_table(report_month)}
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
        })

    blend_pct = _imported_coal_blend_pct(report_month)
    if blend_pct is not None:
        out.append({
            "parameter": "Imported Coking Coal in Blend", "unit": "%",
            "target": "", "month_actual": f"{blend_pct:.1f}",
            "delta_pct": None, "good": None,
        })
    return out


def _special_steel_section(report_month: str, month_label: str) -> dict:
    sail = generate_special_steel_sail(report_month)
    total = next((r for r in sail.get("rows", []) if r.get("type") == "sail-total"), {})
    orders, actual = _num(total.get("orders")), _num(total.get("actual"))
    pct_growth = total.get("pct_growth", "")
    return {
        "orders": total.get("orders", ""), "actual": total.get("actual", ""),
        "pct_ful": total.get("pct_ful", ""),
        "pct_growth": pct_growth, "growth_good": None if pct_growth == "" else int(pct_growth) >= 0,
        "abp_fy": total.get("abp_fy", ""),
        "special_pct": sail.get("special_pct", {}).get("current", ""),
        "bar_svg": _two_bar_svg("Orders", orders, "Actual", actual,
                                 title=f"Special Steel — {month_label} (T)"),
    }


_CR_GRACE_DAYS = 1.5  # e.g. a 10-day plan finishing on day 11.5 still counts as on time

_CR_DATE_RANGE_RE = _re.compile(
    r"(\d{1,2})\.(\d{1,2})\.(\d{2})\s*-\s*(\d{1,2})\.(\d{1,2})\.(\d{2})"
)


def _parse_planned_days(schedule_days) -> float:
    """schedule_days is free text like '9 days', '45 days', '5 Months', or
    '7 days/20 days' (one DB row is treated as one repair job for these
    counts regardless of how many numbers its schedule text happens to
    mention — see the module's own note that this field is inherently messy
    free text). '+'-joined figures (e.g. '1+10+2*') are additive phases of
    the SAME job and are summed; '/'-joined figures (e.g. '7 days/20 days')
    are alternative windows we can't disambiguate against the single
    `actual` field, so only the first is used."""
    if not schedule_days:
        return None
    s = schedule_days.strip()
    m = _re.search(r"(\d+(?:\.\d+)?)\s*Month", s, _re.I)
    if m:
        return float(m.group(1)) * 30
    if "+" in s:
        nums = _re.findall(r"\d+(?:\.\d+)?", s)
        return sum(float(n) for n in nums) if nums else None
    m = _re.search(r"(\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else None


def _parse_actual_status(actual):
    """-> (status, duration_days). status is one of:
    "not_started" (actual blank), "in_progress" (open-ended, e.g.
    "7.6.26-cont.."), "completed" (a full D.M.YY-D.M.YY range), or
    "unknown" (present but not in a recognized format)."""
    if not actual or not actual.strip():
        return "not_started", None
    s = actual.strip()
    m = _CR_DATE_RANGE_RE.match(s)
    if m:
        d1, mo1, y1, d2, mo2, y2 = (int(g) for g in m.groups())
        try:
            start = _dt.date(2000 + y1, mo1, d1)
            end = _dt.date(2000 + y2, mo2, d2)
        except ValueError:
            return "unknown", None
        return "completed", (end - start).days + 1
    if _re.search(r"cont", s, _re.I):
        return "in_progress", None
    return "unknown", None


def _capital_repair_section(report_month: str) -> list:
    """Per plant: repair JOB counts (completed vs. total planned for the FY —
    one capital_repair_table row = one job), split further into on-time vs.
    delayed (a completed job counts as on time if its actual duration is
    within _CR_GRACE_DAYS of its planned days), plus the average overrun
    across the delayed ones."""
    fy = fy_from_month(report_month)
    out = []
    for plant in CR_PAGES.values():  # BSP, DSP, RSP, BSL, ISP — page order 36-40
        cr = generate_capital_repair(plant, fy)
        rows = [r for sec in cr.get("sections", []) for r in sec.get("rows", [])]
        total = len(rows)
        completed = on_time = delayed = 0
        overrun_days = []
        for r in rows:
            status, duration = _parse_actual_status(r.get("actual"))
            if status != "completed":
                continue
            completed += 1
            planned = _parse_planned_days(r.get("schedule_days"))
            if planned is None or duration is None:
                continue
            if duration <= planned + _CR_GRACE_DAYS:
                on_time += 1
            else:
                delayed += 1
                overrun_days.append(duration - planned)
        out.append({
            "plant": plant,
            "completed": completed,
            "total": total,
            "pct": round(completed / total * 100) if total else None,
            "on_time": on_time,
            "delayed": delayed,
            "avg_delay_days": round(sum(overrun_days) / len(overrun_days), 1) if overrun_days else None,
        })
    return out


def _trend_section(report_month: str) -> dict:
    months = _trailing_months(report_month, 6)
    labels = [_dt.datetime.strptime(m, "%Y-%m").strftime("%b'%y") for m in months]
    series, colors = {}, {}
    for name, color in _TREND_SERIES:
        series[name] = [db.get_sail_production_actual(m, name) for m in months]
        colors[name] = color
    return {
        "months": labels,
        "svg": _trend_line_svg(labels, series, colors),
    }


# ── public API ────────────────────────────────────────────────────────────────

def generate_at_a_glance(report_month: str) -> dict:
    dt = _dt.datetime.strptime(report_month, "%Y-%m")
    month_label = dt.strftime("%B %Y")
    month_short = dt.strftime("%b'%y")

    return {
        "type": "at_a_glance",
        "title": "SAIL Performance — Report at a Glance",
        "month_label": month_label,
        "production": _production_section(report_month),
        "ytd_trend": _ytd_trend_section(report_month),
        "techno": _techno_section(report_month),
        "special_steel": _special_steel_section(report_month, month_short),
        "capital_repair": _capital_repair_section(report_month),
        "trend": _trend_section(report_month),
    }
