"""
Special Steel (Value Added Steel) — Trend & Performance Analysis (Page 24).

Three visuals, per plant (BSP/DSP/RSP/BSL/ISP) plus a SAIL aggregate, each
entity getting its own independently-scaled mini bar chart (SAIL's total is
~5-10x any single plant's, so sharing one axis would flatten every plant bar
to a sliver):
  1. Annual despatch — 6 blocks (BSP/DSP/RSP top row, BSL/ISP/SAIL bottom
     row), each with 4 bars: the last 3 closed FYs' actuals plus the current
     (partial) FY's likely rate, annualized from days elapsed so far — not a
     plan or a plain YTD total.
  2. For-the-month despatch — one bar per entity.
  3. Till-the-month (YTD) despatch — one bar per entity.
Every bar: rounded ("half-circle") top, the despatch quantity labeled
inside in bold 12pt, and that period's Special Steel % of Saleable Steel
labeled above the bar top. FY (or entity) labeled below.

special_steel_orders only has data from 2025-04 onward (see db.py), so the
two oldest FYs are currently empty for every entity. Rather than
special-case that, every lookup here is "sum what exists, and say so if
nothing does" — an FY/entity with zero matching rows renders as a blank/N-A
bar instead of a misleading 0, so populating the older months later makes
the chart fill in on its own.
"""
import calendar
import datetime as _dt
import db

_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_SSPS = "SSPs"
_ENTITIES = _PLANTS + ["SAIL"]
# Display order for the 6 annual blocks: BSP/DSP/RSP top row, BSL/ISP/SAIL
# bottom row (per spec) - not the same order as _ENTITIES above.
_BLOCK_ORDER = ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"]

# Same house palette as the page-3 techno bar charts, one fixed color per
# entity so it stays consistent across the month/till-month charts.
_COLORS = {
    "BSP": "#4472C4",
    "DSP": "#ED7D31",
    "RSP": "#A5A5A5",
    "BSL": "#FFC000",
    "ISP": "#5B9BD5",
    "SAIL": "#70AD47",
}
# Annual chart: same entity across 4 periods, so color encodes "how recent"
# instead — historical FYs shade from light to full gold, current FY (a
# projected rate, not a closed actual) is green.
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


def _period_saleable(cur, months: list, entity: str):
    """SAIL/plant Saleable Steel ('000T) summed across these months."""
    plants = _PLANTS if entity == "SAIL" else [entity]
    total, has = 0.0, False
    for m in months:
        for p in plants:
            v = _saleable_steel(cur, m, p)
            if v is not None:
                total += v
                has = True
    return total if has else None


def _period_value_pct(cur, months: list, entity: str):
    """(qty_tonnes, pct_of_saleable) for this entity's Special Steel despatch
    over these months, or (None, None) if nothing's been reported yet."""
    qty, has = _sum_actual(cur, months, entity)
    if not has:
        return None, None
    saleable_000T = _period_saleable(cur, months, entity)
    pct = qty / (saleable_000T * 1000) * 100 if saleable_000T else None
    return qty, pct


def _current_fy_rate(cur, report_month, entity):
    """Annualized '000T rate: actual-to-date / elapsed days * days-in-FY."""
    ytd_months = db.get_ytd_months(report_month)
    total, has = _sum_actual(cur, ytd_months, entity)
    if not has:
        return None
    elapsed_days = sum(calendar.monthrange(int(m[:4]), int(m[5:7]))[1] for m in ytd_months)
    days_in_fy = _days_in_fy(db.get_fy_for_month(report_month))
    return (total / elapsed_days * days_in_fy) / 1000.0


# ── formatting helpers ──────────────────────────────────────────────────────

def _fmt_int(v) -> str:
    return f"{v:,.0f}"


def _contrast_text(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#0f172a" if luminance > 0.6 else "#ffffff"


def _fy_short(fy_label: str) -> str:
    return f"FY{fy_label}"


# ── SVG: half-circle-top bar path ──────────────────────────────────────────

def _rounded_bar_path(x: float, y: float, w: float, h: float, r: float) -> str:
    r = max(0.0, min(r, w / 2, h))
    if r <= 0.05:
        return f'M{x:.1f},{y + h:.1f} L{x:.1f},{y:.1f} L{x + w:.1f},{y:.1f} L{x + w:.1f},{y + h:.1f} Z'
    return (f'M{x:.1f},{y + h:.1f} '
            f'L{x:.1f},{y + r:.1f} '
            f'A{r:.1f},{r:.1f} 0 0 1 {x + r:.1f},{y:.1f} '
            f'L{x + w - r:.1f},{y:.1f} '
            f'A{r:.1f},{r:.1f} 0 0 1 {x + w:.1f},{y + r:.1f} '
            f'L{x + w:.1f},{y + h:.1f} Z')


# ── SVG: one bar group (N bars, one x-axis, shared y-scale) ────────────────
# Used for both the 6 per-entity annual blocks (4 bars: 3 FY + current) and
# the month/till-month charts (6 bars: one per entity) — same visual spec
# either way: half-circle top, despatch qty in bold 12pt centered inside the
# bar, that period's % of Saleable Steel above the bar top, x-axis label
# below.

def _bar_group_svg(bars: list, title: str, vw: int = 240, vh: int = 200) -> str:
    """bars: [(x_label, qty_tonnes_or_None, pct_or_None, color), ...]"""
    ml, mr, mt, mb = 12, 10, 30, 24
    cw, ch = vw - ml - mr, vh - mt - mb

    qty_vals = [b[1] for b in bars if b[1] is not None]
    yhi = max(qty_vals) * 1.35 if qty_vals else 10.0
    yhi = max(yhi, 5.0)

    n = len(bars)
    slot_w = cw / n
    bar_w = max(14.0, slot_w * 0.55)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']
    if title:
        lines.append(f'<text x="{vw / 2:.0f}" y="12" text-anchor="middle" font-size="9" '
                     f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{title}</text>')
    lines.append(f'<line x1="{ml}" y1="{mt + ch:.1f}" x2="{vw - mr}" y2="{mt + ch:.1f}" '
                 f'stroke="#374151" stroke-width="0.7"/>')

    for i, (label, qty, pct, color) in enumerate(bars):
        cx = ml + i * slot_w + slot_w / 2
        if qty is None:
            by, bh = mt + ch - 3, 3
            lines.append(f'<rect x="{cx - bar_w / 2:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh}" '
                         f'fill="none" stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="2,1.5"/>')
            lines.append(f'<text x="{cx:.1f}" y="{by - 4:.1f}" text-anchor="middle" '
                         f'font-size="6.5" font-family="Arial,sans-serif" fill="#94a3b8">N/A</text>')
        else:
            bh = max(2.0, ch * qty / yhi)
            by = mt + ch - bh
            path = _rounded_bar_path(cx - bar_w / 2, by, bar_w, bh, bar_w / 2)
            lines.append(f'<path d="{path}" fill="{color}"/>')
            if pct is not None:
                lines.append(f'<text x="{cx:.1f}" y="{by - 5:.1f}" text-anchor="middle" font-size="7.6" '
                             f'font-weight="bold" font-family="Arial,sans-serif" fill="{color}">{pct:.1f}%</text>')
            val_str = _fmt_int(qty)
            fill = _contrast_text(color)
            if 12 * len(val_str) * 0.62 <= bar_w - 4:
                # Horizontal, centered — fits within the bar's own width.
                ty = by + bh / 2 + 4.2
                lines.append(f'<text x="{cx:.1f}" y="{ty:.1f}" text-anchor="middle" font-size="12" '
                             f'font-weight="bold" font-family="Arial,sans-serif" fill="{fill}">{val_str}</text>')
            else:
                # Too wide for a narrow bar at 12pt — rotate vertical
                # (bottom-to-top), centered on the bar's own midpoint, same
                # technique as the at-a-glance production-trend bars.
                ty = by + bh / 2
                lines.append(f'<text x="{cx:.1f}" y="{ty:.1f}" text-anchor="middle" dominant-baseline="middle" '
                             f'transform="rotate(-90 {cx:.1f} {ty:.1f})" font-size="12" font-weight="bold" '
                             f'font-family="Arial,sans-serif" fill="{fill}">{val_str}</text>')
        lines.append(f'<text x="{cx:.1f}" y="{mt + ch + 13:.1f}" text-anchor="middle" font-size="7.5" '
                     f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{label}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ── public API ──────────────────────────────────────────────────────────────

def generate_special_steel_trend(report_month: str) -> dict:
    fys = _last_n_fys(report_month, 4)
    ytd_months = db.get_ytd_months(report_month)

    conn = db.connect()
    cur = conn.cursor()
    try:
        annual_svgs = {}
        for ent in _BLOCK_ORDER:
            bars = []
            for fy in fys[:-1]:
                qty, pct = _period_value_pct(cur, _fy_months(fy), ent)
                bars.append((_fy_short(fy), qty, pct, _FY_BAR_COLORS[len(bars)]))
            cur_fy = fys[-1]
            _, cur_pct = _period_value_pct(cur, ytd_months, ent)
            cur_rate = _current_fy_rate(cur, report_month, ent)
            cur_qty = cur_rate * 1000 if cur_rate is not None else None
            bars.append((f"{_fy_short(cur_fy)} (Likely)", cur_qty, cur_pct, _FY_BAR_COLORS[3]))
            annual_svgs[ent] = _bar_group_svg(bars, ent, vw=240, vh=200)

        month_bars, ytd_bars = [], []
        for ent in _BLOCK_ORDER:
            qty, pct = _period_value_pct(cur, [report_month], ent)
            month_bars.append((ent, qty, pct, _COLORS[ent]))
            qty, pct = _period_value_pct(cur, ytd_months, ent)
            ytd_bars.append((ent, qty, pct, _COLORS[ent]))
    finally:
        conn.close()

    dt = _dt.datetime.strptime(report_month, "%Y-%m")
    month_label = dt.strftime("%b'%y")
    cum_label = _dt.datetime.strptime(ytd_months[0], "%Y-%m").strftime("%b'%y") + "-" + month_label

    return {
        "type": "special_steel_trend",
        "title": "SPECIAL STEEL — TREND & PERFORMANCE ANALYSIS",
        "annual_svgs": [annual_svgs[e] for e in _BLOCK_ORDER],
        "month_svg": _bar_group_svg(
            month_bars, f"Special Steel Despatch — {month_label} (T, % of Saleable Steel)",
            vw=700, vh=220),
        "till_month_svg": _bar_group_svg(
            ytd_bars, f"Special Steel Despatch — {cum_label} YTD (T, % of Saleable Steel)",
            vw=700, vh=220),
        "fy_range_label": f"{_fy_short(fys[0])} to {_fy_short(fys[-1])}",
    }
