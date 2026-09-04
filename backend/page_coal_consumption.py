"""
"Consumption of Coking Coal and CDI Coal" — landscape page reproducing
Report_format/Coal_co2/Coal Format.pdf's OIS-1 table exactly: per-plant
(BSP/DSP/RSP/BSL/ISP/SAIL) row groups, each with the report month's own
row and (except in April, the FY's first month) an "Apr-<Mon>'YY"
FY-cumulative row directly below it, under a compound column header
(Indigenous Coking Coal PCC/MCC/Total, Imported Coking Coal Hard/Soft/
Total, Total Coking Coal, CDI Coal, then the same two group breakdowns
again as Blend %).

Pure lookup/display, no computation — every value (including the totals
and blend%) was already computed by the source workbook and extracted
verbatim by techno_project/coal_omi_extractor.py's extract_ois1_detail
into techno_data (unit="Coal_Consumption", one row per plant/SAIL, keyed
by report_month like every other techno_data row). Data entry (the Excel
upload) and its own validation live entirely in api_coal_omi_techno.py —
this module only reads what's already been saved there.
"""
import json
import db
from page_special_steel_trend import (
    _last_n_fys, _fy_months, _rounded_bar_path, _contrast_text,
)

PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_UNIT = "Coal_Consumption"

# Colors for the 6 bars of the "% Imported Coking Coal in Blend" chart —
# encodes period TYPE (matching page_special_steel_trend's annual-chart
# convention: closed FYs shade light-to-full gold, current-FY figure is a
# different color since it's not a closed actual). Target (a plan, not an
# actual) gets its own neutral gray so it doesn't read as a 4th closed FY.
_PCT_BAR_FY_COLORS = ["#FFE699", "#FFD966", "#FFC000"]
_PCT_BAR_TARGET_COLOR = "#94A3B8"
_PCT_BAR_MONTH_COLOR = "#4472C4"
_PCT_BAR_YTD_COLOR = "#70AD47"

# (label, key) — column order matches the sheet/PDF left-to-right.
QTY_COLS = [
    ("PCC", "pcc"), ("MCC", "mcc"), ("Total", "indigenous_total"),
    ("Hard", "hard"), ("Soft", "soft"), ("Total", "imported_total"),
]
PCT_COLS = [
    ("PCC", "pcc_pct"), ("MCC", "mcc_pct"), ("Total", "indigenous_total_pct"),
    ("Hard", "hard_pct"), ("Soft", "soft_pct"), ("Total", "imported_total_pct"),
]

_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_label(report_month: str) -> str:
    y, m = report_month.split("-")
    return f"{_MON_ABBR[int(m)]}'{y[-2:]}"


def _till_month_label(report_month: str) -> str:
    y, m = report_month.split("-")
    m = int(m)
    if m == 4:
        return f"Apr'{y[-2:]}"
    return f"Apr-{_month_label(report_month)}"


def _batched_techno_rows(conn, plant: str, unit: str, months: list) -> dict:
    """{report_month: techno_json_dict} for every month in `months` that has
    a stored row — ONE query on a shared connection, instead of one
    db.get_techno_data() call (each opening its own fresh MySQL TCP
    connection — see dbengine.connect, no pooling) per month. The %import
    FY-actual backward-walk below needs up to 3 FYs x 12 months per plant;
    looping db.get_techno_data per month there previously opened up to
    ~36 connections per plant (~200+ for the whole page) and was the
    actual cause of a real PDF-generation slowdown after this chart was
    added — confirmed by tracing dbengine.connect()'s per-call
    pymysql.connect(), which has no pooling."""
    cur = conn.cursor()
    ph = ",".join("?" * len(months))
    cur.execute(
        f"SELECT report_month, techno_json FROM techno_data "
        f"WHERE plant=? AND unit=? AND report_month IN ({ph})",
        (plant, unit, *months),
    )
    out = {}
    for report_month, techno_json in cur.fetchall():
        try:
            out[report_month] = json.loads(techno_json)
        except (TypeError, ValueError):
            out[report_month] = {}
    return out


def _fy_end_actual_pct(fy_rows: dict, fy_label: str):
    """Latest available Apr-to-date cumulative %import for a (closed) FY,
    reading from an already-batched {month: techno_json} dict (see
    _batched_techno_rows) — walks backward from the FY's last month to
    April looking for the first month with a stored till_month figure
    (same backward-walk idea as page_key_parameters._demurrage_by_plant),
    so a not-yet-finalized last month doesn't blank out an otherwise
    fully-reported FY. Coal_Consumption is a relatively new techno_data
    unit, so older FYs legitimately have no data at all — returns None
    then, rendered as an N/A bar rather than a fabricated 0 (see
    page_special_steel_trend's module docstring for the same "sum what
    exists" philosophy this mirrors)."""
    for m in reversed(_fy_months(fy_label)):
        row = fy_rows.get(m)
        if row:
            v = (row.get("till_month") or {}).get("imported_total_pct")
            if v is not None:
                return v
    return None


def _fy_target_pcts(conn, plants: list, fy_label: str, unit: str) -> dict:
    """{plant: imported_total_pct_target_or_None} for every plant, one
    query on the shared connection — techno_plan_fy (plant,
    Coal_Consumption, fy).imported_total_pct, entered via
    /data-entry/annual-target's "Coal Blend %" tab (see main.py's
    /api/coal-blend-targets and page_at_a_glance._imported_coal_blend_target,
    the SAIL-only precedent this generalizes to all 6 plants). Deliberately
    NOT db.get_techno_plan — that helper opens its own fresh connection
    per call with no conn= param (see _batched_techno_rows' note on why
    that matters), which would reintroduce one extra connection per plant
    here."""
    cur = conn.cursor()
    ph = ",".join("?" * len(plants))
    cur.execute(
        f"SELECT plant_name, techno_json FROM techno_plan_fy "
        f"WHERE plant_name IN ({ph}) AND fy=? AND unit=?",
        (*plants, fy_label, unit),
    )
    out = {}
    for plant_name, techno_json in cur.fetchall():
        try:
            data = json.loads(techno_json) if techno_json else {}
        except (TypeError, ValueError):
            data = {}
        v = data.get("imported_total_pct")
        out[plant_name] = v.get("value") if isinstance(v, dict) else v
    return out


def _import_pct_bar_svg(bars: list, title: str, vw: int = 220, vh: int = 150) -> str:
    """One mini bar chart: 6 bars (3 closed FYs, FY target, report month,
    Apr-report month YTD), half-circle-top bars matching
    page_special_steel_trend's visual language, value labeled inside each
    bar as "NN.N%", x-axis label below. bars: [(label, pct_or_None, color), ...]"""
    ml, mr, mt, mb = 8, 6, 16, 20
    cw, ch = vw - ml - mr, vh - mt - mb
    vals = [v for _, v, _ in bars if v is not None]
    yhi = max((max(vals) * 1.3 if vals else 10.0), 10.0)

    n = len(bars)
    slot_w = cw / n
    bar_w = max(14.0, slot_w * 0.62)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'style="width:100%;height:auto;display:block;">']
    if title:
        lines.append(f'<text x="{vw / 2:.0f}" y="12" text-anchor="middle" font-size="9" '
                     f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{title}</text>')
    lines.append(f'<line x1="{ml}" y1="{mt + ch:.1f}" x2="{vw - mr}" y2="{mt + ch:.1f}" '
                 f'stroke="#374151" stroke-width="0.7"/>')

    for i, (label, val, color) in enumerate(bars):
        cx = ml + i * slot_w + slot_w / 2
        if val is None:
            by, bh = mt + ch - 3, 3
            lines.append(f'<rect x="{cx - bar_w / 2:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh}" '
                         f'fill="none" stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="2,1.5"/>')
            lines.append(f'<text x="{cx:.1f}" y="{by - 4:.1f}" text-anchor="middle" '
                         f'font-size="6" font-family="Arial,sans-serif" fill="#94a3b8">N/A</text>')
        else:
            bh = max(2.0, ch * val / yhi)
            by = mt + ch - bh
            path = _rounded_bar_path(cx - bar_w / 2, by, bar_w, bh, bar_w / 2)
            lines.append(f'<path d="{path}" fill="{color}"/>')
            fill = _contrast_text(color)
            ty = by + bh / 2 + 3.4
            lines.append(f'<text x="{cx:.1f}" y="{ty:.1f}" text-anchor="middle" font-size="9.5" '
                         f'font-weight="bold" font-family="Arial,sans-serif" fill="{fill}">{val:.1f}%</text>')
        lines.append(f'<text x="{cx:.1f}" y="{mt + ch + 12:.1f}" text-anchor="middle" font-size="7.5" '
                     f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{label}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def generate_coal_consumption(report_month: str) -> dict:
    is_april = report_month.endswith("-04")
    plants = PLANTS + ["SAIL"]

    fys = _last_n_fys(report_month, 4)   # [FY-3, FY-2, FY-1, current FY], chronological
    closed_fys, cur_fy = fys[:-1], fys[-1]
    closed_fy_months = [m for fy in closed_fys for m in _fy_months(fy)]

    conn = db.connect()
    try:
        target_pcts = _fy_target_pcts(conn, plants, cur_fy, _UNIT)

        groups = []
        import_pct_charts = []
        for plant in plants:
            stored = db.get_techno_data(plant, report_month, unit=_UNIT, conn=conn).get(_UNIT, {})
            month_row = stored.get("month") or {}
            till_row = stored.get("till_month") or {}
            # NOT "values" — Jinja2's dot-notation resolves that to dict.values
            # (the built-in method) before falling back to item lookup, since
            # getattr succeeds first; "vals" avoids the collision.
            sub_rows = [{
                "label": month_row.get("label") or _month_label(report_month),
                "vals": month_row,
            }]
            if not is_april:
                sub_rows.append({
                    "label": till_row.get("label") or _till_month_label(report_month),
                    "vals": till_row,
                })
            groups.append({"plant": plant, "sub_rows": sub_rows})

            fy_rows = _batched_techno_rows(conn, plant, _UNIT, closed_fy_months)
            bars = [(fy[2:], _fy_end_actual_pct(fy_rows, fy), _PCT_BAR_FY_COLORS[i])
                    for i, fy in enumerate(closed_fys)]
            bars.append((f"{cur_fy[2:]} Tgt", target_pcts.get(plant), _PCT_BAR_TARGET_COLOR))
            bars.append((_month_label(report_month), month_row.get("imported_total_pct"), _PCT_BAR_MONTH_COLOR))
            ytd_pct = month_row.get("imported_total_pct") if is_april else till_row.get("imported_total_pct")
            bars.append((_till_month_label(report_month), ytd_pct, _PCT_BAR_YTD_COLOR))
            import_pct_charts.append({"plant": plant, "svg": _import_pct_bar_svg(bars, plant)})
    finally:
        conn.close()

    return {
        "type": "coal_consumption",
        "title": f"Details of Coking Coal Consumption, Blend and Stocks - Consumption ({_month_label(report_month)})",
        "qty_cols": QTY_COLS,
        "pct_cols": PCT_COLS,
        "groups": groups,
        "import_pct_charts": import_pct_charts,
    }
