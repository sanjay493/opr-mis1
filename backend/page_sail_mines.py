"""
"SAIL Mines Production & Despatch Performance" — 7 tables covering Iron Ore
(production + sales), Coal (mines production, washery, despatch) and Flux
(limestone/dolomite production + despatch), each a cumulative April-<report
month> view against Annual Plan (APP) and the corresponding period last
year (CPLY), per direct instruction.

Every "production"-kind table's row (APP, Actual, % Fulfillment, CPLY, %
Growth) is built from monthly Actual + Plan entered via the SAIL Mines
Entry data-entry page (db.sail_mines_monthly) — APP/Actual are the entered
monthly figures summed April->report_month (same YTD convention as
page4.py's "YTD APP"/"YTD Actual" columns), CPLY is the same sum for last
FY's April->same month (db.get_cply_month, one call per YTD month so a
report month early in the FY still gets the right prior-year months).
"flow"-kind tables (despatch/sales) skip APP/% Fulfillment entirely — those
have no plan figure, just Actual/CPLY/% Growth.

A few rows are computed, never entered directly:
  - Coal Mines Production's "Total" = Raw Coking Coal + Thermal Coal.
  - Washery's "Yield (Clean Coal/Raw Coal)" = Clean Coal / Input Raw Coal
    x100 — computed for Actual/APP/CPLY the same way, before % Fulfillment/
    % Growth are derived from those (not an independently entered %), and
    displayed with 1 decimal (a %) rather than the tonnage tables' whole T.
Iron Ore Production's "SAIL" row is its own directly-entered figure, NOT a
sum of CGoM/OGoM/JGoM — same reasoning as Cost Trend's SAIL row (see
page_cost_trend.py): a mine group's own reported/blended total isn't
necessarily the arithmetic sum of the individual mines.
"""
import db

# Every (section key, item) pair listed under "items" is entered directly
# via the SAIL Mines Entry data-entry page; "derived" rows are computed
# from those and never entered (see module docstring). kind='production'
# tables show APP/Actual/%Ful/CPLY/%Growth; kind='flow' tables (despatch/
# sales) show just Actual/CPLY/%Growth.
SAIL_MINES_SECTIONS = [
    {
        "key": "iron_ore_prod", "title": "IRON ORE PRODUCTION", "kind": "production",
        "items": ["CGoM", "OGoM", "JGoM", "SAIL"],
        "derived": [],
    },
    {
        "key": "iron_ore_sales", "title": "SALES OF IRON ORE", "kind": "flow",
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
        "key": "coal_despatch", "title": "DESPATCH OF CLEAN COAL, THERMAL & MIDDLINGS", "kind": "flow",
        "items": ["Clean Coal", "Thermal", "Middlings"],
        "derived": [],
    },
    {
        "key": "flux_prod", "title": "FLUX PRODUCTION (LIMESTONE & DOLOMITE)", "kind": "production",
        "items": ["Limestone", "Dolomite"],
        "derived": [],
    },
    {
        "key": "flux_despatch", "title": "FLUX DESPATCH (LIMESTONE & DOLOMITE)", "kind": "flow",
        "items": ["Limestone", "Dolomite"],
        "derived": [],
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


def generate_sail_mines(report_month: str) -> dict:
    ytd_months = db.get_ytd_months(report_month)
    cply_months = [db.get_cply_month(m) for m in ytd_months]

    monthly = db.get_sail_mines_monthly(ytd_months)
    cply_monthly = db.get_sail_mines_monthly(cply_months)

    y, m = int(report_month[:4]), int(report_month[5:7])
    period_label = f"April-{_MON_ABBR[m]}'{y % 100:02d}"

    tables = []
    for section in SAIL_MINES_SECTIONS:
        raw = {}  # item/derived label -> (app, actual, cply) raw numbers
        rows = []
        for item in section["items"]:
            app, actual, cply = _leaf_values(
                monthly, cply_monthly, section["key"], item, ytd_months, cply_months, section["kind"]
            )
            raw[item] = (app, actual, cply)
            rows.append(_row(item, app, actual, cply, section["kind"], bold=(item == "SAIL")))

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
            rows.append(_row(d["label"], app, actual, cply, section["kind"], value_fmt, bold=True))

        columns = (
            ["APP", "Actual", "% Fulfillment", "CPLY", "% Growth"] if section["kind"] == "production"
            else ["Actual", "CPLY", "% Growth"]
        )
        tables.append({
            "key": section["key"], "title": section["title"], "kind": section["kind"],
            "columns": columns, "rows": rows,
        })

    return {
        "type": "sail_mines",
        "title": "SAIL Mines Production & Despatch Performance",
        "period_label": period_label,
        "unit": "'000 T",
        "tables": tables,
    }
