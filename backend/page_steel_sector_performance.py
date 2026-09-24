"""
"Indian Steel Sector Performance" — pages 2.1-2.3, right after the Index
(see main.py's STEEL_SECTOR_PAGES). Reproduces the monthly PIB (Ministry of
Steel) release archived by pdf_extractor_steel_sector_performance.py /
/api/steel-sector-performance/confirm into steel_sector_performance_table,
verbatim — EXCEPT Table 1a (Production Overview), which gets SAIL's own
Crude Steel / Hot Metal / Finished Steel actuals appended as extra rows
(rounded to 1 decimal, matching the PDF's own India figures), with SAIL's
own YoY%/CPLY% growth computed the same way the PDF computes India's, and
SAIL's % share of the India total for each of the table's four value
columns (report month, CPLY month, Apr-report-month cumulative, CPLY
Apr-report-month cumulative) shown bracketed under the SAIL figures.

SAIL rollup for those extra rows reuses db.get_sail_production_ytd_actual()
— the same helper page_records.py / page_jpc_report.py's SAIL total already
relies on (5 core plants + ASP/SSP/VISL, with the Finished-Steel SSP/VISL
alias) — passed a single-element month list for a single month's actual, or
db.get_ytd_months(month) for an Apr-to-month cumulative. No new SAIL-rollup
logic here.

Page 2.1 (prod_prices) and 2.2 (demand_trade) each additionally carry a small
line chart at the bottom (per direct instruction, 2026-09-12 — both pages had
leftover blank space after a CSS pass): 2.1 gets Table 1c's 4 steel-product
prices, 2.2 gets Table 4a's 2 NMDC iron-ore prices, both trended from the
current FY's April onward wherever archived data actually exists. Neither
table's own row/column labels are ever archived as a full time series — each
month's steel_sector_performance_table row only carries that release's own
rolling ~3-month window (e.g. Aug'26's Table 1c shows Jun/Jul/Aug columns) —
so _series_from_archive scans EVERY archived row (not just the latest, unlike
_load_row above) and merges every column that parses as a real calendar month
(_parse_month_header), which also naturally drops each table's trailing
MoM%/YoY% summary columns since those don't parse as a month at all. Row
labels are matched by prefix/substring (_match_steel_price_item/_match_nmdc_
item) rather than exact string, since a PIB release changing e.g. "TMT
(10 mm)" to a different rolled spec next month shouldn't silently drop that
whole series."""
import json
import re

import db

# PDF's Table 1a item label -> production_table's own item_name.
_ITEM_DB_NAME = {
    "Crude Steel": "Total Crude Steel",
    "Hot Metal": "Hot Metal",
    "Finished Steel": "Finished Steel",
}

_VALUE_COLS = ["report_month", "cply_month", "apr_report_month", "cply_apr_report_month"]


def _load_row(report_month: str):
    """Freshest archived release at-or-before report_month — same
    "latest snapshot at-or-before" convention page_power_data.py uses for
    its Cum. row, so a month gets last month's release shown (labelled as
    such) rather than a blank page until that month's own PDF is uploaded."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT report_month, data_json, source_file FROM steel_sector_performance_table
            WHERE report_month <= ?
            ORDER BY report_month DESC LIMIT 1
        """, (report_month,))
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None, None, None
    data_month, data_json, source_file = row
    return data_month, (json.loads(data_json) if data_json else None), source_file


# ── Table 1c / 4a price trend charts (page 2.1 / 2.2 footer) ──────────────────

_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MON_NUM = {name: i for i, name in enumerate(_MON_ABBR) if name}

_STEEL_PRICE_CHART_COLORS = {
    # Same 4-hue categorical set as page_sail_mines.py's _C_IRON_ORE/_C_CLEAN_
    # COAL/_C_FLUX/_C_SALES (already validated per the dataviz skill's six-
    # check gate) — reused rather than picking new colors needing their own pass.
    "TMT":      "#2a78d6",
    "HR Coil":  "#eb6834",
    "CR Coil":  "#1baf7a",
    "GP Sheet": "#eda100",
}
_NMDC_PRICE_CHART_COLORS = {
    "NMDC Lump":  "#2a78d6",
    "NMDC Fines": "#eb6834",
}


def _parse_month_header(h) -> "str | None":
    """'May-26' / 'Jun 2026' -> '2026-05'; anything else (e.g. 'Product',
    'MoM %', 'YoY %', 'Commodity', 'MoM Change') -> None. Used to pick out
    just the real calendar-month columns from a table's headers, whatever
    that release's exact header wording/column count was."""
    m = re.match(r"^([A-Za-z]{3})[A-Za-z]*[\s-](\d{2,4})$", (h or "").strip())
    if not m:
        return None
    mon_num = _MON_NUM.get(m.group(1).title())
    if not mon_num:
        return None
    yr = m.group(2)
    year = int(yr) if len(yr) == 4 else 2000 + int(yr)
    return f"{year:04d}-{mon_num:02d}"


def _parse_price(v) -> "float | None":
    """'₹ 60,068' -> 60068.0 — strips the currency symbol, commas and
    spaces (anything that isn't a digit or '.'). None/blank/unparseable ->
    None."""
    if v is None:
        return None
    s = re.sub(r"[^0-9.]", "", str(v))
    try:
        return float(s) if s not in ("", ".") else None
    except ValueError:
        return None


def _series_from_archive(table_key: str, label_match, floor_month: str) -> dict:
    """{series_name: {'YYYY-MM': value}}, merged across EVERY archived
    steel_sector_performance_table row's tables[table_key] — a single
    archived row only ever carries that release's own rolling ~3-month
    window (see module docstring), so the full trend has to be assembled
    across releases. label_match(row_label) -> series name to bucket under,
    or None to skip that row. Only columns whose header parses as a real
    month >= floor_month ('YYYY-MM') are kept."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute("SELECT data_json FROM steel_sector_performance_table ORDER BY report_month")
        archives = [json.loads(r[0]) for r in cur.fetchall() if r[0]]
    finally:
        conn.close()

    out: dict = {}
    for data in archives:
        t = (data.get("tables") or {}).get(table_key) or {}
        month_cols = [(i, mk) for i, mk in enumerate(_parse_month_header(h) for h in t.get("headers") or [])
                      if mk and mk >= floor_month]
        if not month_cols:
            continue
        for row in t.get("rows") or []:
            if not row:
                continue
            name = label_match(row[0])
            if not name:
                continue
            bucket = out.setdefault(name, {})
            for i, mk in month_cols:
                if i < len(row):
                    val = _parse_price(row[i])
                    if val is not None:
                        bucket[mk] = val
    return out


def _match_steel_price_item(label: str) -> "str | None":
    label = label or ""
    for key in _STEEL_PRICE_CHART_COLORS:
        if label.startswith(key):
            return key
    return None


def _match_nmdc_item(label: str) -> "str | None":
    label = label or ""
    if "NMDC" not in label:
        return None
    if "Lump" in label:
        return "NMDC Lump"
    if "Fines" in label:
        return "NMDC Fines"
    return None


def _fmt_k1(v: float) -> str:
    """58002 -> '58.0K' — '000s to 1 decimal, matching the report's own
    Mt-style compact convention (see page_steel_sector_performance's Table
    1a, which also shows 1-decimal rounded figures)."""
    return f"{v / 1000:.1f}K"


def _price_trend_svg(labels: list, series: dict, colors: dict, vw: int = 480, vh: int = 118) -> str:
    """Multi-line price trend, y-axis zoomed to the data's own min/max
    rather than starting at 0 (unlike page_at_a_glance._trend_line_svg,
    which page_sail_mines.py's tonnage charts want zero-based) — these
    series sit in a tight band far from zero (e.g. Rs 56,000-87,000), so a
    zero baseline would flatten all of them into a cramped cluster at the
    top. Every data point carries its own value label (in '000, 1 decimal,
    e.g. "58.0K" — _fmt_k1) directly above it; series identity comes from
    a swatch+name legend in the top-right corner (reserved via `mr`)
    instead of a name on the line itself, per direct instruction
    (2026-09-12) — that's what keeps per-point labels short enough to fit
    without the 3-4 series colliding."""
    ml, mr, mt, mb = 16, 74, 18, 16
    cw, ch = vw - ml - mr, vh - mt - mb
    n = len(labels)
    step = cw / max(n - 1, 1)

    def xs(i):
        return ml + i * step

    all_vals = [v for vals in series.values() for v in vals if v is not None]
    lo = min(all_vals) if all_vals else 0.0
    hi = max(all_vals) if all_vals else 1.0
    pad = (hi - lo) * 0.15 or hi * 0.1 or 1.0
    lo, hi = lo - pad, hi + pad

    def ys(v):
        return mt + ch * (1.0 - (v - lo) / (hi - lo))

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
           f'style="width:100%;height:auto;display:block;">']
    for name, vals in series.items():
        color = colors.get(name, "#0284c7")
        pts = [(i, xs(i), ys(v)) for i, v in enumerate(vals) if v is not None]
        if len(pts) > 1:
            d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for _, x, y in pts)
            out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6"/>')
        for j, (i, x, y) in enumerate(pts):
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="{color}"/>')
            anchor = "start" if j == 0 else "end" if j == len(pts) - 1 else "middle"
            tx = x + 3 if j == 0 else (x - 3 if j == len(pts) - 1 else x)
            out.append(f'<text x="{tx:.1f}" y="{y - 5:.1f}" text-anchor="{anchor}" font-size="6.5" '
                       f'font-weight="bold" font-family="Arial,sans-serif" fill="{color}">{_fmt_k1(vals[i])}</text>')

    base = mt + ch
    out.append(f'<line x1="{ml}" y1="{base:.1f}" x2="{vw - mr}" y2="{base:.1f}" '
               f'stroke="#94a3b8" stroke-width="0.6"/>')
    for i, lab in enumerate(labels):
        out.append(f'<text x="{xs(i):.1f}" y="{base + 11:.1f}" text-anchor="middle" font-size="7" '
                   f'font-family="Arial,sans-serif" fill="#475569">{lab}</text>')

    # Legend: top-right, one swatch+name row per series, inside the `mr`
    # margin the plotted lines never reach.
    lx, ly = vw - mr + 8, mt - 6
    for name in series:
        color = colors.get(name, "#0284c7")
        out.append(f'<rect x="{lx}" y="{ly - 5:.1f}" width="7" height="7" rx="1" fill="{color}"/>')
        out.append(f'<text x="{lx + 10}" y="{ly:.1f}" font-size="7" font-weight="bold" '
                   f'font-family="Arial,sans-serif" fill="#1e293b">{name}</text>')
        ly += 10

    out.append("</svg>")
    return "".join(out)


def _price_chart_html(title: str, table_key: str, label_match, colors: dict, floor_month: str, vh: int = 118) -> str:
    """Self-contained inline-styled HTML block (title + line chart), same
    pattern as page_sail_mines.py's _mines_charts_html — or "" when there's
    no archived data at all yet for this table/floor_month (a brand new
    report shouldn't show an empty chart frame)."""
    series_by_item = _series_from_archive(table_key, label_match, floor_month)
    all_months = sorted({mk for s in series_by_item.values() for mk in s})
    if not all_months:
        return ""
    labels = [f"{_MON_ABBR[int(mk[5:7])]}'{mk[2:4]}" for mk in all_months]
    series = {name: [series_by_item[name].get(mk) for mk in all_months] for name in colors if name in series_by_item}
    svg = _price_trend_svg(labels, series, colors, vh=vh)
    return (
        '<div class="ssp-chart-block" style="font-family:Arial,sans-serif;margin-top:4px;">'
        f'<div style="font-weight:700;font-size:11pt;margin:1px 0 2px;color:#1e293b; padding-bottom:5px">{title}</div>'
        f'<div style="border:1px solid #e2e8f0;border-radius:3px;padding:3px 5px;">{svg}</div>'
        '</div>'
    )


_KT_TO_MT = 1000.0  # production_table stores '000 T (see page_jpc_report.py's "Unit:'000 T");
                     # the PDF's Table 1a figures are in Mt (Million Tonnes) — convert to match.


def _sail_value(item_db_name: str, months: list) -> float:
    """Unrounded Mt — kept full precision here so YoY%/CPLY% growth (below)
    is computed off the real value, not off an already-rounded display
    figure. Display rounding to 1 decimal happens separately, in the
    dict built by _augment_production_overview."""
    v = db.get_sail_production_ytd_actual(months, item_db_name)
    return v / _KT_TO_MT if v is not None else None


def _round1(v):
    return round(v, 1) if v is not None else None


def _share_pct(sail_val, india_val):
    if sail_val is None or not india_val:
        return None
    return round(sail_val / india_val * 100, 1)


def _growth_pct(cur_v, prev_v):
    """% growth over CPLY — same formula page_jpc_report.py's _gr() uses
    for India's own YoY%/CPLY% columns, applied here to SAIL's figures."""
    if cur_v is None or prev_v is None or prev_v == 0:
        return None
    return round((cur_v - prev_v) / abs(prev_v) * 100, 1)


def _augment_production_overview(items: list, report_month: str) -> list:
    """One group per item (Crude Steel / Hot Metal / Finished Steel):
    {"item": ..., "india": {...the 6 PDF columns, unchanged...}, "sail":
    {...4 value columns (1 decimal) + yoy_pct/cply_pct...}, "share": {...
    SAIL's % of India, same 4 value columns...}} — the item-name column
    spans both the India and SAIL rows in the rendered table, and each
    SAIL-row value cell shows its own SAIL-share-of-India % underneath in
    brackets (see page_templates/steel_sector_performance.html /
    SteelSectorPerformanceTemplate.js)."""
    cply_month = db.get_cply_month(report_month)
    ytd_months = db.get_ytd_months(report_month)
    cply_ytd_months = db.get_ytd_months(cply_month)

    out = []
    for row in items:
        db_item = _ITEM_DB_NAME.get(row["item"])
        if not db_item:
            out.append({"item": row["item"], "india": row, "sail": None, "share": None})
            continue

        sail_raw = {
            "report_month": _sail_value(db_item, [report_month]),
            "cply_month": _sail_value(db_item, [cply_month]),
            "apr_report_month": _sail_value(db_item, ytd_months),
            "cply_apr_report_month": _sail_value(db_item, cply_ytd_months),
        }
        sail = {
            **{col: _round1(sail_raw[col]) for col in _VALUE_COLS},
            "yoy_pct": _growth_pct(sail_raw["report_month"], sail_raw["cply_month"]),
            "cply_pct": _growth_pct(sail_raw["apr_report_month"], sail_raw["cply_apr_report_month"]),
        }
        share = {col: _share_pct(sail_raw[col], row.get(col)) for col in _VALUE_COLS}
        out.append({"item": row["item"], "india": row, "sail": sail, "share": share})
    return out


_DEFAULT_TITLE = "Indian Steel Sector Performance"


def generate_steel_sector_performance(report_month: str, section: str = "all") -> dict:
    """section selects which physical page's slice of content to return
    (see main.py's STEEL_SECTOR_PAGES) — 'all' returns everything, for
    direct/API use outside the paginated report flow."""
    data_month, data, source_file = _load_row(report_month)
    page = {
        "type": "steel_sector_performance",
        # Always present — PageData.title is required, so a month with no
        # archived release (data is None below) would otherwise fail the
        # whole PDF export with a 422.
        "title": _DEFAULT_TITLE,
        "section": section,
        "report_month": report_month,
        "data_month": data_month,
        "available": data is not None,
    }
    if data is None:
        return page

    page.update({
        "title": data.get("title") or _DEFAULT_TITLE,
        "posted_on": data.get("posted_on"),
        "tables": data.get("tables", {}),
        "text_sections": data.get("text_sections", {}),
        "footer_note": data.get("footer_note"),
        "source_file": source_file,
        "production_overview_1a": _augment_production_overview(
            data.get("production_overview_1a_items", []), data_month or report_month,
        ),
    })

    floor_month = db.get_fy_months(report_month)[0]  # this FY's April, e.g. "2026-04"
    if section in ("prod_prices", "all"):
        page["steel_price_chart_html"] = _price_chart_html(
            "Steel Prices Trend (₹/tonne)", "1c", _match_steel_price_item,
            _STEEL_PRICE_CHART_COLORS, floor_month, vh=105,
        )
    if section in ("demand_trade", "all"):
        page["nmdc_price_chart_html"] = _price_chart_html(
            "NMDC Iron Ore Price Trend (₹/tonne)", "4a", _match_nmdc_item,
            _NMDC_PRICE_CHART_COLORS, floor_month,vh=90
        )
    return page
