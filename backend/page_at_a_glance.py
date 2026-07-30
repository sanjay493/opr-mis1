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
from page_techno import generate_summary_te_table
from page_special_steel import generate_special_steel_sail
from page_capital_repair import generate_capital_repair, fy_from_month, CR_PAGES

_PROD_ITEMS = ["Hot Metal", "Crude Steel", "Finished Steel", "Saleable Steel"]

# compute_item_row/db.get_sail_production_*_actual expect the DB's own item
# names — "Crude Steel" is stored as "Total Crude Steel"; Finished Steel is
# already correct as-is.
_YTD_DB_ITEM = {"Crude Steel": "Total Crude Steel"}

# Rate/consumption metrics are "good" when they go down; productivity is
# "good" when it goes up.
_TE_LOWER_IS_BETTER = {"Coke Rate", "Fuel Rate", "Specific Energy Consumption"}
_TE_PARAMS = ["Coke Rate", "Fuel Rate", "BF Productivity", "Specific Energy Consumption"]

# FY bar shading: 3 historical FYs light->dark blue, current (partial) FY in
# green — same "current year reads differently" convention page_special_steel
# _trend.py's _annual_bar_svg uses (there, gold shades + green; here, blue
# shades + green, to match this page's blue banner instead).
_YTD_BAR_COLORS = ["#bfdbfe", "#60a5fa", "#0284c7", "#059669"]

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

def _ytd_bar_chart_svg(items: list, data: dict, fy_labels: list, growth: dict,
                        vw: int = 980, vh: int = 230) -> str:
    ml, mr, mt, mb = 34, 10, 22, 40
    cw, ch = vw - ml - mr, vh - mt - mb

    all_vals = [v for item in items for (_, v) in data[item] if v is not None]
    yhi = max(all_vals) * 1.25 if all_vals else 10.0
    yhi = max(yhi, 5.0)

    n_groups = len(items)
    group_w = cw / n_groups
    n_bars = len(fy_labels)
    bar_gap = 3.0
    bar_w = max(8.0, (group_w - 14) / n_bars - bar_gap)
    fs = min(7.5, max(5.5, bar_w * 0.62))

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']

    lx, ly = ml, 12
    for j, fy_label in enumerate(fy_labels):
        note = " (YTD)" if j == len(fy_labels) - 1 else ""
        label = f"FY{fy_label}{note}"
        lines.append(f'<rect x="{lx}" y="{ly - 6}" width="9" height="7" fill="{_YTD_BAR_COLORS[j]}"/>')
        lines.append(f'<text x="{lx + 12}" y="{ly}" font-size="6.8" font-family="Arial,sans-serif" '
                     f'fill="#334155">{label}</text>')
        lx += 12 + len(label) * 4.4 + 12

    lines.append(f'<line x1="{ml}" y1="{mt + ch:.1f}" x2="{vw - mr}" y2="{mt + ch:.1f}" '
                 f'stroke="#374151" stroke-width="0.7"/>')

    gx = ml
    for item in items:
        bx = gx + 7
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
                lines.append(f'<rect x="{x:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                             f'fill="{color}" rx="1"/>')
                val_str = f"{v:,.0f}"
                if bh >= 14:
                    ty, fill = by + bh / 2 + fs * 0.35, _contrast_text(color)
                else:
                    ty, fill = by - 3, color
                lines.append(f'<text x="{cx:.1f}" y="{ty:.1f}" text-anchor="middle" '
                             f'font-size="{fs:.1f}" font-weight="bold" font-family="Arial,sans-serif" '
                             f'fill="{fill}">{val_str}</text>')
        lxc = gx + group_w / 2
        lyc = mt + ch + 13
        lines.append(f'<text x="{lxc:.1f}" y="{lyc:.1f}" text-anchor="middle" font-size="8" '
                     f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{item}</text>')
        g = growth.get(item, {})
        if g.get("pct") is not None:
            arrow = "▲" if g["good"] else "▼"
            gcolor = "#059669" if g["good"] else "#b91c1c"
            lines.append(f'<text x="{lxc:.1f}" y="{lyc + 11:.1f}" text-anchor="middle" font-size="7.5" '
                         f'font-weight="bold" font-family="Arial,sans-serif" fill="{gcolor}">'
                         f'{arrow} {abs(g["pct"]):.1f}%</text>')
        gx += group_w

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


def _techno_section(report_month: str) -> list:
    te = {row["parameter"]: row for row in generate_summary_te_table(report_month)}
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


def _parse_schedule_days(schedule_days, period) -> float:
    """schedule_days is free text like '9 days', '45 days', or '7 days each'
    (the last meaning that many days per period listed in `period`, e.g.
    "Apr'26, Jan'27" -> two separate repair windows of 7 days apiece)."""
    if not schedule_days:
        return 0.0
    m = _re.search(r"(\d+(?:\.\d+)?)", schedule_days)
    if not m:
        return 0.0
    days = float(m.group(1))
    if "each" in schedule_days.lower():
        n_periods = len([p for p in (period or "").split(",") if p.strip()]) or 1
        days *= n_periods
    return days


def _capital_repair_section(report_month: str) -> list:
    """Days under repair (scheduled vs. actually-started/completed, going by
    whether `actual` has been filled in), not job counts — a plant with a
    few very long jobs and one with many short ones aren't comparable by job
    count alone."""
    fy = fy_from_month(report_month)
    out = []
    for plant in CR_PAGES.values():  # BSP, DSP, RSP, BSL, ISP — page order 36-40
        cr = generate_capital_repair(plant, fy)
        rows = [r for sec in cr.get("sections", []) for r in sec.get("rows", [])]
        total_days = sum(_parse_schedule_days(r.get("schedule_days"), r.get("period")) for r in rows)
        completed_days = sum(_parse_schedule_days(r.get("schedule_days"), r.get("period"))
                              for r in rows if (r.get("actual") or "").strip())
        out.append({
            "plant": plant,
            "completed_days": round(completed_days),
            "total_days": round(total_days),
            "pct": round(completed_days / total_days * 100) if total_days else None,
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
        "title": "SAIL OMI — Report at a Glance",
        "month_label": month_label,
        "production": _production_section(report_month),
        "ytd_trend": _ytd_trend_section(report_month),
        "techno": _techno_section(report_month),
        "special_steel": _special_steel_section(report_month, month_short),
        "capital_repair": _capital_repair_section(report_month),
        "trend": _trend_section(report_month),
    }
