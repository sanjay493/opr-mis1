"""
"SAIL Mines Production & Despatch Performance" — 7 tables covering Iron Ore
(production+despatch, plus sales), Coal (mines production, washery,
despatch) and Flux (limestone/dolomite production + despatch), each a
cumulative April-<report month> view against Annual Plan (APP) and the
corresponding period last year (CPLY), per direct instruction.

Every "production"-kind table's row (APP, Act., %FF, CPLY, %Grth) is built
from monthly Actual + Plan entered via the SAIL Mines Entry data-entry page
(db.sail_mines_monthly) — APP/Actual are the entered monthly figures summed
April->report_month (same YTD convention as page4.py's "YTD APP"/"YTD
Actual" columns), CPLY is the same sum for last FY's April->same month
(db.get_cply_month, one call per YTD month so a report month early in the
FY still gets the right prior-year months). "flow"-kind tables would skip
APP/%FF entirely (just Act./CPLY/%Grth) — per direct instruction, every
despatch/sales section now carries its own Plan too, so every section here
is currently 'production'-kind; 'flow' stays supported (not deleted) in
case a future section genuinely has no plan figure.

Iron Ore Production (table 1) additionally carries a DESPATCH column group
per mine group (per direct instruction) — a second section (iron_ore_
despatch, same 4 items) whose rows are merged into table 1's rows as extra
columns rather than rendered as their own table (see "merge_into" below);
the resulting table has kind='production_despatch' and a "column_groups"
list (PRODUCTION + DESPATCH) instead of a flat "columns" list. Both groups
now carry the full APP/Act./%FF/CPLY/%Grth span (per direct instruction,
the despatch side previously only had Act./CPLY/%Grth) since iron_ore_
despatch is 'production'-kind too. This is a separate concept from table 2
(Sales of Iron Ore), which tracks disposal CHANNEL (Auction vs Despatch)
rather than per-mine-group despatch.

A few rows are computed, never entered directly:
  - Coal Mines Production's "Total" = Raw Coking Coal + Thermal Coal.
  - Washery's "Yield (Clean Coal/Raw Coal)" = Clean Coal / Input Raw Coal
    x100 — computed for Actual/APP/CPLY the same way, before %FF/%Grth are
    derived from those (not an independently entered %), and displayed
    with 1 decimal (a %) rather than the tonnage tables' whole T.
Iron Ore Production's "SAIL" row (both production and despatch) is its own
directly-entered figure, NOT a sum of CGoM/OGoM/JGoM — same reasoning as
Cost Trend's SAIL row (see page_cost_trend.py): a mine group's own
reported/blended total isn't necessarily the arithmetic sum of the
individual mines.
"""
import db
from page_at_a_glance import _trend_line_svg

# Same fixed-order categorical hues as pdf.py's _BADGE_COLORS / globals.css's
# .dept-badge.grp-N (already validated per the dataviz skill's six-check
# gate) — reused here rather than picking new colors, so this chart's
# palette is consistent with the rest of the report and doesn't need its
# own separate validation pass.
_MINES_CHART_COLORS = {
    "Iron Ore": "#2a78d6",   # blue
    "Coal": "#eb6834",       # orange
    "Flux": "#1baf7a",       # aqua
}

# Every (section key, item) pair listed under "items" is entered directly
# via the SAIL Mines Entry data-entry page; "derived" rows are computed
# from those and never entered (see module docstring). kind='production'
# tables show APP/Act./%FF/CPLY/%Grth; kind='flow' tables (despatch/sales)
# show just Act./CPLY/%Grth. A section with "merge_into" set is never its
# own table — its rows fold into the named section's table as an extra
# DESPATCH column group instead (see _merge_despatch_columns).
SAIL_MINES_SECTIONS = [
    {
        "key": "iron_ore_prod", "title": "IRON ORE MINES PERFORMANCE", "kind": "production",
        "items": ["CGoM", "OGoM", "JGoM", "SAIL"],
        "derived": [],
    },
    {
        "key": "iron_ore_despatch", "kind": "production",
        "items": ["CGoM", "OGoM", "JGoM", "SAIL"],
        "derived": [], "merge_into": "iron_ore_prod",
    },
    {
        "key": "iron_ore_sales", "title": "SALES OF IRON ORE", "kind": "production",
        "items": ["Auction", "Despatch"],
        "derived": [],
    },
    {
        "key": "coal_prod", "title": "COAL MINES PRODUCTION PERFORMANCE", "kind": "production",
        "items": ["Raw Coking Coal", "Thermal Coal"],
        "derived": [{"label": "Total", "kind": "sum", "of": ["Raw Coking Coal", "Thermal Coal"]}],
    },
    {
        "key": "washery", "title": "WASHERY PERFORMANCE", "kind": "production",
        "items": ["Input Raw Coal", "Clean Coal"],
        "derived": [{
            "label": "Yield (Clean Coal/Raw Coal)", "kind": "ratio", "value_fmt": "pct",
            "numerator": "Clean Coal", "denominator": "Input Raw Coal",
        }],
    },
    {
        "key": "coal_despatch", "title": "DESPATCH OF CLEAN COAL, THERMAL & MIDDLINGS", "kind": "production",
        "items": ["Clean Coal", "Thermal", "Middlings"],
        "derived": [],
    },
    {
        "key": "flux_prod", "title": "FLUX PRODUCTION & DESPATCH (LIMESTONE & DOLOMITE)", "kind": "production",
        "items": ["Limestone", "Dolomite"],
        "derived": [],
    },
    {
        "key": "flux_despatch", "kind": "production",
        "items": ["Limestone", "Dolomite"],
        "derived": [], "merge_into": "flux_prod",
    },
]

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


def _mines_performance_chart_svg(ytd_months: list) -> str:
    """Illustrative placeholder ONLY — not wired to real mines figures yet
    (per direct instruction: fills the space freed up by narrowing the
    Sales/Coal-Production/Washery/Despatch tables, to be mapped to real
    Iron Ore/Coal/Flux production data once that's decided). Kept as its
    own function so swapping in real series later only touches this one
    spot, not the layout around it."""
    labels = [_MON_ABBR[int(m.split("-")[1])] for m in ytd_months]
    n = len(labels)
    series = {
        "Iron Ore": [420 + 18 * i for i in range(n)],
        "Coal": [140 + 6 * ((i * 3) % 7) for i in range(n)],
        "Flux": [60 + 4 * ((i * 5) % 5) for i in range(n)],
    }
    return _trend_line_svg(labels, series, _MINES_CHART_COLORS)


def generate_sail_mines(report_month: str) -> dict:
    ytd_months = db.get_ytd_months(report_month)
    cply_months = [db.get_cply_month(m) for m in ytd_months]

    monthly = db.get_sail_mines_monthly(ytd_months)
    cply_monthly = db.get_sail_mines_monthly(cply_months)

    y, m = int(report_month[:4]), int(report_month[5:7])
    period_label = f"April-{_MON_ABBR[m]}'{y % 100:02d}"

    # Pass 1: compute every section's rows (by label) regardless of whether
    # it ends up as its own table or gets folded into another one below.
    section_rows = {}
    for section in SAIL_MINES_SECTIONS:
        raw = {}  # item/derived label -> (app, actual, cply) raw numbers
        rows = {}
        for item in section["items"]:
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
                    {"label": "PRODUCTION", "columns": _columns_for(section["kind"])},
                    {"label": "DESPATCH", "columns": desp_columns},
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
        "mines_chart_svg": _mines_performance_chart_svg(ytd_months),
    }
