"""
"SAIL Mines Production & Despatch Performance" — 7 tables covering Iron Ore
(production+despatch, plus sales), Coal (mines production, washery,
despatch) and Flux (limestone/dolomite production + despatch), each a
cumulative April-<report month> view against Annual Plan (APP) and the
corresponding period last year (CPLY), per direct instruction.

Every "production"-kind table's row (APP, Act., %FF, CPLY, %Grth) is built
from monthly Actual + Plan summed April->report_month (same YTD convention
as page4.py's "YTD APP"/"YTD Actual" columns), CPLY is the same sum for
last FY's April->same month (db.get_cply_month, one call per YTD month so a
report month early in the FY still gets the right prior-year months).
"flow"-kind tables would skip APP/%FF entirely (just Act./CPLY/%Grth) — per
direct instruction, every despatch/sales section now carries its own Plan
too, so every section here is currently 'production'-kind; 'flow' stays
supported (not deleted) in case a future section genuinely has no plan
figure.

Every section except Iron Ore Production/Despatch is entered via the SAIL
Mines Entry data-entry page (db.sail_mines_monthly). Iron Ore Production
and Iron Ore Despatch are the odd ones out (per direct instruction,
2026-08-26): they're rolled up at read time from the mine-level tables
(11 mines' worth of Lump/Fines production and all-materials despatch,
entered via the separate Iron Ore Mines Production & Despatch form) via
db.get_iron_ore_group_rollup_monthly, NOT from sail_mines_monthly — see
that function's docstring for exactly what Production vs Despatch mean at
this rolled-up group level. The SAIL Mines Entry form no longer has "Iron
Ore Mines Performance" or "Sales of Iron Ore" inputs — both moved to the
mine-level form above (Iron Ore Production/Despatch AND Sales' Booked
Quantity/Despatch are now entered there, then rolled up to group level
here; only Sales' old "Auction" item, renamed "Booked Quantity", needed a
brand new mine-level table — see mines_booked_qty_actual_monthly /
mines_booked_qty_plan_monthly).

Iron Ore Production (table 1) additionally carries a DESPATCH column group
per mine group (per direct instruction) — a second section (iron_ore_
despatch, same 4 items) whose rows are merged into table 1's rows as extra
columns rather than rendered as their own table (see "merge_into" below);
the resulting table has kind='production_despatch' and a "column_groups"
list (PRODUCTION + DESPATCH) instead of a flat "columns" list. Both groups
now carry the full APP/Act./%FF/CPLY/%Grth span (per direct instruction,
the despatch side previously only had Act./CPLY/%Grth) since iron_ore_
despatch is 'production'-kind too.

Table 2 (Sales of Iron Ore) uses the exact same merge_into mechanism (per
direct instruction, 2026-08-26) — its two column groups are labelled
BOOKED QTY / DESPATCH instead of PRODUCTION / DESPATCH (see each section's
"group_label", defaulting to "PRODUCTION"/"DESPATCH" when unset) since
"Booked Quantity" replaced the old flat "Auction" item. Its Despatch column
means despatch to the SALES end-use specifically (a subset of table 1's
Despatch, which sums every end-use) — see
db.get_iron_ore_sales_group_rollup_monthly's docstring.

A few rows are computed, never entered directly:
  - Coal Mines Production's "Total" = Raw Coking Coal + Thermal Coal.
  - Washery's "Yield (Clean Coal/Raw Coal)" = Clean Coal / Input Raw Coal
    x100 — computed for Actual/APP/CPLY the same way, before %FF/%Grth are
    derived from those (not an independently entered %), and displayed
    with 1 decimal (a %) rather than the tonnage tables' whole T.
  - Iron Ore Production's "SAIL" row (both production and despatch column
    groups) = CGoM + OGoM + JGoM, per direct instruction (2026-08-24) —
    unlike Cost Trend's SAIL row (see page_cost_trend.py), which stays a
    directly-entered figure.
"""
import math

import db
import hardcoded_loader

# Fixed-order categorical hues from pdf.py's _BADGE_COLORS / globals.css's
# .dept-badge.grp-N (already validated per the dataviz skill's six-check
# gate) — reused here so this page's charts stay consistent with the rest of
# the report. Re-checked as a 4-slot categorical palette
# (validate_palette.js "#2a78d6,#eb6834,#1baf7a,#eda100" --mode light → all
# pass; the sub-3:1 surface-contrast WARN is covered by the direct value/
# %-labels every chart carries).
_C_IRON_ORE = "#2a78d6"   # blue
_C_CLEAN_COAL = "#eb6834"  # orange
_C_FLUX = "#1baf7a"        # aqua
_C_SALES = "#eda100"       # yellow

# All figures on this page that have no DB source yet (the 3-year trend bars,
# the despatch-mix donuts, and the iron-ore group table) are hand-maintained
# in hardcoded_config.json's "sail_mines" section — a stopgap per direct
# instruction (2026-08-27) until real series / mine-level actuals exist. Read
# via hardcoded_loader inside the functions below so edits need no restart.
# Only the despatch-mix slice colours stay here (presentation, not data).
_DESPATCH_MIX_COLORS = [_C_IRON_ORE, _C_CLEAN_COAL, _C_SALES]

# Every (section key, item) pair listed under "items" is entered directly
# via the SAIL Mines Entry data-entry page; "derived" rows are computed
# from those and never entered (see module docstring). kind='production'
# tables show APP/Act./%FF/CPLY/%Grth; kind='flow' tables (despatch/sales)
# show just Act./CPLY/%Grth. A section with "merge_into" set is never its
# own table — its rows fold into the named section's table as an extra
# DESPATCH column group instead (see _merge_despatch_columns).
SAIL_MINES_SECTIONS = [
    {
        "key": "iron_ore_prod", "title": "Iron Ore Mines Performance", "kind": "production",
        "items": ["CGoM", "OGoM", "JGoM"],
        "derived": [{"label": "SAIL", "kind": "sum", "of": ["CGoM", "OGoM", "JGoM"]}],
    },
    {
        "key": "iron_ore_despatch", "kind": "production",
        "items": ["CGoM", "OGoM", "JGoM"],
        "derived": [{"label": "SAIL", "kind": "sum", "of": ["CGoM", "OGoM", "JGoM"]}], "merge_into": "iron_ore_prod",
    },
    {
        "key": "iron_ore_sales", "title": "Sales of Iron Ore", "kind": "production", "group_label": "BOOKED QTY",
        "items": ["CGoM", "OGoM", "JGoM"],
        "derived": [{"label": "SAIL", "kind": "sum", "of": ["CGoM", "OGoM", "JGoM"]}],
    },
    {
        "key": "iron_ore_sales_despatch", "kind": "production",
        "items": ["CGoM", "OGoM", "JGoM"],
        "derived": [{"label": "SAIL", "kind": "sum", "of": ["CGoM", "OGoM", "JGoM"]}], "merge_into": "iron_ore_sales",
    },
    {
        "key": "coal_prod", "title": "Coal Mines Production Performance", "kind": "production",
        "items": ["Raw Coking Coal", "Thermal Coal"],
        "derived": [{"label": "Total", "kind": "sum", "of": ["Raw Coking Coal", "Thermal Coal"]}],
    },
    {
        "key": "washery", "title": "Washery Performance", "kind": "production",
        "items": ["Input Raw Coal", "Clean Coal"],
        "derived": [{
            "label": "Yield (Clean Coal/Raw Coal)", "kind": "ratio", "value_fmt": "pct",
            "numerator": "Clean Coal", "denominator": "Input Raw Coal",
        }],
    },
    {
        "key": "coal_despatch", "title": "Despatch of Clean Coal & Thermal Coal (incl. Middlings)", "kind": "production",
        "items": ["Clean Coal", "Thermal"],
        "derived": [],
    },
    {
        "key": "flux_prod", "title": "Flux Production & Despatch (Limestone & Dolomite)", "kind": "production",
        "items": ["Limestone", "Dolomite"],
        "derived": [{"label": "Total", "kind": "sum", "of": ["Limestone", "Dolomite"]}],
    },
    {
        "key": "flux_despatch", "kind": "production",
        "items": ["Limestone", "Dolomite"],
        "derived": [{"label": "Total", "kind": "sum", "of": ["Limestone", "Dolomite"]}],
        "merge_into": "flux_prod",
    },
]

# Iron Ore Production / Despatch and Sales of Iron Ore (Booked Qty / Despatch)
# — CGoM/OGoM/JGoM — are hard-coded, delinked from the mine-level rollups
# (db.get_iron_ore_group_rollup_monthly / _sales_group_rollup_monthly) per
# direct instruction (2026-08-27): mine-level despatch/sales actuals were never
# entered, so the rollups' Despatch/Sales sides rendered blank. The figures now
# live in hardcoded_config.json ("sail_mines" -> "iron_ore_group_kt"), each
# item -> [APP, YTD Actual Apr-Jul'26, YTD CPLY] in '000 T. "SAIL" rows stay
# derived (sum of the three groups). Update that file — or restore the rollup
# calls in generate_sail_mines() — once real figures are available.

_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fmt_t(v):
    return None if v is None else f"{v:,.0f}"


def _fmt_pct(v):
    return None if v is None else f"{v:,.1f}"


def _sum_or_none(values) -> "float | None":
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def _ytd_sum(monthly: dict, section: str, item: str, months: list, field: str):
    """Sum monthly[m][section][item][field] across months, skipping any
    month with no entry — None only if every month is missing."""
    return _sum_or_none(monthly.get(m, {}).get(section, {}).get(item, {}).get(field) for m in months)


def _leaf_values(monthly: dict, cply_monthly: dict, section: str, item: str,
                  ytd_months: list, cply_months: list, kind: str):
    """-> (app, actual, cply) raw YTD sums for one directly-entered item."""
    actual = _ytd_sum(monthly, section, item, ytd_months, "actual")
    app = _ytd_sum(monthly, section, item, ytd_months, "plan") if kind == "production" else None
    cply = _ytd_sum(cply_monthly, section, item, cply_months, "actual")
    return app, actual, cply


def _pct_ful(app, actual):
    if app in (None, 0) or actual is None:
        return None
    return actual / app * 100


def _pct_growth(actual, cply):
    if cply in (None, 0) or actual is None:
        return None
    return (actual - cply) / cply * 100


def _ratio(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator * 100


def _columns_for(kind: str) -> list:
    return ["APP", "Act.", "%FF", "CPLY", "%Grth"] if kind == "production" else ["Act.", "CPLY", "%Grth"]


def _row(label: str, app, actual, cply, kind: str, value_fmt: str = "t", bold: bool = False) -> dict:
    fmt = _fmt_pct if value_fmt == "pct" else _fmt_t
    row = {
        "label": label,
        "bold": bold,
        "actual": fmt(actual),
        "cply": fmt(cply),
        "pct_growth": _fmt_pct(_pct_growth(actual, cply)),
    }
    if kind == "production":
        row["app"] = fmt(app)
        row["pct_ful"] = _fmt_pct(_pct_ful(app, actual))
    return row


def _num(v: float) -> str:
    """Compact number: drop trailing zeros (25.4, 0.345, 3), keep >=2 sig
    figs for sub-1 values."""
    if v == int(v):
        return f"{int(v)}"
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _mini_bar_svg(title: str, labels: list, values: list, color: str) -> str:
    """One small single-series bar chart with its own y-scale — the title
    names the series so no legend is needed; each bar carries a direct value
    label (dataviz: selective direct labels, not a grid). vw/vh are a
    viewBox only; the SVG scales to its grid cell."""
    vw, vh = 170, 122
    ml, mr, mt, mb = 6, 6, 24, 16
    cw, ch = vw - ml - mr, vh - mt - mb
    yhi = max(values) * 1.28 if any(values) else 1.0
    n = len(values)
    slot = cw / n
    bw = min(34.0, slot * 0.5)
    baseline = mt + ch

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
           f'style="width:100%;height:auto;display:block;">']
    out.append(f'<text x="{vw / 2:.0f}" y="10" text-anchor="middle" font-size="8.3" font-weight="bold" '
               f'font-family="Arial,sans-serif" fill="#1e293b">{title}</text>')
    out.append(f'<line x1="{ml}" y1="{baseline:.1f}" x2="{vw - mr}" y2="{baseline:.1f}" '
               f'stroke="#94a3b8" stroke-width="0.6"/>')
    for i, (lab, v) in enumerate(zip(labels, values)):
        cx = ml + i * slot + slot / 2
        bh = max(1.5, ch * v / yhi)
        by = baseline - bh
        r = min(3.0, bw / 2, bh)
        out.append(
            f'<path d="M{cx - bw / 2:.1f},{baseline:.1f} L{cx - bw / 2:.1f},{by + r:.1f} '
            f'Q{cx - bw / 2:.1f},{by:.1f} {cx - bw / 2 + r:.1f},{by:.1f} '
            f'L{cx + bw / 2 - r:.1f},{by:.1f} Q{cx + bw / 2:.1f},{by:.1f} {cx + bw / 2:.1f},{by + r:.1f} '
            f'L{cx + bw / 2:.1f},{baseline:.1f} Z" fill="{color}"/>')
        out.append(f'<text x="{cx:.1f}" y="{by - 3.5:.1f}" text-anchor="middle" font-size="8" '
                   f'font-weight="bold" font-family="Arial,sans-serif" fill="#1e293b">{_num(v)}</text>')
        out.append(f'<text x="{cx:.1f}" y="{baseline + 12:.1f}" text-anchor="middle" font-size="7.2" '
                   f'font-family="Arial,sans-serif" fill="#475569">{lab}</text>')
    out.append("</svg>")
    return "".join(out)


def _share_donut_svg(title: str, cats: list, values: list, colors: list) -> str:
    """Composition donut (3 slices) with a side legend (swatch · category ·
    value). 2px white ring between slices (dataviz mark spec); % labels only
    on slices with room; the FY/period total sits in the hole. Landscape
    viewBox — donut left, legend right."""
    vw, vh = 262, 134
    cx, cy, r_out, r_in = 64.0, 70.0, 40.0, 22.5
    total = sum(values) or 1.0

    def polar(r, deg):
        a = math.radians(deg)
        return cx + r * math.sin(a), cy - r * math.cos(a)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
           f'style="width:100%;height:auto;display:block;">']
    out.append(f'<text x="{vw / 2:.0f}" y="11" text-anchor="middle" font-size="8.3" font-weight="bold" '
               f'font-family="Arial,sans-serif" fill="#1e293b">{title}</text>')
    ang = 0.0
    for cat, v, col in zip(cats, values, colors):
        sweep = v / total * 360.0
        a0, a1 = ang, ang + sweep
        large = 1 if sweep > 180 else 0
        x1o, y1o = polar(r_out, a0)
        x2o, y2o = polar(r_out, a1)
        x1i, y1i = polar(r_in, a1)
        x2i, y2i = polar(r_in, a0)
        out.append(f'<path d="M {x1o:.2f} {y1o:.2f} A {r_out} {r_out} 0 {large} 1 {x2o:.2f} {y2o:.2f} '
                   f'L {x1i:.2f} {y1i:.2f} A {r_in} {r_in} 0 {large} 0 {x2i:.2f} {y2i:.2f} Z" '
                   f'fill="{col}" stroke="#ffffff" stroke-width="2"/>')
        if sweep >= 26:
            lx, ly = polar((r_out + r_in) / 2, (a0 + a1) / 2)
            out.append(f'<text x="{lx:.1f}" y="{ly + 3.5:.1f}" text-anchor="middle" font-size="9" '
                       f'font-weight="bold" font-family="Arial,sans-serif" fill="#ffffff">'
                       f'{v / total * 100:.0f}%</text>')
        ang = a1
    out.append(f'<text x="{cx:.1f}" y="{cy + 4:.1f}" text-anchor="middle" font-size="11" font-weight="bold" '
               f'font-family="Arial,sans-serif" fill="#1e293b">{_num(round(total, 2))}</text>')

    lx0, ly0 = 122, 44
    for i, (cat, v) in enumerate(zip(cats, values)):
        y = ly0 + i * 21
        out.append(f'<rect x="{lx0}" y="{y - 8:.0f}" width="10" height="10" rx="1.5" fill="{colors[i]}"/>')
        out.append(f'<text x="{lx0 + 15}" y="{y:.0f}" font-size="8" font-family="Arial,sans-serif" '
                   f'fill="#334155">{cat}</text>')
        out.append(f'<text x="{vw - 6}" y="{y:.0f}" text-anchor="end" font-size="8" '
                   f'font-family="Arial,sans-serif" font-weight="bold" fill="#1e293b">'
                   f'{_num(v)}  ({v / total * 100:.0f}%)</text>')
    out.append("</svg>")
    return "".join(out)


def _mines_charts_html() -> str:
    """The chart cluster for this page: four independent single-series bar
    charts (Iron Ore / Clean Coal / Flux production + Sales booking, 3 FYs
    each, each on its own scale) and two despatch-mix donuts (FY 2025-26 vs
    Apr-Jul'26). All hard-coded — see hardcoded_config.json's "sail_mines"
    section. One self-contained HTML fragment (inline styles only) so both the
    React view and the Jinja PDF template can drop it in verbatim."""
    cfg = hardcoded_loader.section("sail_mines")
    fys = cfg["trend_fys"]
    bars = [
        _mini_bar_svg("Iron Ore Production", fys, cfg["iron_ore_prod_mt"], _C_IRON_ORE),
        _mini_bar_svg("Clean Coal Production", fys, cfg["clean_coal_prod_mt"], _C_CLEAN_COAL),
        _mini_bar_svg("Flux Production", fys, cfg["flux_prod_mt"], _C_FLUX),
        _mini_bar_svg("Sales Booking", fys, cfg["sales_booking_mt"], _C_SALES),
    ]
    donuts = [
        _share_donut_svg(f"Despatch Mix — {label}", cfg["despatch_mix_cats"], vals, _DESPATCH_MIX_COLORS)
        for label, vals in cfg["despatch_mix"].items()
    ]
    cell = 'border:1px solid #e2e8f0;border-radius:3px;padding:2px 4px;'
    grid = "".join(f'<div style="{cell}">{s}</div>' for s in bars)
    drow = "".join(f'<div style="{cell}">{s}</div>' for s in donuts)
    return (
        '<div style="font-family:Arial,sans-serif;margin-top:6px;">'
        '<div style="font-weight:700;font-size:9pt;margin:2px 0 4px;">Mines Performance'
        '<span style="font-weight:400;font-style:italic;font-size:7.5pt;color:#64748b;">'
        ' — 3-year trend &amp; iron-ore despatch mix (million tonnes)</span></div>'
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;">{grid}</div>'
        f'<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:4px;margin-top:4px;">{drow}</div>'
        '</div>'
    )


def generate_sail_mines(report_month: str) -> dict:
    ytd_months = db.get_ytd_months(report_month)
    cply_months = [db.get_cply_month(m) for m in ytd_months]

    monthly = db.get_sail_mines_monthly(ytd_months)
    cply_monthly = db.get_sail_mines_monthly(cply_months)

    # Iron Ore Production/Despatch (iron_ore_prod / iron_ore_despatch) are NOT
    # read from the DB — they're hard-coded group-wise in hardcoded_config.json
    # ("sail_mines" -> "iron_ore_group_kt") and injected directly into
    # section_rows in Pass 1 below (per direct instruction, 2026-08-27). Every
    # other section stays on sail_mines_monthly.
    iron_ore_group = hardcoded_loader.section("sail_mines")["iron_ore_group_kt"]

    y, m = int(report_month[:4]), int(report_month[5:7])
    period_label = f"April-{_MON_ABBR[m]}'{y % 100:02d}"

    # Pass 1: compute every section's rows (by label) regardless of whether
    # it ends up as its own table or gets folded into another one below.
    section_rows = {}
    for section in SAIL_MINES_SECTIONS:
        raw = {}  # item/derived label -> (app, actual, cply) raw numbers
        rows = {}
        hardcoded = iron_ore_group.get(section["key"])
        for item in section["items"]:
            if hardcoded is not None:
                app, actual, cply = hardcoded[item]
            else:
                app, actual, cply = _leaf_values(
                    monthly, cply_monthly, section["key"], item, ytd_months, cply_months, section["kind"]
                )
            raw[item] = (app, actual, cply)
            rows[item] = _row(item, app, actual, cply, section["kind"], bold=(item == "SAIL"))

        for d in section.get("derived", []):
            value_fmt = d.get("value_fmt", "t")
            if d["kind"] == "sum":
                parts = [raw[i] for i in d["of"]]
                app = _sum_or_none(p[0] for p in parts) if section["kind"] == "production" else None
                actual = _sum_or_none(p[1] for p in parts)
                cply = _sum_or_none(p[2] for p in parts)
            else:  # "ratio"
                num, den = raw[d["numerator"]], raw[d["denominator"]]
                app = _ratio(num[0], den[0]) if section["kind"] == "production" else None
                actual = _ratio(num[1], den[1])
                cply = _ratio(num[2], den[2])
            rows[d["label"]] = _row(d["label"], app, actual, cply, section["kind"], value_fmt, bold=True)

        section_rows[section["key"]] = rows

    # Pass 2: emit one table per section, except sections with "merge_into"
    # (folded into the named section's table as a DESPATCH column group —
    # see iron_ore_despatch/iron_ore_prod in SAIL_MINES_SECTIONS above).
    tables = []
    for section in SAIL_MINES_SECTIONS:
        if "merge_into" in section:
            continue
        item_order = list(section["items"]) + [d["label"] for d in section.get("derived", [])]
        merge_section = next((s for s in SAIL_MINES_SECTIONS if s.get("merge_into") == section["key"]), None)

        if merge_section:
            desp_columns = _columns_for(merge_section["kind"])
            rows = []
            for label in item_order:
                prod_row = section_rows[section["key"]][label]
                desp_row = section_rows[merge_section["key"]].get(label, {})
                rows.append({
                    "label": label, "bold": prod_row["bold"],
                    "app": prod_row.get("app"), "actual": prod_row.get("actual"),
                    "pct_ful": prod_row.get("pct_ful"), "cply": prod_row.get("cply"),
                    "pct_growth": prod_row.get("pct_growth"),
                    "d_app": desp_row.get("app"), "d_actual": desp_row.get("actual"),
                    "d_pct_ful": desp_row.get("pct_ful"), "d_cply": desp_row.get("cply"),
                    "d_pct_growth": desp_row.get("pct_growth"),
                })
            tables.append({
                "key": section["key"], "title": section["title"], "kind": "production_despatch",
                "column_groups": [
                    {"label": section.get("group_label", "PRODUCTION"), "columns": _columns_for(section["kind"])},
                    {"label": merge_section.get("group_label", "DESPATCH"), "columns": desp_columns},
                ],
                "rows": rows,
            })
        else:
            tables.append({
                "key": section["key"], "title": section["title"], "kind": section["kind"],
                "columns": _columns_for(section["kind"]),
                "rows": [section_rows[section["key"]][label] for label in item_order],
            })

    return {
        "type": "sail_mines",
        "title": "SAIL Mines Production & Despatch Performance",
        "period_label": period_label,
        "unit": "'000 T",
        "tables": tables,
        "mines_charts_html": _mines_charts_html(),
    }
