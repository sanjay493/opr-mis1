"""
Special Steel — Trend & Performance Analysis (Page 24).

Three visuals, per plant (BSP/DSP/RSP/BSL/ISP) plus a SAIL aggregate:
  1. Line chart  — monthly Special Steel % of Saleable Steel, last 3 FY + current FY.
  2. Bar chart   — annual Special Steel production ('000T): last 3 FY actuals plus
                   the current (partial) FY's rate, annualized from days elapsed
                   so far — not a plain YTD total.
  3. Bar chart   — current month's Special Steel production ('000T).

special_steel_orders only has data from 2025-04 onward (see db.py), so the two
oldest FYs are currently empty for every entity. Rather than special-case that,
every lookup here is "sum what exists, and say so if nothing does" — an FY/entity
with zero matching rows renders as a blank/"No data" bar instead of a misleading
0, so populating the older months later makes the chart fill in on its own.
"""
import calendar
import datetime as _dt
import sqlite3
import db

_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_SSPS = "SSPs"
_ENTITIES = _PLANTS + ["SAIL"]

# Same house palette as the page-3 techno bar charts (page_techno.py _C_FY/_C_TARGET/
# _C_MONTHLY = gold/green/blue) extended to a full 6-series Office-style set so each
# plant keeps one consistent color across both the line chart and the month bar chart.
_COLORS = {
    "BSP": "#4472C4",
    "DSP": "#ED7D31",
    "RSP": "#A5A5A5",
    "BSL": "#FFC000",
    "ISP": "#5B9BD5",
    "SAIL": "#70AD47",
}
# Annual bar chart: same bar (one entity) across 4 periods, so color encodes
# "how recent" instead — historical FYs shade from light to full gold, and the
# current FY's bar is green since it's a projected rate, not a closed actual.
_FY_BAR_COLORS = ["#FFE699", "#FFD966", "#FFC000", "#70AD47"]


def _fy_start_year(fy_label: str) -> int:
    return int(fy_label[:4])


def _fy_label_for_start(y: int) -> str:
    return f"{y}-{(y + 1) % 100:02d}"


def _last_n_fys(report_month: str, n: int = 4) -> list:
    """Chronological FY labels ending with the FY containing report_month."""
    cur_start = _fy_start_year(db.get_fy_for_month(report_month))
    return [_fy_label_for_start(cur_start - k) for k in range(n - 1, -1, -1)]


def _fy_months(fy_label: str) -> list:
    y = _fy_start_year(fy_label)
    return [f"{y}-{m:02d}" for m in range(4, 13)] + [f"{y + 1}-{m:02d}" for m in range(1, 4)]


def _days_in_fy(fy_label: str) -> int:
    y = _fy_start_year(fy_label)
    months = [(y, m) for m in range(4, 13)] + [(y + 1, m) for m in range(1, 4)]
    return sum(calendar.monthrange(yy, mm)[1] for yy, mm in months)


def _entity_plants(entity: str) -> list:
    return _PLANTS + [_SSPS] if entity == "SAIL" else [entity]


def _sum_actual(cur, months: list, entity: str):
    """(total_T, has_data) summed over the entity's underlying plant(s) for these months."""
    ph = ",".join("?" * len(months))
    total, has_any = 0.0, False
    for p in _entity_plants(entity):
        cur.execute(f"""
            SELECT COALESCE(SUM(actual_despatch),0), COUNT(*)
            FROM special_steel_orders WHERE report_month IN ({ph}) AND plant_name=?
        """, (*months, p))
        t, c = cur.fetchone()
        if c > 0:
            has_any = True
            total += (t or 0)
    return total, has_any


def _saleable_steel(cur, month, plant):
    cur.execute("""
        SELECT month_actual FROM production_table
        WHERE report_month=? AND plant_name=? AND item_name='Saleable Steel'
    """, (month, plant))
    r = cur.fetchone()
    return r[0] if r and r[0] is not None else None  # '000T


def _entity_saleable(cur, month, entity) -> float:
    plants = _PLANTS if entity == "SAIL" else [entity]
    vals = [v for p in plants if (v := _saleable_steel(cur, month, p)) is not None]
    return sum(vals) if vals else None


def _month_pct(cur, month, entity):
    special_T, has = _sum_actual(cur, [month], entity)
    if not has:
        return None
    saleable_000T = _entity_saleable(cur, month, entity)
    if not saleable_000T:
        return None
    return special_T / (saleable_000T * 1000) * 100


def _fy_annual_total(cur, fy_label, entity):
    """(value_000T or None). None means no rows at all for this FY/entity yet."""
    total, has = _sum_actual(cur, _fy_months(fy_label), entity)
    return (total / 1000.0) if has else None


def _current_fy_rate(cur, report_month, entity):
    """Annualized '000T rate: actual-to-date / elapsed days * days-in-FY."""
    ytd_months = db.get_ytd_months(report_month)
    total, has = _sum_actual(cur, ytd_months, entity)
    if not has:
        return None
    elapsed_days = sum(calendar.monthrange(int(m[:4]), int(m[5:7]))[1] for m in ytd_months)
    days_in_fy = _days_in_fy(db.get_fy_for_month(report_month))
    return (total / elapsed_days * days_in_fy) / 1000.0


# ── formatting / color helpers ─────────────────────────────────────────────────

def _fmt(v, dp=1):
    if v is None:
        return None
    return f"{v:.{dp}f}"


def _contrast_text(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#0f172a" if luminance > 0.6 else "#ffffff"


def _fy_short(fy_label: str) -> str:
    return f"FY{fy_label}"


# ── SVG: monthly % line chart ──────────────────────────────────────────────────

def _line_chart_svg(months: list, series: dict, fy_boundaries: list) -> str:
    vw, vh = 980, 340
    ml, mr, mt, mb = 40, 10, 22, 34
    cw, ch = vw - ml - mr, vh - mt - mb

    all_vals = [v for s in series.values() for v in s if v is not None]
    yhi = max(all_vals) if all_vals else 10.0
    yhi = max(5.0, yhi * 1.15)
    ylo = 0.0

    n = len(months)
    step = cw / max(n - 1, 1)

    def xs(i):
        return ml + i * step

    def ys(v):
        return mt + ch * (1.0 - (v - ylo) / (yhi - ylo))

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']

    # gridlines + y-axis labels (5 bands)
    for k in range(5):
        v = ylo + (yhi - ylo) * k / 4
        gy = ys(v)
        lines.append(f'<line x1="{ml}" y1="{gy:.1f}" x2="{vw - mr}" y2="{gy:.1f}" '
                      f'stroke="#e2e8f0" stroke-width="0.6"/>')
        lines.append(f'<text x="{ml - 4}" y="{gy + 2.5:.1f}" text-anchor="end" '
                      f'font-size="7" font-family="Arial,sans-serif" fill="#64748b">{v:.0f}%</text>')

    # FY boundary markers
    for idx, label in fy_boundaries:
        bx = xs(idx)
        lines.append(f'<line x1="{bx:.1f}" y1="{mt}" x2="{bx:.1f}" y2="{mt + ch}" '
                      f'stroke="#94a3b8" stroke-width="0.7" stroke-dasharray="2,2"/>')
        lines.append(f'<text x="{bx:.1f}" y="{mt + ch + 12}" text-anchor="middle" '
                      f'font-size="7" font-weight="bold" font-family="Arial,sans-serif" '
                      f'fill="#334155">{label}</text>')

    # baseline
    lines.append(f'<line x1="{ml}" y1="{mt + ch:.1f}" x2="{vw - mr}" y2="{mt + ch:.1f}" '
                  f'stroke="#374151" stroke-width="0.8"/>')

    for entity in _ENTITIES:
        color = _COLORS[entity]
        vals = series[entity]
        segs, cur_seg = [], []
        for i, v in enumerate(vals):
            if v is None:
                if len(cur_seg) > 1:
                    segs.append(cur_seg)
                cur_seg = []
            else:
                cur_seg.append((xs(i), ys(v)))
        if len(cur_seg) > 1:
            segs.append(cur_seg)
        for seg in segs:
            d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in seg)
            lines.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.4"/>')
        # small end-dot on the last plotted point so a lone/short segment is still visible
        last_pt = next((seg[-1] for seg in reversed(segs)), None)
        if last_pt:
            lines.append(f'<circle cx="{last_pt[0]:.1f}" cy="{last_pt[1]:.1f}" r="1.8" fill="{color}"/>')

    # legend
    lx = ml
    ly = 12
    for entity in _ENTITIES:
        color = _COLORS[entity]
        lines.append(f'<rect x="{lx}" y="{ly - 6}" width="10" height="3" fill="{color}"/>')
        lines.append(f'<text x="{lx + 13}" y="{ly - 3}" font-size="7.5" font-weight="bold" '
                      f'font-family="Arial,sans-serif" fill="#1e293b">{entity}</text>')
        lx += 13 + len(entity) * 5 + 14

    lines.append("</svg>")
    return "\n".join(lines)


# ── SVG: grouped annual bar chart (3 FY actuals + current FY rate) ─────────────
#
# SAIL's annual total is ~5-10x any single plant's (it's the sum of all of
# them), so it needs its own call/scale — plotting it alongside individual
# plants on one axis would compress every plant bar to a sliver. Callers pass
# an explicit `entities` list: once for the 5 plants together, once for SAIL
# alone, each getting a y-scale that fits its own data.

def _annual_bar_svg(fys: list, values: dict, entities: list, title: str,
                     vw: int = 470, vh: int = 250) -> str:
    ml, mr, mt, mb = 30, 8, 28, 36
    cw, ch = vw - ml - mr, vh - mt - mb

    all_vals = [v for ent in entities for (_, v, _r) in values[ent] if v is not None]
    yhi = max(all_vals) if all_vals else 10.0
    yhi = max(5.0, yhi * 1.22)

    n_groups = len(entities)
    group_w = cw / n_groups
    n_bars = len(fys)
    bar_gap = 2.0
    bar_w = max(6.0, (group_w - 8) / n_bars - bar_gap)
    fs = min(7.0, max(5.2, bar_w * 0.62))

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']
    lines.append(f'<text x="{vw / 2:.0f}" y="12" text-anchor="middle" font-size="9" '
                 f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{title}</text>')
    lines.append(f'<line x1="{ml}" y1="{mt + ch:.1f}" x2="{vw - mr}" y2="{mt + ch:.1f}" '
                 f'stroke="#374151" stroke-width="0.7"/>')

    gx = ml
    for ent in entities:
        bx = gx + 4
        for j, (fy, v, is_rate) in enumerate(values[ent]):
            color = _FY_BAR_COLORS[j]
            x = bx + j * (bar_w + bar_gap)
            cx = x + bar_w / 2
            if v is None:
                bh = 3
                by = mt + ch - bh
                lines.append(f'<rect x="{x:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh}" '
                             f'fill="none" stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="2,1.5"/>')
                lines.append(f'<text x="{cx:.1f}" y="{by - 3:.1f}" text-anchor="middle" '
                             f'font-size="5.6" font-family="Arial,sans-serif" fill="#94a3b8">N/A</text>')
            else:
                bh = max(2.0, ch * v / yhi)
                by = mt + ch - bh
                lines.append(f'<rect x="{x:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                             f'fill="{color}" rx="1"/>')
                val_str = _fmt(v, 0)
                # Horizontal label only — centered inside the bar when there's
                # room for the text's own height, otherwise just above it
                # (matching the bar's fill color, same fallback page 3 uses).
                if bh >= 11:
                    ty = by + bh / 2 + fs * 0.35
                    lines.append(f'<text x="{cx:.1f}" y="{ty:.1f}" text-anchor="middle" '
                                 f'font-size="{fs:.1f}" font-weight="bold" font-family="Arial,sans-serif" '
                                 f'fill="{_contrast_text(color)}">{val_str}</text>')
                else:
                    ty = by - 3
                    lines.append(f'<text x="{cx:.1f}" y="{ty:.1f}" text-anchor="middle" '
                                 f'font-size="{fs:.1f}" font-weight="bold" font-family="Arial,sans-serif" '
                                 f'fill="{color}">{val_str}</text>')
        lx = gx + group_w / 2
        ly = mt + ch + 11
        lines.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="7.5" '
                     f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{ent}</text>')
        gx += group_w

    # legend: FY labels + current-year rate note
    lx = ml
    ly = mt + ch + 24
    for j, fy in enumerate(fys):
        label = _fy_short(fy) + (" (rate)" if j == len(fys) - 1 else "")
        lines.append(f'<rect x="{lx}" y="{ly - 6}" width="9" height="7" fill="{_FY_BAR_COLORS[j]}"/>')
        lines.append(f'<text x="{lx + 12}" y="{ly}" font-size="6.6" font-family="Arial,sans-serif" '
                     f'fill="#334155">{label}</text>')
        lx += 12 + len(label) * 4.4 + 10

    lines.append("</svg>")
    return "\n".join(lines)


# ── SVG: current-month bar chart ───────────────────────────────────────────────

def _month_bar_svg(month_label: str, values: dict) -> str:
    vw, vh = 470, 300
    ml, mr, mt, mb = 30, 8, 30, 26
    cw, ch = vw - ml - mr, vh - mt - mb

    vals = [v for v in values.values() if v is not None]
    yhi = max(vals) if vals else 10.0
    yhi = max(5.0, yhi * 1.2)

    n = len(_ENTITIES)
    slot_w = cw / n
    bar_w = max(10.0, slot_w * 0.6)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']
    lines.append(f'<text x="{vw / 2:.0f}" y="12" text-anchor="middle" font-size="9" '
                 f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">'
                 f"Special Steel Production — {month_label} ('000T)</text>")
    lines.append(f'<line x1="{ml}" y1="{mt + ch:.1f}" x2="{vw - mr}" y2="{mt + ch:.1f}" '
                 f'stroke="#374151" stroke-width="0.7"/>')

    x = ml
    for ent in _ENTITIES:
        color = _COLORS[ent]
        v = values.get(ent)
        bx = x + (slot_w - bar_w) / 2
        if v is None:
            bh = 3
            by = mt + ch - bh
            lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh}" '
                         f'fill="none" stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="2,1.5"/>')
            lines.append(f'<text x="{bx + bar_w / 2:.1f}" y="{by - 4:.1f}" text-anchor="middle" '
                         f'font-size="6.5" font-family="Arial,sans-serif" fill="#94a3b8">N/A</text>')
        else:
            bh = max(2.0, ch * v / yhi)
            by = mt + ch - bh
            lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                         f'fill="{color}" rx="1.5"/>')
            txt_color = _contrast_text(color)
            val_str = _fmt(v, 1)
            if bh >= 16:
                ty = by + bh / 2 + 3
                lines.append(f'<text x="{bx + bar_w / 2:.1f}" y="{ty:.1f}" text-anchor="middle" '
                             f'font-size="8" font-weight="bold" font-family="Arial,sans-serif" '
                             f'fill="{txt_color}">{val_str}</text>')
            else:
                ty = by - 4
                lines.append(f'<text x="{bx + bar_w / 2:.1f}" y="{ty:.1f}" text-anchor="middle" '
                             f'font-size="7" font-weight="bold" font-family="Arial,sans-serif" '
                             f'fill="{color}">{val_str}</text>')
        lx = x + slot_w / 2
        ly = mt + ch + 12
        lines.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="8" '
                     f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{ent}</text>')
        x += slot_w

    lines.append("</svg>")
    return "\n".join(lines)


# ── public API ──────────────────────────────────────────────────────────────

def generate_special_steel_trend(report_month: str) -> dict:
    fys = _last_n_fys(report_month, 4)
    all_months = []
    for fy in fys:
        all_months.extend(_fy_months(fy))

    conn = db.connect()
    cur = conn.cursor()
    try:
        series_pct = {ent: [] for ent in _ENTITIES}
        for m in all_months:
            for ent in _ENTITIES:
                series_pct[ent].append(_month_pct(cur, m, ent) if m <= report_month else None)

        fy_boundaries = []
        for fy in fys:
            idx = all_months.index(_fy_months(fy)[0])
            fy_boundaries.append((idx, _fy_short(fy)))

        annual = {ent: [] for ent in _ENTITIES}
        for fy in fys[:-1]:
            for ent in _ENTITIES:
                annual[ent].append((fy, _fy_annual_total(cur, fy, ent), False))
        cur_fy = fys[-1]
        for ent in _ENTITIES:
            annual[ent].append((cur_fy, _current_fy_rate(cur, report_month, ent), True))

        month_vals = {ent: None for ent in _ENTITIES}
        for ent in _ENTITIES:
            t, has = _sum_actual(cur, [report_month], ent)
            month_vals[ent] = (t / 1000.0) if has else None
    finally:
        conn.close()

    dt = _dt.datetime.strptime(report_month, "%Y-%m")
    month_label = dt.strftime("%b'%y")

    return {
        "type": "special_steel_trend",
        "title": "SPECIAL STEEL — TREND & PERFORMANCE ANALYSIS",
        "line_chart_svg": _line_chart_svg(all_months, series_pct, fy_boundaries),
        "annual_bar_plants_svg": _annual_bar_svg(
            fys, annual, _PLANTS, "Annual Special Steel Production — Plants ('000T)",
            vw=980, vh=300),
        "annual_bar_sail_svg": _annual_bar_svg(
            fys, annual, ["SAIL"], "SAIL ('000T)", vw=300, vh=300),
        "month_bar_svg": _month_bar_svg(month_label, month_vals),
        "fy_range_label": f"{_fy_short(fys[0])} to {_fy_short(fys[-1])}",
    }
