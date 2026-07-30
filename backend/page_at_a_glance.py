"""
MIS at a Glance — infographic-style snapshot page inserted right after the
Cover page (see AT_A_GLANCE_PAGE_ID in main.py). Composites headline numbers
already computed elsewhere in the report — production, techno-economic,
special steel, capital repair — into one visual dashboard, plus a short
production trend line, so a reader gets the month's story in one page before
diving into the detailed 40-page report.

Not part of the fixed 1-40 page numbering — see main.py's comment next to
AT_A_GLANCE_PAGE_ID for why (PDF-export-only, no on-screen preview slot).
"""
import datetime as _dt

import db
from report_utils import compute_item_row
from page_techno import generate_summary_te_table
from page_special_steel import generate_special_steel_sail
from page_capital_repair import generate_capital_repair, fy_from_month, CR_PAGES

_PROD_ITEMS = ["Hot Metal", "Crude Steel", "Finished Steel", "Saleable Steel"]

# Rate/consumption metrics are "good" when they go down; productivity is
# "good" when it goes up.
_TE_LOWER_IS_BETTER = {"Coke Rate", "Fuel Rate", "Specific Energy Consumption"}
_TE_PARAMS = ["Coke Rate", "Fuel Rate", "BF Productivity", "Specific Energy Consumption"]


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


# ── SVG: small monthly trend line (single series) ───────────────────────────

def _trend_line_svg(labels: list, values: list, vw: int = 480, vh: int = 150) -> str:
    ml, mr, mt, mb = 32, 10, 12, 20
    cw, ch = vw - ml - mr, vh - mt - mb

    nums = [v for v in values if v is not None]
    yhi = max(nums) * 1.2 if nums else 10.0
    yhi = max(yhi, 5.0)

    n = len(values)
    step = cw / max(n - 1, 1)

    def xs(i):
        return ml + i * step

    def ys(v):
        return mt + ch * (1.0 - v / yhi)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']

    for k in range(4):
        gy = ys(yhi * k / 3)
        lines.append(f'<line x1="{ml}" y1="{gy:.1f}" x2="{vw - mr}" y2="{gy:.1f}" '
                      f'stroke="#e2e8f0" stroke-width="0.6"/>')
    lines.append(f'<line x1="{ml}" y1="{mt + ch:.1f}" x2="{vw - mr}" y2="{mt + ch:.1f}" '
                 f'stroke="#374151" stroke-width="0.8"/>')

    pts = [(xs(i), ys(v)) for i, v in enumerate(values) if v is not None]
    if len(pts) > 1:
        d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        lines.append(f'<path d="{d}" fill="none" stroke="#0284c7" stroke-width="1.8"/>')
    for i, v in enumerate(values):
        if v is None:
            continue
        x, y = xs(i), ys(v)
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.2" fill="#0284c7"/>')
        lines.append(f'<text x="{x:.1f}" y="{y - 5:.1f}" text-anchor="middle" font-size="7" '
                     f'font-family="Arial,sans-serif" fill="#1e293b">{v:.0f}</text>')
    for i, label in enumerate(labels):
        lines.append(f'<text x="{xs(i):.1f}" y="{mt + ch + 13:.1f}" text-anchor="middle" '
                     f'font-size="7" font-family="Arial,sans-serif" fill="#64748b">{label}</text>')

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


# ── data sections ────────────────────────────────────────────────────────────

def _production_section(report_month: str) -> list:
    rows = []
    for item in _PROD_ITEMS:
        v = compute_item_row(report_month, item)
        rows.append({
            "item": item,
            "month_act": v[1], "month_pct_ful": v[3],
            "pct_growth_cply": v[5], "growth_good": None if v[5] == "" else int(v[5]) >= 0,
            "ytd_act": v[7],
            "ytd_cply_act": v[10],
            "ytd_pct_growth": v[11], "ytd_growth_good": None if v[11] == "" else int(v[11]) >= 0,
        })
    return rows


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


def _capital_repair_section(report_month: str) -> list:
    fy = fy_from_month(report_month)
    out = []
    for plant in CR_PAGES.values():  # BSP, DSP, RSP, BSL, ISP — page order 36-40
        cr = generate_capital_repair(plant, fy)
        rows = [r for sec in cr.get("sections", []) for r in sec.get("rows", [])]
        total = len(rows)
        completed = sum(1 for r in rows if (r.get("actual") or "").strip())
        out.append({
            "plant": plant, "completed": completed, "total": total,
            "pct": round(completed / total * 100) if total else None,
        })
    return out


def _trend_section(report_month: str) -> dict:
    months = _trailing_months(report_month, 6)
    values = [db.get_sail_production_actual(m, "Saleable Steel") for m in months]
    labels = [_dt.datetime.strptime(m, "%Y-%m").strftime("%b'%y") for m in months]
    return {
        "months": labels,
        "svg": _trend_line_svg(labels, values),
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
        "techno": _techno_section(report_month),
        "special_steel": _special_steel_section(report_month, month_short),
        "capital_repair": _capital_repair_section(report_month),
        "trend": _trend_section(report_month),
    }
